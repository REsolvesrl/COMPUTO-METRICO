// Il filo col motore: la vista del progetto aperto, e i gesti che la cambiano.
//
// Il modello è quello di Streamlit senza Streamlit: si manda un gesto, torna
// la vista intera ricalcolata. `stato.vista` è l'unica fonte di quello che
// si vede; nessun componente tiene copie sue dei numeri del progetto.
import { reactive } from "vue";

export const stato = reactive({
  vista: null,
  errore: "",       // il motore non risponde
  fette: [],        // i messaggi che compaiono e se ne vanno (st.toast)
  occupato: false,
});

let prossima = 1;

export function toast(testo, tipo = "ok") {
  const id = prossima++;
  stato.fette.push({ id, testo, tipo });
  setTimeout(() => {
    const i = stato.fette.findIndex((f) => f.id === id);
    if (i >= 0) stato.fette.splice(i, 1);
  }, tipo === "errore" ? 7000 : 4000);
}

async function leggi(risposta) {
  if (!risposta.ok) {
    let dettaglio = risposta.statusText;
    try { dettaglio = (await risposta.json()).detail || dettaglio; } catch (e) { /* niente */ }
    throw new Error(dettaglio);
  }
  return risposta.json();
}

export async function caricaVista() {
  try {
    stato.vista = await leggi(await fetch("/api/vista"));
    stato.errore = "";
  } catch (e) {
    stato.errore = `Il motore non risponde: ${e.message}. È aperta la finestra nera?`;
  }
}

// Un gesto sul progetto. Torna l'esito ({tipo, testo}) se il motore ha
// qualcosa da dire; gli errori finiscono comunque in un tostapane.
export async function gesto(nome, argomenti = {}, { zitto = false } = {}) {
  stato.occupato = true;
  try {
    const r = await leggi(await fetch("/api/gesto", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ nome, argomenti }),
    }));
    stato.vista = r.vista;
    stato.errore = "";
    if (r.esito && !(zitto && r.esito.tipo === "ok")) toast(r.esito.testo, r.esito.tipo);
    return r.esito;
  } catch (e) {
    toast(e.message, "errore");
    return { tipo: "errore", testo: e.message };
  } finally {
    stato.occupato = false;
  }
}

export async function apriFile(file) {
  const dati = new FormData();
  dati.append("file", file);
  try {
    const r = await leggi(await fetch("/api/apri_file", { method: "POST", body: dati }));
    if (r.vista) stato.vista = r.vista;
    if (r.esito) toast(r.esito.testo, r.esito.tipo);
  } catch (e) {
    toast(e.message, "errore");
  }
}

// Scaricare un file: il browser segue il collegamento, il motore lo
// costruisce adesso. Dopo il .json la testata va ridetta («salvato»).
export function scarica(che_cosa) {
  const a = document.createElement("a");
  a.href = `/api/scarica/${che_cosa}`;
  document.body.appendChild(a);
  a.click();
  a.remove();
  if (che_cosa === "json") setTimeout(caricaVista, 800);
}
