# CME — Computo Metrico Estimativo

App web per il settore edile, live su
<https://computometrico.streamlit.app/>:

- **Computo metrico**: il computo porta **solo le voci di questo cantiere**,
  pescate con un clic dal **pool** in fondo alla scheda (~70 voci pronte fra
  demolizioni, ricostruzioni, impianti e serramenti, con una barra di
  ricerca); una volta su, ogni voce è modificabile in tutto — descrizione,
  unità, quantità e prezzo — e le lavorazioni che il listino non ha si
  scrivono a mano, scegliendo la categoria (il codice lo mette l'app).
  Totali per categoria con incidenze percentuali,
  **imprevisti %** e IVA, salvataggio del lavoro ed export in Excel/CSV.
- **Materiali a cura del Committente**: la seconda linguetta della scheda
  Computo, con quello che compri tu e l'impresa non fornisce, per capitoli
  (bagno, porte e infissi, impianto elettrico, muratura, pavimenti,
  riscaldamento…). L'elenco nasce già pieno delle cose che si comprano su
  ogni cantiere; accanto a ognuna ci sono **fornitore**, **link** del
  negozio e **stato** dell'ordine. Ne esce l'**Allegato 1** in PDF da
  firmare con l'impresa.
- **Misura da planimetria** (stile AreaPlan): più planimetrie per progetto,
  zone colorate per categoria con percentuale commerciale, scala a vettore,
  misura pareti e riepilogo delle superfici commerciali del fabbricato.

Costruita con [Streamlit](https://streamlit.io); la logica di calcolo è
separata dall'interfaccia ed è coperta da test automatici.

## Struttura

```
CME/
├── streamlit_app.py           # interfaccia (Streamlit)
├── calcoli.py                 # logica del computo (funzioni pure, testabili)
├── planimetria.py             # geometria e superfici commerciali (pure)
├── rilevamento.py             # rilevamento automatico delle stanze (OpenCV)
├── listino.py                 # listino guida delle voci di lavorazione
├── listino_personale.py       # i tuoi prezzi, fuori dal singolo progetto
├── materiali.py               # i materiali a cura del committente (puro)
├── stampa.py                  # il computo come PDF da consegnare
├── formato.py                 # numeri e importi all'italiana (puro)
├── tabelle.py                 # colonne e conversioni tabella↔dati (puro)
├── fattibilita.py             # business plan: fattibilità, spese, MCA
├── cantiere.py                # contratto d'appalto, SAL, extra finali
├── storico.py                 # le operazioni chiuse, fuori dai progetti
├── fattura.py                 # lettura fatture PDF/XML (FatturaPA)
├── archivio.py                # archivio dei progetti su Supabase Storage
├── cme_viewer/                # componente visualizzatore planimetrie
│   ├── __init__.py            #   lato Python
│   └── frontend/              #   lato browser (canvas + barra strumenti)
├── assets/                    # logo Resolve (schermata di accesso)
├── tests/                     # test pytest sui moduli di logica
├── archivio_locale.py         # archivio dei progetti in una cartella del PC
├── requirements.txt           # librerie necessarie all'app
├── requirements-dev.txt       # come sopra + pytest (per lo sviluppo)
├── Avvia CME.bat              # avvio quotidiano (si aggiorna da sé)
├── Dockerfile                 # immagine per il deploy su Render
├── render.yaml                # ricetta del servizio su Render
└── pytest.ini
```

## Come avviare l'app sul proprio PC

**Doppio clic su `Avvia CME.bat`.** Si apre una finestra nera — è il motore,
va lasciata aperta — e il browser con l'app. Per chiudere CME si chiude la
finestra nera.

**L'aggiornamento è automatico**: a ogni avvio `Avvia CME.bat` scarica da
sé l'ultima versione del codice, poi parte. Non c'è niente da premere.

Se l'aggiornamento non riesce — niente rete, git assente, modifiche locali
non salvate — **il programma parte lo stesso** con la versione che c'è, e
scrive nella finestra nera il perché. I progetti non vengono mai toccati:
vivono in un'altra cartella.

> C'era un `Aggiorna CME.bat` da lanciare a mano. È stato tolto: un
> aggiornamento che dipende da chi si ricorda di premerlo non è un
> aggiornamento, e si finisce a lavorare per giorni sulla versione vecchia
> convinti di avere l'ultima.

### Perché nel browser e non in una finestra dedicata

C'è stata (2026-08-08/09) una versione che apriva l'app in una finestra
propria, prima con pywebview/WebView2 e poi con Edge in modalità
applicazione, impacchettata anche come `CME.exe` autonomo. **È stata
rimossa**: in quella finestra il componente della planimetria si bloccava
dopo un paio di annullamenti o cancellazioni, mentre nel browser — con lo
stesso identico codice Python, gli stessi log, nessuna eccezione — non è mai
successo.

La causa non è stata isolata; la decisione è stata di non spendere altro
tempo su un guscio che non porta funzioni, quando il browser fa lo stesso
lavoro in modo affidabile. Il codice sta nella storia di git (fino al commit
`7a91afa`) se un giorno servisse riprenderlo.

Da terminale, in alternativa:

1. Apri la cartella `CME` in Esplora File, clic destro → **Apri nel terminale**.
2. La prima volta, installa le librerie:
   ```
   python -m pip install -r requirements-dev.txt
   ```
3. Avvia l'app:
   ```
   python -m streamlit run streamlit_app.py
   ```
4. Si apre il browser su `http://localhost:8501`. Per fermare l'app torna
   nel terminale e premi `Ctrl+C`.

## Rami: lavoro e versione pubblicata

- `sviluppo` — dove si lavora ogni giorno.
- `main` — la versione **pubblicata**: Streamlit Community Cloud ripubblica
  in automatico tutto ciò che vi arriva. Ci si porta il lavoro solo quando il
  proprietario dell'app lo chiede esplicitamente.

## Come eseguire i test

Dalla cartella `CME`, nel terminale:

```
python -m pytest
```

Girano **in parallelo sui core della macchina** (`pytest-xdist`, già
configurato in `pytest.ini`): sono poco più di cinquecento e un terzo avvia
l'app intera, quindi in fila richiederebbero quattro minuti contro il minuto
scarso che ci mettono così. Per lanciarne uno solo e leggerne l'output senza
che si mescoli a quello degli altri, `-n 0` li rimette in fila:

```
python -m pytest -n 0 tests/test_calcoli.py
```

## Salvataggio del lavoro

Il bottone **Salva progetto (.json)** scarica un file con tutto il progetto:
computo **e planimetrie** (immagini incluse, con zone, pareti e scala). Per
riprendere il lavoro si ricarica quel file dal pannello **📋 Dati del
progetto · Apri / Nuovo** in cima alla scheda Computo metrico. Con le
immagini incorporate il file può pesare qualche MB.

## Archivio dei progetti

Dal pannello **📋 Dati del progetto** si apre un progetto da un menu a
tendina, lo si archivia con un nome e lo si elimina — senza scaricare e
ricaricare file a mano. L'app sceglie da sola **dove** archiviare, e lo scrive
sempre in chiaro sopra il menu:

| Dove gira l'app | Dove finiscono i progetti |
|---|---|
| Sul tuo computer | **una cartella del computer**: `~/CME/progetti`, oppure il percorso in `CME_ARCHIVIO` (`archivio_locale.py`) |
| Su Streamlit Cloud / Render, con credenziali Supabase | **bucket privato Supabase** (`archivio.py`) |

La cartella locale non ha niente da configurare e funziona senza connessione.
Il salvataggio è atomico (file temporaneo e poi rinomina): un'interruzione a
metà non lascia un progetto troncato.

### Archivio online (solo se l'app gira su un server)

Serve perché gli host di app hanno un disco **effimero**, che si azzera a ogni
riavvio: lì i progetti devono vivere fuori dall'app.

Configurazione (una volta sola):

1. Crea un progetto su [supabase.com](https://supabase.com) → **Storage** →
   nuovo bucket **privato** chiamato `progetti`.
2. **Project Settings → API**: copia il *Project URL* e la **chiave segreta**
   lato server (`service_role`, oppure `sb_secret_…` nelle chiavi nuove).
   ⚠️ Non la chiave *anon/publishable*, e mai dentro il codice.
3. Incolla le credenziali dove gira l'app:

   - **Streamlit Cloud** → *Manage app → Settings → Secrets*:
     ```toml
     [supabase]
     url = "https://xxxx.supabase.co"
     key = "…chiave segreta…"
     bucket = "progetti"
     ```
   - **Render** → *Environment*: `SUPABASE_URL`, `SUPABASE_KEY`,
     `SUPABASE_BUCKET`.
   - **In locale**: le stesse righe TOML in `.streamlit/secrets.toml`
     (già escluso da git).

## Accesso protetto

L'app può stare dietro una **password unica**, impostata in `APP_PASSWORD`
(secrets di Streamlit o variabile d'ambiente). Il cancello si attiva **solo
se la password è configurata**: senza, l'accesso resta libero e i deploy
esistenti non cambiano comportamento. Il confronto usa
`hmac.compare_digest`, a tempo costante.

## Deploy su dominio proprio (`computo.resolvesrl.com`)

Due vincoli, verificati:

- **Streamlit Community Cloud non supporta i domini personalizzati**: solo
  sottodomini `*.streamlit.app`.
- **L'hosting condiviso non fa girare Streamlit**: non è un sito di file, è
  un processo Python che deve restare acceso. Vale per Aruba come per
  Hostinger; servirebbe un VPS da amministrare.

Soluzione: l'app gira su **Render** (che legge `render.yaml` e `Dockerfile`),
il dominio resta dov'è e si aggiunge **un solo record DNS**.

1. **Render** → *New +* → **Blueprint** → repo `REsolvesrl/COMPUTO-METRICO`,
   branch `main` → *Apply*. Nasce il servizio `cme-resolve`.
2. *Environment* → aggiungi `APP_PASSWORD` e le tre variabili `SUPABASE_*`.
3. **Prima il DNS.** `resolvesrl.com` è registrato su Hostinger e usa i
   nameserver `ns1/ns2.dns-parking.com` → *hPanel → Domini → resolvesrl.com →
   DNS / Nameserver → Gestisci i record DNS* → **Aggiungi record**: tipo
   `CNAME`, nome `computo`, destinazione `<nome-servizio>.onrender.com`,
   TTL default.
4. **Poi Render**: *Settings → Custom Domains → Add Custom Domain* →
   `computo.resolvesrl.com`.
5. Il certificato HTTPS lo genera Render da sé quando la verifica passa.

⚠️ **L'ordine conta.** Se aggiungi il dominio su Render *prima* che il record
esista, il controllo riceve un «non esiste» che resta in cache per il TTL
negativo del dominio (600 s), e l'emissione del certificato fallisce anche
dopo che il record c'è. Creando prima il record, la verifica passa al primo
colpo.

⚠️ Nel pannello **non** creare `computo` come "sottodominio/sito web":
creerebbe un record verso l'hosting in conflitto con il CNAME. Serve solo il
record nella zona DNS. I record del sito e della posta (`MX` verso
`mx1/mx2.hostinger.com`) non si toccano.

> Nota: esiste anche il dominio `resolve.srl`, registrato su **Aruba** e già
> usato dal sito aziendale. Se un domani l'app dovesse stare lì, cambia solo
> il pannello dove si aggiunge il CNAME (Aruba → *Gestione DNS*).

**Memoria richiesta**: misurata in locale, l'app sta sui ~180 MB a riposo con
picchi di ~270 MB durante il rilevamento stanze su una planimetria da
2000×1500 px. I piani Render *Free* e *Starter* (512 MB) reggono una o due
sessioni per volta; per un uso contemporaneo di più persone serve il piano da
2 GB.

## Materiali a cura del Committente

La scheda **Computo metrico** ha due linguette: **📝 Il computo** e **🛒
Materiali**. La seconda è l'elenco di quello che compri tu e l'impresa non
fornisce. Non sono voci di computo e non entrano
nel totale dei lavori: quel documento è dell'impresa, e questa roba dalla
sua fattura non passa.

**L'elenco nasce già pieno**, con le voci che si comprano su ogni cantiere
di questo tipo — sanitari, rubinetteria, porte, maniglie, frutti, placche,
gres, unità di clima. Si sfoltisce quello che non serve invece di
riscriverlo ogni volta.

Ogni riga ha un **capitolo** (bagno, porte e infissi, impianto elettrico,
muratura, pavimenti, riscaldamento, cucina, arredo, esterni) — con un
pallino colorato davanti, come le categorie di spesa — la descrizione, la
quantità, e poi le colonne che servono mentre si compra:

| Colonna | A cosa serve |
| --- | --- |
| **Fornitore** | da chi lo compri |
| **Link** | la pagina del negozio, cliccabile: sei mesi dopo si ritrova **quel** modello, non una ricerca da rifare |
| **Stato** | da ordinare · ordinato · consegnato — un semaforo: rosso, giallo, verde |

⚠️ **Prezzi non ce ne sono, ed è voluto.** L'allegato firmato è un elenco di
forniture, non di importi, e i soldi dei materiali vivono già nel **registro
delle spese**, dove arrivano dalle fatture vere (categoria `MATERIALE`).
Tenerne una seconda contabilità qui vorrebbe dire due numeri per la stessa
cosa, e prima o poi due numeri diversi. Finché sono ancora un budget, si
mettono fra le **spese da sostenere** — che è anche il posto da cui il
confronto «il computo alla prova del cantiere» li legge.

Dal bottone **🖨️ Allegato 1 (da firmare)** esce il PDF: l'elenco per
capitoli, la clausola che dice che quelle forniture restano fuori
dall'appalto, «*Luogo*, lì *data*» e le due firme per accettazione. Il luogo
si scrive nel pannello **📋 Dati del progetto**. Fornitore, link e stato
dell'ordine **non** compaiono sul foglio: sono appunti tuoi, e quel foglio
lo legge l'impresa. Le **note** di una riga diventano invece la nota a piè
di pagina, richiamata da un asterisco accanto alla descrizione.

Nell'export Excel l'elenco è il foglio **Materiali**, con anche fornitore,
link e stato.

## Misura da planimetria

Nella scheda **Misura da planimetria** ogni pagina del progetto (piano
terra, piano primo…) è una planimetria; i PDF multipagina creano una pagina
per foglio. La barra strumenti sul disegno offre: ✋ sposta (con zoom a
rotellina sempre attivo), ✏️ disegno delle aree, ➤ modifica (vertici,
spostamento, eliminazione), ↔️ scala su misura nota, 🧱 misura pareti e
zoom +/−/adatta.

A ogni **categoria di superficie** (interna, balcone, garage…) sono legati
un colore e una **percentuale commerciale**: il riepilogo somma le zone di
tutte le planimetrie applicando le percentuali e calcola la **superficie
commerciale** del fabbricato, riportabile nel computo con un clic.

La geometria (calibrazione, formula di Gauss per l'area, riepilogo
superfici) vive in `planimetria.py` ed è coperta dai test.

### Dal disegno al computo

Con l'interruttore **🔗 Tieni il computo agganciato al disegno** le quantità
delle voci di listino seguono la planimetria da sé: si traccia un muro o si
cambia una spunta e il computo si aggiorna, senza premere niente. Le
quantità vengono **scritte**, non sommate, quindi il rilevamento si può
rifare quante volte si vuole; le voci non spuntate non vengono mai toccate e
una misura che scende a zero non cancella un numero battuto a mano.
Spegnendo l'interruttore torna il bottone di prima.

Le quantità arrivano già **al netto dei vani**:

| Apertura | Toglie parete da rasare e tinteggiare | Toglie battiscopa |
| --- | --- | --- |
| Porta interna | sì, due lati | sì, due lati |
| Portoncino d'ingresso | sì, un lato | sì, un lato |
| Finestra | sì, un lato | no (passa sotto il davanzale) |
| Porta finestra | sì, un lato | sì, un lato |

Ovunque si dichiara **quante** aperture ci sono, non quanti metri quadri:
i m² li fa l'app dalle misure tipo, che sono quelle correnti (porta
0,80 × 2,10, finestra 1,20 × 1,40, porta finestra 1,20 × 2,30) e si cambiano
dai campi accanto. Vale anche per i muri da demolire e da costruire, dove si
indica il **numero di vani** contenuti: dove c'è un'apertura non c'è
muratura da buttare giù né da tirare su. Nei locali *rivestiti* la fascia
piastrellata non si rasa né si tinteggia, e il loro perimetro non fa
battiscopa.

## Rilevamento automatico delle stanze (beta)

Il pulsante **🪄 Rileva stanze** analizza la planimetria con OpenCV
(visione classica, `rilevamento.py`): binarizza il disegno, sigilla i
varchi delle porte dilatando i muri, isola le regioni chiuse e ne
ricostruisce il contorno fino ai muri veri. Le stanze trovate diventano
aree proposte, da rifinire a mano con gli strumenti di modifica.

## Prossimi passi (roadmap)

- [x] Misura delle superfici da planimetria (v2).
- [x] Zoom a rotellina, più planimetrie, zone con percentuali, superficie
      commerciale (v3, stile AreaPlan).
- [x] Rilevamento automatico delle stanze (beta, OpenCV).
- [x] Pareti da demolire / costruire con aggiornamento automatico del
      computo.
- [ ] Riconoscimento muri con modelli di computer vision (fase 2).
- [x] Listino personale riutilizzabile delle voci più usate.
- [x] Stampa del computo in PDF.
- [x] Contratto e SAL, con lo sforamento finale che tara gli imprevisti.
- [x] Materiali a cura del committente, con l'Allegato 1 da firmare.
- [ ] Import da prezzari regionali (Excel/CSV).
- [ ] Spessore dei muri: distinguere tramezzi e murature portanti.
- [x] Pubblicazione su Streamlit Community Cloud.
- [x] Archivio dei progetti online (Supabase Storage).
- [x] Accesso protetto da password.
- [x] Pubblicazione su `computo.resolvesrl.com` (Render, regione Frankfurt,
      CNAME su Hostinger, HTTPS automatico).
