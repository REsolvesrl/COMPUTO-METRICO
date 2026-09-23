// La pagina di CME: la testata col cartiglio e il tasto Salva, le tre
// linguette e le loro sottolinguette — le stesse del programma vecchio, con
// gli stessi nomi e nello stesso ordine:
//
//   📝 Computo metrico       → 📝 Il computo · 🛒 Materiali
//   📐 Misura da planimetria
//   📊 Business plan         → 🏦 Studio di fattibilità · 🧾 Spese a
//                              consuntivo · 🏗️ Cantiere — contratto e SAL ·
//                              🏷️ MCA — prezzo di vendita
import { computed, createApp, defineComponent, onMounted, ref, watch } from "vue";
import { Avviso, CampioneVuoto } from "./componenti.js";
import { SchedaComputo } from "./computo.js";
import { SchedaMateriali } from "./materiali.js";
import { caricaVista, gesto, stato } from "./rete.js";

const SCHEDE = [
  { id: "computo", nome: "📝 Computo metrico",
    sotto: [{ id: "il_computo", nome: "📝 Il computo" }, { id: "materiali", nome: "🛒 Materiali" }] },
  { id: "planimetria", nome: "📐 Misura da planimetria", sotto: [] },
  { id: "bp", nome: "📊 Business plan",
    sotto: [{ id: "fattibilita", nome: "🏦 Studio di fattibilità" },
            { id: "spese", nome: "🧾 Spese a consuntivo" },
            { id: "cantiere", nome: "🏗️ Cantiere — contratto e SAL" },
            { id: "mca", nome: "🏷️ MCA — prezzo di vendita" }] },
];

// La linguetta aperta si ricorda nel browser: è una comodità di chi guarda,
// non un dato del progetto. Se il browser non lascia scrivere, pazienza.
function ricorda(chiave, predefinito) {
  let iniziale = predefinito;
  try { iniziale = localStorage.getItem(chiave) || predefinito; } catch (e) { /* niente */ }
  const r = ref(iniziale);
  watch(r, (v) => { try { localStorage.setItem(chiave, v); } catch (e) { /* niente */ } });
  return r;
}

// Le schede che non sono ancora passate di qua: il vecchio le ha tutte, e
// finché non arrivano si dice chiaramente dove trovarle.
const InCostruzione = defineComponent({
  components: { CampioneVuoto },
  props: { nome: String },
  template: `
  <div class="in-costruzione">
    <CampioneVuoto :titolo="nome + ' — in arrivo'"
      testo="Questa scheda non è ancora passata nella versione nuova. Il lavoro vero si fa col programma di sempre (Avvia CME.bat): lì c'è tutta, e legge gli stessi progetti." />
  </div>`,
});

const Testata = defineComponent({
  setup() {
    const t = computed(() => stato.vista.testata);
    return { t, gesto };
  },
  template: `
  <div class="testata-riga">
    <div class="cme-testata">
      <h1><span class="sigla">CME</span> Computo Metrico Estimativo</h1>
      <template v-if="t.nome"><span class="cme-etichetta">progetto</span><span class="progetto">{{ t.nome }}</span></template>
      <template v-else-if="!t.vuoto"><span class="cme-etichetta">progetto</span><span class="progetto">senza nome</span></template>
      <span v-else class="cme-etichetta">nessun progetto aperto</span>
      <span class="versione">{{ t.versione }}</span>
      <span v-if="t.stato === 'mai'" class="salvataggio sospeso">mai salvato in questa sessione</span>
      <span v-else-if="t.stato === 'modificato'" class="salvataggio sospeso">modifiche non salvate</span>
      <span v-else-if="t.stato === 'pari'" class="salvataggio pari">salvato alle {{ t.salvato_alle }}</span>
    </div>
    <button class="bottone primario salva-testata" @click="gesto('salva')"
            :title="'Salva subito in archivio come «' + t.nome_archivio + '», sovrascrivendo la versione precedente. Cartella: ' + t.cartella">
      💾 Salva</button>
  </div>`,
});

const App = defineComponent({
  components: { Testata, SchedaComputo, SchedaMateriali, InCostruzione, Avviso },
  setup() {
    const scheda = ricorda("cme_scheda", "computo");
    const sotto = {
      computo: ricorda("cme_sotto_computo", "il_computo"),
      bp: ricorda("cme_sotto_bp", "fattibilita"),
    };
    const aperta = computed(() => SCHEDE.find((s) => s.id === scheda.value) || SCHEDE[0]);
    const nomeSotto = computed(() => {
      const s = aperta.value.sotto.find((x) => x.id === sotto[aperta.value.id]?.value);
      return s ? s.nome : aperta.value.nome;
    });
    onMounted(caricaVista);
    return { stato, SCHEDE, scheda, sotto, aperta, nomeSotto };
  },
  template: `
  <template v-if="stato.vista">
    <Testata />
    <Avviso v-if="stato.vista.piante_scartate.length" tipo="attenzione">⚠️ <b>{{ stato.vista.piante_scartate.length }}
      {{ stato.vista.piante_scartate.length === 1 ? 'planimetria' : 'planimetrie' }} non si sono potute rileggere</b>
      dal file del progetto: {{ stato.vista.piante_scartate.map(n => '«' + n + '»').join(', ') }}. Tutto il resto —
      computo, spese, business plan e le altre planimetrie — è stato caricato regolarmente. Ricarica il disegno
      mancante dalla scheda <b>Misura da planimetria</b>.</Avviso>
    <nav class="linguette" role="tablist">
      <button v-for="s in SCHEDE" :key="s.id" class="linguetta" :class="{aperta: s.id === scheda}"
              role="tab" :aria-selected="s.id === scheda" @click="scheda = s.id">{{ s.nome }}</button>
    </nav>
    <nav v-if="aperta.sotto.length" class="linguette" role="tablist">
      <button v-for="s in aperta.sotto" :key="s.id" class="linguetta"
              :class="{aperta: s.id === sotto[aperta.id].value}" role="tab"
              :aria-selected="s.id === sotto[aperta.id].value" @click="sotto[aperta.id].value = s.id">{{ s.nome }}</button>
    </nav>
    <SchedaComputo v-if="scheda === 'computo' && sotto.computo.value === 'il_computo'" />
    <SchedaMateriali v-else-if="scheda === 'computo'" />
    <InCostruzione v-else :nome="nomeSotto" />
  </template>
  <Avviso v-else-if="stato.errore" tipo="errore">{{ stato.errore }}</Avviso>
  <p v-else class="grigio">Apro il banco…</p>
  <div class="tostapane" aria-live="polite">
    <div v-for="f in stato.fette" :key="f.id" class="fetta" :class="f.tipo">{{ f.testo }}</div>
  </div>`,
});

createApp(App).mount("#app");
