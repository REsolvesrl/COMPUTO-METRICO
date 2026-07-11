// cme_viewer — visualizzatore planimetrie con barra strumenti.
// Tutte le coordinate scambiate col server sono nello spazio dell'immagine
// originale ("canoniche"); zoom e spostamento sono solo visivi.

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

let drawing = [];            // poligono in corso (coord. immagine)
let cursorPos = null;        // mouse in coord. immagine (per il rubber band)
let selZona = null, selParete = null;
let drag = null;             // {kind:"pan"|"vertex"|"move"|"vector", ...}
let vecStart = null, vecEnd = null;
let seqN = 0;

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
function fmtLunghezza(pxLen) {
  let t = Math.round(pxLen) + " px";
  if (mpp > 0) t += "  ·  " + fmt(pxLen * mpp, 2) + " m";
  return t;
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

function drawLabel(cxy, testo, size) {
  if (!testo) return;
  const righe = String(testo).split("\n").filter(function (r) { return r; });
  if (!righe.length) return;
  ctx.font = "600 " + size + "px system-ui, sans-serif";
  let maxW = 0;
  for (const r of righe) maxW = Math.max(maxW, ctx.measureText(r).width);
  const lineH = size * 1.3;
  const w = maxW + 14, h = righe.length * lineH + 8;
  const x = cxy[0] - w / 2, y = cxy[1] - h / 2;
  pill(x, y, w, h, 6);
  ctx.fillStyle = "rgba(255,255,255,0.92)";
  ctx.fill();
  ctx.strokeStyle = "rgba(26,39,68,0.30)";
  ctx.lineWidth = 1;
  ctx.stroke();
  ctx.fillStyle = "#1A2744";
  ctx.textAlign = "center";
  ctx.textBaseline = "middle";
  for (let i = 0; i < righe.length; i++) {
    ctx.fillText(righe[i], cxy[0], y + 4 + lineH * (i + 0.5));
  }
}

function tratteggio(on) {
  ctx.setLineDash(on ? [7 / scale, 5 / scale] : []);
}

function drawVettore(p1, p2, dashed, colore) {
  ctx.strokeStyle = colore;
  ctx.lineWidth = 3 / scale;
  tratteggio(dashed);
  ctx.beginPath();
  ctx.moveTo(p1[0], p1[1]);
  ctx.lineTo(p2[0], p2[1]);
  ctx.stroke();
  tratteggio(false);
  // tacche perpendicolari alle estremità
  const dx = p2[0] - p1[0], dy = p2[1] - p1[1];
  const L = Math.hypot(dx, dy) || 1;
  const nx = -dy / L * (8 / scale), ny = dx / L * (8 / scale);
  ctx.beginPath();
  ctx.moveTo(p1[0] - nx, p1[1] - ny); ctx.lineTo(p1[0] + nx, p1[1] + ny);
  ctx.moveTo(p2[0] - nx, p2[1] - ny); ctx.lineTo(p2[0] + nx, p2[1] + ny);
  ctx.stroke();
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

  for (const z of zone) {
    const sel = (z.id === selZona);
    ctx.beginPath();
    z.punti.forEach(function (p, i) {
      if (i === 0) ctx.moveTo(p[0], p[1]); else ctx.lineTo(p[0], p[1]);
    });
    ctx.closePath();
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
    drawVettore(p.p1, p.p2, false, p.id === selParete ? "#E66767" : "#C9A96A");
  }
  if (scalaTemp) drawVettore(scalaTemp.p1, scalaTemp.p2, true, "#C9A96A");
  if (drag && drag.kind === "vector" && vecStart && vecEnd) {
    drawVettore(vecStart, vecEnd, mode === "scala", "#C9A96A");
  }

  // --- spazio schermo (etichette e maniglie) ---
  ctx.setTransform(dpr, 0, 0, dpr, 0, 0);

  for (const z of zone) {
    drawLabel(img2scr(baricentro(z.punti)), z.etichetta, fontPx);
  }
  for (const p of pareti) {
    const m = img2scr([(p.p1[0] + p.p2[0]) / 2, (p.p1[1] + p.p2[1]) / 2]);
    drawLabel([m[0], m[1] - 14], p.etichetta, Math.max(10, fontPx - 2));
  }
  if (scalaTemp) {
    const m = img2scr([(scalaTemp.p1[0] + scalaTemp.p2[0]) / 2,
                       (scalaTemp.p1[1] + scalaTemp.p2[1]) / 2]);
    drawLabel([m[0], m[1] - 16],
              fmtLunghezza(dist(scalaTemp.p1, scalaTemp.p2)),
              Math.max(10, fontPx - 2));
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

  // misura "live" vicino al cursore
  if (cursorPos) {
    let testo = null;
    if (drag && drag.kind === "vector" && vecStart && vecEnd) {
      testo = fmtLunghezza(dist(vecStart, vecEnd));
    } else if (mode === "disegna" && drawing.length && mpp > 0) {
      testo = fmt(dist(drawing[drawing.length - 1], cursorPos) * mpp, 2) + " m";
    }
    if (testo) {
      const s = img2scr(cursorPos);
      drawLabel([s[0] + 14, s[1] - 20], testo, Math.max(10, fontPx - 2));
    }
  }
}

// ------------------------------------------------------------------- eventi
function setMode(m) {
  mode = m;
  drawing = [];
  vecStart = vecEnd = null;
  drag = null;
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

function hitVertice(z, s) {
  for (let i = 0; i < z.punti.length; i++) {
    if (dist(img2scr(z.punti[i]), s) < 9) return i;
  }
  return -1;
}
function hitZona(p) {
  for (let i = zone.length - 1; i >= 0; i--) {
    if (dentro(p, zone[i].punti)) return zone[i];
  }
  return null;
}
function hitParete(s) {
  for (let i = pareti.length - 1; i >= 0; i--) {
    if (distSeg(s, img2scr(pareti[i].p1), img2scr(pareti[i].p2)) < 7) {
      return pareti[i];
    }
  }
  return null;
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
    const z = hitZona(p);
    if (z) {
      if (z.id === selZona) {
        drag = { kind: "move", z: z, start: p, moved: false,
                 orig: z.punti.map(function (q) { return q.slice(); }) };
      } else {
        selZona = z.id;
        selParete = null;
        send({ tipo: "zona_selezionata", id: z.id });
      }
      render();
    } else {
      const w = hitParete(s);
      if (w) {
        selParete = w.id;
        if (selZona != null) {
          selZona = null;
          send({ tipo: "zona_selezionata", id: null });
        }
        render();
      } else {
        if (selZona != null) {
          selZona = null;
          send({ tipo: "zona_selezionata", id: null });
        }
        selParete = null;
        render();
      }
    }

  } else if (mode === "scala" || mode === "parete") {
    vecStart = p;
    vecEnd = null;
    drag = { kind: "vector" };
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
    }
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
  } else if (d.kind === "vector" && vecStart && vecEnd &&
             dist(img2scr(vecStart), img2scr(vecEnd)) > 8) {
    const p1 = arrotonda([vecStart])[0];
    const p2 = arrotonda([vecEnd])[0];
    if (mode === "scala") send({ tipo: "scala", p1: p1, p2: p2 });
    else send({ tipo: "parete", p1: p1, p2: p2 });
    vecStart = vecEnd = null;
  } else if (d.kind === "vector") {
    vecStart = vecEnd = null;
  }
  render();
}

function onDbl() {
  if (mode === "disegna" && drawing.length >= 3) chiudiPoligono();
}

function onKey(e) {
  if (e.key === "Escape") {
    if (drawing.length) drawing = [];
    else if (selZona != null) {
      selZona = null;
      send({ tipo: "zona_selezionata", id: null });
    }
    selParete = null;
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
