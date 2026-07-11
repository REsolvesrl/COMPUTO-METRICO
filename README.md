# CME — Computo Metrico Estimativo

App web per il settore edile, live su
<https://computometrico.streamlit.app/>:

- **Computo metrico**: voci di lavorazione con quantità calcolate dalle
  dimensioni, totali per categoria con incidenze percentuali, IVA,
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
├── cme_viewer/                # componente visualizzatore planimetrie
│   ├── __init__.py            #   lato Python
│   └── frontend/              #   lato browser (canvas + barra strumenti)
├── tests/                     # test pytest su calcoli.py e planimetria.py
├── requirements.txt           # librerie necessarie all'app
├── requirements-dev.txt       # come sopra + pytest (per lo sviluppo)
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
riprendere il lavoro si ricarica quel file dalla barra laterale (**Apri un
progetto salvato**). Con le immagini incorporate il file può pesare
qualche MB.

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
