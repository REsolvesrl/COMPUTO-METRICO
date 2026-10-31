// Le spiegazioni: il foglietto che dice a cosa serve una cosa, e come si è
// fatto un conto.
//
// Il `title` del browser si vede solo col mouse, e solo se ci si ferma: da
// tastiera o col dito tutto quello che c'è scritto là dentro non esisteva.
// Qui `title` resta il modo di scrivere una spiegazione, in tutte le schede,
// e un solo foglietto la mostra: passandoci sopra, arrivandoci con Tab, o
// toccando il «?». Si può portarci sopra il cursore per leggerla con calma,
// e Esc la chiude.
//
// ⚠️ Le caselle restano fuori. Il loro title è il testo intero di una cella
// stretta: un foglietto che spunta a ogni Tab coprirebbe la riga sotto, e
// fra le celle si lavora.

const FUORI = "input:not([type=checkbox]):not([type=radio]), textarea, select, iframe";
const INTERATTIVO = "a, button, label, input, select, textarea";
const ATTESA = 350;
const GRAZIA = 120;

let foglio = null;
let host = null;
let fissa = false;
let descritto = null;
let attesa = null;
let chiusura = null;

function spiegabile(bersaglio) {
  const el = bersaglio?.closest?.("[title], [data-spiega]");
  if (!el || el.matches(FUORI)) return null;
  return (el.dataset.spiega ?? el.getAttribute("title") ?? "").trim() ? el : null;
}

function colloca() {
  const r = host.getBoundingClientRect();
  const f = foglio.getBoundingClientRect();
  const margine = 8;
  const sotto = r.bottom + 6;
  const top = sotto + f.height > window.innerHeight - margine ? r.top - f.height - 6 : sotto;
  const destra = window.innerWidth - f.width - margine;
  foglio.style.top = `${Math.max(margine, top)}px`;
  foglio.style.left = `${Math.max(margine, Math.min(r.left, destra))}px`;
}

function fermaTempi() {
  clearTimeout(attesa);
  clearTimeout(chiusura);
}

function chiudi() {
  fermaTempi();
  foglio.hidden = true;
  fissa = false;
  if (!host) return;
  // se nel frattempo la pagina ha riscritto il title, vale il suo
  if (!host.hasAttribute("title")) host.setAttribute("title", host.dataset.spiega);
  delete host.dataset.spiega;
  if (descritto) host.setAttribute("aria-describedby", descritto);
  else host.removeAttribute("aria-describedby");
  host = null;
}

// Il title si toglie subito, anche se il foglietto arriva dopo: altrimenti
// il browser fa spuntare il suo sopra il nostro.
function prendi(el) {
  chiudi();
  host = el;
  host.dataset.spiega = host.getAttribute("title");
  host.removeAttribute("title");
  descritto = host.getAttribute("aria-describedby");
  host.setAttribute("aria-describedby", foglio.id);
}

function mostra() {
  if (!host?.isConnected) { chiudi(); return; }
  foglio.textContent = host.dataset.spiega;
  foglio.hidden = false;
  colloca();
}

function apri(el, ritardo) {
  fermaTempi();
  if (el !== host) prendi(el);
  if (ritardo) attesa = setTimeout(mostra, ritardo);
  else mostra();
}

function sopra(ev) {
  if (fissa) return;
  if (foglio.contains(ev.target)) { clearTimeout(chiusura); return; }
  const el = spiegabile(ev.target);
  if (el) { if (el !== host) apri(el, ATTESA); else clearTimeout(chiusura); }
  else if (host) chiusura = setTimeout(chiudi, GRAZIA);
}

function fuoco(ev) {
  const el = spiegabile(ev.target);
  if (el && ev.target.matches(":focus-visible")) apri(el, 0);
}

function clic(ev) {
  const el = spiegabile(ev.target);
  if (el && (el.matches(".aiuto") || !ev.target.closest(INTERATTIVO))) {
    if (fissa && el === host) { chiudi(); return; }
    apri(el, 0);
    fissa = true;
  } else if (!foglio.contains(ev.target)) {
    chiudi();
  }
}

export function installaSpiegazioni() {
  foglio = document.createElement("div");
  foglio.id = "spiegazione";
  foglio.className = "spiegazione";
  foglio.setAttribute("role", "tooltip");
  foglio.hidden = true;
  document.body.append(foglio);
  document.addEventListener("mouseover", sopra);
  document.addEventListener("focusin", fuoco);
  document.addEventListener("focusout", () => { if (!fissa) chiudi(); });
  document.addEventListener("click", clic);
  document.addEventListener("keydown", (ev) => { if (ev.key === "Escape") chiudi(); });
  window.addEventListener("scroll", (ev) => { if (!foglio.contains(ev.target)) chiudi(); }, true);
  window.addEventListener("resize", chiudi);
}
