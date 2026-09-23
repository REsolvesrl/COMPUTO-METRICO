// I pezzi della pagina: uno per ogni componente di Streamlit che il
// programma vecchio usava, con lo stesso aspetto (stile.css) e gli stessi
// comportamenti che contavano — scritti una volta, usati da tutte le schede.
import { Transition, computed, defineComponent, h, nextTick, onBeforeUnmount,
         onMounted, ref, watch } from "vue";
import { euro, numeroDaIt, numeroIt } from "./formato.js";

// ---------------------------------------------------------------- metrica
// st.metric: l'etichetta piccola nomina, il numero grande è il protagonista.
// Sotto, la pastiglia della variazione con la sua freccia. ⚠️ La freccia
// segue la regola di Streamlit: in giù solo se il testo comincia col segno
// meno ASCII; le detrazioni del vecchio si scrivono col «−» tipografico, e
// Streamlit le mostrava con la freccia in su — così resta.
export const Metrica = defineComponent({
  props: { nome: String, valore: [String, Number], delta: String,
           verso: { type: String, default: "spento" }, aiuto: String },
  setup(props) {
    const freccia = computed(() => (String(props.delta || "").trim().startsWith("-") ? "↓" : "↑"));
    return { freccia };
  },
  template: `
  <div class="metrica" :title="aiuto">
    <div class="nome">{{ nome }}</div>
    <div class="valore">{{ valore }}</div>
    <div v-if="delta" class="delta" :class="{su: verso==='su', giu: verso==='giu'}">
      <span class="freccia" aria-hidden="true">{{ freccia }}</span>{{ delta }}</div>
  </div>`,
});

// ---------------------------------------------------------- scorrimento
// Le tendine si aprono e si chiudono scorrendo, non di scatto: si misura
// l'altezza vera del contenuto e la si raggiunge con una transizione (il
// ritmo sta in stile.css, .scorre-attivo). Chi ha chiesto al sistema meno
// movimento la vede aprirsi e basta.
function scorri(el, da, a, fatto) {
  el.classList.add("scorre-attivo");
  el.style.height = da;
  el.style.opacity = a === "0px" ? "1" : "0";
  // Leggere offsetHeight obbliga il browser a fissare la misura di
  // partenza: da lì la nuova altezza è una transizione, non uno scatto.
  // (Non si aspetta il fotogramma dopo: a finestra coperta il browser non
  // ne disegna, e la tendina restava chiusa fino allo scadere del tempo.)
  // eslint-disable-next-line no-unused-expressions
  el.offsetHeight;
  el.style.height = a === "auto" ? `${el.scrollHeight}px` : a;
  el.style.opacity = a === "0px" ? "0" : "1";
  let chiuso = false;
  const fine = () => {
    if (chiuso) return;
    chiuso = true;
    el.classList.remove("scorre-attivo");
    el.style.height = "";
    el.style.opacity = "";
    fatto();
  };
  el.addEventListener("transitionend", (e) => { if (e.target === el && e.propertyName === "height") fine(); });
  setTimeout(fine, 400);
}
export const Scorre = defineComponent({
  setup(_, { slots }) {
    return () => h(Transition, {
      css: false,
      onEnter: (el, fatto) => scorri(el, "0px", "auto", fatto),
      onLeave: (el, fatto) => scorri(el, `${el.scrollHeight}px`, "0px", fatto),
    }, slots.default);
  },
});

// ------------------------------------------------------- riquadro a scatto
// st.expander. Resta aperto da solo: nel vecchio la tendina si richiudeva
// a ogni giro, qui il giro non tocca la pagina.
export const Pannello = defineComponent({
  components: { Scorre },
  props: { titolo: String, aperto: Boolean },
  setup(props) {
    const aperto = ref(props.aperto);
    return { aperto };
  },
  template: `
  <div class="pannello" :class="{aperto}">
    <button type="button" class="pannello-testa" :aria-expanded="aperto" @click="aperto = !aperto">
      <span class="segno" aria-hidden="true">›</span><slot name="titolo">{{ titolo }}</slot></button>
    <Scorre><div v-if="aperto" class="corpo-esterno"><div class="corpo"><slot /></div></div></Scorre>
  </div>`,
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
    // Le colonne larghe quanto il loro contenuto, come l'«autosize» della
    // tabella di Streamlit: si misura il testo più lungo (intestazione
    // compresa) e l'ultima colonna si prende quello che resta.
    const misuratore = document.createElement("canvas").getContext("2d");
    const larghezze = computed(() => {
      misuratore.font = '14px "Source Sans", "Segoe UI", sans-serif';
      return props.colonne.map((c) => {
        let massimo = misuratore.measureText(c.titolo).width + 34;
        for (const r of locali.value) {
          let t = testoCella(c, r[c.chiave]);
          if (c.tipo === "scelta") {
            const o = (c.opzioni || []).find((x) => (x.valore ?? x) === r[c.chiave]);
            t = o ? (o.testo ?? o) : t;
          }
          if (c.tipo === "spunta") t = "✓";
          massimo = Math.max(massimo, misuratore.measureText(String(t ?? "")).width + 20);
        }
        return Math.round(Math.min(c.tipo === "link" ? 180 : 420, Math.max(c.minimo_px || 56, massimo)));
      });
    });
    const schermoIntero = ref(false);
    function scaricaCsv() {
      const q = (v) => `"${String(v ?? "").replace(/"/g, '""')}"`;
      const righe = [props.colonne.map((c) => q(c.titolo)).join(";")].concat(
        locali.value.map((r) => props.colonne.map((c) => {
          const v = r[c.chiave];
          if (c.tipo === "numero") return v === null || v === undefined ? "" : String(v).replace(".", ",");
          return q(v);
        }).join(";")));
      const a = document.createElement("a");
      a.href = URL.createObjectURL(new Blob(["﻿" + righe.join("\n")], { type: "text/csv" }));
      a.download = "tabella.csv";
      a.click();
      URL.revokeObjectURL(a.href);
    }
    const ancheBozze = computed(() => locali.value);
    return { locali: ancheBozze, scelte, testoCella, scrivi, aggiungi, togliScelte,
             scegli, copia, incolla, larghezze, schermoIntero, scaricaCsv };
  },
  template: `
  <div class="griglia-scatola" :class="{'a-tutto-schermo': schermoIntero}">
    <div class="griglia-barra">
      <div class="attrezzi">
        <button v-if="dinamica" type="button" @click="aggiungi" title="Aggiungi una riga in fondo" aria-label="Aggiungi riga">
          <svg viewBox="0 0 24 24"><path d="M11 5h2v6h6v2h-6v6h-2v-6H5v-2h6z"/></svg></button>
        <button type="button" :disabled="!scelte.size" @click="copia" aria-label="Copia righe"
                title="Copia le righe spuntate: si incollano anche in Excel">
          <svg viewBox="0 0 24 24"><path d="M16 1H4a2 2 0 0 0-2 2v14h2V3h12V1zm3 4H8a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h11a2 2 0 0 0 2-2V7a2 2 0 0 0-2-2zm0 16H8V7h11v14z"/></svg></button>
        <button v-if="dinamica" type="button" :disabled="!scelte.size" @click="togliScelte" aria-label="Cancella righe"
                title="Cancella le righe spuntate">
          <svg viewBox="0 0 24 24"><path d="M6 19a2 2 0 0 0 2 2h8a2 2 0 0 0 2-2V7H6v12zM19 4h-3.5l-1-1h-5l-1 1H5v2h14V4z"/></svg></button>
        <button type="button" @click="scaricaCsv" title="Scarica la tabella come CSV" aria-label="Scarica CSV">
          <svg viewBox="0 0 24 24"><path d="M5 20h14v-2H5v2zM19 9h-4V3H9v6H5l7 7 7-7z"/></svg></button>
        <button type="button" @click="schermoIntero = !schermoIntero"
                :title="schermoIntero ? 'Esci dallo schermo intero' : 'Schermo intero'" aria-label="Schermo intero">
          <svg viewBox="0 0 24 24"><path d="M7 14H5v5h5v-2H7v-3zm-2-4h2V7h3V5H5v5zm12 7h-3v2h5v-5h-2v3zM14 5v2h3v3h2V5h-5z"/></svg></button>
      </div>
    </div>
    <div class="griglia-scorre" :style="altezzaMax ? {maxHeight: altezzaMax, overflowY: 'auto'} : null">
    <table class="griglia">
      <colgroup><col style="width:32px"><col v-for="(c, j) in colonne" :key="c.chiave"
        :style="j < colonne.length - 1 ? {width: larghezze[j] + 'px'} : {minWidth: larghezze[j] + 'px'}"></colgroup>
      <thead><tr>
        <th class="scelta-riga"></th>
        <th v-for="c in colonne" :key="c.chiave" :class="{num: c.tipo==='numero'}" :title="c.aiuto">
          <span class="icona-colonna" aria-hidden="true">{{ {testo: '≡', numero: '#', scelta: '▾', spunta: '☑', link: '🔗'}[c.tipo] }}</span>{{ c.titolo }}</th>
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
