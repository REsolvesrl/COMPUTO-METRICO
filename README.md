# CME — Computo Metrico Estimativo

App web per redigere computi metrici estimativi nel settore edile:
voci di lavorazione con quantità calcolate dalle dimensioni, totali per
categoria con incidenze percentuali, IVA, salvataggio del lavoro ed
export in Excel/CSV.

Costruita con [Streamlit](https://streamlit.io); la logica di calcolo è
separata dall'interfaccia ed è coperta da test automatici.

## Struttura

```
CME/
├── streamlit_app.py       # interfaccia (Streamlit)
├── calcoli.py             # logica di calcolo (funzioni pure, testabili)
├── tests/test_calcoli.py  # test pytest su calcoli.py
├── requirements.txt       # librerie necessarie all'app
├── requirements-dev.txt   # come sopra + pytest (per lo sviluppo)
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

Il bottone **Salva computo (.json)** scarica un file che contiene tutto il
computo; per riprendere il lavoro si ricarica quel file dalla barra
laterale (**Apri un computo salvato**).

## Misura da planimetria

Nella scheda **Misura da planimetria** si carica un'immagine o un PDF,
si calibra la scala cliccando i due estremi di una misura nota (es. un lato
quotato) e si disegnano gli angoli di ogni stanza: il programma calcola
superficie e perimetro e li aggiunge come voce al computo. La geometria
(calibrazione e formula di Gauss per l'area) vive in `planimetria.py` ed è
coperta dai test.

## Prossimi passi (roadmap)

- [x] Misura delle superfici da planimetria (v2).
- [ ] Listino personale riutilizzabile delle voci più usate.
- [ ] Import da prezzari regionali (Excel/CSV).
- [ ] Pubblicazione su Streamlit Community Cloud.
