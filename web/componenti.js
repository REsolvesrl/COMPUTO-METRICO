// I pezzi della pagina: uno per ogni componente di Streamlit che il
// programma vecchio usava, con lo stesso aspetto (stile.css) e gli stessi
// comportamenti che contavano — scritti una volta, usati da tutte le schede.
import { computed, defineComponent, h, nextTick, onBeforeUnmount, onMounted,
         ref, watch } from "vue";
import { euro, numeroDaIt, numeroIt } from "./formato.js";

// ---------------------------------------------------------------- metrica
// st.metric: l'etichetta piccola nomina, il numero grande è il protagonista.
export const Metrica = defineComponent({
  props: { nome: String, valore: [String, Number], delta: String,
           verso: { type: String, default: "spento" }, aiuto: String },
  template: `
  <div class="metrica" :title="aiuto">
    <div class="nome">{{ nome }}</div>
    <div class="valore">{{ valore }}</div>
    <div v-if="delta" class="delta" :class="{su: verso==='su', giu: verso==='giu'}">{{ delta }}</div>
  </div>`,
});

// ------------------------------------------------------- riquadro a scatto
// st.expander. Resta aperto da solo: nel vecchio la tendina si richiudeva
// a ogni giro, qui il giro non tocca la pagina.
export const Pannello = defineComponent({
  props: { titolo: String, aperto: Boolean },
  setup(props) {
    const aperto = ref(props.aperto);
    return { aperto };
  },
  template: `
  <details class="pannello" :open="aperto" @toggle="aperto = $event.target.open">
    <summary><slot name="titolo">{{ titolo }}</slot></summary>
    <div class="corpo" v-if="aperto"><slot /></div>
  </details>`,
});

// ------------------------------------------------------------------ avviso
export const Avviso = defineComponent({
  props: { tipo: { type: String, default: "info" } },
  template: `<div class="avviso" :class="tipo"><slot /></div>`,
});

// ------------------------------------------------------------ stato vuoto
// La cartella di campioni aperta, con la sua spiegazione (campione_vuoto).
export const CampioneVuoto = defineComponent({
  props: { titolo: String, testo: String,
           tinte: { type: Array, default: () => ["#C1502E", "#C9A96A", "#4E7A5E", "#6E7377"] } },
  template: `
  <div class="cme-vuoto">
    <div class="campioni"><i v-for="t in tinte" :style="{background: t}"></i></div>
    <h3>{{ titolo }}</h3><p>{{ testo }}<slot /></p>
  </div>`,
});

// ------------------------------------------------------------ interruttore
export const Interruttore = defineComponent({
  props: { acceso: Boolean, etichetta: String, aiuto: String },
  emits: ["cambia"],
  template: `
  <label class="interruttore" :title="aiuto">
    <input type="checkbox" :checked="acceso" @change="$emit('cambia', $event.target.checked)">
    <span class="binario"></span><span>{{ etichetta }}</span>
    <span v-if="aiuto" class="aiuto" :title="aiuto">?</span>
  </label>`,
});

export const Aiuto = defineComponent({
  props: { testo: String },
  template: `<span v-if="testo" class="aiuto" :title="testo">?</span>`,
});

// ------------------------------------------------------------ campo testo
// Il valore parte quando si esce dalla casella o si preme Invio, non a ogni
// tasto: è un gesto, come il campo di Streamlit.
export const CampoTesto = defineComponent({
  props: { valore: String, etichetta: String, segnaposto: String,
           aiuto: String, area: Boolean, tipo: { type: String, default: "text" },
           classe: String },
  emits: ["cambia"],
  setup(props, { emit }) {
    const testo = ref(props.valore ?? "");
    watch(() => props.valore, (v) => { testo.value = v ?? ""; });
    function manda() {
      if ((testo.value ?? "") !== (props.valore ?? "")) emit("cambia", testo.value);
    }
    return { testo, manda };
  },
  template: `
  <div class="campo">
    <label v-if="etichetta">{{ etichetta }}<span v-if="aiuto" class="aiuto" :title="aiuto">?</span></label>
    <textarea v-if="area" class="casella" :class="classe" v-model="testo" :placeholder="segnaposto"
              rows="1" @change="manda" :aria-label="etichetta"></textarea>
    <input v-else class="casella" :class="classe" :type="tipo" v-model="testo" :placeholder="segnaposto"
           @change="manda" @keydown.enter="$event.target.blur()" :aria-label="etichetta">
  </div>`,
});

// ------------------------------------------------------- campo numerico
// Gli importi si scrivono all'italiana, con le migliaia col punto: il
// campo numerico di Streamlit non lo sapeva fare (campo_numero_it). Quello
// che non è un numero NON si applica e NON si cancella: resta scritto, e
// il valore di prima continua a valere.
export const CampoNumero = defineComponent({
  props: { valore: Number, etichetta: String, decimali: { type: Number, default: 2 },
           aiuto: String, minimo: { type: Number, default: 0 }, massimo: Number,
           segnaposto: String, classe: String, disabilitato: Boolean },
  emits: ["cambia"],
  setup(props, { emit }) {
    const scritto = (v) => numeroIt(v ?? 0, props.decimali);
    const testo = ref(scritto(props.valore));
    const sbagliato = ref(false);
    watch(() => props.valore, (v) => { testo.value = scritto(v); sbagliato.value = false; });
    function manda() {
      const n = numeroDaIt(testo.value);
      if (n === null) { sbagliato.value = testo.value.trim() !== ""; return; }
      let v = Math.max(props.minimo, n);
      if (props.massimo !== undefined) v = Math.min(props.massimo, v);
      sbagliato.value = false;
      if (Math.abs(v - (props.valore ?? 0)) > 0.0005) emit("cambia", v);
      else testo.value = scritto(props.valore);
    }
    return { testo, manda, sbagliato };
  },
  template: `
  <div class="campo">
    <label v-if="etichetta">{{ etichetta }}<span v-if="aiuto" class="aiuto" :title="aiuto">?</span></label>
    <input class="casella" :class="classe" inputmode="decimal" v-model="testo" :placeholder="segnaposto"
           :disabled="disabilitato" @change="manda" @keydown.enter="$event.target.blur()"
           :aria-label="etichetta" :style="sbagliato ? {borderColor: 'var(--cotto)'} : null"
           :title="sbagliato ? 'Non è un numero: non l\\'ho applicato' : null">
  </div>`,
});

// Il campo con le frecce: dove si contano pezzi (st.number_input a passi).
export const CampoPassi = defineComponent({
  props: { valore: Number, etichetta: String, passo: { type: Number, default: 1 },
           minimo: { type: Number, default: 0 }, massimo: Number,
           decimali: { type: Number, default: 0 }, aiuto: String, classe: String },
  emits: ["cambia"],
  setup(props, { emit }) {
    const testo = ref(Number(props.valore ?? 0).toFixed(props.decimali));
    watch(() => props.valore, (v) => { testo.value = Number(v ?? 0).toFixed(props.decimali); });
    function manda() {
      const n = numeroDaIt(testo.value);
      if (n === null) { testo.value = Number(props.valore ?? 0).toFixed(props.decimali); return; }
      let v = Math.max(props.minimo, n);
      if (props.massimo !== undefined) v = Math.min(props.massimo, v);
      if (Math.abs(v - (props.valore ?? 0)) > 0.0005) emit("cambia", v);
    }
    return { testo, manda };
  },
  template: `
  <div class="campo">
    <label v-if="etichetta">{{ etichetta }}<span v-if="aiuto" class="aiuto" :title="aiuto">?</span></label>
    <input class="casella" :class="classe" type="number" :step="passo" :min="minimo" :max="massimo"
           v-model="testo" @change="manda" :aria-label="etichetta">
  </div>`,
});

export const Tendina = defineComponent({
  props: { valore: [String, Number], opzioni: Array, etichetta: String, aiuto: String,
           classe: String, disabilitato: Boolean },
  emits: ["cambia"],
  template: `
  <div class="campo">
    <label v-if="etichetta">{{ etichetta }}<span v-if="aiuto" class="aiuto" :title="aiuto">?</span></label>
    <select class="casella" :class="classe" :value="valore" :disabled="disabilitato"
            @change="$emit('cambia', $event.target.value)" :aria-label="etichetta">
      <option v-for="o in opzioni" :key="o.valore ?? o" :value="o.valore ?? o">{{ o.testo ?? o }}</option>
    </select>
  </div>`,
});

// -------------------------------------------------------------- popover
// Il pannellino che si apre da un bottone e si chiude cliccando fuori.
export const Popover = defineComponent({
  props: { classeBottone: { type: String, default: "bottone" }, aiuto: String },
  setup() {
    const aperto = ref(false);
    const radice = ref(null);
    function fuori(ev) {
      if (aperto.value && radice.value && !radice.value.contains(ev.target)) aperto.value = false;
    }
    onMounted(() => document.addEventListener("mousedown", fuori));
    onBeforeUnmount(() => document.removeEventListener("mousedown", fuori));
    return { aperto, radice, chiudi: () => { aperto.value = false; } };
  },
  template: `
  <div class="popover-ancora" ref="radice">
    <button type="button" :class="classeBottone" :title="aiuto" @click="aperto = !aperto"
            :aria-expanded="aperto"><slot name="bottone" /></button>
    <div v-if="aperto" class="popover" @keydown.esc="aperto = false"><slot :chiudi="chiudi" /></div>
  </div>`,
});

// -------------------------------------------------------------- grafico
// Le figure le costruisce il motore con le stesse funzioni del vecchio
// (grafici.py); qui Plotly le disegna e basta.
export const Grafico = defineComponent({
  props: { figura: Object },
  setup(props) {
    const el = ref(null);
    function disegna() {
      if (!el.value || !props.figura || !window.Plotly) return;
      window.Plotly.react(el.value, props.figura.data, props.figura.layout,
                          { displayModeBar: false, responsive: true });
    }
    onMounted(disegna);
    watch(() => props.figura, () => nextTick(disegna));
    onBeforeUnmount(() => { if (el.value && window.Plotly) window.Plotly.purge(el.value); });
    return { el };
  },
  template: `<div class="grafico" ref="el"></div>`,
});

// ------------------------------------------------- tabella modificabile
// Al posto di st.data_editor. Colonne: {chiave, titolo, tipo, opzioni,
// larghezza, sola_lettura, aiuto, decimali, formato}. tipo: testo, numero,
// scelta, spunta, link.
//
// ⚠️ Una riga nuova resta QUI finché non ha la sua colonna obbligatoria
// (la descrizione dei materiali, l'importo delle spese): è quello che il
// motore considera una riga, e mandargli una riga vuota vorrebbe dire
// vederla sparire al giro dopo. Il vecchio faceva lo stesso, dentro il suo
// componente.
//
// Copia e incolla: le righe spuntate si copiano come testo a tabulazioni
// (quello che Excel incolla), e un blocco incollato in una cella si
// distribuisce sulle celle a destra e in basso, come in Excel.
export const Griglia = defineComponent({
  props: { colonne: Array, righe: Array, dinamica: Boolean, obbligatoria: String,
           nuova: Object, altezzaMax: String },
  emits: ["cambia"],
  setup(props, { emit }) {
    const locali = ref([]);
    const scelte = ref(new Set());
    const clona = (r) => JSON.parse(JSON.stringify(r));
    function riallinea() {
      const bozze = props.obbligatoria
        ? locali.value.filter((r) => r.__bozza && !String(r[props.obbligatoria] ?? "").trim()
            && !(typeof r[props.obbligatoria] === "number"))
        : [];
      locali.value = [...(props.righe || []).map(clona), ...bozze];
    }
    watch(() => props.righe, riallinea, { immediate: true, deep: true });

    function vere() {
      return locali.value.map((r) => {
        const c = { ...r }; delete c.__bozza; return c;
      }).filter((r) => {
        if (!props.obbligatoria) return true;
        const v = r[props.obbligatoria];
        return typeof v === "number" ? true : String(v ?? "").trim() !== "";
      });
    }
    function manda() { emit("cambia", vere()); }

    function testoCella(col, v) {
      if (v === null || v === undefined || v === "") return "";
      if (col.tipo === "numero") {
        if (col.formato === "euro") return euro(v);
        return numeroIt(v, col.decimali ?? 2);
      }
      return v;
    }
    function scrivi(riga, col, grezzo) {
      let v = grezzo;
      if (col.tipo === "numero") {
        if (String(grezzo).trim() === "") v = null;
        else {
          v = numeroDaIt(grezzo);
          if (v === null) return;             // non è un numero: non si applica
          if (col.minimo !== undefined) v = Math.max(col.minimo, v);
          if (col.massimo !== undefined) v = Math.min(col.massimo, v);
        }
      }
      if (riga[col.chiave] === v) return;
      riga[col.chiave] = v;
      manda();
    }
    function aggiungi() {
      const r = { ...(props.nuova || {}), __bozza: true };
      for (const c of props.colonne) if (!(c.chiave in r)) r[c.chiave] = c.tipo === "spunta" ? false : null;
      locali.value.push(r);
    }
    function togliScelte() {
      locali.value = locali.value.filter((_, i) => !scelte.value.has(i));
      scelte.value = new Set();
      manda();
    }
    function scegli(i, si) {
      const s = new Set(scelte.value);
      if (si) s.add(i); else s.delete(i);
      scelte.value = s;
    }
    async function copia() {
      const modificabili = props.colonne;
      const testo = locali.value.filter((_, i) => scelte.value.has(i))
        .map((r) => modificabili.map((c) => {
          const v = r[c.chiave];
          if (c.tipo === "numero") return v === null || v === undefined ? "" : numeroIt(v, c.decimali ?? 2);
          return v ?? "";
        }).join("\t")).join("\n");
      try { await navigator.clipboard.writeText(testo); } catch (e) { /* niente */ }
    }
    function incolla(ev, i, j) {
      const testo = ev.clipboardData?.getData("text") ?? "";
      if (!testo.includes("\t") && !testo.includes("\n")) return;   // incollo normale
      ev.preventDefault();
      const righe = testo.replace(/\r/g, "").replace(/\n$/, "").split("\n").map((r) => r.split("\t"));
      righe.forEach((celle, di) => {
        while (i + di >= locali.value.length) {
          if (!props.dinamica) return;
          aggiungi();
        }
        const riga = locali.value[i + di];
        celle.forEach((grezzo, dj) => {
          const col = props.colonne[j + dj];
          if (!col || col.sola_lettura) return;
          let v = grezzo;
          if (col.tipo === "numero") v = grezzo.trim() === "" ? null : numeroDaIt(grezzo);
          else if (col.tipo === "spunta") v = /^(1|s[iì]|vero|true|x)$/i.test(grezzo.trim());
          else if (col.tipo === "scelta") {
            const trovata = (col.opzioni || []).find((o) => (o.valore ?? o).toString().toLowerCase()
              === grezzo.trim().toLowerCase() || (o.testo ?? o).toString().toLowerCase().includes(grezzo.trim().toLowerCase()));
            v = trovata ? (trovata.valore ?? trovata) : riga[col.chiave];
          }
          riga[col.chiave] = v;
        });
      });
      manda();
    }
    const ancheBozze = computed(() => locali.value);
    return { locali: ancheBozze, scelte, testoCella, scrivi, aggiungi, togliScelte,
             scegli, copia, incolla };
  },
  template: `
  <div class="griglia-scatola">
    <div class="griglia-barra">
      <button v-if="dinamica" type="button" @click="aggiungi" title="Aggiungi una riga in fondo">＋ riga</button>
      <button type="button" :disabled="!scelte.size" @click="copia"
              title="Copia le righe spuntate: si incollano anche in Excel">Copia</button>
      <button v-if="dinamica" type="button" :disabled="!scelte.size" @click="togliScelte"
              title="Cancella le righe spuntate">Cancella</button>
    </div>
    <div class="griglia-scorre" :style="altezzaMax ? {maxHeight: altezzaMax, overflowY: 'auto'} : null">
    <table class="griglia">
      <thead><tr>
        <th class="scelta-riga"></th>
        <th v-for="c in colonne" :key="c.chiave" :class="{num: c.tipo==='numero'}"
            :style="c.larghezza ? {minWidth: c.larghezza + 'px'} : null" :title="c.aiuto">{{ c.titolo }}</th>
      </tr></thead>
      <tbody>
        <tr v-for="(r, i) in locali" :key="i" :class="{selezionata: scelte.has(i), nuova: r.__bozza}">
          <td class="scelta-riga"><input type="checkbox" :checked="scelte.has(i)"
              @change="scegli(i, $event.target.checked)" aria-label="Seleziona la riga"></td>
          <td v-for="(c, j) in colonne" :key="c.chiave" :class="{num: c.tipo==='numero', 'sola-lettura': c.sola_lettura}">
            <template v-if="c.sola_lettura">{{ testoCella(c, r[c.chiave]) }}</template>
            <input v-else-if="c.tipo==='spunta'" type="checkbox" :checked="!!r[c.chiave]"
                   @change="scrivi(r, c, $event.target.checked)" :aria-label="c.titolo">
            <select v-else-if="c.tipo==='scelta'" class="cella" :value="r[c.chiave] ?? ''"
                    @change="scrivi(r, c, $event.target.value || null)" :aria-label="c.titolo">
              <option value=""></option>
              <option v-for="o in c.opzioni" :key="o.valore ?? o" :value="o.valore ?? o">{{ o.testo ?? o }}</option>
            </select>
            <div v-else-if="c.tipo==='link'" style="display:flex;align-items:center">
              <input class="cella" :value="r[c.chiave] ?? ''" @change="scrivi(r, c, $event.target.value)"
                     @paste="incolla($event, i, j)" :aria-label="c.titolo">
              <a v-if="r[c.chiave]" :href="r[c.chiave]" target="_blank" rel="noopener">apri ↗</a>
            </div>
            <input v-else class="cella" :class="{num: c.tipo==='numero'}" :value="testoCella(c, r[c.chiave])"
                   :style="c.tipo==='numero' ? {textAlign: 'right'} : null"
                   @change="scrivi(r, c, $event.target.value)" @keydown.enter="$event.target.blur()"
                   @paste="incolla($event, i, j)" :aria-label="c.titolo" :title="r[c.chiave] ?? ''">
          </td>
        </tr>
      </tbody>
    </table>
    </div>
  </div>`,
});

// una tabella di sola lettura (st.dataframe)
export const Tabella = defineComponent({
  props: { colonne: Array, righe: Array },
  template: `
  <div class="tabella-scorre"><table class="tabella">
    <thead><tr><th v-for="c in colonne" :key="c.chiave" :class="{num: c.num}">{{ c.titolo }}</th></tr></thead>
    <tbody><tr v-for="(r, i) in righe" :key="i" :style="r.__stile">
      <td v-for="c in colonne" :key="c.chiave" :class="{num: c.num}">{{ r[c.chiave] }}</td>
    </tr></tbody>
  </table></div>`,
});

export { h };
