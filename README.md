# CME — Computo Metrico Estimativo

Programma per il settore edile, che gira sul computer e si usa dal browser:

- **Computo metrico**: un progetto nuovo porta nel computo, a quantità
  zero, le **84 voci dei nostri cantieri** (ENI e La Spezia Migliarina, coi
  loro testi e prezzi): si toglie quello che non serve. Il **pool** in fondo
  alla scheda ha il resto del listino (137 voci in tutto, con una barra di
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

Un motore Python ([FastAPI](https://fastapi.tiangolo.com)) tiene aperto il
progetto e fa i conti; la pagina (Vue 3, senza assemblatore) li mostra. La
logica di calcolo è separata dall'interfaccia ed è coperta da test
automatici. Fino al 25 settembre 2026 l'interfaccia era Streamlit: com'è
avvenuto il passaggio, e che cosa è rimasto uguale, in
[VERSIONE-NUOVA.md](VERSIONE-NUOVA.md).

## Struttura

```
CME/
├── server/                    # il motore: rotte FastAPI e la vista
├── web/                       # la pagina (Vue 3, niente npm)
├── banco.py                   # il progetto aperto e i gesti del computo
├── banco_disegno.py           #   … della planimetria
├── banco_bp.py                #   … del business plan
├── costanti.py                # colori, categorie, voci agganciate al disegno
├── calcoli.py                 # logica del computo (funzioni pure, testabili)
├── planimetria.py             # geometria e superfici commerciali (pure)
├── rilevamento.py             # rilevamento automatico delle stanze (OpenCV)
├── listino.py                 # listino guida delle voci di lavorazione
├── listino_personale.py       # i tuoi prezzi, fuori dal singolo progetto
├── modello_computo.py         # da dove parte un progetto nuovo (Migliarina)
├── materiali.py               # i materiali a cura del committente (puro)
├── stampa.py                  # il computo come PDF da consegnare
├── esporta.py                 # PDF, Excel, CSV, Allegato 1
├── grafici.py                 # le figure Plotly
├── formato.py                 # numeri e importi all'italiana (puro)
├── tabelle.py                 # colonne e conversioni tabella↔dati (puro)
├── fattibilita.py             # business plan: fattibilità, spese, MCA
├── merito.py                  # la griglia dei coefficienti di merito (MCA)
├── cantiere.py                # contratto d'appalto, SAL, extra finali
├── storico.py                 # le operazioni chiuse, fuori dai progetti
├── fattura.py                 # lettura fatture PDF/XML (FatturaPA)
├── tavola.py                  # la planimetria disegnata, per la stampa
├── uso.py                     # registro d'uso (uguale in MORA e CATASTO)
├── archivio_locale.py         # archivio dei progetti in una cartella del PC
├── cme_viewer/frontend/       # la tela delle planimetrie (canvas + strumenti)
├── assets/                    # logo RESolve
├── tests/                     # test pytest
├── requirements.txt           # librerie necessarie
├── requirements-dev.txt       # come sopra + pytest (per lo sviluppo)
├── Avvia CME.bat              # avvio quotidiano (si aggiorna da sé)
└── pytest.ini
```

## Come avviare l'app sul proprio PC

> **Dal 24 settembre 2026 CME è la versione nuova**: motore FastAPI e pagina
> Vue al posto di Streamlit, stesse schede, stessa grafica, stesso archivio
> (`~/CME/progetti`) e stesso formato dei file. La versione a Streamlit è
> stata tolta il 25 settembre. Tutto il resto in
> [VERSIONE-NUOVA.md](VERSIONE-NUOVA.md).

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
3. Avvia il motore:
   ```
   python -m uvicorn server.principale:app --host 127.0.0.1 --port 8504
   ```
4. Apri il browser su `http://127.0.0.1:8504`. Per fermarlo torna nel
   terminale e premi `Ctrl+C`.

## Rami: lavoro e versione pubblicata

- `sviluppo` — dove si lavora ogni giorno, ed è quello che `Avvia CME.bat`
  scarica.
- `main` — era la versione **pubblicata** online (Streamlit Community Cloud,
  poi Render). Il programma online non serve più (24/09/2026) e `main` è
  rimasto com'era: non ci si porta niente.

## Come eseguire i test

Dalla cartella `CME`, nel terminale:

```
python -m pytest
```

Girano **in parallelo sui core della macchina** (`pytest-xdist`, già
configurato in `pytest.ini`) e durano pochi secondi. Per lanciarne uno solo
e leggerne l'output senza che si mescoli a quello degli altri, `-n 0` li
rimette in fila:

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

I progetti stanno in **una cartella del computer**: `~/CME/progetti`,
oppure il percorso in `CME_ARCHIVIO` (`archivio_locale.py`). La cartella non ha niente da configurare e funziona senza connessione.
Il salvataggio è atomico (file temporaneo e poi rinomina): un'interruzione a
metà non lascia un progetto troncato.

> Finché CME girava anche online c'erano un archivio su Supabase Storage,
> una password d'accesso e il servizio su Render con il dominio
> `computo.resolvesrl.com`. Non servono più (24/09/2026) e il codice se n'è
> andato col programma a Streamlit; come erano configurati sta nella storia
> di git di questo file.

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
- [x] Pubblicazione online (Streamlit Cloud, poi Render), archivio su
      Supabase, accesso con password — poi tolti: CME gira sul computer.
- [x] Motore FastAPI e pagina Vue al posto di Streamlit (24-25/09/2026).
