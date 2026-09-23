// La scheda «📐 Misura da planimetria».
//
// La tela è il visualizzatore del programma vecchio (cme_viewer/frontend),
// servito così com'è in /tela: parla il protocollo dei componenti di
// Streamlit — un messaggio «render» con gli argomenti, e indietro
// «setComponentValue» a ogni gesto e «setFrameHeight» quando cambia
// altezza — e questa pagina glielo parla uguale. Zoom, strumenti,
// scorciatoie e tutte le correzioni fatte in questi mesi restano identici.
import { computed, defineComponent, nextTick, onBeforeUnmount, onMounted, ref,
         watch } from "vue";
import { Avviso, CampioneVuoto, CampoNumero, CampoPassi, CampoTesto, Interruttore,
         Metrica, Pannello, Tabella, Tendina } from "./componenti.js";
import { euro, numeroIt } from "./formato.js";
import { gesto, scarica, stato, toast } from "./rete.js";

// --------------------------------------------------------------- la tela
const Tela = defineComponent({
  props: { argomenti: Object },
  setup(props) {
    const cornice = ref(null);
    const altezza = ref(360);
    let pronta = false;

    function manda() {
      const f = cornice.value;
      if (!f || !f.contentWindow || !pronta || !props.argomenti) return;
      // una copia pulita: il messaggio attraversa la finestra
      const args = JSON.parse(JSON.stringify(props.argomenti));
      f.contentWindow.postMessage({ type: "streamlit:render", args,
                                    disabled: false }, "*");
    }
    function ascolta(ev) {
      if (!cornice.value || ev.source !== cornice.value.contentWindow) return;
      const m = ev.data || {};
      if (!m.isStreamlitMessage) return;
      if (m.type === "streamlit:componentReady") { pronta = true; manda(); }
      else if (m.type === "streamlit:setFrameHeight") altezza.value = m.height;
      else if (m.type === "streamlit:setComponentValue" && m.value) {
        gesto("evento_tela", { evento: m.value }, { zitto: true });
      }
    }
    onMounted(() => window.addEventListener("message", ascolta));
    onBeforeUnmount(() => window.removeEventListener("message", ascolta));
    watch(() => props.argomenti, () => nextTick(manda), { deep: true });
    return { cornice, altezza };
  },
  template: `<iframe ref="cornice" src="/tela/index.html" class="tela-cornice"
                     :style="{height: altezza + 'px'}" title="Planimetria"></iframe>`,
});

// il cursore (st.slider)
const Cursore = defineComponent({
  props: { valore: Number, minimo: Number, massimo: Number, passo: Number,
           etichetta: String, aiuto: String, decimali: { type: Number, default: 0 } },
  emits: ["cambia"],
  setup(props) {
    const v = ref(props.valore);
    watch(() => props.valore, (x) => { v.value = x; });
    return { v, numeroIt };
  },
  template: `
  <div class="campo">
    <label>{{ etichetta }}<span v-if="aiuto" class="aiuto" :title="aiuto">?</span></label>
    <div class="cursore">
      <input type="range" :min="minimo" :max="massimo" :step="passo" v-model.number="v"
             @change="$emit('cambia', v)" :aria-label="etichetta">
      <b>{{ numeroIt(v, decimali) }}</b>
    </div>
  </div>`,
});

// ------------------------------------------------------------ la scheda
export const SchedaPlanimetria = defineComponent({
  components: { Tela, Cursore, Avviso, CampioneVuoto, CampoNumero, CampoPassi, CampoTesto,
                Interruttore, Metrica, Pannello, Tabella, Tendina },
  setup() {
    const p = computed(() => stato.vista.planimetria);
    const caricamento = ref(null);
    const metriScala = ref(0);
    const forza = ref(1);
    const orizzontale = ref(false);

    async function carica(ev) {
      const file = ev.target.files[0];
      if (!file) return;
      const dati = new FormData();
      dati.append("file", file);
      stato.occupato = true;
      try {
        const r = await (await fetch("/api/planimetrie", { method: "POST", body: dati })).json();
        if (r.vista) stato.vista = r.vista;
        if (r.esito) toast(r.esito.testo, r.esito.tipo);
      } catch (e) { toast(`Non riesco a leggere questo file: ${e.message}`, "errore"); }
      finally { stato.occupato = false; ev.target.value = ""; }
    }
    const g = (nome, argomenti = {}, zitto = true) => gesto(nome, argomenti, { zitto });
    const opzioniCat = computed(() => p.value.categorie.map((c) => ({
      valore: c.nome, testo: `${c.nome} — ${numeroIt(c.percento, 0)}%` })));
    const nomeAttiva = computed(() => (p.value.attiva === null ? "" : p.value.piante[p.value.attiva].nome));
    async function impostaScala() {
      await g("imposta_scala", { metri: metriScala.value }, false);
    }
    const colonneSup = ["Pianta", "Categoria", "Zone", "m² reali", "%", "m² commerciali", "Serve a"]
      .map((c) => ({ chiave: c, titolo: c, num: ["Zone", "m² reali", "%", "m² commerciali"].includes(c) }));
    const colonneConto = computed(() => (p.value.conto && p.value.conto.censimento
      ? Object.keys(p.value.conto.censimento[0]).map((c) => ({ chiave: c, titolo: c, num: c.includes("(") }))
      : []));
    const stileTotale = (r) => (r.Locale === "TOTALE" ? { fontWeight: 700 } : null);
    const d = computed(() => p.value.dal_disegno);
    const muri = computed(() => p.value.muri);
    const f = computed(() => p.value.finiture);
    function finitura(campo, valore) { g("finitura", { campo, valore }); }
    function stampaPdf() { scarica(orizzontale.value ? "pdf_planimetrie_orizzontale" : "pdf_planimetrie"); }
    return { p, caricamento, carica, g, opzioniCat, nomeAttiva, metriScala, impostaScala, forza,
             orizzontale, colonneSup, colonneConto, stileTotale, d, muri, f, finitura, stampaPdf,
             scarica, numeroIt, euro };
  },
  template: `
  <div>
    <template v-if="!p.piante.length">
      <CampioneVuoto titolo="Il banco è sgombro"
        testo="Porta qui la planimetria — una foto, una scansione o il PDF del progetto — e da lì si misurano le superfici, si contano i muri e le quantità passano nel computo. Un PDF di più pagine diventa una planimetria per foglio: piano terra, piano primo, e così via." />
      <div class="campo"><label>Carica una planimetria (PNG, JPG o PDF)</label>
        <input type="file" accept=".png,.jpg,.jpeg,.pdf" @change="carica"></div>
    </template>
    <template v-else>
    <div class="colonne" style="gap:2rem">
      <!-- le planimetrie del progetto -->
      <div class="col-piante" style="flex:0.55">
        <p><b>Planimetrie</b></p>
        <div v-for="pi in p.piante" :key="pi.indice + pi.impronta" style="margin-bottom:12px">
          <div class="colonne centro resta" style="gap:6px;margin-bottom:6px">
            <button class="bottone" style="flex:5;font-size:14px;min-height:34px;justify-content:flex-start"
                    @click="g('scegli_pianta', {indice: pi.indice})">{{ pi.indice === p.attiva ? '✅' : '📄' }} {{ pi.nome }}</button>
            <button class="bottone" style="flex:1;min-height:34px;padding:0 6px" title="Rimuovi questa planimetria"
                    @click="g('togli_pianta', {indice: pi.indice})">✖</button>
          </div>
          <img :src="'/api/piante/' + pi.indice + '/miniatura?v=' + pi.impronta" alt="" style="width:100%;display:block">
        </div>
        <hr>
        <div class="campo"><label>➕ Aggiungi planimetria</label>
          <input type="file" accept=".png,.jpg,.jpeg,.pdf" @change="carica" style="font-size:13px;max-width:100%"></div>
      </div>

      <!-- il disegno e i suoi comandi -->
      <div style="flex:4">
        <div class="colonne resta" style="margin-bottom:12px">
          <CampoTesto style="flex:2" etichetta="Nome planimetria" :valore="nomeAttiva"
                      @cambia="g('rinomina_pianta', {nome: $event})" />
          <Tendina style="flex:2" etichetta="Categoria per le nuove aree (colore e %)" :valore="p.cat_attiva"
                   :opzioni="opzioniCat" @cambia="g('categoria_nuove', {nome: $event})" />
          <Tendina style="flex:2" etichetta="Tipo per le nuove pareti 🧱" :valore="p.tipo_parete"
                   aiuto="Da demolire = rosso · Da costruire = giallo · In cartongesso = verde"
                   :opzioni="p.tipi_parete.map(t => ({valore: t.codice, testo: t.nome}))"
                   @cambia="g('tipo_parete', {codice: $event})" />
        </div>
        <div class="colonne centro resta" style="margin-bottom:12px">
          <button class="bottone" style="flex:1" :disabled="!p.storia" @click="g('annulla_disegno', {}, false)"
                  title="Torna indietro di un passo su aree, muri e scala. Non tocca il computo né le altre schede.">
            ↩️ Annulla ({{ p.storia ? p.storia.passi : 0 }})</button>
          <p class="didascalia" style="flex:3;margin:0">
            <template v-if="p.storia">Ultima operazione: <b>{{ p.storia.ultima }}</b> · si può tornare indietro di
              {{ p.storia.passi }} pass{{ p.storia.passi === 1 ? 'o' : 'i' }}</template>
            <span v-else class="grigio">Niente da annullare: non hai ancora modificato il disegno in questa sessione.</span>
          </p>
        </div>
        <Avviso v-if="p.scala_persa" tipo="attenzione">↩️ Tornando indietro è stata annullata anche <b>la scala</b>:
          questa planimetria non è più calibrata, quindi le misure non sono in metri finché non la reimposti con lo
          strumento ↔️. Le aree disegnate restano dove sono.</Avviso>
        <p v-if="p.mpp" class="didascalia">✅ Scala impostata — le misure sono in metri reali.</p>
        <Avviso v-else tipo="attenzione">⚠️ Scala non impostata per questa planimetria: scegli <b>Scala</b> nella
          barra sul disegno, poi <b>clicca l'inizio e la fine</b> di una misura nota (es. un lato quotato). Zooma con
          la rotellina per essere preciso: lo zoom non altera le misure.</Avviso>

        <div class="tela"><Tela :argomenti="p.tela" /></div>
        <div v-if="p.vicino.length" class="colonne resta totali-tela" style="margin-bottom:16px">
          <Metrica v-for="m in p.vicino" :key="m.nome" style="flex:1" :nome="m.nome"
                   :valore="numeroIt(m.valore, 2) + ' ' + m.um" />
        </div>

        <div v-if="p.tela.scala_temp" class="colonne fondo resta" style="margin-bottom:16px">
          <CampoNumero style="flex:2" etichetta="Quanto misura in metri, nella realtà, il segmento nero tracciato?"
                       :valore="metriScala" :decimali="2" @cambia="metriScala = $event" />
          <button class="bottone primario" style="flex:1" @click="impostaScala">📏 Imposta scala</button>
          <button class="bottone" style="flex:1" @click="g('annulla_scala')">Annulla</button>
        </div>

        <template v-if="p.zona_sel">
          <p style="margin-bottom:8px"><b>Zona selezionata</b></p>
          <div class="colonne fondo resta" style="margin-bottom:8px">
            <CampoTesto style="flex:2" etichetta="Nome (facoltativo)" :valore="p.zona_sel.nome"
                        @cambia="g('nome_zona', {nome: $event})" />
            <Tendina style="flex:2" etichetta="Categoria" :valore="p.zona_sel.categoria" :opzioni="opzioniCat"
                     @cambia="g('categoria_zona', {categoria: $event})" />
            <button class="bottone" style="flex:1" :disabled="p.zona_sel.involucro || !p.mpp"
                    title="Aggiunge questa superficie come voce del computo. Il perimetro commerciale ne resta fuori: serve solo a misurare la superficie vendibile."
                    @click="g('zona_al_computo', {}, false)">➕ Al computo</button>
            <button class="bottone" style="flex:1" @click="g('elimina_zona')">🗑 Elimina</button>
          </div>
          <p v-if="p.zona_sel.area !== null" class="didascalia">Superficie <b>{{ numeroIt(p.zona_sel.area, 2) }} m²</b> ·
            Perimetro <b>{{ numeroIt(p.zona_sel.perimetro, 2) }} m</b></p>
        </template>

        <template v-if="p.parete_sel">
          <p style="margin-bottom:8px"><b>Parete selezionata</b></p>
          <div class="colonne fondo resta" style="margin-bottom:16px">
            <Tendina style="flex:2" etichetta="Tipo di intervento" :valore="p.parete_sel.tipo"
                     :opzioni="p.tipi_parete.map(t => ({valore: t.codice, testo: t.nome}))"
                     @cambia="g('tipo_parete_sel', {codice: $event})" />
            <CampoPassi v-if="p.parete_sel.lunghezza !== null" style="flex:1" etichetta="Lunghezza (m)"
                        :valore="p.parete_sel.lunghezza" :passo="0.05" :minimo="0.01" :decimali="2"
                        aiuto="Scrivi la misura giusta: il muro si allunga o si accorcia dal capo di arrivo. Sulla tela, in Modifica, puoi anche trascinarne i capi."
                        @cambia="g('lunghezza_parete', {metri: $event})" />
            <Metrica v-else style="flex:1" nome="Lunghezza" :valore="p.parete_sel.etichetta" />
            <button class="bottone" style="flex:1" @click="g('elimina_parete')">🗑 Elimina</button>
          </div>
        </template>

        <Pannello titolo="🧹 Pulisci la planimetria (togli le scritte)">
          <p class="didascalia">Cancella nomi dei locali, quote e simboli ridipingendoli con il fondo del foglio: i
            muri restano intatti. Serve al <b>rilevamento delle stanze</b>, che così non può scambiare una lettera per
            un muro, e libera il disegno dalle scritte che finiscono sotto le etichette delle aree. Le dimensioni non
            cambiano: <b>scala, zone e pareti già impostate restano valide</b>.</p>
          <Cursore etichetta="Quanto insistere" :valore="forza" :minimo="0.5" :massimo="2.5" :passo="0.25" :decimali="2"
                   aiuto="Sotto 1 toglie solo il minuto (quote, simboli). Sopra 1 prende anche le parole grandi: esagerando iniziano a sparire i muri più corti, e lì il rilevamento peggiora invece di migliorare."
                   @cambia="forza = $event" style="margin-bottom:12px" />
          <div class="colonne resta" style="margin-bottom:12px">
            <button class="bottone primario" style="flex:1" @click="g('prova_pulizia', {forza})">🧹 Prova la pulizia</button>
            <button v-if="p.pulizia.originale" class="bottone" style="flex:1" @click="g('ripristina_originale')">↩️ Ripristina l'originale</button>
            <span v-else style="flex:1"></span>
          </div>
          <template v-if="p.pulizia.anteprima">
            <Avviso v-if="!p.pulizia.rimossi">Non ho trovato scritte da togliere. Se ne restano, alza il cursore e riprova.</Avviso>
            <template v-else>
              <div class="colonne resta" style="margin-bottom:8px">
                <div style="flex:1"><p class="didascalia">Adesso</p><img :src="p.tela.src" alt="" style="width:100%"></div>
                <div style="flex:1"><p class="didascalia">Dopo la pulizia (forza {{ numeroIt(p.pulizia.forza, 2) }})</p>
                  <img :src="'/api/anteprima_pulizia?t=' + p.pulizia.forza + p.pulizia.rimossi" alt="" style="width:100%"></div>
              </div>
              <p class="didascalia">Controlla che i <b>muri</b> siano tutti al loro posto: se ne mancano, abbassa il cursore.</p>
              <div class="colonne resta">
                <button class="bottone primario" style="flex:1" @click="g('usa_pulizia', {}, false)">✅ Usa la versione pulita</button>
                <button class="bottone" style="flex:1" @click="g('scarta_pulizia')">Scarta l'anteprima</button>
              </div>
            </template>
          </template>
        </Pannello>

        <Pannello titolo="🪄 Rileva stanze automaticamente (beta)">
          <p class="didascalia">Il programma prova a riconoscere le <b>stanze chiuse dai muri</b> (ignorando scritte e
            quote) e le propone come <b>Superficie interna</b>: sono <b>proposte da rifinire</b> con ➤ Modifica (sposta
            i vertici, cambia categoria, elimina con Canc). Le proposte <b>non si sovrappongono</b> tra loro né alle zone
            già disegnate: puoi rilanciare il rilevamento per completare. Funziona meglio su disegni nitidi e con la
            <b>scala già impostata</b>.</p>
          <div class="colonne resta">
            <button class="bottone primario" style="flex:1" @click="g('rileva_stanze', {}, false)">🪄 Rileva le stanze su questa planimetria</button>
            <button v-if="p.rilevamento" class="bottone" style="flex:1" @click="g('annulla_rilevamento')">
              ↩️ Annulla ultimo rilevamento ({{ p.rilevamento }} aree)</button>
            <span v-else style="flex:1"></span>
          </div>
        </Pannello>
      </div>
    </div>

    <p class="legenda">
      <span v-for="c in p.categorie" :key="c.nome" style="display:inline-block;margin:2px 12px 2px 0">
        <span class="dot" :style="{background: c.colore}"></span>{{ c.nome }} · {{ numeroIt(c.percento, 0) }}%<span
          v-if="c.soglia && c.oltre !== null" style="color:#A9B4C9"> (oltre {{ numeroIt(c.soglia, 0) }} m²:
          {{ numeroIt(c.oltre, 0) }}%)</span>
      </span>
    </p>

    <Pannello titolo="🔤 Etichette sulle zone (layout)">
      <Cursore etichetta="Dimensione carattere" :valore="p.etichette.font" :minimo="10" :massimo="24" :passo="1"
               @cambia="g('etichette', {campo: 'font', valore: $event})" style="margin-bottom:12px" />
      <div class="colonne resta" style="margin-bottom:12px">
        <label class="spunta" style="flex:1"><input type="checkbox" :checked="p.etichette.nome"
               @change="g('etichette', {campo: 'nome', valore: $event.target.checked})"> Nome / categoria</label>
        <label class="spunta" style="flex:1"><input type="checkbox" :checked="p.etichette.m2"
               @change="g('etichette', {campo: 'm2', valore: $event.target.checked})"> Superficie (m²)</label>
        <label class="spunta" style="flex:1"><input type="checkbox" :checked="p.etichette.perimetro"
               @change="g('etichette', {campo: 'perimetro', valore: $event.target.checked})"> Perimetro (m)</label>
        <label class="spunta" style="flex:1"><input type="checkbox" :checked="p.etichette.percento"
               @change="g('etichette', {campo: 'percento', valore: $event.target.checked})"> Percentuale</label>
      </div>
      <p class="didascalia">Di norma le etichette stanno <b>fuori dalle aree</b>, collegate da una linea di richiamo.
        Se ne hai trascinata qualcuna, questo tasto le rimette tutte al loro posto.</p>
      <button class="bottone" :disabled="!p.etichette_spostate" @click="g('riporta_etichette')">
        ↩️ Riporta le etichette fuori dal disegno ({{ p.etichette_spostate }} spostate)</button>
    </Pannello>

    <h3 class="sottotitolo">🧮 Superfici commerciali (tutte le planimetrie)</h3>
    <Avviso v-if="p.superfici.senza_scala.length" tipo="attenzione">Escluse dal totale perché <b>senza scala</b>:
      {{ p.superfici.senza_scala.join(', ') }}</Avviso>
    <Avviso v-if="p.superfici.manca_perimetro" tipo="attenzione">Hai disegnato le superfici interne ma <b>nessun
      perimetro commerciale</b>: per la superficie vendibile traccia un'area della categoria <b>Superficie
      commerciale</b> attorno all'immobile.</Avviso>
    <Avviso v-if="!p.superfici.righe.length">Disegna le aree con ✏️ sulla planimetria: qui compare il riepilogo per
      categoria con le percentuali applicate.</Avviso>
    <template v-else>
      <Tabella :colonne="colonneSup" :righe="p.superfici.righe" />
      <p v-if="p.superfici.interne" class="didascalia">La <b>superficie commerciale</b> è il perimetro «Superficie
        commerciale» più le pertinenze con la loro percentuale. La <b>superficie interna</b> è il calpestabile: resta
        fuori da questo conteggio e va al computo metrico.</p>
      <div class="colonne resta" style="margin-bottom:16px">
        <Metrica style="flex:1" nome="Superficie reale totale" :valore="numeroIt(p.superfici.totale, 2) + ' m²'" />
        <Metrica style="flex:1" nome="Superficie commerciale totale" :valore="numeroIt(p.superfici.commerciale, 2) + ' m²'" />
      </div>
      <button class="bottone primario" style="margin-bottom:16px" @click="g('superficie_al_computo', {}, false)">
        ➕ Riporta la superficie commerciale nel computo</button>
    </template>

    <h3 class="sottotitolo">📏 Dalle superfici al computo (locale per locale)</h3>
    <CampoPassi v-if="p.mostra_altezza" etichetta="Altezza dei locali e dei muri (m)" :valore="p.altezza"
                :passo="0.05" :minimo="1" :massimo="6" :decimali="2" style="max-width:420px;margin-bottom:16px"
                aiuto="Usata per pareti da tinteggiare e per la superficie dei muri da demolire o costruire (lunghezza × altezza)."
                @cambia="g('altezza', {metri: $event})" />
    <Avviso v-if="p.locali.senza_scala.length" tipo="attenzione">Locali esclusi perché la planimetria è <b>senza
      scala</b>: {{ p.locali.senza_scala.join(', ') }}</Avviso>
    <Avviso v-if="!p.locali.righe.length">Quando ci sono zone disegnate (su piante con scala), qui trovi i perimetri
      per battiscopa e tinteggiature.</Avviso>
    <template v-else>
      <p class="didascalia larga">Spunta, locale per locale, che cosa si rifà. <b>Rivestito</b> (bagni, fascia della
        cucina): la fascia piastrellata non si rasa né si tinteggia, e di norma lì il battiscopa non c'è — ma se c'è
        basta spuntarlo. Pavimento = superficie calpestabile; pareti = perimetro × altezza; soffitti = superficie
        calpestabile.</p>
      <div class="tabella-scorre"><table class="tabella">
        <thead><tr><th>Pianta</th><th>Locale</th><th class="num">Superficie (m²)</th><th class="num">Perimetro (m)</th>
          <th title="Conta nella superficie da pavimentare">Pavimento</th>
          <th title="Conta nel totale del battiscopa">Battiscopa</th>
          <th title="Conta in pareti e soffitti da tinteggiare">Tinteggiatura</th>
          <th title="Locale piastrellato (bagno, fascia cucina): la fascia rivestita non si rasa né si tinteggia. Il battiscopa lo comanda la sua spunta: di norma qui non ce n'è, ma con la fascia bassa lo zoccolino ci va — spuntalo e il perimetro rientra nel totale">Rivestito</th></tr></thead>
        <tbody><tr v-for="r in p.locali.righe" :key="r.pianta + '-' + r.zona">
          <td>{{ r.Pianta }}</td><td>{{ r.Locale }}</td>
          <td class="num">{{ numeroIt(r.m2, 2) }}</td><td class="num">{{ numeroIt(r.perimetro, 2) }}</td>
          <td v-for="campo in ['pavimento', 'battiscopa', 'pittura', 'rivestito']" :key="campo">
            <input type="checkbox" :checked="r[campo]" :aria-label="campo + ' ' + r.Locale"
                   @change="g('spunta_locale', {pianta: r.pianta, zona: r.zona, campo, valore: $event.target.checked})"></td>
        </tr></tbody>
      </table></div>

      <div class="pannello-cemento">
        <p><b>🚪 Porte e rivestimenti (detrazioni)</b></p>
        <p class="didascalia larga">Il vano di una porta non ha battiscopa e non si tinteggia; nei locali rivestiti la
          fascia piastrellata non si rasa né si tinteggia. Una porta <b>interna</b> affaccia su due locali, quindi vale
          <b>due lati</b>; il portoncino d'ingresso uno solo. Le quantità qui sotto sono già al netto.</p>
        <div class="colonne resta" style="margin-bottom:12px">
          <CampoPassi style="flex:1" etichetta="Larghezza porte (m)" :valore="f.porta_larg" :passo="0.05" :massimo="3" :decimali="2" @cambia="finitura('porta_larg', $event)" />
          <CampoPassi style="flex:1" etichetta="Altezza porte (m)" :valore="f.porta_alt" :passo="0.05" :massimo="4" :decimali="2" @cambia="finitura('porta_alt', $event)" />
          <CampoPassi style="flex:1" etichetta="Porte interne" :valore="f.porta_n" :massimo="200"
                      aiuto="Porte fra due locali: il vano vale due lati, perché interrompe il battiscopa (e toglie parete da tinteggiare) di qua e di là."
                      @cambia="finitura('porta_n', $event)" />
          <CampoPassi style="flex:1" etichetta="Porte esterne" :valore="f.porta_n_est" :massimo="50"
                      aiuto="Portoncino d'ingresso e porte verso l'esterno o verso locali non computati: vale un lato solo."
                      @cambia="finitura('porta_n_est', $event)" />
          <CampoPassi style="flex:1" etichetta="Altezza rivestimenti (m)" :valore="f.riv_alt" :passo="0.05" :massimo="4" :decimali="2"
                      aiuto="Fascia piastrellata nei locali spuntati «Rivestito» (di norma 1,20 m; zona doccia anche 2,40)."
                      @cambia="finitura('riv_alt', $event)" />
        </div>
        <div class="colonne resta">
          <CampoPassi style="flex:1" etichetta="Porte nei locali rivestiti" :valore="f.riv_porte_n" :massimo="50"
                      aiuto="Di norma una per bagno. Vale un lato solo: l'altra faccia del vano è fuori dal rivestimento."
                      @cambia="finitura('riv_porte_n', $event)" />
          <CampoPassi style="flex:1" etichetta="Finestre nei locali rivestiti" :valore="f.riv_finestre_n" :massimo="50"
                      aiuto="Zero nei bagni ciechi. Si toglie solo la parte che cade dentro la fascia."
                      @cambia="finitura('riv_finestre_n', $event)" />
        </div>
      </div>

      <div class="pannello-cemento">
        <p><b>🪟 Finestre e porte finestra (detrazioni)</b></p>
        <p class="didascalia larga">Stanno su un muro perimetrale, quindi affacciano su <b>un solo locale</b>: valgono
          un lato. La finestra ha il davanzale in alto e il battiscopa ci passa sotto, quindi toglie superficie
          <b>solo</b> a rasatura e tinteggiatura; la <b>porta finestra</b> arriva a terra e interrompe anche il
          battiscopa. Le misure predefinite sono quelle correnti: cambiale se le tue sono diverse.</p>
        <div class="colonne resta">
          <CampoPassi style="flex:1" etichetta="Finestre" :valore="f.fin_n" :massimo="200"
                      aiuto="Quante finestre nei locali spuntati «Tinteggiatura»." @cambia="finitura('fin_n', $event)" />
          <CampoPassi style="flex:1" etichetta="Larghezza finestra (m)" :valore="f.fin_larg" :passo="0.05" :massimo="6" :decimali="2" @cambia="finitura('fin_larg', $event)" />
          <CampoPassi style="flex:1" etichetta="Altezza finestra (m)" :valore="f.fin_alt" :passo="0.05" :massimo="4" :decimali="2" @cambia="finitura('fin_alt', $event)" />
          <CampoPassi style="flex:1" etichetta="Porte finestra" :valore="f.pf_n" :massimo="200"
                      aiuto="Vanno a terra: tolgono anche battiscopa." @cambia="finitura('pf_n', $event)" />
          <CampoPassi style="flex:1" etichetta="Larghezza p. finestra (m)" :valore="f.pf_larg" :passo="0.05" :massimo="6" :decimali="2" @cambia="finitura('pf_larg', $event)" />
          <CampoPassi style="flex:1" etichetta="Altezza p. finestra (m)" :valore="f.pf_alt" :passo="0.05" :massimo="4" :decimali="2" @cambia="finitura('pf_alt', $event)" />
        </div>
      </div>

      <template v-if="p.quantita">
        <div class="colonne resta" style="margin-bottom:16px">
          <Metrica style="flex:1" nome="Pavimento (interni)" :valore="numeroIt(p.quantita.pavimento, 2) + ' m²'" />
          <Metrica style="flex:1" nome="Battiscopa" :valore="numeroIt(p.quantita.battiscopa, 2) + ' m'"
                   :delta="p.quantita.detr_ml ? '−' + numeroIt(p.quantita.detr_ml, 2) + ' m vani' : ''" />
          <Metrica style="flex:1" :nome="'Pareti (h ' + numeroIt(p.altezza, 2) + ' m)'" :valore="numeroIt(p.quantita.pareti, 2) + ' m²'"
                   :delta="p.quantita.detr_m2 ? '−' + numeroIt(p.quantita.detr_m2, 2) + ' m² vani e rivestimenti' : ''" />
          <Metrica style="flex:1" nome="Soffitti" :valore="numeroIt(p.quantita.soffitti, 2) + ' m²'" />
        </div>
        <div class="colonne resta" style="margin-bottom:16px">
          <Metrica style="flex:1" nome="Pavimento esterno (balconi, terrazzi)" :valore="numeroIt(p.quantita.pavimento_esterno, 2) + ' m²'" />
          <Metrica style="flex:1" :nome="'Rivestimenti (fascia h ' + numeroIt(f.riv_alt, 2) + ' m)'"
                   :valore="numeroIt(p.quantita.rivestimenti, 2) + ' m²'"
                   :delta="p.quantita.detr_riv ? '−' + numeroIt(p.quantita.detr_riv, 2) + ' m² vani' : ''" />
        </div>
        <p v-if="p.quantita.nessun_rivestito" class="didascalia grigio">Nessun locale spuntato <b>Rivestito</b>: la
          voce dei rivestimenti resta a zero. La spunta è nella tabella dei locali qui sopra — di norma i bagni e la
          fascia della cucina.</p>
        <Pannello titolo="🔍 Il conto in chiaro — chi entra nei totali e ogni detrazione, riga per riga">
          <template v-if="p.conto.censimento">
            <p><b>Locale per locale — chi entra in quale totale</b></p>
            <p class="didascalia">Uno zero vuol dire che quel locale, in quel totale, non c'è: le sue spunte sono nella
              tabella qui sopra.</p>
            <Tabella :colonne="colonneConto" :righe="p.conto.censimento.map(r => ({...r, __stile: stileTotale(r)}))" />
          </template>
          <template v-for="s in p.conto.sezioni" :key="s.titolo">
            <p><b>{{ s.titolo }}</b></p>
            <table class="tabella">
              <thead><tr><th>{{ s.intestazione }}</th><th>Come si calcola</th><th class="num">Quanto</th></tr></thead>
              <tbody>
                <tr v-for="(r, i) in s.righe" :key="i"><td>{{ r[0] }}</td><td>{{ r[1] }}</td><td class="num">{{ r[2] }}</td></tr>
                <tr><td><b>Totale</b></td><td></td><td class="num"><b>{{ s.totale }}</b></td></tr>
              </tbody>
            </table>
          </template>
        </Pannello>
      </template>
    </template>

    <h3 class="sottotitolo">🧱 Dai muri al computo (demolire / costruire / cartongesso)</h3>
    <Avviso v-if="p.muri_senza_scala.length" tipo="attenzione">Muri esclusi perché la planimetria è <b>senza
      scala</b>: {{ p.muri_senza_scala.join(', ') }}</Avviso>
    <Avviso v-if="!muri">Traccia i muri con lo strumento <b>PARETE</b> sul disegno (scegli sopra se sono da demolire,
      da costruire o in cartongesso): qui trovi metri lineari e superfici pronti per il computo.</Avviso>
    <template v-else>
      <p class="didascalia larga">Superficie = lunghezza × altezza (<b>{{ numeroIt(p.altezza, 2) }} m</b>), al netto
        delle aperture dichiarate qui sotto: dove c'è un vano non c'è muratura da buttare giù né da tirare su.</p>
      <div class="pannello-cemento">
        <div class="colonne resta">
          <CampoPassi style="flex:1" etichetta="Aperture nei muri da demolire" :valore="f.apert_dem_n" :massimo="200"
                      aiuto="Quanti vani (porte, passaggi, finestre) ci sono nei muri rossi. I m² li fa l'app, con le misure qui accanto."
                      @cambia="finitura('apert_dem_n', $event)" />
          <CampoPassi style="flex:1" etichetta="Aperture nei muri da costruire" :valore="f.apert_cos_n" :massimo="200"
                      aiuto="Vani previsti nei muri gialli: quella superficie non va murata." @cambia="finitura('apert_cos_n', $event)" />
          <CampoPassi style="flex:1" etichetta="Aperture nei muri in cartongesso" :valore="f.apert_car_n" :massimo="200"
                      aiuto="Vani previsti nei muri verdi: quella superficie non va lastrata." @cambia="finitura('apert_car_n', $event)" />
          <CampoPassi style="flex:1" etichetta="Larghezza apertura (m)" :valore="f.apert_larg" :passo="0.05" :massimo="6" :decimali="2"
                      aiuto="Misura della porta tipo: 0,80 × 2,10 nelle case. Cambiala se i tuoi vani sono diversi."
                      @cambia="finitura('apert_larg', $event)" />
          <CampoPassi style="flex:1" etichetta="Altezza apertura (m)" :valore="f.apert_alt" :passo="0.05" :massimo="4" :decimali="2"
                      @cambia="finitura('apert_alt', $event)" />
        </div>
      </div>
      <p v-if="muri.demolire.aperture || muri.costruire.aperture || muri.cartongesso.aperture" class="didascalia larga grigio">
        Un vano da {{ numeroIt(f.apert_larg, 2) }} × {{ numeroIt(f.apert_alt, 2) }} m vale
        <b>{{ numeroIt(f.apert_larg * f.apert_alt, 2) }} m²</b>: {{ f.apert_dem_n }} da demolire =
        {{ numeroIt(muri.demolire.aperture, 2) }} m², {{ f.apert_cos_n }} da costruire =
        {{ numeroIt(muri.costruire.aperture, 2) }} m², {{ f.apert_car_n }} in cartongesso =
        {{ numeroIt(muri.cartongesso.aperture, 2) }} m².</p>
      <div class="colonne resta muri" style="margin-bottom:16px">
        <Metrica style="flex:1" :nome="'🔴 Da demolire (' + muri.demolire.n + ')'" :valore="numeroIt(muri.demolire.ml, 2) + ' m'" />
        <Metrica style="flex:1" nome="→ superficie" :valore="numeroIt(muri.demolire.netto, 2) + ' m²'"
                 :delta="muri.demolire.aperture ? '−' + numeroIt(muri.demolire.aperture, 2) + ' m² aperture' : ''" />
        <Metrica style="flex:1" :nome="'🟡 Da costruire (' + muri.costruire.n + ')'" :valore="numeroIt(muri.costruire.ml, 2) + ' m'" />
        <Metrica style="flex:1" nome="→ superficie" :valore="numeroIt(muri.costruire.netto, 2) + ' m²'"
                 :delta="muri.costruire.aperture ? '−' + numeroIt(muri.costruire.aperture, 2) + ' m² aperture' : ''" />
      </div>
      <div class="colonne resta muri" style="margin-bottom:16px">
        <Metrica style="flex:1" :nome="'🟢 In cartongesso (' + muri.cartongesso.n + ')'" :valore="numeroIt(muri.cartongesso.ml, 2) + ' m'" />
        <Metrica style="flex:1" nome="→ superficie" :valore="numeroIt(muri.cartongesso.netto, 2) + ' m²'"
                 :delta="muri.cartongesso.aperture ? '−' + numeroIt(muri.cartongesso.aperture, 2) + ' m² aperture' : ''" />
      </div>
      <p v-if="muri.esistente.n" class="didascalia grigio">Esclusi {{ muri.esistente.n }} muri «esistenti»
        ({{ numeroIt(muri.esistente.ml, 2) }} m): non sono lavorazioni.</p>
      <p v-if="muri.costruire.netto" class="didascalia larga grigio"><b>Rasatura</b>:
        {{ numeroIt(2 * muri.costruire.netto, 2) }} m² — le due facce dei muri nuovi in forati
        ({{ numeroIt(muri.costruire.netto, 2) }} m² × 2). È il minimo che serve di sicuro; se si rasa anche dell'altro,
        scrivi tu la quantità nella voce 3.18 e il disegno smette di riscrivertela.</p>
    </template>

    <template v-if="d.attivo">
      <p style="margin-bottom:8px"><b>➕ Porta queste quantità nel computo</b></p>
      <Interruttore :acceso="d.agganciato" etichetta="🔗 Tieni il computo agganciato al disegno"
                    aiuto="Acceso: sposti un muro o cambi una spunta e la quantità nel computo si aggiorna da sé. Spento: la porti tu, con il bottone."
                    @cambia="g('aggancia', {acceso: $event})" />
      <p class="didascalia larga" style="margin-top:8px">Le quantità vengono <b>scritte</b> nelle voci del listino,
        non sommate: si può rifare il rilevamento e cambiare le spunte senza contare niente due volte.</p>
      <label v-for="v in d.voci" :key="v.codice" class="spunta" style="display:flex;margin-bottom:6px">
        <input type="checkbox" :checked="v.spuntata" @change="g('voce_dal_disegno', {codice: v.codice, acceso: $event.target.checked})">
        <span><b>{{ v.codice }}</b> · {{ v.descrizione }} → <b>{{ numeroIt(v.quantita, 2) }} {{ v.um }}</b>
          <span v-if="v.attuale && Math.abs(v.attuale - v.quantita) > 0.005" class="arancio">(sostituisce {{ numeroIt(v.attuale, 2) }})</span></span>
      </label>
      <p v-if="!d.spuntate" class="didascalia grigio">Nessuna voce selezionata.</p>
      <div v-if="d.a_mano.length" class="colonne centro resta" style="margin-bottom:8px">
        <p class="didascalia arancio" style="flex:4;margin:0">✎ Scritte a mano, quindi non aggiornate dal disegno:
          {{ d.a_mano.join(', ') }}.</p>
        <button class="bottone" style="flex:1" title="Ridà al disegno il comando su queste voci: le quantità tornano quelle misurate."
                @click="g('riaggancia')">↺ Riaggancia</button>
      </div>
      <p v-if="d.agganciato" class="didascalia verde">✔ Computo allineato al disegno — {{ d.spuntate }}
        {{ d.spuntate === 1 ? 'voce' : 'voci' }} che si aggiornano da sé.</p>
      <button v-else class="bottone primario" :disabled="!d.da_scrivere" @click="g('scrivi_dal_disegno', {}, false)">
        ➕ Scrivi le quantità nel listino</button>
    </template>

    <hr>
    <div class="colonne resta">
      <div style="flex:1">
        <label class="spunta" style="margin-bottom:8px"
               title="Il foglio steso: la pianta più grande, e le misure principali in colonna a destra invece che sotto.">
          <input type="checkbox" v-model="orizzontale"> Foglio orizzontale</label>
        <button class="bottone largo" @click="stampaPdf"
                title="Le piante disegnate, con le misure delle zone e dei muri, e con la prima le quantità principali.">
          🖨️ Stampa planimetrie (PDF)</button>
      </div>
      <div style="flex:2;display:flex;align-items:flex-end">
        <button class="bottone largo" @click="scarica('json')">💾 Salva progetto (.json) — computo e planimetrie</button>
      </div>
    </div>
    </template>
  </div>`,
});
