// Numeri e importi all'italiana: le stesse regole di formato.py.
//
// ⚠️ Stesse regole, non «simili»: la pagina scrive i numeri che il motore
// rilegge. `numeroIt` è `numero_it`, `euro` è `euro`, `numeroDaIt` è
// `numero_da_it` — compreso il punto ambiguo, che vale migliaia solo se
// raggruppa a tre a tre.

export function numeroIt(valore, decimali = 3) {
  if (valore === null || valore === undefined || Number.isNaN(valore)) return "";
  const segno = valore < 0 ? "-" : "";
  const [intero, frazione] = Math.abs(valore).toFixed(decimali).split(".");
  const migliaia = intero.replace(/\B(?=(\d{3})+(?!\d))/g, ".");
  return segno + migliaia + (frazione ? "," + frazione : "");
}

export function euro(valore) {
  if (valore === null || valore === undefined || Number.isNaN(valore)) return "";
  return `${numeroIt(valore, 2)} €`;
}

export function numeroDaIt(testo) {
  if (testo === null || testo === undefined) return null;
  let t = String(testo).replace(/[€%]/g, "").replace(/[\s ]/g, "");
  if (!t) return null;
  if (t.includes(",")) {
    t = t.replace(/\./g, "").replace(",", ".");
  } else if (t.includes(".")) {
    const pezzi = t.replace(/^[+-]/, "").split(".");
    const migliaia = pezzi.length > 1 && pezzi[0] !== ""
      && pezzi.slice(1).every((p) => p.length === 3);
    if (migliaia) t = t.replace(/\./g, "");
  }
  const n = Number(t);
  return Number.isFinite(n) ? n : null;
}

export function dataIt(iso) {
  if (!iso) return "";
  const [a, m, g] = iso.slice(0, 10).split("-");
  return `${g}/${m}/${a}`;
}

export function oraIt(iso) {
  return iso ? iso.slice(11, 16) : "";
}
