// La sottoscheda «📝 Il computo»: dati del progetto e archivio, le schede
// delle categorie con le loro voci, la voce tua, il pool, il riepilogo
// costi, la tabella completa e «Salva ed esporta».
//
// Stessa pagina del vecchio, pezzo per pezzo e nello stesso ordine: chi la
// apre deve ritrovare tutto dov'era. Le ragioni di ogni scelta sono
// scritte in streamlit_app.py accanto al pezzo corrispondente; qui si
// ripetono solo dove la pagina nuova fa diversamente.
import { computed, defineComponent, reactive, ref } from "vue";
import { Avviso, CampoNumero, CampoPassi, CampoTesto, Grafico, Interruttore,
         Pannello, Popover, Tabella, Tendina } from "./componenti.js";
import { dataIt, euro, numeroIt } from "./formato.js";
import { apriFile, gesto, scarica, stato } from "./rete.js";

// Quali categorie sono aperte, nel computo e nel pool: memoria della
// pagina, non del progetto (come cat_aperte / pool_aperte nel vecchio).
const aperte = reactive({ computo: new Set(), pool: new Set() });

// ------------------------------------------------ dati del progetto
const DatiProgetto = defineComponent({
  components: { Pannello, CampoTesto, Tendina, Avviso },
  setup() {
    const v = computed(() => stato.vista);
    const scelto = ref("");
    const confermaElimina = ref(false);
    const nomeArchivio = ref("");
    const toccato = ref(false);
    const confermaSovra = ref(false);
    const confermaNuovo = ref(false);
    const fileScelto = ref(null);

    // la casella segue il nome del progetto finché non ci scrivi sopra
    const nomeProposto = computed(() => (v.value.progetto.nome || "").trim());
    const nomeVisto = computed(() => (toccato.value ? nomeArchivio.value : nomeProposto.value));
    const esisteGia = computed(() => v.value.archivio.progetti.includes(nomeVisto.value.trim()));
    const progetti = computed(() => v.value.archivio.progetti);

    function imposta(campo, valore) { gesto("imposta_progetto", { campo, valore }, { zitto: true }); }
    async function apri() {
      const nome = scelto.value || progetti.value[0];
      if (nome) await gesto("apri", { nome });
    }
    async function elimina() {
      const nome = scelto.value || progetti.value[0];
      await gesto("elimina", { nome });
      confermaElimina.value = false;
      scelto.value = "";
    }
    async function archivia() {
      const esito = await gesto("archivia", { nome: nomeVisto.value, sovrascrivi: confermaSovra.value });
      if (esito && esito.tipo === "ok") { confermaSovra.value = false; }
    }
    async function svuota() {
      await gesto("nuovo");
      confermaNuovo.value = false;
    }
    function caricaFile() { if (fileScelto.value) apriFile(fileScelto.value); }
    function quando(iso) {
      return `${iso.slice(8, 10)}/${iso.slice(5, 7)} alle `;
    }
    return { v, scelto, confermaElimina, nomeArchivio, toccato, confermaSovra, confermaNuovo,
             fileScelto, nomeVisto, esisteGia, progetti, imposta, apri, elimina, archivia,
             svuota, caricaFile, quando, gesto };
  },
  template: `
  <Pannello titolo="📋 Dati del progetto · Apri / Nuovo">
    <div class="colonne resta" style="margin-bottom:16px">
      <CampoTesto style="flex:1" etichetta="Nome del computo" :valore="v.progetto.nome"
                  segnaposto="Es. Ristrutturazione app.to Via Roma 1" @cambia="imposta('nome', $event)" />
      <CampoTesto style="flex:1" etichetta="Committente" :valore="v.progetto.committente"
                  @cambia="imposta('committente', $event)" />
    </div>
    <div class="colonne resta" style="margin-bottom:16px">
      <CampoTesto style="flex:3" etichetta="Oggetto dei lavori" :valore="v.progetto.oggetto"
                  @cambia="imposta('oggetto', $event)" />
      <CampoTesto style="flex:1.2" etichetta="Luogo" :valore="v.progetto.luogo" segnaposto="Es. La Spezia"
                  aiuto="Compare come «Luogo, lì data» sopra le firme dell'allegato materiali."
                  @cambia="imposta('luogo', $event)" />
      <CampoTesto style="flex:1" etichetta="Data" tipo="date" :valore="v.progetto.data"
                  @cambia="imposta('data', $event)" />
    </div>
    <hr>
    <p v-if="!v.testata.vuoto" class="didascalia">⚠️ Aprire un progetto <b>sostituisce</b> il lavoro in
      corso: se ti serve ancora, salvalo prima.</p>
    <div class="campo" style="margin-bottom:12px">
      <label>📂 Apri un progetto salvato (.json)</label>
      <div class="colonne centro resta">
        <input type="file" accept=".json,application/json" @change="fileScelto = $event.target.files[0]">
        <button v-if="fileScelto" class="bottone" @click="caricaFile">Carica nel programma</button>
      </div>
    </div>

    <hr>
    <p style="margin-bottom:4px"><b>💾 Progetti in archivio</b> <span class="grigio">— sul tuo computer</span></p>
    <p class="didascalia">Cartella: <code>{{ v.archivio.cartella }}</code></p>
    <Avviso v-if="v.archivio.errore" tipo="errore">Non riesco a leggere l'archivio: {{ v.archivio.errore }}</Avviso>
    <div v-if="progetti.length" class="colonne fondo resta" style="margin-bottom:12px">
      <Tendina style="flex:3" etichetta="Apri un progetto archiviato" :valore="scelto || progetti[0]"
               :opzioni="progetti" @cambia="scelto = $event" />
      <button class="bottone" style="flex:1" @click="apri">📂 Apri</button>
      <div style="flex:1;display:flex;flex-direction:column;gap:4px">
        <label class="spunta" title="Spunta e premi il cestino per rimuovere definitivamente il progetto selezionato">
          <input type="checkbox" v-model="confermaElimina"> elimina</label>
        <button class="bottone largo" :disabled="!confermaElimina" @click="elimina">🗑️</button>
      </div>
    </div>
    <p v-else class="didascalia">Nessun progetto ancora archiviato.</p>
    <div class="colonne fondo resta" style="margin-bottom:8px">
      <div class="campo" style="flex:3">
        <label>Nome con cui archiviare</label>
        <input class="casella" :value="nomeVisto" placeholder="Es. Ristrutturazione Via Roma 1"
               @input="toccato = true; nomeArchivio = $event.target.value">
      </div>
      <button class="bottone" style="flex:1" @click="archivia">💾 Archivia</button>
    </div>
    <label v-if="esisteGia && nomeVisto.trim()" class="spunta" style="margin-bottom:8px"
           title="Senza la spunta il salvataggio non parte: la versione archiviata resta quella di prima.">
      <input type="checkbox" v-model="confermaSovra"> Sovrascrivi «{{ nomeVisto.trim() }}», già presente in archivio</label>

    <hr>
    <p style="margin-bottom:4px"><b>🗑️ Nuovo progetto</b></p>
    <p class="didascalia">Il computo nuovo parte dalle voci di Migliarina, con i loro testi e prezzi e
      le quantità a zero.</p>
    <div class="colonne fondo resta">
      <label class="spunta" style="flex:3"><input type="checkbox" v-model="confermaNuovo">
        Ho capito: svuota computo, planimetrie, business plan e spese</label>
      <button class="bottone distrugge" style="flex:1" :disabled="!confermaNuovo" @click="svuota">🗑️ Svuota tutto</button>
    </div>

    <template v-if="v.archivio.versioni.length">
      <hr>
      <p style="margin-bottom:8px"><b>🕘 Versioni precedenti</b> <span class="grigio">— le ultime
        {{ v.archivio.tenute }} contando questa; riaprirne una <b>sostituisce</b> il lavoro in corso</span></p>
      <div v-for="ver in v.archivio.versioni" :key="ver.file" class="colonne centro resta" style="margin-bottom:8px">
        <span class="grigio" style="flex:4">{{ quando(ver.quando) }}<b>{{ ver.quando.slice(11, 19) }}</b> · {{ ver.kb }} KB</span>
        <button class="bottone" style="flex:1" @click="gesto('apri_versione', {file: ver.file})">↩️ Riapri</button>
      </div>
    </template>
  </Pannello>`,
});

// ------------------------------------------------------------ una riga
const RigaVoce = defineComponent({
  components: { CampoNumero, CampoPassi, Popover, Tendina },
  props: { voce: Object, categorie: Array },
  setup(props) {
    const nuovaCategoria = ref(props.voce.categoria);
    const g = (nome, argomenti) => gesto(nome, { codice: props.voce.codice, ...argomenti },
                                         { zitto: nome !== "sposta" });
    return { nuovaCategoria, g, euro };
  },
  template: `
  <div class="riga-voce">
    <Popover classe-bottone="codice-voce" aiuto="Ordine, categoria e nota della voce">
      <template #bottone>{{ voce.codice }}{{ voce.a_mano ? ' ✎' : '' }}<span class="freccia">⌄</span></template>
      <p style="margin-bottom:.6rem"><b>{{ voce.codice }}</b> · {{ voce.descrizione }}</p>
      <template v-if="voce.a_mano">
        <p class="didascalia arancio">✎ Quantità scritta a mano: il disegno non la aggiorna più.</p>
        <button class="bottone largo" @click="g('riaggancia')">↺ Riaggancia al disegno</button>
      </template>
      <div class="fila">
        <button class="bottone" title="Scambia con la voce sopra, nella sua categoria" @click="g('scambia', {verso: -1})">↑ Su</button>
        <button class="bottone" title="Scambia con la voce sotto, nella sua categoria" @click="g('scambia', {verso: 1})">↓ Giù</button>
      </div>
      <template v-if="voce.tua">
        <hr>
        <Tendina etichetta="Sposta nella categoria" :valore="nuovaCategoria" :opzioni="categorie"
                 @cambia="nuovaCategoria = $event" />
        <button class="bottone" style="margin-top:8px" title="Il codice cambia con la categoria: la serie dice dove sta di casa la voce."
                @click="g('sposta', {categoria: nuovaCategoria})">↔️ Sposta</button>
      </template>
      <template v-if="voce.aiuto"><hr><p class="didascalia" style="white-space:pre-line">{{ voce.aiuto }}</p></template>
    </Popover>
    <textarea class="casella" rows="1" :value="voce.descrizione" :aria-label="'Descrizione ' + voce.codice"
              @change="g('descrizione', {testo: $event.target.value})"></textarea>
    <select class="casella" :value="voce.um" :aria-label="'Unità ' + voce.codice"
            @change="g('unita', {um: $event.target.value})">
      <option v-for="u in voce.unita" :key="u" :value="u">{{ u }}</option>
    </select>
    <CampoPassi v-if="voce.a_passi" :valore="voce.quantita" @cambia="g('quantita', {valore: $event})" />
    <CampoNumero v-else :valore="voce.quantita" :decimali="2" @cambia="g('quantita', {valore: $event})" />
    <CampoNumero :valore="voce.prezzo" :decimali="2" @cambia="g('prezzo', {valore: $event})" />
    <div class="parziale" :class="{vuoto: voce.parziale === null}">
      {{ voce.parziale === null ? 'da quantificare' : euro(voce.parziale) }}</div>
    <button class="togli" title="Rimanda la voce nel pool" @click="g('togli')">✕</button>
  </div>`,
});

// ----------------------------------------------------- scheda categoria
const SchedaCategoria = defineComponent({
  components: { RigaVoce },
  props: { cat: Object, categorie: Array },
  setup(props) {
    const aperta = computed(() => aperte.computo.has(props.cat.nome));
    function scambia() {
      const s = new Set(aperte.computo);
      if (s.has(props.cat.nome)) s.delete(props.cat.nome); else s.add(props.cat.nome);
      aperte.computo = s;
    }
    const classeNome = computed(() => ({ red: "rosso", green: "verde", blue: "azzurro",
      orange: "arancio", violet: "viola" }[props.cat.md] || ""));
    return { aperta, scambia, classeNome, euro };
  },
  template: `
  <section class="scheda-cat" :class="{aperta}" :style="{'--tinta': cat.colore, '--su-tinta': cat.su_tinta}">
    <button class="testa" @click="scambia" :aria-expanded="aperta">
      <span class="pastiglia">{{ String(cat.serie).padStart(2, '0') }}</span>
      <span class="nome-cat" :class="classeNome">{{ aperta ? '▾' : '▸' }} {{ cat.nome }}</span>
      <span class="totale-cat">{{ euro(cat.totale) }}</span>
    </button>
    <div v-if="aperta" class="righe-voci">
      <template v-if="cat.voci.length">
        <div class="riga-voce intestazione">
          <span>Cod.</span><span>Voce</span><span>U.M.</span><span>Quantità</span><span>Prezzo €</span>
          <span class="intestazione-parziale">Parziale</span><span></span>
        </div>
        <RigaVoce v-for="voce in cat.voci" :key="voce.codice + voce.categoria" :voce="voce" :categorie="categorie" />
      </template>
      <p v-else class="didascalia grigio" style="padding:.3rem 0">Nessuna voce in questa categoria.
        Prendile dal pool in fondo alla pagina.</p>
    </div>
  </section>`,
});

// ------------------------------------------------- una voce tua
const AggiungiVoce = defineComponent({
  components: { Pannello, Tendina, CampoTesto, CampoNumero },
  setup() {
    const c = computed(() => stato.vista.computo);
    const nuova = reactive({ categoria: "", descrizione: "", um: "", quantita: 0, prezzo: 0 });
    const categoria = computed(() => nuova.categoria || c.value.categorie_accese[0]);
    const unita = computed(() => c.value.unita_per_categoria[categoria.value] || []);
    const um = computed(() => (unita.value.includes(nuova.um) ? nuova.um : unita.value[0]));
    function cambiaCategoria(v) { nuova.categoria = v; nuova.um = ""; }
    function cambiaUnita(v) {
      nuova.um = v;
      // «a corpo»: la quantità si propone da sé, 1 — solo se era vuota
      if (v === c.value.um_a_corpo && !nuova.quantita) nuova.quantita = 1;
    }
    async function crea() {
      const esito = await gesto("crea_voce", { categoria: categoria.value, descrizione: nuova.descrizione,
        um: um.value, quantita: nuova.quantita, prezzo: nuova.prezzo });
      if (esito && esito.tipo === "ok") {
        aperte.computo = new Set([...aperte.computo, categoria.value]);
        nuova.descrizione = "";
      }
    }
    return { c, nuova, categoria, unita, um, cambiaCategoria, cambiaUnita, crea };
  },
  template: `
  <div class="scheda-aggiungi">
  <Pannello>
    <template #titolo><b>➕ Aggiungi una voce tua</b></template>
    <p class="didascalia">Va nella categoria che scegli, insieme alle altre. Il codice lo mette l'app,
      nella serie della categoria. Con <b>a corpo</b> la quantità si propone da sé — <b>1</b>, il prezzo
      è già l'importo — e la puoi cambiare.</p>
    <div class="colonne resta" style="margin-bottom:12px">
      <Tendina style="flex:1" etichetta="Categoria" :valore="categoria" :opzioni="c.categorie_accese"
               @cambia="cambiaCategoria" />
      <CampoTesto style="flex:2" etichetta="Descrizione" :valore="nuova.descrizione"
                  segnaposto="Es. Allestimento del cantiere" @cambia="nuova.descrizione = $event" />
    </div>
    <div class="colonne fondo resta">
      <Tendina style="flex:1" etichetta="U.M." :valore="um" :opzioni="unita" @cambia="cambiaUnita" />
      <CampoNumero style="flex:1" etichetta="Quantità" :valore="nuova.quantita" @cambia="nuova.quantita = $event" />
      <CampoNumero style="flex:1" etichetta="Prezzo €" :valore="nuova.prezzo" @cambia="nuova.prezzo = $event" />
      <button class="bottone primario" style="flex:1.1" @click="crea">➕ Al computo</button>
    </div>
  </Pannello>
  </div>`,
});

// ------------------------------------------------------------ il pool
const Pool = defineComponent({
  setup() {
    const c = computed(() => stato.vista.computo);
    const termine = ref("");
    // la stessa ricerca di voce_trovata: tutte le parole, su codice,
    // descrizione, unità e nota
    function trovata(voce) {
      const t = termine.value.trim().toLowerCase();
      if (!t) return true;
      const testo = `${voce.codice} ${voce.descrizione} ${voce.um} ${voce.nota}`.toLowerCase();
      return t.split(/\s+/).every((p) => testo.includes(p));
    }
    const categorie = computed(() => c.value.pool
      .map((cat) => ({ ...cat, disponibili: cat.voci.filter(trovata) }))
      .filter((cat) => cat.disponibili.length));
    const quante = computed(() => categorie.value.reduce((n, cat) => n + cat.disponibili.length, 0));
    function aperta(nome) { return !!termine.value.trim() || aperte.pool.has(nome); }
    function scambia(nome) {
      const s = new Set(aperte.pool);
      if (s.has(nome)) s.delete(nome); else s.add(nome);
      aperte.pool = s;
    }
    const colore = (md) => ({ red: "rosso", green: "verde", blue: "azzurro", orange: "arancio",
                              violet: "viola" }[md] || "");
    return { c, termine, categorie, quante, aperta, scambia, colore, gesto, euro };
  },
  template: `
  <div class="scheda-pool">
    <p class="titolo-pool">🧰 <b>Pool voci</b> · scegli cosa portare nel computo</p>
    <button class="bottone" style="margin-bottom:12px" @click="gesto('prendi_tutte', {}, {zitto: true})"
            title="Porta nel computo tutte le voci del listino non ancora scelte né scartate su questo progetto — non tocca quelle che hai già deciso.">
      📥 Prendi tutte le voci del listino</button>
    <input class="casella" style="margin-bottom:12px" v-model="termine"
           placeholder="🔎  Cerca fra le voci — codice, descrizione, unità" aria-label="Cerca una voce">
    <template v-for="cat in categorie" :key="cat.nome">
      <button class="cat-pool" @click="scambia(cat.nome)">
        <span :class="colore(cat.md)">{{ aperta(cat.nome) ? '▾' : '▸' }} {{ cat.nome }}</span>
        <span class="grigio"> · {{ cat.disponibili.length }}</span>
      </button>
      <template v-if="aperta(cat.nome)">
        <div v-for="voce in cat.disponibili" :key="voce.codice" class="voce-pool">
          <button class="prendi" title="Porta la voce nel computo"
                  @click="gesto('porta', {codice: voce.codice}, {zitto: true})">＋</button>
          <span :title="voce.nota"><span class="grigio"><b>{{ voce.codice }}</b></span> {{ voce.descrizione }}
            <span class="grigio">· {{ voce.um }}</span><span v-if="voce.tua" class="arancio"> · tua</span></span>
          <span class="grigio">{{ euro(voce.prezzo) }}</span>
          <button class="cestina" title="Togli la voce dal pool di questo progetto (si rimette dal fondo)"
                  @click="gesto('scarta', {codice: voce.codice}, {zitto: true})">🗑</button>
        </div>
      </template>
    </template>
    <div v-if="c.scartate" class="colonne centro resta" style="margin:8px 0">
      <p class="didascalia grigio" style="flex:4;margin:0">🗑 {{ c.scartate }}
        {{ c.scartate === 1 ? 'voce scartata' : 'voci scartate' }} da questo progetto — il listino non è stato toccato</p>
      <button class="bottone" style="flex:1" @click="gesto('ripristina_scarti', {}, {zitto: true})">↩️ Rimetti tutte</button>
    </div>
    <p v-if="!quante" class="didascalia grigio">
      <template v-if="!termine.trim()">Nessuna voce da aggiungere: sono già tutte nel computo.</template>
      <template v-else>Nessuna voce trovata per «{{ termine.trim() }}». Le voci che hai già preso non
        compaiono qui: cercale nel computo qui sopra.</template>
    </p>
  </div>`,
});

// ---------------------------------------------------- il mio listino
const MioListino = defineComponent({
  components: { Pannello },
  setup() {
    const l = computed(() => stato.vista.computo.listino_personale);
    const conferma = ref(false);
    const titolo = computed(() => (l.value.salvati
      ? `📓 Il mio listino — ${l.value.salvati} prezzi${l.value.quando ? `, aggiornato il ${l.value.quando}` : ""}`
      : "📓 Il mio listino — non ancora salvato"));
    async function cancella() { await gesto("elimina_listino"); conferma.value = false; }
    return { l, conferma, titolo, gesto, cancella };
  },
  template: `
  <Pannello :titolo="titolo">
    <p class="didascalia">I prezzi del listino guida sono indicativi: quando li correggi valgono <b>solo
      per questo progetto</b>. Qui li metti da parte una volta sola e li ritrovi in tutti i progetti che
      verranno. Si salvano <b>solo quelli che hai cambiato</b>: le voci che non hai toccato continuano a
      seguire il listino guida.</p>
    <div class="colonne resta" style="margin-bottom:12px">
      <button class="bottone" style="flex:1" :disabled="!l.miei" @click="gesto('salva_listino')"
              title="Sovrascrive il listino personale con i prezzi che hai corretto qui.">
        💾 Salva i {{ l.miei }} prezzi di questo progetto</button>
      <button class="bottone" style="flex:1" :disabled="!l.da_applicare" @click="gesto('applica_listino')"
              title="Riscrive i prezzi di questo progetto con i tuoi. Le quantità non si toccano.">
        📥 Applica il mio listino ({{ l.da_applicare }} voci)</button>
    </div>
    <p v-if="!l.miei && !l.salvati" class="didascalia grigio">Correggi il prezzo di qualche voce qui
      sotto: poi potrai metterlo da parte.</p>
    <p v-else-if="l.salvati && !l.da_applicare" class="didascalia verde">Questo progetto usa già i tuoi prezzi.</p>
    <template v-if="l.salvati">
      <label class="spunta"><input type="checkbox" v-model="conferma"> Voglio cancellare il mio listino</label>
      <button v-if="conferma" class="bottone distrugge" style="margin-top:8px" @click="cancella">🗑️ Cancella il listino personale</button>
    </template>
  </Pannello>`,
});

// --------------------------------------------------- riepilogo costi
const Riepilogo = defineComponent({
  components: { CampoNumero, Grafico },
  setup() {
    const r = computed(() => stato.vista.computo.riepilogo);
    function iva(v) { gesto("imposta_progetto", { campo: "aliquota_iva", valore: v }, { zitto: true }); }
    return { r, euro, numeroIt, iva };
  },
  template: `
  <div class="riepilogo">
    <h4>💰 Riepilogo costi</h4>
    <p v-if="r.totale === 0" class="didascalia">Inserisci le quantità nelle categorie per vedere la
      distribuzione dei costi.</p>
    <div v-for="riga in r.righe" :key="riga.nome" class="riga-dot">
      <span><span class="dot" :style="{background: riga.colore}"></span>{{ riga.nome }}</span>
      <b>{{ euro(riga.importo) }}</b>
    </div>
    <hr>
    <div class="metrica" style="margin-bottom:16px">
      <div class="nome">Totale lavori (IVA esclusa)</div><div class="valore">{{ euro(r.totale) }}</div>
    </div>
    <CampoNumero etichetta="Aliquota IVA (%)" :valore="r.aliquota_iva" :decimali="2" :massimo="100"
                 aiuto="10% ristrutturazioni (predefinita), 22% ordinaria, 4% prima casa"
                 @cambia="iva" style="margin-bottom:16px" />
    <div class="metrica" style="margin-bottom:16px">
      <div class="nome">IVA {{ numeroIt(r.aliquota_iva, 0) }}%</div><div class="valore">{{ euro(r.iva) }}</div>
    </div>
    <div class="totale-oro">
      <div class="nome">Totale finale · IVA inclusa</div>
      <div class="valore">{{ euro(r.totale_con_iva) }}</div>
    </div>
    <Grafico v-if="r.grafico" :figura="r.grafico" />
  </div>`,
});

// -------------------------------------------------- salva ed esporta
const SalvaEsporta = defineComponent({
  components: { Pannello, Tabella },
  setup() {
    const v = computed(() => stato.vista);
    const colonne = [
      { chiave: "categoria", titolo: "Categoria" }, { chiave: "codice", titolo: "Codice" },
      { chiave: "descrizione", titolo: "Descrizione" }, { chiave: "um", titolo: "U.M." },
      { chiave: "quantita", titolo: "Quantità", num: true }, { chiave: "prezzo", titolo: "Prezzo unit.", num: true },
      { chiave: "importo", titolo: "Importo", num: true }];
    // due decimali come nelle righe e nel PDF
    const righe = computed(() => v.value.computo.tabella.map((r) => ({
      ...r, quantita: numeroIt(r.quantita, 2), prezzo: euro(r.prezzo), importo: euro(r.importo) })));
    return { v, colonne, righe, scarica };
  },
  template: `
  <div>
    <Pannello v-if="v.computo.tabella.length" titolo="📄 Computo calcolato (tabella completa)">
      <Tabella :colonne="colonne" :righe="righe" />
    </Pannello>
    <h3 class="sottotitolo">💾 Salva ed esporta</h3>
    <p class="didascalia">Il file <b>.json</b> è il salvataggio del lavoro (comprese le planimetrie):
      conservalo e ricaricalo dal pannello <b>📋 Dati del progetto · Apri / Nuovo</b> in cima alla pagina.
      Il <b>PDF</b> è il computo completo, con i totali e le firme; il <b>PDF senza prezzi</b> è lo stesso
      elenco di lavorazioni e quantità da mandare alle imprese perché ci facciano il preventivo. Excel e
      CSV servono a rielaborare i numeri. L'<b>Allegato 1 dei materiali</b> si scarica dalla sua sezione:
      è un documento suo, e si firma a parte.</p>
    <p>
      <template v-if="v.testata.stato === 'mai' || v.testata.stato === 'vuoto'"><b class="arancio">Mai
        salvato in questa sessione.</b> Il tasto 💾 Salva in cima alla pagina scrive in archivio, ed è da lì
        che l'app riapre da sola al prossimo avvio. Il .json è la copia da portarsi altrove.</template>
      <template v-else-if="v.testata.stato === 'modificato'"><b class="arancio">Modifiche non salvate.</b>
        Ultimo salvataggio alle {{ v.testata.salvato_alle }}.</template>
      <template v-else><b class="verde">Salvato</b> alle {{ v.testata.salvato_alle }}: sei in pari.</template>
    </p>
    <div class="colonne resta" style="flex-wrap:wrap">
      <button class="bottone primario" style="flex:1" @click="scarica('json')">💾 Salva progetto (.json)</button>
      <button class="bottone" style="flex:1" @click="scarica('pdf')"
              title="Il computo come documento da consegnare: le voci per categoria, i totali e le firme.">🖨️ Stampa PDF</button>
      <button class="bottone" style="flex:1" @click="scarica('pdf_senza_prezzi')"
              title="Da mandare alle imprese per il preventivo: lavorazioni e quantità, senza prezzi né importi.">📄 PDF senza prezzi</button>
      <button class="bottone" style="flex:1" @click="scarica('xlsx')"
              title="Fogli: Computo, Riepilogo, Materiali, Superfici e Dati progetto.">📊 Esporta Excel (.xlsx)</button>
      <button class="bottone" style="flex:1" @click="scarica('csv')">📄 Esporta CSV</button>
    </div>
  </div>`,
});

// ============================================================ la scheda
export const SchedaComputo = defineComponent({
  components: { DatiProgetto, SchedaCategoria, AggiungiVoce, Pool, MioListino, Riepilogo,
                SalvaEsporta, Interruttore, Avviso, Popover },
  setup() {
    const v = computed(() => stato.vista);
    const c = computed(() => stato.vista.computo);
    async function annulla() { await gesto("annulla_computo"); }
    function facoltativo(nome, acceso) { gesto("facoltativo", { categoria: nome, acceso }, { zitto: true }); }
    return { v, c, annulla, facoltativo, gesto, dataIt };
  },
  template: `
  <div>
    <div v-if="v.ripreso" class="colonne centro resta" style="margin-bottom:16px">
      <Avviso style="flex:4;margin:0">↩️ Ripreso <b>{{ v.ripreso.nome }}</b>, salvato il
        {{ v.ripreso.quando.slice(8, 10) }}/{{ v.ripreso.quando.slice(5, 7) }} alle {{ v.ripreso.quando.slice(11, 16) }}.</Avviso>
      <Popover style="flex:1" classe-bottone="bottone largo">
        <template #bottone>Progetto nuovo ⌄</template>
        <p>Svuota <b>computo, planimetrie, business plan e spese</b>.</p>
        <p>Le planimetrie perdono la scala calibrata e le zone disegnate a mano: l'annulla non le riporta indietro.</p>
        <p>Il computo nuovo parte dalle voci di Migliarina, con i loro testi e prezzi e le quantità a zero.</p>
        <button class="bottone distrugge largo" @click="gesto('nuovo')">🗑️ Sì, svuota tutto</button>
      </Popover>
    </div>
    <DatiProgetto />
    <div class="colonne" style="gap:2rem">
      <div style="flex:2.9">
        <div v-if="c.storia" class="colonne centro resta" style="margin-bottom:16px">
          <button class="bottone" style="flex:1" @click="annulla"
                  title="Torna indietro di un passo su quantità e prezzi del computo. Non tocca le planimetrie.">
            ↩️ Annulla ({{ c.storia.passi }})</button>
          <p class="didascalia" style="flex:3;margin:0">Ultima operazione sul computo: <b>{{ c.storia.ultima }}</b></p>
        </div>
        <MioListino />
        <div class="colonne centro resta" style="margin-bottom:16px">
          <p class="didascalia" style="flex:1.6;margin:0">Lavori che non ci sono in ogni cantiere:</p>
          <div v-for="f in c.facoltative" :key="f.nome" style="flex:1">
            <Interruttore :acceso="f.acceso" :etichetta="f.nome" @cambia="facoltativo(f.nome, $event)"
                          :aiuto="'Acceso: la categoria ' + f.nome + ' entra nel computo, nei totali e in stampa. Spento: sparisce, ma voci, quantità e prezzi restano da parte.'" />
          </div>
        </div>
        <SchedaCategoria v-for="cat in c.categorie" :key="cat.nome" :cat="cat" :categorie="c.categorie_accese" />
        <AggiungiVoce />
        <Pool />
      </div>
      <div style="flex:1.1"><Riepilogo /></div>
    </div>
    <SalvaEsporta />
  </div>`,
});
