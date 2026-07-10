// Visualizzatore immagine per CME: zoom con la rotellina (verso il cursore),
// spostamento con il trascinamento, e click che restituisce le coordinate nel
// sistema dell'immagine ORIGINALE (indipendente da zoom/pan). Lo zoom vive solo
// nel browser: il server riceve sempre coordinate "canoniche".

let scale = 1, tx = 0, ty = 0;     // trasformazione corrente (px immagine -> px vista)
let baseW = 0, baseH = 0;          // dimensioni naturali dell'immagine
let fitScale = 1;                  // scala che fa entrare tutta l'immagine
let containerH = 0;                // altezza fissa della "finestra" di vista
let ready = false;                 // immagine misurata e adattata almeno una volta
let curToken = null;               // reset_token corrente (per capire quando riadattare
let listeners = false;             // listener agganciati una sola volta

function el(id) { return document.getElementById(id); }

function containerWidth() {
  return Math.max(50, Math.floor(
    document.documentElement.clientWidth || window.innerWidth || 700));
}

function applyTransform() {
  el("image").style.transform = `translate(${tx}px, ${ty}px) scale(${scale})`;
}

function clampPan() {
  const w = containerWidth();
  const dispW = baseW * scale, dispH = baseH * scale;
  const loX = Math.min(0, w - dispW), hiX = Math.max(0, w - dispW);
  const loY = Math.min(0, containerH - dispH), hiY = Math.max(0, containerH - dispH);
  tx = Math.max(loX, Math.min(tx, hiX));
  ty = Math.max(loY, Math.min(ty, hiY));
}

function fit() {
  const w = containerWidth();
  // "contain": tutta l'immagine visibile, centrata orizzontalmente.
  fitScale = Math.min(w / baseW, 640 / baseH);
  scale = fitScale;
  containerH = Math.max(80, Math.round(baseH * fitScale));
  tx = Math.round((w - baseW * scale) / 2);
  ty = 0;
  el("viewer").style.height = containerH + "px";
  applyTransform();
  Streamlit.setFrameHeight(containerH + 2);
}

function setupListeners() {
  if (listeners) return;
  listeners = true;
  const cont = el("viewer");

  // Zoom con la rotellina, centrato sul punto sotto il cursore.
  cont.addEventListener("wheel", (ev) => {
    ev.preventDefault();
    if (!ready) return;
    const rect = cont.getBoundingClientRect();
    const cx = ev.clientX - rect.left, cy = ev.clientY - rect.top;
    const ix = (cx - tx) / scale, iy = (cy - ty) / scale;
    const factor = ev.deltaY < 0 ? 1.15 : 1 / 1.15;
    const ns = Math.max(fitScale, Math.min(scale * factor, fitScale * 25));
    tx = cx - ix * ns;
    ty = cy - iy * ns;
    scale = ns;
    clampPan();
    applyTransform();
  }, { passive: false });

  // Trascinamento = spostamento; click senza movimento = punto.
  let dragging = false, moved = false, sx = 0, sy = 0, otx = 0, oty = 0;
  cont.addEventListener("mousedown", (ev) => {
    dragging = true; moved = false;
    sx = ev.clientX; sy = ev.clientY; otx = tx; oty = ty;
  });
  window.addEventListener("mousemove", (ev) => {
    if (!dragging) return;
    const dx = ev.clientX - sx, dy = ev.clientY - sy;
    if (Math.abs(dx) + Math.abs(dy) > 4) moved = true;
    tx = otx + dx; ty = oty + dy;
    clampPan(); applyTransform();
  });
  window.addEventListener("mouseup", (ev) => {
    if (!dragging) return;
    dragging = false;
    if (moved || !ready) return;
    const rect = cont.getBoundingClientRect();
    const cx = ev.clientX - rect.left, cy = ev.clientY - rect.top;
    if (cx < 0 || cy < 0 || cx > containerWidth() || cy > containerH) return;
    const ix = (cx - tx) / scale, iy = (cy - ty) / scale;
    if (ix < 0 || iy < 0 || ix > baseW || iy > baseH) return;
    Streamlit.setComponentValue({ x: ix, y: iy, unix_time: Date.now() });
  });

  window.addEventListener("resize", () => { if (ready) fit(); });
}

function onRender(event) {
  const { src, reset_token, cursor } = event.detail.args;
  const img = el("image"), cont = el("viewer");
  cont.style.cursor = cursor || "crosshair";
  setupListeners();
  const tokenChanged = reset_token !== curToken;

  function afterLoad() {
    baseW = img.naturalWidth;
    baseH = img.naturalHeight;
    img.style.width = baseW + "px";
    img.style.height = baseH + "px";
    if (!ready || tokenChanged) {
      fit();
      ready = true;
      curToken = reset_token;
    } else {
      applyTransform();
      Streamlit.setFrameHeight(containerH + 2);
    }
  }

  if (img.src !== src) {
    img.onload = afterLoad;
    img.src = src;
  } else {
    afterLoad();
  }
}

Streamlit.events.addEventListener(Streamlit.RENDER_EVENT, onRender);
Streamlit.setComponentReady();
Streamlit.setFrameHeight(200);
