---
target: streamlit_app.py
total_score: 27
max_score: 40
na_heuristics: 
p0_count: 1
p1_count: 2
timestamp: 2026-07-25T19-51-36Z
slug: streamlit-app-py
---
# Critique — CME (streamlit_app.py)

Method: dual-agent (A: design review · B: detector + browser evidence)

## Design Health Score

| # | Euristica | Punteggio | Problema chiave |
|---|-----------|-----------|-----------------|
| 1 | Visibilità dello stato del sistema | 3 | Totali live e spinner ok; nessun indicatore di "lavoro non salvato"; toast che confermano azioni il cui effetto è in un'altra scheda |
| 2 | Corrispondenza sistema/mondo reale | 3 | Italiano di dominio eccellente; ma etichette finanza in inglese ("Buy cost", "Return of Equity" errato) e chrome Streamlit non tradotto |
| 3 | Controllo e libertà dell'utente | 2 | Nessun undo per eliminazione zone/pareti; "🗑️ Nuovo progetto (svuota tutto)" senza conferma; refresh distrugge la sessione; "Apri" scarta il lavoro in corso in silenzio |
| 4 | Coerenza e standard | 2 | "💎 TOTALE FINALE" a schermo = pre-IVA, ma nell'export Excel "Totale finale (IVA inclusa)" = post-IVA; tre idiomi diversi per eliminare; formato numeri input ≠ display |
| 5 | Prevenzione degli errori | 2 | Parsing fatture/JSON blindato (ottimo); ma svuota-tutto e F5 senza guardrail; "Data" spese è testo libero non validato; "Salva online" sovrascrive in silenzio (x-upsert, archivio.py:98) |
| 6 | Riconoscimento vs richiamo | 3 | Listino a checklist ottimo; ma convenzioni "0 = dalla planimetria / dal computo" da sapere a memoria |
| 7 | Flessibilità ed efficienza | 3 | Campi bidirezionali %↔€, trasferimenti a un click; ma ogni number_input parte con "0.00" da selezionare prima di digitare (verificato: produce "0.0080") |
| 8 | Estetica e design minimalista | 3 | Identità navy/oro coerente; ~20 emoji come iconografia e due card oro "TOTALE" in competizione |
| 9 | Recupero dagli errori | 3 | Copy di errore umano e specifico; ma dal data-loss non si recupera |
| 10 | Aiuto e documentazione | 3 | Help inline denso e ben scritto ovunque; tutto però sepolto nei tooltip |
| **Totale** | | **27/40** | **Accettabile (fascia 20–27)** |

## Verdetto di specificità del design

**Valutazione LLM (Assessment A)**: software genuinamente "autoriale", non un dashboard generico. Il vocabolario di dominio è esatto e ovunque (libretto delle misure, coefficiente di merito, scorporo IVA, PDF di cortesia SdI); le scelte strutturali (listino a schede colorate per categoria, foglio fattibilità volutamente a forma di Excel con heatmap ancorate alla mediana) riproducono gli artefatti di lavoro reali del titolare. Scivola nel generico a livello di "chrome": furniture Streamlit non tradotta ("Upload", "200MB per file", "Select a date.", bottone "Deploy"), formato anglosassone "100.00" negli input contro "100,00 €" ovunque nel display, ed emoji come iconografia (💎💠🥧🔮🪄) che sa più di hobby-project che di brand Resolve. Specificità: alta nella sostanza, media nella finitura.

**Scansione deterministica (Assessment B)**: CLI pulito su cme_viewer/frontend (exit 0, verificato con canary che il detector funziona). Scansione live nel browser sulla prima scheda: 126 segnalazioni, di cui ~90 "gray-on-color" riconducibili a un'unica decisione di design (testo crema #ECE7DA su navy — contrasto in realtà ampio, falso allarme di famiglia); ~24 "text-occlusion" in gran parte artefatti da expander collassati. Colpi reali che la review non aveva visto: viola #B27EFF a 4.2:1 (sotto la soglia 4.5:1), testo a 11.5px, righe da 124–159 caratteri, due salti di gerarchia titoli (h1→h4, h3→h5). Limite di copertura: solo la prima scheda; il viewer planimetrie (iframe) mai raggiunto dallo scan live.

**Overlay visivi**: iniezione riuscita (126 overlay renderizzati), ma il pannello browser non componeva i frame e la tab di valutazione è stata chiusa: nessun overlay persistente visibile ora.

## Impressione generale

Uno strumento di lavoro vero, con pensiero reale nei flussi (provenienza dei valori tra moduli, ingestione difensiva delle fatture, listino-checklist). I due difetti che pesano: l'esposizione totale alla perdita di dati (F5, svuota-tutto, sovrascritture silenziose) e la deriva di coerenza su numeri ed etichette proprio dove il prodotto promette "numeri affidabili". La singola opportunità più grande: proteggere il lavoro dell'utente con autosave + conferme.

## Cosa funziona

1. **Listino a checklist con totali disegnati in CSS** (streamlit_app.py:439–497): schede colorate per categoria con "Totale:" nel titolo via `::after` per non far collassare l'expander a ogni tasto — soluzione sofisticata e specifica del prodotto; preventivare diventa spuntare una checklist di cantiere.
2. **Flusso dei valori tra moduli con provenienza visibile**: superficie commerciale → computo, computo (+imprevisti) → fattibilità, MCA → prezzo di vendita, ognuno con bottone esplicito e caption "(dal computo, imprevisti inclusi)". Il principio "un progetto, un filo unico" implementato, non solo dichiarato.
3. **Ingestione difensiva**: `dati_fattura_da_file` non solleva mai, fatture illeggibili elencate per nome con fallback manuale, JSON corrotto degrada con grazia. Postura di errore esattamente giusta per file FatturaPA del mondo reale.

## Problemi prioritari

1. **[P0] Perdita di dati irrecuperabile su refresh e "Nuovo progetto"** — F5 cancella tutto in silenzio (verificato dal vivo); "🗑️ Nuovo progetto (svuota tutto)" (riga 1287) è un click singolo senza conferma accanto ai controlli di caricamento; "Salva online" sovrascrive senza avviso. *Perché conta*: è la scogliera emotiva del prodotto; un pomeriggio di computo perso azzera la fiducia. *Fix*: conferma a due passi su svuota-tutto (come già per l'eliminazione online), avviso "esiste già" sul salvataggio online, autosave leggero (serializzare `progetto_json_bytes()` su file locale o oggetto `_autosave` Supabase ogni N interazioni) con "riprendi l'ultima sessione?" all'avvio. → `/impeccable harden`
2. **[P1] "COSTI TOTALI (→ business plan)" è una promessa falsa** — `spese_costi_totali` (riga 2387) viene scritto e mai letto; la fattibilità ignora il consuntivo. L'etichetta più sensibile alla fiducia dichiara un flusso che non esiste. *Fix*: consumare il valore (opzione "usa i costi reali al posto della ristrutturazione stimata") oppure togliere la freccia dall'etichetta. → `/impeccable harden` (flusso) o `/impeccable clarify` (etichetta)
3. **[P1] Contraddizione "TOTALE FINALE"** — a schermo la card oro 💎 è il totale pre-IVA; nell'export Excel "Totale finale (IVA inclusa)" è il post-IVA. Ambiguità su quale numero sia "finale" in un prodotto numbers-first. *Fix*: rinominare la card "TOTALE LAVORI (IVA esclusa)" e dare al valore IVA inclusa peso pari o maggiore, allineando l'export. → `/impeccable clarify`
4. **[P2] Business plan a riposo mostra perdite finte allarmanti** — con acquisto/vendita a 0, ROE −100% ed EBIT −26.900 € in rosso da costi di default. *Fix*: con `bp_acquisto == 0` rendere em-dash per ROI/ROE/EBIT (come già per €/mq). → `/impeccable harden`
5. **[P2] Strato di incoerenza linguistica/formato + finiture rilevate dal detector** — etichette inglesi ereditate dall'Excel ("Buy cost", "ESTIMATED", "Return of Equity" errato → "Return on Equity"), chrome Streamlit non tradotto, punto decimale negli input vs virgola nel display, caption spese stantia (riga 2263); più i colpi del detector: viola #B27EFF a 4.2:1, testo 11.5px, salti di gerarchia h1→h4 / h3→h5. → `/impeccable clarify` + `/impeccable polish`

## Segnalazioni persona

**Alex (power user — l'utente reale)**: ogni number_input pre-riempito "0.00" obbliga a seleziona-tutto-poi-digita su ~50 voci (verificato: click-e-digita produce "0.0080"); rerun completo di Streamlit dopo ogni campo; "Carica nel programma" richiede file + secondo click; nessun export della sola fattibilità/BP — metà "valutazione affare" del prodotto non esporta nulla.

**Sam (accessibilità)**: le tre schede principali non hanno nome accessibile (verificato nell'albero a11y); i totali di categoria sono pseudo-contenuto CSS `::after`, invisibili a screen reader e al copia-testo; tutte le tabelle `st.data_editor` sono griglie canvas opache all'assistive tech; il canvas planimetrie è solo-mouse per il lavoro principale; etichette toolbar a 8.5px e placeholder "/" #5B688A su navy (~2.8:1) sotto soglia.

**Riley (stress tester)**: F5 a metà computo = tutto perso (verificato); salvataggio online su nome esistente = sovrascrittura silenziosa; "Data" spese accetta "31/02/2025" o "domani"; `aliquota_iva` limitata nell'editor ma non ri-validata su JSON caricato; prezzo negativo nelle voci aggiuntive accettato senza commento — un computo può totalizzare negativo in silenzio.

## Osservazioni minori

- Formattazione italiana `euro()`/`numero_it()` coerente nel display — rende più stonato il `%.2f` anglosassone negli input.
- Copy della beta "Rileva stanze" esemplare ("proposte da rifinire").
- Toolbar del viewer ben fatta (veri `<button>`, tooltip italiani, stato attivo oro) ma stretta (58px, etichette 8.5px) e flottante sopra il disegno.
- Heatmap di sensitività con bianco ancorato alla mediana: dettaglio di fedeltà all'Excel che l'utente sente senza saperlo nominare.
- Su mobile il riepilogo arriva dopo ~8 expander e la fattibilità è un canvas fisso 1750px in un contenitore da 343px: analisi di punta desktop-only nei fatti — merita un hint esplicito su schermi piccoli.
- Carico cognitivo: 5 voci su 8 della checklist fallite (alto, mitigato dal contesto mono-utente esperto); punti di decisione >4 opzioni: U.M. (10), categorie spese (7), categorie superficie (7), toolbar viewer (9 controlli), dettaglio costi BP (8 celle + 2 coppie bidirezionali).
- Viaggio emotivo: ingresso caldo e sicuro; valle 1 = primo Business plan con perdite finte; valle 2 = refresh accidentale; picco = "il mio Excel, ma vivo" (totali live + heatmap); finale debole — il salvataggio è un download senza cerimonia né "ultimo salvataggio" (peak-end inutilizzato).

## Domande da considerare

1. Se la promessa è "numeri mai stantii", perché il lavoro dell'utente è l'unica cosa che può azzerarsi in silenzio? Quale pomeriggio ha più ROI di quello che previene il primo computo perso?
2. Ora che i numeri sono vivi, il layout-Excel della fattibilità è ancora il contenitore giusto — o il foglio potrebbe dichiarare un verdetto ("l'affare regge / non regge fino a X") invece di far leggere 12 metriche?
3. L'app già calcola "preventivo vs consuntivo" per il cantiere: perché quel confronto si ferma a tre metriche invece di diventare il fulcro emotivo dello strumento (il momento in cui il titolare scopre se aveva ragione)?
