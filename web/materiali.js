// La sottoscheda «🛒 Materiali»: quello che compra il committente e
// l'impresa non fornisce. Elenco a parte, niente prezzi (quelli stanno nel
// registro delle spese, dove arrivano dalla fattura), e ne esce l'Allegato
// 1 da firmare con l'impresa.
import { computed, defineComponent, ref } from "vue";
import { CampioneVuoto, Griglia, Metrica, Scelta } from "./componenti.js";
import { gesto, scarica, stato } from "./rete.js";

const TUTTI = "Tutti gli stati";

export const SchedaMateriali = defineComponent({
  components: { Griglia, Metrica, CampioneVuoto, Scelta },
  setup() {
    const m = computed(() => stato.vista.materiali);
    const filtro = ref(TUTTI);
    const colonne = computed(() => [
      { chiave: "capitolo", titolo: "Capitolo", tipo: "scelta", larghezza: 190,
        aiuto: "Il capitolo dell'allegato: raggruppa le voci sul foglio che si firma con l'impresa.",
        opzioni: m.value.capitoli.map((c) => ({ valore: c.nome, testo: `${c.tessera} ${c.nome}`.trim() })) },
      { chiave: "descrizione", titolo: "Descrizione", tipo: "testo", larghezza: 260,
        aiuto: "Il nome della cosa, come lo scriveresti sull'allegato. È l'unica colonna che serve perché la riga esista." },
      { chiave: "quantita", titolo: "Q.tà", tipo: "numero", decimali: 0, minimo: 0, larghezza: 60,
        aiuto: "Quante ne servono. Si può lasciare vuota: sull'allegato una quantità non scritta resta non scritta." },
      { chiave: "fornitore", titolo: "Fornitore", tipo: "testo", larghezza: 130,
        aiuto: "Da chi lo compri. Non finisce sull'allegato: è roba tua." },
      { chiave: "link", titolo: "Link", tipo: "link", larghezza: 150,
        aiuto: "La pagina del negozio dove l'hai comprato. Incolla l'indirizzo: la cella diventa un collegamento." },
      { chiave: "stato", titolo: "Stato", tipo: "scelta", larghezza: 150,
        aiuto: "A che punto è l'acquisto. Il pagamento no: quello ha già il suo registro nelle spese a consuntivo.",
        opzioni: m.value.stati.map((s) => ({ valore: s.nome, testo: `${s.tessera} ${s.nome}`.trim() })) },
      { chiave: "note", titolo: "Note", tipo: "testo", larghezza: 200,
        aiuto: "Sull'allegato diventa la nota in fondo, richiamata da un asterisco accanto alla descrizione." },
    ]);
    // ⚠️ Il filtro nasconde righe, e le righe nascoste non devono sparire:
    // ogni riga vista porta con sé la sua posizione nell'elenco vero, e
    // alla fine torna esattamente da dove veniva.
    const indici = computed(() => {
      if (filtro.value === TUTTI) return null;
      return m.value.righe.map((r, i) => [r, i])
        .filter(([r]) => (r.stato || m.value.stato_predefinito) === filtro.value).map(([, i]) => i);
    });
    const vista = computed(() => (indici.value === null ? m.value.righe
      : indici.value.map((i) => m.value.righe[i])));
    function cambia(righe) {
      if (indici.value === null) { gesto("materiali", { righe }, { zitto: true }); return; }
      const tutte = m.value.righe.map((r) => ({ ...r }));
      indici.value.forEach((i, posizione) => { if (righe[posizione]) tutte[i] = righe[posizione]; });
      gesto("materiali", { righe: tutte }, { zitto: true });
    }
    const nascoste = computed(() => m.value.righe.length - (indici.value?.length ?? 0));
    const capitoli = computed(() => Object.entries(m.value.per_capitolo)
      .map(([c, n]) => `${c.charAt(0)}${c.slice(1).toLowerCase()} ${n}`));
    return { m, filtro, colonne, vista, cambia, indici, nascoste, capitoli, TUTTI, gesto, scarica,
             nuova: computed(() => ({ capitolo: m.value.capitolo_predefinito, stato: m.value.stato_predefinito })) };
  },
  template: `
  <div class="scheda-materiali">
    <p class="titolo-materiali">🛒 Materiali</p>
    <div class="colonne resta" style="margin-bottom:12px">
      <button class="bottone" style="flex:1" @click="gesto('riordina_materiali', {criterio: 'Capitolo'}, {zitto: true})"
              title="Raggruppa per capitolo, nell'ordine dell'allegato: bagno, porte e infissi, elettrico, muratura, pavimenti, riscaldamento.">⇅ Capitolo</button>
      <button class="bottone" style="flex:1" @click="gesto('riordina_materiali', {criterio: 'Stato'}, {zitto: true})"
              title="Prima quello da ordinare, poi l'ordinato, in fondo il consegnato: quello che ti resta da fare in cima.">⇅ Stato</button>
      <button class="bottone" style="flex:1" @click="gesto('riordina_materiali', {criterio: 'Fornitore'}, {zitto: true})"
              title="Raggruppa per negozio — comodo quando si va a comprare. Chi non ha ancora un fornitore va in fondo.">⇅ Fornitore</button>
      <Scelta style="flex:1.5" classe="casella" :valore="filtro" etichetta="Mostra"
              :opzioni="[TUTTI, ...m.stati.map(s => ({valore: s.nome, testo: (s.tessera + ' ' + s.nome).trim()}))]"
              title="Mostra solo le voci in un certo stato — per esempio solo quelle da ordinare. Mentre il filtro è attivo non si aggiungono né si cancellano righe: torna a «tutti gli stati» per farlo."
              @cambia="filtro = $event" />
      <span style="flex:1.9"></span>
    </div>
    <Griglia :colonne="colonne" :righe="vista" :dinamica="indici === null" obbligatoria="descrizione"
             :nuova="nuova" @cambia="cambia" />
    <p v-if="indici === null" class="didascalia grigio">Il <b>+</b> in alto a destra aggiunge una riga · la casella a
      sinistra della riga (compare passandoci sopra) la seleziona, e da lì si cancella o si copia · un blocco di celle copiato da Excel
      si incolla in una cella e si distribuisce sulle altre.</p>
    <p v-else class="didascalia"><span class="arancio">Filtro attivo: vedi <b>{{ indici.length }}</b> voci,
      <b>{{ nascoste }}</b> sono nascoste.</span> <span class="grigio">Le modifiche si salvano normalmente; per
      aggiungere o cancellare righe torna a «tutti gli stati».</span></p>

    <template v-if="m.righe.length">
      <div class="colonne resta" style="margin-bottom:12px">
        <Metrica style="flex:1" nome="Voci in elenco" :valore="m.righe.length"
                 :delta="Object.keys(m.per_capitolo).length + ' capitoli'" />
        <Metrica v-for="s in m.stati" :key="s.nome" style="flex:1" :nome="s.nome" :valore="m.per_stato[s.nome] || 0" />
      </div>
      <p class="didascalia grigio"><template v-for="(c, i) in capitoli" :key="c"><span v-if="i"> · </span>
        <b>{{ c.replace(/ \\d+$/, '') }}</b> {{ c.match(/\\d+$/)[0] }}</template></p>
    </template>
    <CampioneVuoto v-else titolo="Nessun materiale in elenco"
      testo="Scrivi nella riga vuota qui sopra che cosa compri tu — il gres, i sanitari, le porte. Da qui esce l'Allegato 1 da firmare con l'impresa." />

    <button class="bottone" :disabled="!m.righe.length" @click="scarica('allegato_materiali')"
            title="L'elenco per capitoli con la clausola e le due firme: è il foglio che si allega al computo e si sottoscrive con l'impresa. Fornitore, link e stato dell'ordine non ci sono — sono appunti tuoi.">
      🖨️ Allegato 1 (da firmare)</button>
  </div>`,
});
