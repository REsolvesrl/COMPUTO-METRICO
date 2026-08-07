# CME — Computo Metrico Estimativo

App web per il settore edile, live su
<https://computometrico.streamlit.app/>:

- **Computo metrico**: voci di lavorazione con quantità calcolate dalle
  dimensioni, **listino guida** con ~50 voci pronte (demolizioni,
  ricostruzioni, impianti, serramenti…) a prezzi indicativi modificabili,
  totali per categoria con incidenze percentuali, **imprevisti %** e IVA,
  salvataggio del lavoro ed export in Excel/CSV.
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
├── fattibilita.py             # business plan: fattibilità, spese, MCA
├── fattura.py                 # lettura fatture PDF/XML (FatturaPA)
├── archivio.py                # archivio dei progetti su Supabase Storage
├── cme_viewer/                # componente visualizzatore planimetrie
│   ├── __init__.py            #   lato Python
│   └── frontend/              #   lato browser (canvas + barra strumenti)
├── assets/                    # logo Resolve (schermata di accesso)
├── tests/                     # test pytest sui moduli di logica
├── requirements.txt           # librerie necessarie all'app
├── requirements-dev.txt       # come sopra + pytest (per lo sviluppo)
├── Dockerfile                 # immagine per il deploy su Render
├── render.yaml                # ricetta del servizio su Render
└── pytest.ini
```

## Come avviare l'app sul proprio PC

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

## Come eseguire i test

Dalla cartella `CME`, nel terminale:

```
python -m pytest
```

## Salvataggio del lavoro

Il bottone **Salva progetto (.json)** scarica un file con tutto il progetto:
computo **e planimetrie** (immagini incluse, con zone, pareti e scala). Per
riprendere il lavoro si ricarica quel file dal pannello **📋 Dati del
progetto · Apri / Nuovo** in cima alla scheda Computo metrico. Con le
immagini incorporate il file può pesare qualche MB.

## Archivio online dei progetti (Supabase)

Per non scaricare e ricaricare il JSON a ogni sessione, l'app può tenere i
progetti in un **bucket privato di Supabase Storage**: dallo stesso pannello
si apre un progetto da un menu a tendina, lo si salva con un nome e lo si
elimina. Se le credenziali non ci sono, l'app funziona lo stesso e mostra un
avviso: l'archivio è un di più, non un requisito.

Perché serve un archivio esterno: gli host di app (Streamlit Cloud, Render)
hanno un disco **effimero**, che si azzera a ogni riavvio. I progetti devono
vivere fuori dall'app.

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

## Deploy su dominio proprio (es. `cme.resolve.srl`)

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
3. *Settings → Custom Domains* → aggiungi `cme.resolve.srl`: Render mostra il
   valore CNAME da usare.
4. **Aruba** (il dominio `resolve.srl` è lì) → *Gestione DNS* → **Aggiungi
   record** → tipo `CNAME`, nome host `cme`, destinazione il valore dato da
   Render → *Aggiungi* → *Prosegui* → **Salva configurazione** → *Conferma*.
5. Torna su Render e clicca **Verify**. Il certificato HTTPS lo genera Render.

⚠️ Su Aruba **non** creare `cme` come "sottodominio/sito web": creerebbe un
record verso l'hosting Aruba in conflitto con il CNAME. Serve solo il record
nella zona DNS. I record del sito (`resolve.srl`) e della posta (`MX`) non si
toccano.

**Memoria richiesta**: misurata in locale, l'app sta sui ~180 MB a riposo con
picchi di ~270 MB durante il rilevamento stanze su una planimetria da
2000×1500 px. I piani Render *Free* e *Starter* (512 MB) reggono una o due
sessioni per volta; per un uso contemporaneo di più persone serve il piano da
2 GB.

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
- [ ] Pareti da demolire / costruire con aggiornamento automatico del
      computo.
- [ ] Riconoscimento muri con modelli di computer vision (fase 2).
- [ ] Listino personale riutilizzabile delle voci più usate.
- [ ] Import da prezzari regionali (Excel/CSV).
- [x] Pubblicazione su Streamlit Community Cloud.
- [x] Archivio dei progetti online (Supabase Storage).
- [x] Accesso protetto da password.
- [ ] Pubblicazione su `cme.resolve.srl` (Render + CNAME su Aruba).
