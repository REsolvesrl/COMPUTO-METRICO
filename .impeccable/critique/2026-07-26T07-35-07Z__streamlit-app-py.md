---
target: streamlit_app.py
total_score: 18
max_score: 40
na_heuristics: 
p0_count: 2
p1_count: 3
timestamp: 2026-07-26T07-35-07Z
slug: streamlit-app-py
---
# Critique — CME (app completa, `streamlit_app.py`) — seconda passata

Method: dual-agent (A: design review · B: detector + browser evidence)

Nota di provenienza: passata più profonda della precedente. Assessment A ha ottenuto pixel reali pilotando Chrome via CDP (23 screenshot) dopo che gli strumenti browser MCP hanno fallito, e ha misurato dal vivo contrasti, numero di controlli focusabili, struttura dei titoli e larghezze dei container. Assessment B ha coperto tutte e tre le schede e ha verificato il proprio strumento con fixture di controllo. Il codice è **byte-identico** alla passata precedente (verificato con git): la variazione di punteggio è metodologica, non una regressione del prodotto.

Deviazione di isolamento dichiarata: Assessment A, durante un grep di verifica su tutto il repo, ha visto incidentalmente una riga di un file in `.impeccable/critique/`. Dichiara che l'ipotesi in questione era già formulata e di non aver letto oltre. Impatto valutato: trascurabile.

## Design Health Score

| # | Euristica | Punteggio | Problema chiave |
|---|-----------|:---:|-----------------|
| 1 | Visibilità dello stato del sistema | 2 | Nessuno stato di salvataggio/modifiche non salvate; "Press Enter to apply" invisibile (misurato ~1.05:1) sui due input prezzo del business plan; nessun indicatore di modalità attiva o scala fuori dal canvas |
| 2 | Corrispondenza sistema/mondo reale | 3 | Vocabolario di dominio e formati numerici italiani eccellenti; ma "Net Return (ROI)" etichetta un money multiple, "ROE" senza distinzione equity/debito, "Total cost" nomina solo gli oneri |
| 3 | Controllo e libertà dell'utente | 1 | "🗑️ Nuovo progetto (svuota tutto)" distrugge tutto con un click non confermato (streamlit_app.py:1287-1289); nessun undo globale; il refresh perde tutto |
| 4 | Coerenza e standard | 2 | La stessa metrica chiamata "Net Return (ROI)" e "Money multiple" in colonne adiacenti; `Importo (€)` vs `€` per lo stesso campo; `lang="en"`; chrome Streamlit non tradotto |
| 5 | Prevenzione degli errori | 1 | Il bottone distruttivo sta accanto al dropzone di apertura con MENO protezione dell'eliminazione in archivio; zone disegnabili prima della scala; valori € tagliati a metà cifra ("16200,0(") |
| 6 | Riconoscimento vs richiamo | 2 | Il listino a checklist è un punto di forza reale, ma il significato degli strumenti vive solo nei tooltip e il business plan impone memoria tra schede |
| 7 | Flessibilità ed efficienza | 2 | Acceleratori forti (➕ Al computo, voci battiscopa automatiche, binding % ⇄ €, estrazione fatture) vanificati da ~465 controlli da attraversare e percentuali di superficie non modificabili |
| 8 | Estetica e design minimalista | 1 | ~17 ripetizioni di "0,00 €" a riposo sulla scheda Computo; "−100,0 %" in rosso prima di qualsiasi input; emoji su ogni titolo; pastelli Excel dentro un tema navy |
| 9 | Recupero dagli errori | 2 | Messaggi di errore in italiano piano genuinamente buoni, ma trapela il testo grezzo delle eccezioni (`f"Errore nell'apertura: {errore}"`) e dallo svuotamento non si recupera |
| 10 | Aiuto e documentazione | 2 | Tooltip di dominio eccellenti; ma "te lo spiego passo-passo" per Supabase non spiega nulla, e l'intro spese descrive un layout che non esiste più |
| **Totale** | | **18/40** | **Scarso (fascia 12–19)** |

## Verdetto di specificità del design

**Assessment A**: parzialmente specifico, e le parti specifiche sono quelle buone. Il listino-checklist per mestieri italiani (Demolizioni / Idraulico / Elettricista / Serramenti), il libretto delle misure con `parti` negative per le detrazioni, la legenda delle categorie di superficie con i pesi commerciali (Balcone scoperto 30%, Garage 50%) e soprattutto la matrice di sensitività rosso→bianco→verde con la cella base riquadrata in nero: non si trapiantano in un altro prodotto, codificano come ragiona davvero un investitore immobiliare italiano. Ma la cornice attorno è Streamlit generico con titoli a emoji, e la superficie PIÙ specifica del prodotto è la meno progettata: la toolbar della planimetria sono sei emoji da sei palette diverse, e il business plan è un foglio Excel fotografato dentro un tema scuro più che ridisegnato per esso. Togliendo le stringhe italiane, circa metà dell'app è uno strumento interno senza marchio.

**Assessment B (deterministico)**: scansione CLI pulita su tutti i sorgenti del progetto (0 findings) — ma verificata come **genuina e superficiale insieme**: fixture di controllo in .html/.js/.py fanno scattare il detector correttamente, mentre le regole di contrasto, dimensione testo e geometria non possono scattare senza un DOM renderizzato. Prova diretta: `index.html` = 0 findings da CLI, lo stesso file renderizzato nel browser = 7 findings. Scansione live per scheda:

| Scheda | Findings grezzi | Firme distinte |
|---|---|---|
| 📝 Computo metrico | 104 | 14 |
| 📐 Misura da planimetria | 12 | 8 |
| 📊 Business plan | 34 | 13 |

Lettura corretta dei numeri grezzi:
- **`gray-on-color` 111 grezzi → 5 coppie distinte**, tutte lo stesso primo piano `#ECE7DA` su varianti di navy. È **una decisione di tema moltiplicata per elemento**, non 111 difetti. Non è un problema di contrasto (i pulsanti inattivi misurano 14.81:1).
- **`undersized-ui-text` 6 grezzi → 1 dichiarazione CSS**: `.tb-btn .lbl { font-size: 8.5px }` in cme_viewer/frontend/index.html:55.
- **`low-contrast` 11 grezzi → 5 coppie distinte, queste genuinamente indipendenti**: 2.7:1 `#5B688A` su `#1A2744` (testo degli avvisi info, 5 occorrenze), 3.7:1 e 3.9:1 `#3D9DF3`, 4.4:1 `#FF6C6C`, 4.2:1 `#B27EFF`.
- Artefatti dichiarati: `skipped-heading`, `tiny-text` e `clipped-overflow-container` scattano identici su tutte e tre le schede con bounding box a zero — Streamlit tiene in DOM i pannelli delle schede inattive; e `clipped-overflow-container` colpisce i container del framework, non il markup dell'app.

Convergenza tra i due: il problema dei titoli è **reale** anche se l'istanza segnalata dal detector era un artefatto — A l'ha misurato dal vivo (H1 → H4 → H3 → H5, 7 titoli in tutta l'app, **zero** nel foglio di fattibilità).

**Overlay visivi**: nessun overlay è visibile ora nel browser. L'iniezione è riuscita durante la raccolta prove, ma il server helper è stato fermato e le tab chiuse a fine valutazione.

**Caveat sullo strumento**: puppeteer non è installato, quindi `detect.mjs <URL>` non può girare — e **fallisce in silenzio**, uscendo con codice 0 e stampando `[]`, indistinguibile da un esito pulito se non si legge stderr.

## Impressione generale

La passata precedente aveva visto la superficie giusta ma non abbastanza a fondo. Con pixel veri e misure dal vivo emergono due difetti che cambiano il quadro: **si può perdere tutto il progetto con un click non confermato**, e **si può digitare un prezzo, vederlo nel campo, e leggere risultati calcolati ancora sullo zero** senza alcun segnale che i due siano disallineati. Su uno strumento che esiste per decidere se comprare un immobile, il secondo è il più grave dei due. La singola opportunità più grande resta la stessa — proteggere il lavoro dell'utente — ma ora con davanti la sincronizzazione tra ciò che si digita e ciò che si legge.

## Cosa funziona

1. **La heatmap di sensitività con il caso base ancorato** (streamlit_app.py:670-770): chip giallo sulla riga di acquisto base, chip blu sulla colonna di vendita base, riquadro nero 3px sull'intersezione, bianco fissato alla mediana come la formattazione condizionale di Excel. Il commento nel codice spiega che le etichette posizionate a pixel si erano rivelate inaffidabili tra browser, quindi l'evidenziazione è stata ancorata alle coordinate dei dati. Artigianato al servizio del modello mentale esistente di un utente specifico.
2. **Le schede di categoria con i totali disegnati in CSS** (css_schede_computo, righe 439-497): colore per mestiere, totale allineato a destra nell'intestazione via `::after`, apposta perché la stringa del titolo non cambi mai e l'expander non si richiuda mentre lavori. Un problema reale della scena d'uso, risolto in modo invisibile.
3. **Le etichette delle zone sulla planimetria**: pillola bianca, testo navy, tre righe nome / m² / % commerciale, trascinabili, con linea di richiamo al centroide quando spostate fuori dal poligono. Leggibili sopra qualsiasi disegno, e mettono il peso commerciale esattamente dove si prende la decisione.

## Problemi prioritari

**[P0] Un click non confermato distrugge l'intero progetto.**
"🗑️ Nuovo progetto (svuota tutto)" (streamlit_app.py:1287-1289) cancella computo, tutte le planimetrie con la loro scala calibrata e le zone disegnate a mano, business plan, spese e MCA. Nessuna conferma, nessun undo, nessuno stile distruttivo, e sta immediatamente a destra del dropzone "Apri un progetto salvato". L'eliminazione *in archivio*, che rimuove un solo file salvato, richiede invece di spuntare una casella (righe 1318-1327). *Perché conta*: la protezione è inversamente proporzionale al danno, esattamente nel punto in cui chi cerca di aprire un progetto può sbagliare click; non c'è autosave e una planimetria multipagina calibrata sono ore di lavoro. *Fix*: stessa conferma a due passi dell'archivio, stile distruttivo, spostarlo fuori dalla riga di apertura, più un indicatore "ultimo salvataggio" e un avviso di modifiche non salvate.

**[P0] I due input che guidano ogni numero hanno uno stato "non applicato" invisibile.**
Gli override in stile Excel (`.st-key-bp_in_acq` / `.st-key-bp_in_ven`, righe 2056-2065) colorano i campi prezzo di acquisto e vendita `#FFF2CC` e `#DDEBF7`. Il suggerimento "Press Enter to apply" di Streamlit viene renderizzato a `rgba(236,231,218,0.6)` sopra `rgb(221,235,247)` — **≈1.05:1, misurato dal vivo**. Stato di errore riprodotto: il campo mostrava `295000` mentre ogni cifra a valle — incluso `ROE −100,0 %` in rosso — era ancora calcolata sullo zero. *Perché conta*: sulla schermata che decide l'investimento, l'utente vede il proprio numero nel campo e un risultato catastrofico sotto, senza alcun segnale che i due siano disallineati. Nel caso peggiore, una decisione reale presa su cifre stantie — l'esatto contrario del principio "numeri mai stantii". *Fix*: mantenere la codifica cromatica Excel ma ridisegnare il suggerimento (testo scuro, o sotto il campo), tradurlo, e marcare il blocco derivato come stantio finché non si conferma.

**[P1] Il foglio di fattibilità non è leggibile come un foglio unico a larghezze desktop normali.**
`min-width:1750px` (riga 2052) dentro un container che a finestra 1600px ne misura 1420. La terza colonna ("SPESE ACQUISTO — dettaglio") è tagliata a metà parola e i suoi input € sono troncati ("16200,0(", "15000,0("); scorrendo a destra per raggiungerli, il riepilogo EBIT/ROE esce completamente dallo schermo. Su mobile il container è 1750px contro un viewport da 338px, e il chip "ESTIMATED" diventa un rettangolo arancione vuoto. *Perché conta*: lo scopo di una matrice di sensitività è leggerla *contro* il caso base; separarli con uno scroll orizzontale impone di trasportare i numeri a memoria, e cifre monetarie tagliate su una superficie di denaro sono inaccettabili. *Fix*: togliere il min-width fisso; rendere il riepilogo una barra sticky o spostare EBIT/ROE sopra le matrici; allargare la colonna "Netto" perché i valori a 7 cifre entrino con i loro stepper.

**[P1] La heatmap colora di rosso scenari profittevoli.**
La scala cromatica fissa il bianco alla *mediana* dell'intervallo mostrato (righe 691-699). Con le cifre di test, la cella da €25.900 di utile (180k/255k) è colorata rosso salmone, e il pareggio a 1,00x è rosa. Non c'è legenda né nota che il colore sia relativo. *Perché conta*: su una schermata compra/non-compra, un rosso a colpo d'occhio si legge "perdita". Il colore oggi è un rango, non un verdetto. *Fix*: ancorare il bianco a una costante significativa — il pareggio (1,00x / €0) — oppure aggiungere una legenda che dichiari che il bianco è la mediana dell'intervallo mostrato. *(Nota: la passata precedente aveva lodato l'ancoraggio alla mediana come fedeltà all'Excel; è la stessa scelta vista dai due lati — fedele al foglio, fuorviante come segnale.)*

**[P1] Lo strumento di misura di punta è inerte al tocco, e il suo indicatore di modalità fallisce il contrasto.**
`cme_viewer/frontend/main.js` associa solo `wheel`, `mousedown/move/up`, `dblclick`, `keydown` — **nessun handler pointer o touch in tutto il file**, mentre `touch-action:none` sul canvas uccide anche lo scroll nativo sopra di esso. Su un tablet — il dispositivo plausibile in cantiere — non si può spostare, disegnare, impostare la scala né misurare, e il canvas diventa una zona morta che blocca la pagina. In più il chip dello strumento attivo è bianco su `#C9A96A` = **2.24:1 misurato**, contro 14.81:1 dei pulsanti inattivi: l'unico stato che deve essere leggibile è il meno leggibile, a 8.5px maiuscolo (confermato indipendentemente dal detector: `undersized-ui-text`, index.html:55). *Perché conta*: misurare da planimetria è il differenziatore del prodotto e la ragione per cui sostituisce Excel. *Fix*: aggiungere handler pointer (coprono mouse e touch); chip attivo navy-su-oro o oro-su-navy; ingrandire il testo delle etichette.

**[P2] Etichette che promettono flussi e layout inesistenti.**
La scheda "💠 COSTI TOTALI (→ business plan)" scrive `st.session_state.spese_costi_totali` (riga 2387) che **non viene mai letto** — la fattibilità usa solo `bp_ristr` o il totale del computo. L'intro spese (righe 2263-2268) descrive ancora "a sinistra le spese sostenute… a destra la torta" benché la tabella sia stata spostata a piena larghezza sopra. L'avviso Supabase promette "te lo spiego passo-passo" e poi non spiega nulla (righe 1295-1297). Le percentuali di superficie che la legenda pubblicizza sono hardcoded e non hanno alcun editor nell'interfaccia. *Perché conta*: su uno strumento di numeri, un'etichetta che sopravvaluta un flusso di dati è un difetto di fiducia, non di copy.

**[P3] "TOTALE FINALE" non è il totale finale.**
La card bordata d'oro (righe 1451-1459) mostra `totale_imprevisti` — prima dell'IVA — mentre il "Totale IVA inclusa" genuinamente finale sta sotto in tipografia normale. *Fix*: incoronare la cifra IVA inclusa, o rinominare la card "Totale lavori (imprevisti inclusi)".

## Segnalazioni persona

**Alex (power user impaziente — l'utente reale)**: apre il Business plan e si sente dire `ROE −100,0 %` prima di digitare qualsiasi cosa. Digita il prezzo di vendita, lo vede nel campo, e legge risultati calcolati sullo zero. A 1600px non riesce a vedere EBIT e matrice insieme, quindi scorre a destra, perde il caso base, torna indietro. Vuole modificare "Balcone coperto 35%" per una valutazione specifica e non trova alcun editor — le percentuali sono congelate in `CATEGORIE_DEFAULT`. Finisce e si trova davanti tre bottoni grigi identici senza alcun indizio che solo "Salva progetto (.json)" preservi il lavoro, e nessuna indicazione se abbia già salvato.

**Sam (accessibilità)**: `<html lang="en">` su un'interfaccia interamente italiana — ogni screen reader applica fonetica inglese a "Computo Metrico Estimativo", "Demolizioni", "Imprevisti". Struttura dei titoli H1 → H4 → H3 → H5 con soli 7 titoli in tutta l'app e **zero** nel foglio di fattibilità, quindi la navigazione per titoli è inutile. **465 controlli focusabili visibili** nel pannello Computo, invariati collassando gli expander — raggiungere "💾 Salva ed esporta" significa tabulare oltre ogni campo quantità e prezzo di tutte e sei le categorie, senza skip link. I pulsanti della toolbar sono raggiungibili da tastiera, ma disegnare, scalare e misurare sono solo-mouse: la funzione di misura è del tutto indisponibile. Il chip dello strumento attivo a 2.24:1 lo penalizza anche da vedente. *(Merito: i pannelli delle schede inattive sono correttamente `hidden`, quindi l'ordine di tabulazione non trabocca tra schede.)*

**Riley (stress tester)**: disegna quattro stanze prima di impostare la scala e ottiene zone completamente colorate, etichettate con sicurezza con nome e "100 %" e **nessuna area** — e quelle planimetrie vengono poi escluse in silenzio dal totale commerciale, segnalate solo da una striscia gialla molto più in basso. Ricarica a metà flusso: tutto perso. Imposta `Durata operazione` a 12 (il default) e trova `Return of Equity (ROE)` e `Rendimento annuo` che mostrano **lo stesso identico 29,2 %** sotto due nomi diversi — matematicamente inevitabile a 12 mesi, e facilissimo da leggere come due conferme indipendenti. Clicca l'ordinato cestino accanto al box di caricamento e perde il progetto senza alcun prompt.

## Osservazioni minori

- `"**➕ {ALTRE_VOCI}** (personalizzate…)"` renderizza come "Voci aggiuntive(personalizzate…" — lo spazio collassa al confine del grassetto. Su mobile la stessa intestazione degrada a un nudo "(personalizzat" con il nome perso del tutto.
- Su mobile la barra delle schede si tronca in "📊 Bu›" e "🏷️ M‹›"; due file di tab scorrevoli consumano ~90px di uno schermo da 375px, e l'H1 si mangia ~380px di 812px prima di qualsiasi contenuto.
- La toolbar mescola sei palette di emoji diverse più un glifo non-emoji (`➤`, navy piatto tra cinque emoji policrome); `↔️` si presenta come una tessera blu piena che si legge come *già selezionata*. La riga dello zoom non è etichettata mentre ogni pulsante di modalità lo è.
- **Scala è l'ultimo pulsante della toolbar** benché sia l'azione obbligatoria iniziale: l'ordine degli strumenti contraddice l'ordine del flusso di lavoro.
- Zone adiacenti della stessa categoria condividono un unico riempimento senza differenziazione dei bordi; il rosso zona `#E57373` e il rosso muro-da-demolire `#E53935` sono quasi identici: "rosso" significa due cose sullo stesso disegno.
- Le etichette auto-posizionate delle zone atterrano sul centroide, esattamente dove è stampato il nome della stanza dell'architetto — occludendo "SOGGIORNO", "CAMERA", "CUCINA", "BAGNO" nel render di test.
- Chrome Streamlit non tradotto in un'app la cui PRODUCT.md dichiara "Tutta l'interfaccia è in italiano": "Upload", "200MB per file", "Press Enter to apply", più "ESTIMATED / Buy cost / Sell cost / Total cost" del business plan.
- I paragrafi `st.caption` corrono per l'intera larghezza del container — ~200 caratteri per riga sulle intro MCA e spese (il detector conferma: ~215 e ~250 caratteri).
- `"6 · Aree esterne"` usa il colore markdown `gray` di Streamlit, facendo leggere come disabilitata una categoria di pari livello.
- Lo stato vuoto della planimetria sono due frasi e un dropzone sopra ~700px di navy morto: la capacità distintiva del prodotto è invisibile finché non esiste un file.
- Genuinamente buoni: il commento sulla gestione dei None in `_cat()` (righe 254-260) documenta un crash reale del data_editor e lo previene; "↩️ Annulla ultimo rilevamento (N aree)" è un undo mirato e ben pensato; il tooltip IVA ("10% ristrutturazioni, 22% ordinaria, 4% prima casa") ha esattamente la profondità giusta per questo utente.
- Testo degli avvisi info a 2.7:1 (`#5B688A` su `#1A2744`, 5 occorrenze) rilevato dal detector: sotto qualsiasi soglia di leggibilità.

## Carico cognitivo

**7 voci su 8 fallite → ALTO.** Unica promossa: raggruppamento (le schede di categoria, le tre colonne del BP e la fascia spese sono genuinamente ben raggruppate).

Punti di decisione con >4 opzioni visibili: toolbar canvas (9 controlli in una colonna 94×310px); 7 schede categoria; 12 voci per scheda × 4 controlli; registro costi BP (12 input); riepilogo BP (12 righe); selectbox Categoria spese (7); menu categorie superficie (7); selectbox U.M. (10); matrici di sensitività (11×9 celle, due volte = 198 valori); navigazione (3 schede + 3 sotto-schede simultanee).

## Viaggio emotivo

La **valle è sulla porta d'ingresso della superficie a più alto rischio**: aprendo il Business plan su un progetto intatto si legge `Buy cost 18.500,00 €`, `Total cost 18.500,00 €` in rosso e **`Return of Equity (ROE) −100,0 %`** — l'app annuncia una perdita totale su un affare che non esiste ancora. È la prima impressione della schermata che decide se comprare un immobile.

Il **picco è reale e guadagnato**: il momento in cui entrambi i prezzi sono inseriti e le due heatmap sbocciano con la cella base riquadrata in nero. È la promessa "il mio Excel, ma vivo", mantenuta.

Il **finale la disfa**: la sessione termina su tre bottoni grigi visivamente identici — "Salva progetto (.json)", "Esporta Excel", "Esporta CSV" — dove solo il primo previene la perdita totale del lavoro, senza enfasi, senza stato di salvataggio, senza autosave, e con un bottone di svuotamento non confermato che aspetta al piano di sopra.

## Domande da considerare

1. Se c'è esattamente un utente e sa già cos'è un computo metrico, perché l'app spende i pixel più preziosi a spiegare se stessa — un H1 su 3 righe con la gru, paragrafi di caption a piena larghezza, un accordion "Dati del progetto · Apri / Nuovo" — e i pixel più economici sulla risposta, con l'EBIT renderizzato a 0.93rem nello stesso peso di "Buy cost"?
2. Il Business plan replica l'Excel abbastanza fedelmente da conservarne le etichette inglesi, i riempimenti gialli e blu e la scala cromatica ancorata alla mediana. A che punto la fedeltà al foglio smette di essere una funzionalità e diventa la ragione per cui lo strumento eredita anche le debolezze del foglio — incluso un "Total cost" che nomina solo gli oneri e un ROE senza equity dentro?
3. La promessa dichiarata è "decisioni d'investimento rapide e numeri affidabili". Oggi un progetto può essere distrutto da un click non confermato, un prezzo digitato può non applicarsi in silenzio, e un utile di €25.900 viene dipinto di rosso. Quale dei tre scopriresti per primo — e ti fideresti ancora dei numeri, dopo?
