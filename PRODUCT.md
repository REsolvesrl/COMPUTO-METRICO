# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Un solo utente: il titolare di Resolve S.r.l. (società immobiliare italiana), che usa CME come strumento di lavoro interno per le proprie operazioni di compravendita + ristrutturazione. Nessun collaboratore o cliente esterno usa l'app oggi; la presentabilità verso terzi non è un requisito confermato.

## Product Purpose

CME (Computo Metrico Estimativo) è un'app web Streamlit, live su <https://computometrico.streamlit.app/>, che copre due lavori ugualmente centrali (confermato dall'utente):

1. **Valutare operazioni immobiliari** — decidere se un acquisto + ristrutturazione conviene: studio di fattibilità / business plan (costi di acquisto e vendita, EBIT, money multiple, ROE, rendimento annualizzato, matrici di sensitività), MCA (market comparison approach), registro spese a consuntivo con confronto preventivo/consuntivo.
2. **Preventivare ristrutturazioni** — produrre il computo metrico: voci di lavorazione con quantità calcolate dalle dimensioni, listino guida (~50 voci a prezzi indicativi modificabili), totali per categoria con incidenze, imprevisti % e IVA, export Excel/CSV.

Successo = decisioni d'investimento rapide e numeri affidabili, senza tornare ai fogli Excel che l'app sostituisce.

## Positioning

Sostituisce i fogli Excel personali dell'utente ("Studio fattibilità" + "MCA sell") replicandone i numeri esatti ma con calcoli sempre "vivi" (le Data Table dell'Excel restavano stantie) e integrandoli con computo metrico e misura da planimetria nello stesso strumento: dall'affare valutato al cantiere preventivato senza cambiare file.

## Operating Context

- Flusso tipico: valutazione dell'affare (business plan / MCA) → computo metrico della ristrutturazione → misura delle superfici da planimetria (PDF o immagine) → durante il cantiere, registrazione delle spese a consuntivo caricando le fatture (XML FatturaPA o PDF di cortesia SdI, estrazione automatica dei campi, tutto in locale).
- Misura da planimetria in stile AreaPlan: più planimetrie per progetto, zone colorate per categoria di superficie con percentuale commerciale, scala su misura nota, misura pareti, riepilogo della superficie commerciale riportabile nel computo; rilevamento automatico stanze (beta, OpenCV).
- Salvataggio: file .json scaricabile (planimetrie incluse) e archivio online su Supabase Storage (bucket privato, credenziali nei secrets di Streamlit).
- Deploy su Streamlit Community Cloud; sviluppo locale con `python -m streamlit run streamlit_app.py`, test con pytest.

## Capabilities and Constraints

- Stack: Python + Streamlit; logica di calcolo separata dall'interfaccia in moduli puri e testati (calcoli.py, planimetria.py, fattibilita.py, fattura.py); componente browser custom per il visualizzatore planimetrie (cme_viewer/, canvas + barra strumenti).
- Vincolo architetturale: la logica resta in funzioni pure coperte da pytest; l'interfaccia vive in streamlit_app.py.
- Terminologia di dominio (italiano, settore edile/immobiliare): computo metrico, voci di lavorazione, libretto delle misure, listino, incidenze, imprevisti, IVA scorporata, superficie commerciale, studio di fattibilità, MCA, coefficiente di merito, FatturaPA/SdI. Categorie spese fisse: ACQUISTO, LAVORI, MATERIALE, ARCHITETTO, COSTI INDIRETTI, AGENZIA, ALTRO.
- L'interfaccia è in italiano, con una eccezione deliberata: lo studio di
  fattibilità conserva le etichette inglesi del foglio Excel di partenza
  (ESTIMATED, Buy cost, Sell cost, Net Return (ROI), Return on Equity, Total
  cost, Net gain, Estimated sell price). Sono il vocabolario con cui l'utente
  legge quei numeri da prima dell'app: **non vanno tradotte**.
- Roadmap dichiarata (README): pareti da demolire/costruire con aggiornamento del computo, riconoscimento muri con computer vision, listino personale riutilizzabile, import da prezzari regionali.

## Brand Commitments

- Nome prodotto: CME — Computo Metrico Estimativo; società: Resolve S.r.l.
- Tema attuale: dark navy + oro champagne dal logo Resolve (#1A2744 navy, #C9A96A oro, #ECE7DA crema), uguale al progetto gemello MORA (.streamlit/config.toml). **Confermato come preferenza, non vincolo**: l'utente è aperto a una proposta migliore che la superi.

## Evidence on Hand

- Modello Excel reale dell'utente replicato e verificato: i test di fattibilita.py usano i numeri esatti di "Studio fattibilità" + "MCA sell".
- App pubblica live: <https://computometrico.streamlit.app/>.
- Listino guida ~50 voci con prezzi indicativi (listino.py).
- Nessuna testimonianza, caso studio o materiale marketing: non fabbricarne.

## Product Principles

1. **I numeri prima di tutto**: ogni calcolo replica o migliora il modello Excel verificato; mai risultati "stantii", tutto si ricalcola dal vivo.
2. **Logica pura, testata, separata dalla UI**: le funzioni di calcolo restano in moduli puri coperti da pytest.
3. **Dal foglio di calcolo allo strumento**: ridurre attrito e passaggi manuali rispetto a Excel (estrazione fatture, quantità dalle dimensioni, superfici dalla planimetria).
4. **Un progetto, un filo unico**: valutazione, computo, planimetrie e consuntivo vivono nello stesso progetto salvabile e riapribile.
5. **Locale e privato**: elaborazione fatture in locale, archivio su bucket privato, credenziali mai nel codice.

## Accessibility & Inclusion

Nessun requisito specifico emerso. Lingua dell'interfaccia: italiano.
