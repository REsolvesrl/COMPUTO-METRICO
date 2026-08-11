// cme_viewer — visualizzatore planimetrie con barra strumenti.
// Tutte le coordinate scambiate col server sono nello spazio dell'immagine
// originale ("canoniche"); zoom e spostamento sono solo visivi.
// L'utente vede SOLO metri: mai pixel.

"use strict";

// ------------------------------------------------------------------ stato
let cont = null, cv = null, ctx = null, dpr = 1;
const img = new Image();
let pronto = false;          // immagine caricata e vista adattata
let curSrc = null;

const MAXH = 560, MINH = 260;
let contH = 420;
let scale = 1, tx = 0, ty = 0, fitScale = 1;

let mode = "sposta";
let zone = [], pareti = [], scalaTemp = null;
let coloreAttivo = "#E57373", mpp = 0, fontPx = 14;
let tipoParete = "demolire";  // che muro si sta per tracciare (dal server)

let drawing = [];            // poligono in corso (coord. immagine)
let cursorPos = null;        // mouse in coord. immagine (per il rubber band)
let selZona = null, selParete = null;
let drag = null;             // {kind:"pan"|"vertex"|"move"|"vector"|"label"}
let vecStart = null, vecEnd = null;
let vettoreAperto = false;   // primo punto fissato, si attende il secondo clic
let misure = [];             // misure "al volo": SOLO locali, mai inviate
let labelRects = [];         // rettangoli (schermo) delle etichette disegnate
let seqN = 0;
let mostraAree = true;       // aree dei locali + etichette a schermo

// Le zone da disegnare adesso: con «AREE» spento restano solo i perimetri
// commerciali, che non sono locali ma l'ingombro dell'immobile.
function zoneVisibili(elenco) {
  return mostraAree ? elenco : elenco.filter(function (z) {
    return z.senza_sfondo;
  });
}
let editor = null;           // <input> di rinomina sovrapposto all'etichetta

const COL_SCALA = "#111111";       // nero — vettore di scala
const COL_MISURA = "#3D9BE9";      // azzurro — misure al volo

// ------------------------------------------------------------- conversioni
function img2scr(p) { return [p[0] * scale + tx, p[1] * scale + ty]; }
function scr2img(s) { return [(s[0] - tx) / scale, (s[1] - ty) / scale]; }
function scrOf(e) {
  const r = cv.getBoundingClientRect();
  return [e.clientX - r.left, e.clientY - r.top];
}
function dist(a, b) { return Math.hypot(a[0] - b[0], a[1] - b[1]); }

function distSeg(p, a, b) {          // distanza punto-segmento (stesse unità)
  const vx = b[0] - a[0], vy = b[1] - a[1];
  const wx = p[0] - a[0], wy = p[1] - a[1];
  const c1 = vx * wx + vy * wy;
  if (c1 <= 0) return dist(p, a);
  const c2 = vx * vx + vy * vy;
  if (c2 <= c1) return dist(p, b);
  const t = c1 / c2;
  return dist(p, [a[0] + t * vx, a[1] + t * vy]);
}

function dentro(p, pts) {            // punto dentro poligono (ray casting)
  let c = false;
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const xi = pts[i][0], yi = pts[i][1], xj = pts[j][0], yj = pts[j][1];
    if (((yi > p[1]) !== (yj > p[1])) &&
        (p[0] < (xj - xi) * (p[1] - yi) / (yj - yi) + xi)) c = !c;
  }
  return c;
}

function baricentro(pts) {
  let a = 0, cx = 0, cy = 0;
  for (let i = 0, j = pts.length - 1; i < pts.length; j = i++) {
    const f = pts[j][0] * pts[i][1] - pts[i][0] * pts[j][1];
    a += f;
    cx += (pts[j][0] + pts[i][0]) * f;
    cy += (pts[j][1] + pts[i][1]) * f;
  }
  if (Math.abs(a) < 1e-6) {
    let sx = 0, sy = 0;
    for (const p of pts) { sx += p[0]; sy += p[1]; }
    return [sx / pts.length, sy / pts.length];
  }
  return [cx / (3 * a), cy / (3 * a)];
}

function hexRgba(hex, alpha) {
  const r = parseInt(hex.slice(1, 3), 16);
  const g = parseInt(hex.slice(3, 5), 16);
  const b = parseInt(hex.slice(5, 7), 16);
  return "rgba(" + r + "," + g + "," + b + "," + alpha + ")";
}

function fmt(n, dec) { return n.toFixed(dec).replace(".", ","); }

// Lunghezza SOLO in metri: senza scala non mostriamo nulla (mai pixel).
function fmtMetri(pxLen) {
  return (mpp > 0) ? fmt(pxLen * mpp, 2) + " m" : "";
}

// ------------------------------------------------------------------- invio
function send(v) {
  v.seq = Date.now() * 100 + (seqN++ % 100);
  Streamlit.setComponentValue(v);
}
function arrotonda(pts) {
  return pts.map(function (p) {
    return [Math.round(p[0] * 10) / 10, Math.round(p[1] * 10) / 10];
  });
}
function inviaSelezione() {
  send({ tipo: "selezione", zona: selZona, parete: selParete });
}

// ------------------------------------------------------------------- vista
function sizeCanvas() {
  const w = Math.max(200, cont.clientWidth);
  cv.style.width = w + "px";
  cv.style.height = contH + "px";
  cv.width = Math.round(w * dpr);
  cv.height = Math.round(contH * dpr);
}

function fit() {
  if (!img.naturalWidth) return;
  const w = Math.max(200, cont.clientWidth);
  let s = Math.min(w / img.naturalWidth, MAXH / img.naturalHeight);
  contH = Math.max(MINH, Math.min(MAXH, Math.round(img.naturalHeight * s)));
  s = Math.min(w / img.naturalWidth, contH / img.naturalHeight);
  fitScale = s;
  scale = s;
  tx = (w - img.naturalWidth * s) / 2;
  ty = (contH - img.naturalHeight * s) / 2;
  cont.style.height = contH + "px";
  sizeCanvas();
  Streamlit.setFrameHeight(contH);
  render();
}

function zoomAt(sx, sy, fattore) {
  const ns = Math.min(40, Math.max(fitScale * 0.25, scale * fattore));
  tx = sx - (sx - tx) * (ns / scale);
  ty = sy - (sy - ty) * (ns / scale);
  scale = ns;
  render();
}

// ------------------------------------------------------------------ disegno
function pill(x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

// Disegna un'etichetta centrata in cxy (coord. schermo) e ne restituisce il
// rettangolo, per il trascinamento. Con box=false niente riquadro bianco:
// solo testo con un alone chiaro che lo rende leggibile sul disegno.
function drawLabel(cxy, testo, size, box) {
  if (box === undefined) box = true;
  if (!testo) return null;
  const righe = String(testo).split("\n").filter(function (r) { return r; });
  if (!righe.length) return null;
  ctx.font = "700 " + size + "px system-ui, sans-serif";
  let maxW = 0;
  for (const r of righe) maxW = Math.max(maxW, ctx.measureText(r).width);
  const lineH = size * 1.3;
  const w = maxW + 14, h = righe.length * lineH + 8;
  const x = cxy[0] - w / 2, y = cxy[1] - h / 2;
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  if (box) {
    pill(x, y, w, h, 6);
    ctx.fillStyle = "rgba(255,255,255,0.92)";
    ctx.fill();
    ctx.strokeStyle = "rgba(26,39,68,0.30)";
    ctx.lineWidth = 1;
    ctx.stroke();
    ctx.fillStyle = "#1A2744";
    for (let i = 0; i < righe.length; i++) {
      ctx.fillText(righe[i], cxy[0], y + 4 + lineH * (i + 0.5));
    }
  } else {
    ctx.lineJoin = "round";
    ctx.strokeStyle = "rgba(255,255,255,0.95)";   // alone per la leggibilità
    ctx.lineWidth = 3.5;
    ctx.fillStyle = "#111111";
    for (let i = 0; i < righe.length; i++) {
      const ty = y + 4 + lineH * (i + 0.5);
      ctx.strokeText(righe[i], cxy[0], ty);
      ctx.fillText(righe[i], cxy[0], ty);
    }
  }
  return { x: x, y: y, w: w, h: h };
}

function tratteggio(on) {
  ctx.setLineDash(on ? [8 / scale, 6 / scale] : []);
}

function seg(ax, ay, bx, by) {
  ctx.moveTo(ax, ay);
  ctx.lineTo(bx, by);
}

// Simboli in stile disegno tecnico. Ogni tipo ha il suo segno, riconoscibile
// anche a colpo d'occhio e in bianco e nero:
//   scala     → linea di quota con le barrette oblique a 45° dei disegni CAD
//   misura    → linea con le punte di freccia
//   demolire  → tratteggio con le crocette (la convenzione delle demolizioni)
//   costruire → linea piena con i giunti dei mattoni
// spessore è in px schermo: viene diviso per lo zoom, così il segno resta
// dello stesso peso a qualunque ingrandimento.
function drawVettore(p1, p2, dashed, colore, spessore, evidenzia, stile) {
  const lw = (spessore || 5) / scale;
  const dx = p2[0] - p1[0], dy = p2[1] - p1[1];
  const L = Math.hypot(dx, dy) || 1;
  const ux = dx / L, uy = dy / L;          // versore lungo il segmento
  const nx = -uy, ny = ux;                 // normale
  const T = 11 / scale;                    // sbraccio delle tacche
  const capo = 13 / scale;

  ctx.lineCap = "round";
  ctx.lineJoin = "round";

  if (evidenzia) {                        // selezione: alone extra
    ctx.strokeStyle = "rgba(255,255,255,0.95)";
    ctx.lineWidth = lw + 8 / scale;
    ctx.beginPath();
    seg(p1[0], p1[1], p2[0], p2[1]);
    ctx.stroke();
  }
  ctx.strokeStyle = "rgba(255,255,255,0.78)";   // alone di contrasto
  ctx.lineWidth = lw + 4 / scale;
  ctx.beginPath();
  seg(p1[0], p1[1], p2[0], p2[1]);
  ctx.stroke();

  // --- corpo della linea
  ctx.strokeStyle = colore;
  ctx.lineWidth = lw;
  if (stile === "demolire") ctx.setLineDash([13 / scale, 8 / scale]);
  else tratteggio(dashed);
  ctx.beginPath();
  seg(p1[0], p1[1], p2[0], p2[1]);
  ctx.stroke();
  tratteggio(false);

  // --- segno caratteristico
  ctx.lineWidth = Math.max(1.6 / scale, lw * 0.55);
  ctx.beginPath();
  if (stile === "scala") {
    // barrette a 45°: (n+u)/√2 ruotato, il tratto obliquo delle quote
    const ox = (ux + nx) * 0.7071, oy = (uy + ny) * 0.7071;
    seg(p1[0] - ox * T, p1[1] - oy * T, p1[0] + ox * T, p1[1] + oy * T);
    seg(p2[0] - ox * T, p2[1] - oy * T, p2[0] + ox * T, p2[1] + oy * T);
    // e i piedini perpendicolari che chiudono la quota
    seg(p1[0] - nx * T * 0.8, p1[1] - ny * T * 0.8,
        p1[0] + nx * T * 0.8, p1[1] + ny * T * 0.8);
    seg(p2[0] - nx * T * 0.8, p2[1] - ny * T * 0.8,
        p2[0] + nx * T * 0.8, p2[1] + ny * T * 0.8);
  } else if (stile === "misura") {
    const a = capo * 0.55;
    seg(p1[0], p1[1], p1[0] + ux * capo + nx * a, p1[1] + uy * capo + ny * a);
    seg(p1[0], p1[1], p1[0] + ux * capo - nx * a, p1[1] + uy * capo - ny * a);
    seg(p2[0], p2[1], p2[0] - ux * capo + nx * a, p2[1] - uy * capo + ny * a);
    seg(p2[0], p2[1], p2[0] - ux * capo - nx * a, p2[1] - uy * capo - ny * a);
  } else if (stile === "demolire") {
    // crocette lungo il tracciato, come sulle tavole di demolizione
    const passo = 30 / scale, c = 6 / scale;
    for (let d = passo * 0.5; d < L; d += passo) {
      const cx = p1[0] + ux * d, cy = p1[1] + uy * d;
      seg(cx - (ux + nx) * c, cy - (uy + ny) * c,
          cx + (ux + nx) * c, cy + (uy + ny) * c);
      seg(cx - (ux - nx) * c, cy - (uy - ny) * c,
          cx + (ux - nx) * c, cy + (uy - ny) * c);
    }
    seg(p1[0] - nx * T * 0.7, p1[1] - ny * T * 0.7,
        p1[0] + nx * T * 0.7, p1[1] + ny * T * 0.7);
    seg(p2[0] - nx * T * 0.7, p2[1] - ny * T * 0.7,
        p2[0] + nx * T * 0.7, p2[1] + ny * T * 0.7);
  } else if (stile === "costruire") {
    // giunti dei mattoni: trattini trasversali a passo regolare
    const passo = 26 / scale, h = 5.5 / scale;
    for (let d = passo; d < L - passo * 0.4; d += passo) {
      const cx = p1[0] + ux * d, cy = p1[1] + uy * d;
      seg(cx - nx * h, cy - ny * h, cx + nx * h, cy + ny * h);
    }
    seg(p1[0] - nx * T * 0.7, p1[1] - ny * T * 0.7,
        p1[0] + nx * T * 0.7, p1[1] + ny * T * 0.7);
    seg(p2[0] - nx * T * 0.7, p2[1] - ny * T * 0.7,
        p2[0] + nx * T * 0.7, p2[1] + ny * T * 0.7);
  } else {
    seg(p1[0] - nx * T, p1[1] - ny * T, p1[0] + nx * T, p1[1] + ny * T);
    seg(p2[0] - nx * T, p2[1] - ny * T, p2[0] + nx * T, p2[1] + ny * T);
  }
  ctx.stroke();
}

function posEtichettaZona(z) {
  return img2scr(z.etichetta_pos || baricentro(z.punti));
}
function posEtichettaParete(p) {
  if (p.etichetta_pos) return img2scr(p.etichetta_pos);
  const m = img2scr([(p.p1[0] + p.p2[0]) / 2, (p.p1[1] + p.p2[1]) / 2]);
  return [m[0], m[1] - 16];
}

function render() {
  if (!pronto || !ctx) return;
  const w = cont.clientWidth;
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  ctx.clearRect(0, 0, w, contH);

  // --- spazio immagine ---
  ctx.setTransform(dpr * scale, 0, 0, dpr * scale, dpr * tx, dpr * ty);
  ctx.imageSmoothingEnabled = scale < 3;
  ctx.drawImage(img, 0, 0);

  // I perimetri commerciali (senza sfondo) si disegnano PRIMA: restano
  // sotto le altre aree, così ci si può disegnare sopra liberamente.
  // E restano visibili anche a locali nascosti: nascondere le aree serve a
  // togliere il velo colorato delle stanze mentre si tracciano i muri, non
  // a perdere di vista l'ingombro dell'immobile — che è un contorno
  // tratteggiato e non copre niente.
  for (const z of zoneVisibili(zoneOrdinate())) {
    const sel = (z.id === selZona);
    ctx.beginPath();
    z.punti.forEach(function (p, i) {
      if (i === 0) ctx.moveTo(p[0], p[1]); else ctx.lineTo(p[0], p[1]);
    });
    ctx.closePath();
    if (z.senza_sfondo) {
      // solo il contorno, tratteggiato: si vede che è un ingombro e non
      // un locale, e non copre quello che c'è sotto
      ctx.setLineDash([12 / scale, 7 / scale]);
      ctx.strokeStyle = sel ? "#FFFFFF" : z.colore;
      ctx.lineWidth = (sel ? 3.6 : 2.6) / scale;
      ctx.stroke();
      ctx.setLineDash([]);
      continue;
    }
    ctx.fillStyle = hexRgba(z.colore, sel ? 0.52 : 0.36);
    ctx.fill();
    ctx.strokeStyle = sel ? "#FFFFFF" : z.colore;
    ctx.lineWidth = (sel ? 3.2 : 2.2) / scale;
    ctx.stroke();
    if (sel) {
      ctx.strokeStyle = z.colore;
      ctx.lineWidth = 1.4 / scale;
      ctx.stroke();
    }
  }

  // poligono in corso di disegno
  if (mode === "disegna" && drawing.length) {
    ctx.beginPath();
    drawing.forEach(function (p, i) {
      if (i === 0) ctx.moveTo(p[0], p[1]); else ctx.lineTo(p[0], p[1]);
    });
    if (cursorPos) ctx.lineTo(cursorPos[0], cursorPos[1]);
    ctx.fillStyle = hexRgba(coloreAttivo, 0.22);
    ctx.fill();
    ctx.strokeStyle = coloreAttivo;
    ctx.lineWidth = 2.4 / scale;
    ctx.stroke();
  }

  for (const p of pareti) {
    drawVettore(p.p1, p.p2, false, p.colore || "#C9A96A", 5,
                p.id === selParete, p.tipo || "esistente");
  }
  for (const m of misure) {
    drawVettore(m.p1, m.p2, false, COL_MISURA, 3.5, false, "misura");
  }
  if (scalaTemp) {
    drawVettore(scalaTemp.p1, scalaTemp.p2, false, COL_SCALA, 4.5, false,
                "scala");
  }
  if (vecStart && vecEnd &&
      (vettoreAperto || (drag && drag.kind === "vector"))) {
    const col = (mode === "scala") ? COL_SCALA
      : (mode === "misura") ? COL_MISURA : coloreParete();
    const stile = (mode === "parete") ? (tipoParete || "demolire") : mode;
    drawVettore(vecStart, vecEnd, false, col,
                mode === "scala" ? 4.5 : 4, false, stile);
    if (vettoreAperto) {          // pallino sul punto già fissato
      ctx.beginPath();
      ctx.arc(vecStart[0], vecStart[1], 4.5 / scale, 0, Math.PI * 2);
      ctx.fillStyle = "#FFFFFF";
      ctx.fill();
      ctx.strokeStyle = col;
      ctx.lineWidth = 2 / scale;
      ctx.stroke();
    }
  }

  // --- spazio schermo (etichette e maniglie) ---
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  labelRects = [];

  for (const z of zoneVisibili(zone)) {
    const pos = posEtichettaZona(z);
    // linea di richiamo quando l'etichetta sta fuori dalla sua area
    if (z.etichetta && z.etichetta_pos && z.punti.length >= 3 &&
        !dentro(z.etichetta_pos, z.punti)) {
      const b = img2scr(baricentro(z.punti));
      ctx.strokeStyle = z.colore;
      ctx.lineWidth = 1.6;
      ctx.beginPath();
      ctx.moveTo(b[0], b[1]);
      ctx.lineTo(pos[0], pos[1]);
      ctx.stroke();
      ctx.beginPath();
      ctx.arc(b[0], b[1], 3.2, 0, Math.PI * 2);
      ctx.fillStyle = z.colore;
      ctx.fill();
    }
    const r = drawLabel(pos, z.etichetta, fontPx);
    if (r) labelRects.push({ r: r, el: "zona", obj: z });
  }
  for (const p of pareti) {
    const pos = posEtichettaParete(p);
    const mid = img2scr([(p.p1[0] + p.p2[0]) / 2, (p.p1[1] + p.p2[1]) / 2]);
    if (p.etichetta && dist(pos, mid) > 30) {   // spostata lontano: richiamo
      ctx.strokeStyle = p.colore || "#C9A96A";
      ctx.lineWidth = 1.4;
      ctx.beginPath();
      ctx.moveTo(mid[0], mid[1]);
      ctx.lineTo(pos[0], pos[1]);
      ctx.stroke();
    }
    const r = drawLabel(pos, p.etichetta, Math.max(10, fontPx - 2), false);
    if (r) labelRects.push({ r: r, el: "parete", obj: p });
  }
  for (const m of misure) {
    const c = img2scr([(m.p1[0] + m.p2[0]) / 2, (m.p1[1] + m.p2[1]) / 2]);
    drawLabel([c[0], c[1] - 16], fmtMetri(dist(m.p1, m.p2)),
              Math.max(10, fontPx - 2), false);
  }
  if (scalaTemp) {
    const c = img2scr([(scalaTemp.p1[0] + scalaTemp.p2[0]) / 2,
                       (scalaTemp.p1[1] + scalaTemp.p2[1]) / 2]);
    drawLabel([c[0], c[1] - 18],
              fmtMetri(dist(scalaTemp.p1, scalaTemp.p2)),
              Math.max(10, fontPx - 2), false);
  }

  // maniglie della zona selezionata
  if (mode === "modifica" && selZona != null) {
    const z = zone.find(function (q) { return q.id === selZona; });
    if (z) {
      for (const p of z.punti) {
        const s = img2scr(p);
        ctx.fillStyle = "#FFFFFF";
        ctx.strokeStyle = z.colore;
        ctx.lineWidth = 2;
        ctx.fillRect(s[0] - 5, s[1] - 5, 10, 10);
        ctx.strokeRect(s[0] - 5, s[1] - 5, 10, 10);
      }
    }
  }

  // cerchietto di chiusura sul primo punto del poligono in corso
  if (mode === "disegna" && drawing.length >= 3) {
    const s0 = img2scr(drawing[0]);
    const vicino = cursorPos && dist(img2scr(cursorPos), s0) < 12;
    ctx.beginPath();
    ctx.arc(s0[0], s0[1], 8, 0, Math.PI * 2);
    ctx.fillStyle = vicino ? coloreAttivo : "rgba(255,255,255,0.85)";
    ctx.fill();
    ctx.strokeStyle = coloreAttivo;
    ctx.lineWidth = 2;
    ctx.stroke();
  }

  // misura "live" vicino al cursore (solo metri)
  if (cursorPos) {
    let testo = null;
    if (drag && drag.kind === "vector" && vecStart && vecEnd) {
      testo = fmtMetri(dist(vecStart, vecEnd));
    } else if (mode === "disegna" && drawing.length && mpp > 0) {
      testo = fmtMetri(dist(drawing[drawing.length - 1], cursorPos));
    }
    if (testo) {
      const s = img2scr(cursorPos);
      drawLabel([s[0] + 16, s[1] - 22], testo, Math.max(10, fontPx - 2));
    }
  }
}

function coloreParete() {
  // stesso colore che avrà una volta salvata (rosso demolire, giallo
  // costruire), così durante il tracciamento si vede già cosa si sta facendo
  if (tipoParete === "demolire") return "#E53935";
  if (tipoParete === "costruire") return "#FFD400";
  return "#C9A96A";
}

// ------------------------------------------------------------------- eventi
function setMode(m) {
  mode = m;
  drawing = [];
  annullaVettore();
  chiudiEditor();
  drag = null;
  misure = [];                       // le misure al volo sono temporanee
  document.querySelectorAll(".tb-btn[data-mode]").forEach(function (b) {
    b.classList.toggle("attivo", b.dataset.mode === m);
  });
  cv.style.cursor = (m === "sposta") ? "grab"
    : (m === "modifica") ? "default" : "crosshair";
  render();
}

function chiudiPoligono() {
  // elimina punti consecutivi troppo vicini (doppio clic, mano incerta)
  const pts = [];
  for (const p of drawing) {
    if (!pts.length || dist(p, pts[pts.length - 1]) * scale >= 3) pts.push(p);
  }
  if (pts.length >= 3 && dist(pts[0], pts[pts.length - 1]) * scale < 3) pts.pop();
  drawing = [];
  if (pts.length >= 3) send({ tipo: "zona_chiusa", punti: arrotonda(pts) });
  render();
}

function hitLabel(s) {
  for (let i = labelRects.length - 1; i >= 0; i--) {
    const q = labelRects[i];
    if (s[0] >= q.r.x && s[0] <= q.r.x + q.r.w &&
        s[1] >= q.r.y && s[1] <= q.r.y + q.r.h) return q;
  }
  return null;
}
function hitVertice(z, s) {
  for (let i = 0; i < z.punti.length; i++) {
    if (dist(img2scr(z.punti[i]), s) < 9) return i;
  }
  return -1;
}
function distContorno(s, pts) {          // distanza (schermo) dal perimetro
  let minima = Infinity;
  for (let i = 0; i < pts.length; i++) {
    const a = img2scr(pts[i]), b = img2scr(pts[(i + 1) % pts.length]);
    minima = Math.min(minima, distSeg(s, a, b));
  }
  return minima;
}

function hitZona(p) {
  // Le aree vere hanno la precedenza; i perimetri commerciali si prendono
  // solo cliccandone il bordo, altrimenti — grandi e sopra tutto il disegno —
  // catturerebbero ogni clic e non si potrebbe più lavorare al loro interno.
  for (let i = zone.length - 1; i >= 0; i--) {
    if (!zone[i].senza_sfondo && dentro(p, zone[i].punti)) return zone[i];
  }
  const s = img2scr(p);
  for (let i = zone.length - 1; i >= 0; i--) {
    if (zone[i].senza_sfondo && zone[i].punti.length >= 3 &&
        distContorno(s, zone[i].punti) < 10) {
      return zone[i];
    }
  }
  return null;
}

function zoneOrdinate() {
  // prima i perimetri senza sfondo (restano sotto), poi le aree piene
  return zone.slice().sort(function (a, b) {
    return (a.senza_sfondo ? 0 : 1) - (b.senza_sfondo ? 0 : 1);
  });
}
function hitParete(s) {
  // presa generosa (12 px): un muro è una linea sottile, va afferrato senza
  // dover centrare il pixel esatto. Vince il più vicino, non il primo che
  // capita, così due muri che si incrociano restano distinguibili.
  let vicino = null, minima = 12;
  for (let i = pareti.length - 1; i >= 0; i--) {
    const d = distSeg(s, img2scr(pareti[i].p1), img2scr(pareti[i].p2));
    if (d < minima) {
      minima = d;
      vicino = pareti[i];
    }
  }
  return vicino;
}

function iniziaDragEtichetta(q, s, p) {
  // posizione attuale dell'etichetta (personalizzata o predefinita)
  const c = (q.el === "zona") ? posEtichettaZona(q.obj)
                              : posEtichettaParete(q.obj);
  const base = q.obj.etichetta_pos || scr2img(c);
  drag = { kind: "label", tgt: q.obj, el: q.el, moved: false, base: base,
           offx: p[0] - base[0],
           offy: p[1] - base[1] };
}

function onDown(e) {
  if (!pronto) return;
  cv.focus();
  const s = scrOf(e);
  const p = scr2img(s);

  if (e.button === 1) {                 // rotellina premuta = sposta sempre
    e.preventDefault();
    drag = { kind: "pan", sx: e.clientX, sy: e.clientY, tx0: tx, ty0: ty };
    return;
  }
  if (e.button !== 0) return;

  // le etichette si trascinano in Sposta e in Modifica
  if (mode === "sposta" || mode === "modifica") {
    const q = hitLabel(s);
    if (q) {
      iniziaDragEtichetta(q, s, p);
      return;
    }
  }

  if (mode === "sposta") {
    drag = { kind: "pan", sx: e.clientX, sy: e.clientY, tx0: tx, ty0: ty };
    cv.style.cursor = "grabbing";

  } else if (mode === "disegna") {
    if (drawing.length >= 3 && dist(s, img2scr(drawing[0])) < 12) {
      chiudiPoligono();
    } else {
      drawing.push(p);
      render();
    }

  } else if (mode === "modifica") {
    if (selZona != null) {
      const zSel = zone.find(function (q) { return q.id === selZona; });
      if (zSel) {
        const vi = hitVertice(zSel, s);
        if (vi >= 0) {
          drag = { kind: "vertex", z: zSel, vi: vi, moved: false };
          return;
        }
      }
    }
    // I MURI HANNO LA PRECEDENZA sulle aree: sono disegnati sopra e sono
    // sottili, quindi vanno presi per primi — altrimenti l'area sottostante
    // se li "mangia" e diventano quasi impossibili da selezionare.
    const wHit = hitParete(s);
    if (wHit) {
      if (selParete !== wHit.id || selZona != null) {
        selParete = wHit.id;
        selZona = null;
        inviaSelezione();
      }
      render();
      return;
    }
    const z = hitZona(p);
    if (z) {
      if (z.id === selZona) {
        drag = { kind: "move", z: z, start: p, moved: false,
                 orig: z.punti.map(function (q) { return q.slice(); }) };
      } else {
        selZona = z.id;
        selParete = null;
        inviaSelezione();
      }
      render();
    } else if (selZona != null || selParete != null) {
      selZona = null;
      selParete = null;
      inviaSelezione();
      render();
    } else {
      render();
    }

  } else if (mode === "scala" || mode === "parete" || mode === "misura") {
    if (vettoreAperto) {          // secondo clic: chiude il segmento
      vecEnd = p;
      completaVettore();
    } else {
      vecStart = p;
      vecEnd = p;
      drag = { kind: "vector" };
    }
  }
}

function onMove(e) {
  if (!cv || !pronto) return;
  const s = scrOf(e);
  cursorPos = scr2img(s);
  if (drag) {
    if (drag.kind === "pan") {
      tx = drag.tx0 + (e.clientX - drag.sx);
      ty = drag.ty0 + (e.clientY - drag.sy);
    } else if (drag.kind === "vertex") {
      drag.z.punti[drag.vi] = cursorPos.slice();
      drag.moved = true;
    } else if (drag.kind === "move") {
      const dx = cursorPos[0] - drag.start[0];
      const dy = cursorPos[1] - drag.start[1];
      if (Math.hypot(dx, dy) * scale > 3) drag.moved = true;
      drag.z.punti = drag.orig.map(function (q) { return [q[0] + dx, q[1] + dy]; });
    } else if (drag.kind === "vector") {
      vecEnd = cursorPos.slice();
    } else if (drag.kind === "label") {
      drag.tgt.etichetta_pos = [cursorPos[0] - drag.offx,
                                cursorPos[1] - drag.offy];
      drag.moved = true;
    }
    render();
  } else if (vettoreAperto && vecStart) {
    vecEnd = cursorPos.slice();   // anteprima fino al secondo clic
    render();
  } else if (mode === "disegna" && drawing.length) {
    render();
  }
}

function onUp() {
  if (!drag) return;
  const d = drag;
  drag = null;
  if (d.kind === "pan") {
    if (mode === "sposta") cv.style.cursor = "grab";
  } else if ((d.kind === "vertex" || d.kind === "move") && d.moved) {
    send({ tipo: "zona_modificata", id: d.z.id, punti: arrotonda(d.z.punti) });
  } else if (d.kind === "label" && d.moved) {
    send({ tipo: "etichetta_spostata", elemento: d.el, id: d.tgt.id,
           pos: arrotonda([d.tgt.etichetta_pos])[0] });
  } else if (d.kind === "vector" && vecStart && vecEnd &&
             dist(img2scr(vecStart), img2scr(vecEnd)) > 8) {
    completaVettore();          // trascinamento: si chiude al rilascio
  } else if (d.kind === "vector") {
    // clic secco (senza trascinare): il primo punto resta fissato e si
    // aspetta il secondo clic. Puntare due volte con calma è più preciso
    // che tenere premuto, soprattutto a forte ingrandimento.
    vettoreAperto = true;
  }
  render();
}

function completaVettore() {
  if (vecStart && vecEnd) {
    const p1 = arrotonda([vecStart])[0];
    const p2 = arrotonda([vecEnd])[0];
    if (dist(img2scr(p1), img2scr(p2)) > 4) {
      if (mode === "scala") send({ tipo: "scala", p1: p1, p2: p2 });
      else if (mode === "parete") send({ tipo: "parete", p1: p1, p2: p2 });
      else if (mode === "misura") misure.push({ p1: p1, p2: p2 });
    }
  }
  annullaVettore();
  render();
}

function annullaVettore() {
  vecStart = vecEnd = null;
  vettoreAperto = false;
}

// Rinomina al volo: doppio clic sull'etichetta di un'area e si scrive il
// nome lì sopra. Cambia SOLO il nome: categoria, superficie e percentuale
// restano quelli calcolati dal server.
function apriEditor(z, r) {
  chiudiEditor();
  editor = document.createElement("input");
  editor.type = "text";
  editor.value = z.nome || "";
  editor.placeholder = "Nome del locale";
  editor.setAttribute("style",
    "position:absolute;z-index:5;box-sizing:border-box;" +
    "left:" + Math.round(r.x - 4) + "px;top:" + Math.round(r.y + r.h / 2 - 15) +
    "px;width:" + Math.max(130, Math.round(r.w + 8)) + "px;" +
    "font:600 " + fontPx + "px system-ui,sans-serif;padding:5px 7px;" +
    "border:2px solid " + z.colore + ";border-radius:7px;" +
    "background:#fff;color:#1A2744;box-shadow:0 3px 10px rgba(0,0,0,.28);");
  editor.addEventListener("keydown", function (e) {
    e.stopPropagation();
    if (e.key === "Enter") {
      send({ tipo: "rinomina", elemento: "zona", id: z.id,
             nome: editor.value.trim() });
      chiudiEditor();
    } else if (e.key === "Escape") {
      chiudiEditor();
    }
  });
  editor.addEventListener("blur", chiudiEditor);
  cont.appendChild(editor);
  editor.focus();
  editor.select();
}

function chiudiEditor() {
  if (editor && editor.parentNode) editor.parentNode.removeChild(editor);
  editor = null;
}

function onDbl(e) {
  if (mode === "disegna" && drawing.length >= 3) { chiudiPoligono(); return; }
  const q = hitLabel(scrOf(e));
  if (q && q.el === "zona") apriEditor(q.obj, q.r);
}

function onKey(e) {
  if (e.key === "Escape") {
    if (vettoreAperto) annullaVettore();   // prima si annulla il segmento
    else if (drawing.length) drawing = [];
    else if (misure.length) misure = [];
    else if (selZona != null || selParete != null) {
      selZona = null;
      selParete = null;
      inviaSelezione();
    }
    vecStart = vecEnd = null;
    drag = null;
    render();
  } else if (e.key === "Backspace" && mode === "disegna" && drawing.length) {
    e.preventDefault();
    drawing.pop();
    render();
  } else if (e.key === "Delete" && mode === "modifica") {
    if (selZona != null) {
      send({ tipo: "zona_eliminata", id: selZona });
      selZona = null;
    } else if (selParete != null) {
      send({ tipo: "parete_eliminata", id: selParete });
      selParete = null;
    }
    render();
  }
}

// ------------------------------------------------------------- inizializza
function onRender(event) {
  const a = event.detail.args;
  zone = a.zone || [];
  pareti = a.pareti || [];
  scalaTemp = a.scala_temp || null;
  coloreAttivo = a.colore_attivo || "#E57373";
  mpp = a.mpp || 0;
  fontPx = a.font_px || 14;
  tipoParete = a.tipo_parete || "demolire";

  if (selZona != null && !zone.some(function (z) { return z.id === selZona; })) {
    selZona = null;
  }
  if (selParete != null &&
      !pareti.some(function (p) { return p.id === selParete; })) {
    selParete = null;
  }

  if (a.src !== curSrc) {
    curSrc = a.src;
    pronto = false;
    img.src = a.src;          // al termine: img.onload → fit()
  } else {
    render();
  }
}

function init() {
  cont = document.getElementById("wrap");
  cv = document.getElementById("cv");
  ctx = cv.getContext("2d");
  dpr = window.devicePixelRatio || 1;

  img.onload = function () {
    pronto = true;
    fit();
  };

  document.querySelectorAll(".tb-btn[data-mode]").forEach(function (b) {
    b.addEventListener("click", function () { setMode(b.dataset.mode); });
  });
  document.getElementById("b-zin").addEventListener("click", function () {
    zoomAt(cont.clientWidth / 2, contH / 2, 1.3);
  });
  document.getElementById("b-zout").addEventListener("click", function () {
    zoomAt(cont.clientWidth / 2, contH / 2, 1 / 1.3);
  });
  document.getElementById("b-fit").addEventListener("click", fit);
  // nascondi/mostra le aree: serve per tracciare i muri senza il velo
  // colorato dei locali sotto. È solo visivo, non tocca i dati.
  const bAree = document.getElementById("b-aree");
  bAree.addEventListener("click", function () {
    mostraAree = !mostraAree;
    bAree.classList.toggle("spento", !mostraAree);
    bAree.title = mostraAree
      ? "Nascondi le aree dei locali (il perimetro commerciale resta)"
      : "Mostra di nuovo le aree dei locali";
    chiudiEditor();
    render();
  });

  cv.addEventListener("wheel", function (e) {
    e.preventDefault();
    const s = scrOf(e);
    zoomAt(s[0], s[1], Math.exp(-e.deltaY * 0.0012));
  }, { passive: false });

  cv.addEventListener("mousedown", onDown);
  cv.addEventListener("dblclick", onDbl);
  cv.addEventListener("contextmenu", function (e) { e.preventDefault(); });
  cv.addEventListener("mouseleave", function () { cursorPos = null; render(); });
  window.addEventListener("mousemove", onMove);
  window.addEventListener("mouseup", onUp);
  window.addEventListener("keydown", onKey);
  window.addEventListener("resize", function () { if (pronto) fit(); });

  Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, onRender);
  Streamlit.setComponentReady();
  Streamlit.setFrameHeight(360);
}

document.addEventListener("DOMContentLoaded", init);
