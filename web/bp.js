// Il «📊 Business plan» e le sue quattro sottolinguette: studio di
// fattibilità, spese a consuntivo, cantiere (contratto e SAL), MCA.
//
// ⚠️ Le etichette inglesi dello studio (ESTIMATED, Buy cost, Net Return…)
// sono il vocabolario del foglio Excel da cui viene: non si traducono.
import { computed, defineComponent, ref } from "vue";
import { Avviso, CampoNumero, CampoPassi, Grafico, Griglia, Metrica, Pannello,
         Tabella, Tendina } from "./componenti.js";
import { euro, numeroIt } from "./formato.js";
import { gesto, stato, toast } from "./rete.js";

const bpv = () => stato.vista.bp;
const imposta = (chiave, valore) => gesto("bp", { chiave, valore }, { zitto: true });

// righe_bp: il blocchetto etichetta / valore stile Excel
const RigheBp = defineComponent({
  props: { righe: Array },
  setup() {
    const colore = (stile) => ({ buono: "#7DDC7D", cattivo: "#FF8A8A" }[stile] || "var(--travertino)");
    return { colore };
  },
  template: `
  <div>
    <template v-for="r in righe" :key="r[0]">
      <div v-if="r[1] !== null && r[1] !== '' && r[1] !== '—'" class="riga-bp"
           :class="{ spiegata: r[3] }" :title="r[3] || null">
        <span>{{ r[0] }}</span>
        <span :style="{fontWeight: r[2] ? 700 : 500, color: colore(r[2])}">{{ r[1] }}</span>
      </div>
    </template>
  </div>`,
});

const Intestazione = defineComponent({
  props: { testo: String },
  template: `<div class="intestazione-bp">{{ testo }}</div>`,
});

// Una legenda che dice cosa vogliono dire i colori della matrice
const Legenda = defineComponent({
  props: { metrica: String },
  template: `
  <div class="legenda-matrice">
    <span class="chip" style="background:#F8696B"></span>in perdita &nbsp;·&nbsp;
    <span class="chip" style="background:#FFFFFF"></span>pareggio ({{ metrica === 'multiplo' ? '1,00x' : '0 €' }}) &nbsp;·&nbsp;
    <span class="chip" style="background:#63BE7B"></span>in utile
  </div>`,
});

// ----------------------------------------------------- studio di fattibilità
const RigaCosto = defineComponent({
  components: { CampoNumero },
  props: { riga: Object },
  setup() { return { imposta, euro }; },
  template: `
  <div class="riga-costo">
    <span class="grigio" :class="{ spiegata: riga.come }" :title="riga.come || null"><b v-if="riga.arancio" class="arancio">{{ riga.etichetta }}</b>
      <template v-else>{{ riga.etichetta }}</template></span>
    <CampoNumero v-if="riga.centro" :valore="riga.centro.valore" :decimali="2" :aiuto="riga.centro.aiuto"
                 @cambia="imposta(riga.centro.chiave, $event)" />
    <div v-else class="barra-vuota">/</div>
    <CampoNumero v-if="riga.destra" :valore="riga.destra.valore" :decimali="2" :aiuto="riga.destra.aiuto"
                 @cambia="imposta(riga.destra.chiave, $event)" />
    <div v-else class="barra-vuota">/</div>
    <CampoNumero v-if="riga.iva" :valore="riga.iva.valore" :decimali="2" :massimo="50"
                 aiuto="Aliquota di questa voce: 22% è l'ordinaria, 10% i lavori edili, 0% le voci che l'IVA non ce l'hanno (l'imposta di registro è già un'imposta)."
                 @cambia="imposta(riga.iva.chiave, $event)" />
    <div v-else class="barra-vuota">/</div>
    <div v-if="riga.iva" style="text-align:right;font-weight:600">{{ euro(riga.iva.euro) }}</div>
    <div v-else class="barra-vuota">/</div>
  </div>`,
});

const Fattibilita = defineComponent({
  components: { CampoNumero, CampoPassi, Grafico, RigheBp, Intestazione, Legenda, RigaCosto, Avviso },
  setup() {
    const f = computed(() => bpv().fattibilita);
    return { f, imposta, gesto, euro, numeroIt };
  },
  template: `
  <div class="bp-scorre">
  <div class="colonne resta" style="gap:3rem;min-width:1560px">
    <div style="flex:1">
      <CampoPassi etichetta="Mq commerciali" :valore="f.mq.valore" :decimali="2"
                  aiuto="Si compila da sé con la superficie commerciale della planimetria. Scrivici sopra quando serve: da quel momento comanda la tua cifra."
                  @cambia="imposta('bp_mq', $event)" />
      <p v-if="f.mq.a_mano" class="didascalia"><span class="arancio">Cifra scritta a mano.</span>
        <span v-if="f.mq.planimetria" class="grigio"> La planimetria dice <b>{{ numeroIt(f.mq.planimetria, 2) }} m²</b>.</span></p>
      <button v-if="f.mq.a_mano && f.mq.planimetria" class="bottone" style="margin-bottom:12px"
              @click="gesto('riprendi_mq', {}, {zitto: true})">↩️ Riprendi dalla planimetria</button>
      <p v-else-if="!f.mq.a_mano && f.mq.planimetria" class="didascalia verde">Compilato dalla planimetria:
        <b>{{ numeroIt(f.mq.planimetria, 2) }} m²</b> commerciali.</p>
      <p v-else-if="!f.mq.a_mano && !f.mq.piante" class="didascalia grigio">Nessuna planimetria caricata: scrivi qui
        i mq, oppure disegnale nella scheda <b>Misura da planimetria</b>.</p>
      <Avviso v-else-if="!f.mq.a_mano && f.mq.calpestabili" tipo="attenzione">Nella planimetria ci sono stanze
        (<b>{{ numeroIt(f.mq.calpestabili, 2) }} m²</b> calpestabili) ma <b>nessun perimetro «Superficie
        commerciale»</b>, e le stanze interne da sole non fanno superficie commerciale: il perimetro le racchiude
        già, contarle in due posti gonfierebbe il totale. Disegna il perimetro d'ingombro con la categoria
        <b>Superficie commerciale</b>, oppure scrivi qui i mq a mano.</Avviso>
      <p v-else-if="!f.mq.a_mano" class="didascalia grigio">La planimetria non ha ancora aree disegnate con una scala:
        scrivi qui i mq, oppure disegnale.</p>
      <CampoNumero etichetta="Passo sensitività (€)" :valore="f.bp.bp_passo" :decimali="0" :minimo="1000"
                   @cambia="imposta('bp_passo', $event)" style="margin-bottom:12px" />
      <CampoPassi etichetta="Durata operazione (mesi)" :valore="f.bp.bp_durata" :minimo="1" :massimo="120"
                  @cambia="imposta('bp_durata', $event)" />
      <Intestazione testo="ESTIMATED" />
      <CampoNumero class="prezzo-acquisto" etichetta="Prezzo base (acquisto, €)" :valore="f.bp.bp_acquisto"
                   :decimali="0" @cambia="imposta('bp_acquisto', $event)" />
      <RigheBp :righe="f.esito.acquisto" />
      <CampoNumero class="prezzo-vendita" etichetta="Estimated sell price (€)" :valore="f.bp.bp_vendita"
                   :decimali="0" aiuto="Puoi stimarlo con l'MCA (terza sezione)"
                   @cambia="imposta('bp_vendita', $event)" style="margin-top:8px" />
      <RigheBp :righe="f.esito.vendita" />
      <div class="nota-base">Risultati calcolati su<br>acquisto
        <b>{{ f.bp.bp_acquisto ? euro(f.bp.bp_acquisto) : '' }}<span v-if="!f.bp.bp_acquisto" class="arancio">non inserito</span></b> ·
        vendita <b>{{ f.bp.bp_vendita ? euro(f.bp.bp_vendita) : '' }}<span v-if="!f.bp.bp_vendita" class="arancio">non inserito</span></b></div>
      <RigheBp :righe="f.esito.risultati" />
    </div>

    <div style="flex:1.85">
      <template v-if="f.matrici">
        <p style="margin-bottom:4px"><b>Money multiple</b> <span class="grigio">(net sell / net purchase — acquisto
          sulle righe, vendita sulle colonne)</span></p>
        <Grafico :figura="f.matrici.multiplo" />
        <Legenda metrica="multiplo" />
        <p style="margin-bottom:4px"><b>Net gain</b> <span class="grigio">(guadagno assoluto, €)</span></p>
        <Grafico :figura="f.matrici.guadagno" />
        <Legenda metrica="guadagno" />
      </template>
      <Avviso v-else>Inserisci <b>prezzo di acquisto</b> e <b>prezzo di vendita</b> per vedere le matrici di
        sensitività (la vendita puoi stimarla con l'MCA).</Avviso>
    </div>

    <div style="flex:2.15">
      <Intestazione testo="Spese acquisto — dettaglio" />
      <p v-if="f.senza_base.length" class="didascalia arancio">Le percentuali qui sotto restano a zero finché manca
        {{ f.senza_base.join(' · ') }}: non c'è ancora un importo su cui calcolarle.</p>
      <div class="riga-costo intestazione"><span>Voce</span><span>%</span><span>Netto</span><span>IVA %</span><span>IVA €</span></div>
      <RigaCosto v-for="r in f.costi" :key="r.etichetta" :riga="r" />
      <label v-if="f.consuntivo > 0" class="spunta" style="margin:8px 0"
             title="Lavori + materiale + architetto dalla scheda «Spese a consuntivo» (sostenute e da sostenere), al posto della stima. Ha la precedenza sulla cifra a mano qui sopra.">
        <input type="checkbox" :checked="f.bp.bp_usa_consuntivo" @change="imposta('bp_usa_consuntivo', $event.target.checked)">
        Usa i costi reali del cantiere ({{ euro(f.consuntivo) }})</label>
      <RigheBp :righe="f.esito.acquisto_totali" />
      <div style="height:10px"></div>
      <RigaCosto :riga="f.agenzia_out" />
      <RigheBp :righe="f.esito.vendita_totali" />
      <template v-if="f.esito.iva_credito.length">
        <RigheBp :righe="f.esito.iva_credito" />
      </template>
    </div>
  </div>
  </div>`,
});

// ------------------------------------------------------ spese a consuntivo
const Spese = defineComponent({
  components: { Griglia, Metrica, Pannello, Grafico, Avviso },
  setup() {
    const s = computed(() => bpv().spese);
    const colSostenute = computed(() => [
      { chiave: "importo", titolo: "Totale fattura", tipo: "numero", formato: "euro", larghezza: 120, minimo: 0,
        aiuto: "Il LORDO, IVA compresa — il «totale documento» della fattura. L'IVA si scorpora da qui con l'aliquota della colonna accanto: mettendoci l'imponibile, l'IVA esce sbagliata." },
      { chiave: "aliquota_iva", titolo: "IVA %", tipo: "numero", decimali: 0, larghezza: 70, minimo: 0, massimo: 22,
        aiuto: "Aliquota della fattura, per lo scorporo (22, 10 o 0)" },
      { chiave: "iva_eur", titolo: "di cui IVA", tipo: "numero", formato: "euro", larghezza: 105, sola_lettura: true,
        aiuto: "Calcolata: l'IVA contenuta nel totale, con l'aliquota della colonna accanto." },
      { chiave: "data", titolo: "Data", tipo: "testo", larghezza: 95, aiuto: "Es. 22/10/2025" },
      { chiave: "nr_fattura", titolo: "Nr. fattura", tipo: "testo", larghezza: 105,
        aiuto: "Numero/riferimento della fattura. «//» quando non sono riuscito a leggerlo dal file." },
      { chiave: "fornitore", titolo: "Fornitore", tipo: "testo", larghezza: 185 },
      { chiave: "oggetto", titolo: "Oggetto", tipo: "testo", larghezza: 250 },
      { chiave: "categoria", titolo: "Categoria", tipo: "scelta", larghezza: 155, opzioni: s.value.categorie },
      { chiave: "note", titolo: "Note", tipo: "testo", larghezza: 130 },
    ]);
    const colPrev = computed(() => [
      { chiave: "oggetto", titolo: "Oggetto", tipo: "testo", larghezza: 190 },
      { chiave: "importo", titolo: "Importo previsto", tipo: "numero", formato: "euro", larghezza: 125, minimo: 0,
        aiuto: "IVA compresa, come le spese sostenute: i due registri si sommano." },
      { chiave: "aliquota_iva", titolo: "IVA %", tipo: "numero", decimali: 0, larghezza: 70, minimo: 0, massimo: 22 },
      { chiave: "categoria", titolo: "Categoria", tipo: "scelta", larghezza: 150, opzioni: s.value.categorie },
      { chiave: "note", titolo: "Note", tipo: "testo", larghezza: 110 },
    ]);
    const anteprima = ref(null);
    async function leggi(ev) {
      const file = [...ev.target.files];
      if (!file.length) return;
      const dati = new FormData();
      file.forEach((f) => dati.append("file", f));
      try {
        const r = await (await fetch("/api/fatture", { method: "POST", body: dati })).json();
        stato.vista = r.vista;
        if (r.esito) toast(r.esito.testo, r.esito.tipo);
        anteprima.value = null;
      } catch (e) { toast(e.message, "errore"); }
      ev.target.value = "";
    }
    function aggiungi() {
      const righe = anteprima.value || s.value.fatture_lette.righe;
      gesto("aggiungi_fatture", { righe }, { zitto: true });
      anteprima.value = null;
    }
    const scrivi = (registro, righe) => gesto("spese", { registro, righe }, { zitto: true });
    return { s, colSostenute, colPrev, leggi, aggiungi, anteprima, scrivi, gesto, euro, numeroIt };
  },
  template: `
  <div>
    <p class="didascalia">Il registro delle spese reali dell'operazione, come il tuo foglio «Spese». A sinistra le
      spese già <b>sostenute</b> (le fatture); <b>accanto</b>, senza scendere in fondo alla pagina, il <b>riepilogo
      per categoria</b>, le spese ancora <b>da sostenere</b> e la torta. La quota <b>cantiere</b> (lavori, materiale,
      architetto) può sostituire la ristrutturazione stimata nello studio di fattibilità.</p>
    <Pannello titolo="📎 Carica fatture (PDF o XML) e auto-compila">
      <p class="didascalia">Trascina una o più fatture: leggo importo, IVA, data, numero e fornitore. Controlla i dati,
        scegli la <b>categoria</b> e aggiungile alle spese sostenute. I file restano sul computer, nessun dato esce.
        Funziona meglio con i PDF «di cortesia» della fattura elettronica e con gli XML; su PDF con layout insoliti
        alcuni campi potrebbero restare da completare a mano.</p>
      <input type="file" multiple accept=".pdf,.xml,.p7m" @change="leggi" aria-label="Fatture">
      <template v-if="s.fatture_lette && s.fatture_lette.righe.length">
        <p style="margin:12px 0 4px"><b>{{ s.fatture_lette.righe.length }} fattura/e lette.</b> Correggi se serve e
          scegli la categoria:</p>
        <Griglia :colonne="colSostenute.filter(c => c.chiave !== 'iva_eur')" :righe="s.fatture_lette.righe"
                 @cambia="anteprima = $event" />
        <div class="colonne resta">
          <button class="bottone primario" @click="aggiungi">➕ Aggiungi alle spese sostenute</button>
          <button class="bottone" @click="gesto('scarta_fatture', {}, {zitto: true})">Scarta</button>
        </div>
      </template>
    </Pannello>

    <div class="colonne" style="gap:2rem">
      <div style="flex:2.2">
        <h5>🧾 Spese sostenute</h5>
        <Griglia :colonne="colSostenute" :righe="s.sostenute" dinamica obbligatoria="importo"
                 @cambia="scrivi('spese', $event)" />
        <Metrica nome="Totale spese sostenute" :valore="euro(s.totale_sostenute)" style="max-width:420px" />
      </div>
      <div style="flex:1.1">
        <h5>📊 Riepilogo — solo le sostenute</h5>
        <table v-if="s.riepilogo.length" class="riepilogo-spese">
          <thead><tr><th>Categoria</th><th class="num">€</th><th class="num">IVA</th></tr></thead>
          <tbody>
            <tr v-for="r in s.riepilogo" :key="r.categoria">
              <td :style="{background: r.colore, color: r.su_colore, fontWeight: 700}">{{ r.categoria }}</td>
              <td class="num">{{ euro(r.importo) }}</td><td class="num grigio">{{ euro(r.iva) }}</td>
            </tr>
            <tr class="totale"><td>TOTALE</td><td class="num">{{ euro(s.totale_sostenute) }}</td>
              <td class="num">{{ euro(s.iva_totale) }}</td></tr>
          </tbody>
        </table>
        <p v-else class="didascalia">Nessuna spesa sostenuta ancora.</p>
        <h5>🔮 Spese da sostenere</h5>
        <Griglia :colonne="colPrev" :righe="s.prev" dinamica obbligatoria="importo"
                 @cambia="scrivi('spese_prev', $event)" />
        <Metrica nome="Totale da sostenere" :valore="euro(s.totale_prev)" style="margin-bottom:12px" />
        <div class="totale-oro">
          <div class="nome">Totale del registro spese</div>
          <div class="valore">{{ euro(s.totale) }}</div>
          <div class="sotto">sostenute {{ euro(s.totale_sostenute) }} + da sostenere {{ euro(s.totale_prev) }}</div>
          <div class="separato">di cui cantiere <b>{{ euro(s.quota_cantiere) }}</b> — riportabile nello studio di fattibilità</div>
        </div>
        <p class="didascalia grigio">Non è il costo dell'operazione: <b>ACQUISTO</b> e <b>AGENZIA</b> qui dentro, nello
          studio di fattibilità, sono già contati nel prezzo d'acquisto e nei suoi oneri. Di qua passa solo la quota
          <b>cantiere</b>.</p>
        <h5>🥧 Sostenute per categoria</h5>
        <Grafico v-if="s.torta" :figura="s.torta" />
        <p v-else class="didascalia">La torta comparirà con le prime spese.</p>
      </div>
    </div>

    <template v-if="s.confronto">
      <hr>
      <h3 class="sottotitolo">⚖️ Il computo alla prova del cantiere</h3>
      <div class="colonne resta" style="margin-bottom:12px">
        <Metrica style="flex:1" nome="Preventivo (computo)" :valore="euro(s.confronto.preventivo)" />
        <Metrica style="flex:1" nome="Speso davvero (fatture)" :valore="euro(s.confronto.speso)" />
        <Metrica style="flex:1" nome="Ancora da sostenere (stime)" :valore="euro(s.confronto.previsto)" />
        <Metrica style="flex:1" nome="Scostamento sul preventivo"
                 :valore="s.confronto.scostamento_pct !== null ? numeroIt(s.confronto.scostamento_pct, 1) + ' %' : '—'"
                 :delta="euro(s.confronto.scostamento)" :verso="s.confronto.scostamento > 0 ? 'giu' : 'su'" />
      </div>
      <p class="didascalia grigio">Lavori, materiale e architetto. Il confronto usa <b>entrambe</b> le colonne — speso
        più da sostenere — perché è il costo atteso del cantiere; finché la seconda non è vuota, lo scostamento è in
        parte una previsione. ⚠️ I materiali che compri tu il computo non li conosce: se sono una fetta grossa,
        mettine il budget fra le <b>spese da sostenere</b>, o questo confronto ti dirà che stai sforando quando non
        è vero.</p>
    </template>
  </div>`,
});

// ------------------------------------------------------------- cantiere
const Cantiere = defineComponent({
  components: { CampoNumero, Griglia, Metrica, Tabella, Avviso },
  setup() {
    const c = computed(() => bpv().cantiere);
    const colSal = [
      { chiave: "etichetta", titolo: "Stato", tipo: "testo", sola_lettura: true },
      { chiave: "percento", titolo: "% del contratto", tipo: "numero", decimali: 1, minimo: 0, massimo: 100 },
      { chiave: "pagato", titolo: "Saldato", tipo: "spunta" },
    ];
    const righeSal = computed(() => c.value.sal.map((q, i) => ({ ...q, etichetta: `SAL ${i + 1}` })));
    function scriviSal(righe) {
      gesto("sal", { righe: righe.map((r) => ({ percento: r.percento ?? 0, pagato: !!r.pagato })) }, { zitto: true });
    }
    const piano = computed(() => c.value.stato.piano.map((s) => ({
      Stato: `SAL ${s.n}`, "% del contratto": `${numeroIt(s.percento, 1)} %`, Importo: euro(s.importo),
      Saldato: c.value.sal[s.n - 1]?.pagato ? "sì" : "—" })));
    const colPiano = ["Stato", "% del contratto", "Importo", "Saldato"].map((k) => ({ chiave: k, titolo: k, num: k === "Importo" }));
    const colStorico = ["Operazione", "Chiusa il", "Contratto", "Extra", "Scostamento", "€/mq lavori"]
      .map((k) => ({ chiave: k, titolo: k }));
    const imposta = (campo, valore) => gesto("cantiere", { campo, valore }, { zitto: true });
    return { c, colSal, righeSal, scriviSal, piano, colPiano, colStorico, imposta, gesto, euro, numeroIt };
  },
  template: `
  <div>
    <h3 class="sottotitolo" style="margin-top:0">🏗️ Contratto d'appalto e stati di avanzamento</h3>
    <p class="didascalia">Le imprese si pagano a <b>SAL</b>, concordati nel contratto prima che il cantiere apra
      (spesso 20-30-30-20, ma ogni cantiere fa storia a sé). Gli <b>extra</b> non si vedono lungo la strada: si
      calcolano a cantiere chiuso, quando ci si siede con le parti e si fa il SAL finale. Qui si tiene il conto, e
      alla chiusura si impara quanto si è sforato — che è il numero che serve all'operazione dopo.</p>
    <div class="colonne resta" style="margin-bottom:16px">
      <div style="flex:1">
        <CampoNumero etichetta="Importo di contratto (€)" :valore="c.contratto"
                     aiuto="Quanto hai firmato con l'impresa. Se lo lasci a zero non c'è niente da ripartire."
                     @cambia="imposta('contratto', $event)" />
        <button v-if="!c.contratto && c.totale_computo" class="bottone" style="margin-top:8px"
                title="Solo le lavorazioni del computo: i materiali a cura tua non fanno parte dell'appalto."
                @click="gesto('contratto_dal_computo', {}, {zitto: true})">Usa il computo: {{ euro(c.totale_computo) }}</button>
      </div>
      <CampoNumero style="flex:1" etichetta="Extra finali (€)" :valore="c.extra"
                   aiuto="Si compila a cantiere chiuso, dopo il SAL finale concordato con le parti."
                   @cambia="imposta('extra', $event)" />
    </div>
    <p style="margin-bottom:4px"><b>Stati di avanzamento</b></p>
    <p class="didascalia">Le quote del contratto. Spunta i SAL già saldati.</p>
    <Griglia :colonne="colSal" :righe="righeSal" dinamica :nuova="{percento: 0, pagato: false}" @cambia="scriviSal" />
    <Avviso v-if="c.sal.length && Math.abs(c.somma - 100) > 0.01" tipo="attenzione">⚠️ Le quote fanno
      <b>{{ numeroIt(c.somma, 1) }}%</b>, non 100: il contratto non è ripartito per intero. Non correggo io — è un
      numero da guardare.</Avviso>
    <template v-if="c.stato.contratto">
      <Tabella :colonne="colPiano" :righe="piano" />
      <div class="colonne resta" style="margin-bottom:16px">
        <Metrica style="flex:1" nome="Saldato" :valore="euro(c.stato.pagato)" />
        <Metrica style="flex:1" nome="Residuo di contratto" :valore="euro(c.stato.residuo)" />
        <Metrica style="flex:1" nome="Totale a fine cantiere" :valore="euro(c.stato.totale_finale)"
                 :delta="c.stato.extra ? '+' + euro(c.stato.extra) + ' extra' : ''" />
        <Metrica style="flex:1" :nome="c.stato.extra ? 'Ancora da pagare' : 'Ancora da pagare (= il residuo: nessun extra)'"
                 :valore="euro(c.stato.da_pagare)" />
      </div>
      <Avviso v-if="c.stato.residuo < 0" tipo="attenzione">⚠️ Hai saldato <b>{{ euro(-c.stato.residuo) }} in più</b>
        dell'importo di contratto: i SAL spuntati fanno <b>{{ numeroIt(c.saldate_pct, 1) }}%</b> di un contratto che ne
        vale 100. O il contratto è stato integrato e l'importo qui sopra va aggiornato, oppure c'è una spunta di troppo.</Avviso>
      <div v-if="c.stato.extra" class="totale-oro">
        <div class="nome">Scostamento dal contratto</div>
        <div class="valore">{{ c.stato.scostamento >= 0 ? '+' : '' }}{{ numeroIt(c.stato.scostamento, 2) }} %</div>
      </div>
    </template>
    <hr>
    <p style="margin-bottom:4px"><b>📕 Chiudi l'operazione</b></p>
    <p class="didascalia">A cantiere concluso l'operazione entra nello storico, che vive <b>fuori dai progetti</b>. Da
      tre operazioni in poi lo storico smette di essere un archivio e diventa una misura: quanto sfori tu, con le tue
      imprese.</p>
    <button class="bottone primario" style="margin-bottom:16px" :disabled="!c.stato.contratto"
            @click="gesto('chiudi_operazione')">📕 Chiudi «{{ c.nome_operazione }}» e mettila nello storico</button>
    <p v-if="!c.chiuse" class="didascalia grigio">Nessuna operazione chiusa: lo storico comincia dalla prima.</p>
    <template v-else>
      <Tabella :colonne="colStorico" :righe="c.storico" />
      <div class="colonne resta" style="margin-bottom:16px">
        <Metrica v-if="c.consigliati !== null" style="flex:1"
                 :nome="'Scostamento medio su ' + c.chiuse + (c.chiuse === 1 ? ' operazione' : ' operazioni')"
                 :valore="numeroIt(c.consigliati, 2) + ' %'" />
        <Metrica v-if="c.media_mq" style="flex:1" nome="Costo medio dei lavori" :valore="numeroIt(c.media_mq, 0) + ' €/mq'" />
      </div>
      <template v-if="c.consigliati !== null">
        <Avviso v-if="c.consigliati < 0">I tuoi cantieri chiusi hanno chiuso in media <b>sotto contratto</b>
          ({{ numeroIt(c.consigliati, 2) }}%): la riserva del business plan, oggi al <b>{{ numeroIt(c.riserva, 1) }}%</b>,
          non è tarata sui tuoi fatti — è prudenza. Tienila se la vuoi, ma sappi che la stai pagando nel conto
          dell'operazione.</Avviso>
        <Avviso v-else-if="Math.abs(c.consigliati - c.riserva) > 0.5">Nel business plan la riserva per imprevisti è
          al <b>{{ numeroIt(c.riserva, 1) }}%</b>, ma i tuoi cantieri chiusi dicono <b>{{ numeroIt(c.consigliati, 2) }}%</b>.
          È la riga «Imprevisti e condominio» dello studio di fattibilità: è lì che si decide se l'affare sta in piedi.</Avviso>
        <button v-if="Math.abs(c.proposta - c.riserva) > 0.5" class="bottone"
                @click="gesto('applica_imprevisti', {percentuale: c.proposta}, {zitto: true})">
          Porta la riserva a {{ numeroIt(c.proposta, 2) }}%</button>
      </template>
    </template>
  </div>`,
});

// ------------------------------------------------------------------ MCA
const Mca = defineComponent({
  components: { CampoNumero, CampoPassi, Griglia, Metrica, Tabella, Tendina, Avviso },
  setup() {
    const m = computed(() => bpv().mca);
    const colonne = computed(() => [
      { chiave: "nome", titolo: "Comparabile", tipo: "testo", larghezza: 160, aiuto: "Es. C1 — via Roma 10" },
      { chiave: "prezzo", titolo: "Prezzo richiesto", tipo: "numero", formato: "euro", larghezza: 145, minimo: 0 },
      { chiave: "mq", titolo: "Mq commerciali", tipo: "numero", decimali: 0, larghezza: 90, minimo: 0,
        aiuto: "La stessa grandezza dei mq del soggetto: superficie commerciale, non calpestabile. È quella che scrivono gli annunci." },
      ...m.value.campi.map((c) => (c === "ascensore"
        ? { chiave: c, titolo: "Ascensore", tipo: "spunta",
            aiuto: "⚠️ Pesa più di ogni altra voce: l'ultimo piano vale 1,10 con ascensore e 0,70 senza. Non spuntato = assente." }
        : { chiave: c, titolo: m.value.tendine[c].etichetta, tipo: "scelta", opzioni: m.value.tendine[c].voci, larghezza: 130 })),
      { chiave: "coeff", titolo: "Coeff. a mano", tipo: "numero", decimali: 3, larghezza: 90, minimo: 0,
        aiuto: "Lascia VUOTO per usare il coefficiente calcolato dalle voci qui accanto. Un numero qui scavalca la griglia." },
      { chiave: "note", titolo: "Note / link annuncio", tipo: "testo", larghezza: 240 },
    ]);
    const blocchi = computed(() => {
      const c = m.value.campi, fuori = [];
      for (let i = 0; i < c.length; i += 4) fuori.push(c.slice(i, i + 4));
      return fuori;
    });
    const colEsito = ["Comparabile", "m²", "€/mq", "Coeff. merito", "Coeff. taglio", "€/mq normalizzato", "Scarto dalla mediana"]
      .map((k) => ({ chiave: k, titolo: k, num: k !== "Comparabile" }));
    const imposta = (chiave, valore) => gesto("bp", { chiave, valore }, { zitto: true });
    return { m, colonne, blocchi, colEsito, imposta, gesto, euro, numeroIt };
  },
  template: `
  <div>
    <p class="didascalia">Stima del prezzo di vendita col <b>metodo comparativo</b> (il tuo foglio «MCA sell»): per ogni
      comparabile inserisci prezzo, mq e <b>com'è fatto</b> — vetustà, finiture, piano, luminosità, riscaldamento… Il
      <b>coefficiente di merito</b> lo calcola CME dalle voci scelte (>1 = immobile migliore della media, <1 =
      peggiore); il €/mq viene normalizzato, mediato e riproporzionato sul tuo immobile. La colonna <b>Coeff. a mano</b>
      serve solo a scavalcare la griglia quando non la si condivide.</p>
    <Griglia :colonne="colonne" :righe="m.righe" dinamica obbligatoria="nome" :nuova="{ascensore: false}"
             @cambia="gesto('comparabili', {righe: $event}, {zitto: true})" />

    <h5>Il tuo immobile a lavori finiti</h5>
    <p class="didascalia grigio">Le stesse voci dei comparabili, ma sul tuo — <b>com'è quando lo vendi</b>, non com'è
      adesso: se lo ristrutturi integralmente, «Condizioni» è <i>Finemente ristrutturato</i>, non <i>Da ristrutturare</i>.</p>
    <div v-for="(b, i) in blocchi" :key="i" class="colonne resta" style="margin-bottom:12px">
      <div v-for="campo in b" :key="campo" style="flex:1">
        <label v-if="campo === 'ascensore'" class="spunta" style="margin-top:28px" title="Non spuntato = assente.">
          <input type="checkbox" :checked="m.soggetto.ascensore"
                 @change="gesto('soggetto', {campo, valore: $event.target.checked}, {zitto: true})"> Ascensore</label>
        <Tendina v-else :etichetta="m.tendine[campo].etichetta" :valore="m.soggetto[campo] || '—'"
                 :opzioni="['—', ...m.tendine[campo].voci]"
                 @cambia="gesto('soggetto', {campo, valore: $event}, {zitto: true})" />
      </div>
      <div v-for="n in 4 - b.length" :key="'v' + n" style="flex:1"></div>
    </div>

    <div class="colonne resta" style="margin-bottom:12px">
      <div style="flex:1">
        <Metrica nome="Coeff. di merito del tuo immobile" :valore="numeroIt(m.coeff_sog, 3)" />
        <p class="didascalia grigio" style="margin-top:4px">
          <template v-if="m.fonte === 'a mano'">Scritto <b>a mano</b> nel campo qui accanto.</template>
          <template v-else-if="m.fonte === 'assente'">Griglia <b>non compilata</b>: vale 1,000, cioè «nella media dei comparabili».</template>
          <template v-else>Calcolato dalle voci qui sopra.</template></p>
      </div>
      <CampoNumero style="flex:1" etichetta="Coeff. a mano (0 = usa la griglia)" :valore="m.bp.bp_coeff_sogg" :decimali="3" :massimo="3"
                   aiuto="A zero comanda la griglia qui sopra. Un numero diverso da zero la scavalca: è così che continuano a tornare i progetti salvati prima che la griglia esistesse."
                   @cambia="imposta('bp_coeff_sogg', $event)" />
      <CampoNumero style="flex:1" etichetta="Correzione per il taglio" :valore="m.bp.bp_taglio" :decimali="2" :massimo="0.6"
                   aiuto="I tagli piccoli costano di più al metro, e la griglia non ha una voce per la superficie. 0 = spenta. 0,15 = un 50 m² vale l'11% in più al metro di un 100 m². È l'unico parametro che puoi TARARE: alzalo o abbassalo e guarda la dispersione dei comparabili — se scende, quel valore descrive meglio il tuo mercato."
                   @cambia="imposta('bp_taglio', $event)" />
      <CampoNumero style="flex:1" etichetta="Sconto di trattativa (%)" :valore="m.bp.bp_sconto" :decimali="1" :massimo="30"
                   aiuto="Differenza media tra prezzo richiesto e prezzo di vendita reale (~13%)"
                   @cambia="imposta('bp_sconto', $event)" />
      <div style="flex:1">
        <Metrica nome="Mq commerciali del soggetto" :valore="numeroIt(m.mq_eff, 0) + ' m²'" />
        <p class="didascalia grigio" style="margin-top:4px">
          <template v-if="m.taglio_sog">Coeff. di taglio <b>{{ numeroIt(m.taglio_sog, 3) }}</b> — dalla superficie, non da una tendina.</template>
          <template v-else>Dal campo <b>Mq commerciali</b> dello studio di fattibilità.</template></p>
      </div>
    </div>
    <Avviso v-if="m.fonte === 'a mano' && m.dettaglio_griglia" tipo="attenzione">⚠️ Hai compilato la griglia, ma comanda
      il <b>coefficiente a mano ({{ numeroIt(m.coeff_sog, 3) }})</b>: dalle voci scelte uscirebbe
      <b>{{ numeroIt(m.calcolato, 3) }}</b>. Metti <b>0</b> in «Coeff. a mano» per usare la griglia.</Avviso>
    <p v-if="m.fonte === 'griglia' && m.mancanti.length" class="didascalia grigio">Voci non indicate, che valgono 1,00:
      <b>{{ m.mancanti.join(', ') }}</b>.</p>

    <h6>Quanto vale, qui, essere già ristrutturati</h6>
    <div class="colonne resta" style="margin-bottom:16px">
      <CampoPassi style="flex:1" etichetta="Costo lavori (€/m² comm.)" :valore="m.bp.bp_costo_ristr_mq" :passo="50" :massimo="3000"
                  aiuto="Quanto costa ristrutturare, al metro quadro COMMERCIALE (la stessa base dei €/mq della stima, non il calpestabile). A zero la voce «Stato dell'unità» resta sulla tabella fissa."
                  @cambia="imposta('bp_costo_ristr_mq', $event)" />
      <CampoPassi style="flex:1" etichetta="Quota riconosciuta (%)" :valore="m.bp.bp_quota_mercato" :passo="5" :massimo="130"
                  aiuto="Quanto di quel costo il mercato te lo ripaga sul prezzo. Non è mai tutto: chi compra da ristrutturare vuole anche il compenso per il rischio, il tempo e la seccatura."
                  @cambia="imposta('bp_quota_mercato', $event)" />
      <div style="flex:2">
        <template v-if="m.salto">
          <p class="didascalia grigio">Coi comparabili in tabella la zona sta sui <b>{{ numeroIt(m.valore_zona, 0) }} €/m²</b>
            richiesti. Su quel livello, «finemente ristrutturato» vale <b>{{ numeroIt(m.salto.finito, 3) }}</b> e «da
            ristrutturare integralmente» <b>{{ numeroIt(m.salto.grezzo, 3) }}</b>: un salto di
            <b>{{ numeroIt(m.salto.eur, 0) }} €/m²</b>, che è il costo dei lavori per la quota qui accanto.</p>
          <p class="didascalia grigio">Una tabella fissa varrebbe solo per un unico livello di prezzo: lo stesso costo
            pesa il 60% del valore in una zona da 1.500 €/m² e il 18% in una da 5.000.</p>
        </template>
        <p v-else class="didascalia grigio">Servono dei comparabili con prezzo e mq per sapere su che livello di prezzo
          sta la zona. Senza, «Stato dell'unità» resta sulla tabella fissa 0,82–1,18, che vale per una zona da ~2.500 €/m².</p>
      </div>
    </div>

    <Avviso v-if="!m.esito">Aggiungi almeno un comparabile completo (prezzo, mq e coefficiente maggiori di zero).</Avviso>
    <template v-else>
      <Tabella :colonne="colEsito" :righe="m.esito.dettaglio" />
      <Avviso v-if="m.esito.scartati" tipo="attenzione">⚠️ <b>{{ m.esito.scartati }} comparabile/i</b> incompleto/i
        <b>non entra/entrano</b> nella stima: serve che prezzo, mq e coefficiente siano tutti maggiori di zero. La media
        qui sotto è su <b>{{ m.esito.usati }}</b>.</Avviso>
      <template v-if="m.esito.usati > 1">
        <Avviso v-if="m.esito.cv <= 15" tipo="bene">✅ I €/mq normalizzati <b>convergono</b> (dispersione
          {{ numeroIt(m.esito.cv, 1) }}%): i comparabili raccontano tutti la stessa zona.</Avviso>
        <Avviso v-else-if="m.esito.cv <= 25" tipo="attenzione">⚠️ Dispersione <b>{{ numeroIt(m.esito.cv, 1) }}%</b>: i
          comparabili non concordano del tutto. Guarda gli scarti qui sopra prima di usare il numero.</Avviso>
        <Avviso v-else tipo="errore">🚨 Dispersione <b>{{ numeroIt(m.esito.cv, 1) }}%</b>: normalizzati, i comparabili
          dovrebbero dire lo stesso €/mq e non lo dicono. O non sono confrontabili, o una voce della griglia è
          sbagliata: <b>il numero non è pronto</b>.</Avviso>
      </template>
      <Avviso v-if="m.esito.outlier.length">🔎 Fuori scala di oltre il 25% dalla mediana:
        <b>{{ m.esito.outlier.join(', ') }}</b>. Spesso è una questione di taglio — i tagli piccoli costano di più al
        metro e la griglia non ha un fattore per la superficie. Con la <b>mediana</b> pesano molto meno; toglierli del
        tutto è un'altra scelta ancora, e la fai tu.</Avviso>
      <div class="colonne resta" style="margin-bottom:16px">
        <Tendina style="flex:1" etichetta="Come si riassumono" :valore="m.statistica" :opzioni="['media', 'mediana']"
                 aiuto="La mediana non si fa spostare da un comparabile fuori scala. La media è quella del foglio Excel."
                 @cambia="gesto('statistica', {valore: $event}, {zitto: true})" />
        <p class="didascalia grigio" style="flex:3;margin-top:28px">
          <b>{{ m.esito.statistica === 'media' ? 'Media aritmetica' : 'Mediana' }}</b> dei €/mq normalizzati di
          <b>{{ m.esito.usati }}</b> {{ m.esito.usati === 1 ? 'comparabile' : 'comparabili' }}: un bilocale pesa quanto un
          quadrilocale — a riproporzionare ci pensa il coefficiente di merito, non la superficie. Media
          {{ numeroIt(m.esito.eur_mq_media, 0) }} €/mq, mediana {{ numeroIt(m.esito.eur_mq_mediana, 0) }} €/mq.</p>
      </div>
      <div class="colonne resta" style="margin-bottom:16px">
        <Metrica style="flex:1" :nome="'€/mq normalizzato (' + m.esito.statistica + ', su ' + m.esito.usati + ')'"
                 :valore="numeroIt(m.esito.statistica === 'media' ? m.esito.eur_mq_media : m.esito.eur_mq_mediana, 0)" />
        <Metrica style="flex:1" nome="€/mq del soggetto" :valore="numeroIt(m.esito.eur_mq_soggetto, 0)" />
        <Metrica style="flex:1" :nome="'€/mq −' + numeroIt(m.bp.bp_sconto, 0) + '%'" :valore="numeroIt(m.esito.eur_mq_probabile, 0)" />
        <Metrica style="flex:1" nome="Valore stimato" :valore="m.esito.valore ? euro(m.esito.valore) : '—'" />
      </div>
      <button v-if="m.esito.valore" class="bottone primario"
              @click="gesto('usa_come_vendita', {valore: m.esito.valore}, {zitto: true})">
        📥 Usa come prezzo di vendita nello studio di fattibilità</button>
    </template>
  </div>`,
});

export const SchedaBp = defineComponent({
  components: { Fattibilita, Spese, Cantiere, Mca },
  props: { sotto: String },
  template: `
  <Fattibilita v-if="sotto === 'fattibilita'" />
  <Spese v-else-if="sotto === 'spese'" />
  <Cantiere v-else-if="sotto === 'cantiere'" />
  <Mca v-else />`,
});
