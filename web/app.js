// La pagina del computo: elenco dei progetti, e le voci di quello aperto.
//
// ⚠️ Le cifre scritte qui restano in pagina finché non si preme «Salva»:
// ogni salvataggio mette da parte una versione, e se ne tengono tre. Il
// server ricalcola a ogni modifica (rotta /prova) senza scrivere niente,
// così importi e totali li fa sempre `calcoli.py`, mai la pagina.
import { createApp, ref, computed, onMounted } from "vue";

// I colori dei mestieri: gli stessi di COLORI_CATEGORIE in streamlit_app.py.
const COLORI = {
  "Pratiche e oneri": "#ECE7DA", "Demolizioni": "#E57373",
  "Ricostruzioni e ripristini": "#66BB6A", "Idraulico": "#64B5F6",
  "Elettricista": "#F0A840", "Serramenti": "#9575CD",
  "Aree esterne": "#B0BEC5", "Tetto": "#B8735A", "Facciata": "#D9C7A7",
};

const euro = (v) => (v ?? 0).toLocaleString("it-IT",
  { style: "currency", currency: "EUR" });
const numero = (v) => (v ?? 0).toLocaleString("it-IT",
  { maximumFractionDigits: 3 });
// «1.234,5» e «1234.5» valgono uguale: si scrive all'italiana.
const leggi = (t) => {
  const s = String(t).trim().replace(/\s/g, "");
  if (!s) return 0;
  const n = Number(s.includes(",") ? s.replace(/\./g, "").replace(",", ".") : s);
  return Number.isFinite(n) ? n : null;
};

async function chiama(url, opzioni = {}) {
  const r = await fetch(url, { headers: { "Content-Type": "application/json" },
                               ...opzioni });
  if (!r.ok) throw new Error((await r.json()).detail || r.statusText);
  return r.json();
}

createApp({
  setup() {
    const progetti = ref([]);
    const aperto = ref(null);
    const vista = ref(null);
    const modifiche = ref({});      // codice -> {quantita?, prezzo?}
    const errore = ref("");
    const salvato = ref("");

    const inSospeso = computed(() => Object.keys(modifiche.value).length);
    const gruppi = computed(() => {
      const g = [];
      for (const r of vista.value?.righe ?? []) {
        if (!g.length || g.at(-1).categoria !== r.categoria)
          g.push({ categoria: r.categoria, righe: [] });
        g.at(-1).righe.push(r);
      }
      return g;
    });
    const elenco = () => Object.entries(modifiche.value)
      .map(([codice, m]) => ({ codice, ...m }));

    async function apri(nome) {
      if (inSospeso.value && !confirm("Ci sono modifiche non salvate. Le lascio?"))
        return;
      errore.value = ""; salvato.value = ""; modifiche.value = {};
      try {
        vista.value = await chiama(`/api/progetti/${encodeURIComponent(nome)}`);
        aperto.value = nome;
      } catch (e) { errore.value = e.message; }
    }

    async function cambia(riga, campo, testo) {
      const valore = leggi(testo);
      if (valore === null || valore < 0) {
        errore.value = `«${testo}» non è un numero`;
        return;
      }
      errore.value = "";
      modifiche.value[riga.codice] = { ...modifiche.value[riga.codice],
                                       [campo]: valore };
      try {
        vista.value = await chiama(
          `/api/progetti/${encodeURIComponent(aperto.value)}/prova`,
          { method: "POST", body: JSON.stringify({ modifiche: elenco() }) });
      } catch (e) { errore.value = e.message; }
    }

    async function salva() {
      try {
        const esito = await chiama(
          `/api/progetti/${encodeURIComponent(aperto.value)}`,
          { method: "PATCH", body: JSON.stringify({ modifiche: elenco() }) });
        vista.value = esito;
        modifiche.value = {};
        salvato.value = new Date(esito.salvato).toLocaleTimeString("it-IT");
        progetti.value = await chiama("/api/progetti");
      } catch (e) { errore.value = e.message; }
    }

    onMounted(async () => {
      try {
        progetti.value = await chiama("/api/progetti");
        const ultimo = progetti.value.find((p) => p.ultimo);
        if (ultimo) await apri(ultimo.nome);
      } catch (e) { errore.value = e.message; }
    });
    window.addEventListener("beforeunload", (ev) => {
      if (inSospeso.value) ev.preventDefault();
    });

    return { progetti, aperto, vista, gruppi, errore, salvato, inSospeso,
             apri, cambia, salva, euro, numero, COLORI };
  },
  template: `
  <header class="testata">
    <span class="marchio">CME <small>cantiere</small></span>
    <select :value="aperto" @change="apri($event.target.value)">
      <option v-for="p in progetti" :value="p.nome">{{ p.nome }}</option>
    </select>
    <button class="salva" :disabled="!inSospeso" @click="salva">
      Salva<span v-if="inSospeso"> ({{ inSospeso }})</span>
    </button>
    <span class="nota" v-if="salvato && !inSospeso">salvato alle {{ salvato }}</span>
  </header>
  <p class="errore" v-if="errore">{{ errore }}</p>
  <main v-if="vista">
    <p class="intestazione">
      {{ vista.progetto.committente }} · {{ vista.progetto.oggetto }}
    </p>
    <section v-for="g in gruppi" :key="g.categoria" class="categoria">
      <h2><span class="pastiglia" :style="{background: COLORI[g.categoria] || '#6E7377'}"></span>
        {{ g.categoria }}
        <span class="parziale">{{ euro(vista.totali.per_categoria[g.categoria]) }}</span></h2>
      <table>
        <thead><tr><th>Codice</th><th>Descrizione</th><th>U.M.</th>
          <th class="num">Quantità</th><th class="num">Prezzo</th>
          <th class="num">Importo</th></tr></thead>
        <tbody>
          <tr v-for="r in g.righe" :key="r.codice" :class="{zero: r.da_quantificare}">
            <td class="codice">{{ r.codice }}</td>
            <td>{{ r.descrizione }}<span v-if="r.a_mano" class="etichetta">a mano</span></td>
            <td>{{ r.um }}</td>
            <td class="num"><input :value="numero(r.quantita)"
                 @change="cambia(r, 'quantita', $event.target.value)"></td>
            <td class="num"><input :value="numero(r.prezzo)"
                 @change="cambia(r, 'prezzo', $event.target.value)"></td>
            <td class="num">{{ r.da_quantificare ? "da quantificare" : euro(r.importo) }}</td>
          </tr>
        </tbody>
      </table>
    </section>
    <table class="totali">
      <tr><th>Totale lavori</th><td>{{ euro(vista.totali.totale) }}</td></tr>
      <tr><th>IVA {{ numero(vista.totali.aliquota_iva) }}%</th><td>{{ euro(vista.totali.iva) }}</td></tr>
      <tr class="finale"><th>Totale IVA inclusa</th><td>{{ euro(vista.totali.totale_con_iva) }}</td></tr>
    </table>
  </main>
  <p class="vuoto" v-else-if="!progetti.length && !errore">
    Nessun progetto nell'archivio di prova.
  </p>`,
}).mount("#app");
