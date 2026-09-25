"""Listino voci guida per ristrutturazioni residenziali.

Voci pronte all'uso con prezzi medi indicativi (fonte: prassi corrente di
mercato per ristrutturazioni complete di appartamenti), organizzate nelle
categorie tipiche di un computo: demolizioni → ricostruzioni e ripristini →
impianti → serramenti → aree esterne. In coda tetto e facciata, presi dai
computi del cantiere ENI: sono lavori che non tutti i cantieri hanno.

I prezzi sono SEMPRE modificabili dopo l'inserimento nel computo: sono un
punto di partenza, non un prezzario ufficiale. Le "note" riportano le regole
pratiche per stimare le quantità.
"""

CATEGORIE = [
    "Pratiche e oneri",
    "Demolizioni",
    "Ricostruzioni e ripristini",
    "Idraulico",
    "Elettricista",
    "Serramenti",
    "Aree esterne",
    "Tetto",
    "Facciata",
]

# Lavori che non ci sono in ogni cantiere: in un progetto restano spenti
# finché non li accendi, e da spenti non compaiono né nel computo né nei
# totali né in stampa. Stanno in coda al listino perché i codici delle altre
# categorie (1.x … 7.x) non si spostino: sono scritti nei progetti salvati.
CATEGORIE_FACOLTATIVE = ["Tetto", "Facciata"]

VOCI = [
    # -------------------------------------------------- 0 · Pratiche e oneri
    # Sta in testa perché è la prima spesa in ordine di tempo — si paga prima
    # che il cantiere apra — ed è quella che si dimentica: non si vede in
    # planimetria, non la propone nessuna impresa, e su una ristrutturazione
    # pesante vale quanto un capitolo di lavorazioni.
    {"codice": "1.1", "categoria": "Pratiche e oneri", "um": "a corpo",
     "prezzo": 1500.0,
     "descrizione": "Rilievo e progetto architettonico",
     "nota": "Rilievo dello stato di fatto, elaborati di progetto e "
             "raffronto. Su un appartamento standard 1.200-2.000 €."},
    {"codice": "1.2", "categoria": "Pratiche e oneri", "um": "a corpo",
     "prezzo": 800.0,
     "descrizione": "CILA — pratica edilizia, asseverazione e deposito",
     "nota": "Manutenzione straordinaria senza interventi strutturali né "
             "cambio di destinazione. Alternativa alla SCIA (0.03): "
             "servono l'una o l'altra, non entrambe."},
    {"codice": "1.3", "categoria": "Pratiche e oneri", "um": "a corpo",
     "prezzo": 1500.0,
     "descrizione": "SCIA — pratica edilizia, asseverazione e deposito",
     "nota": "Quando si toccano strutture, prospetti o la destinazione "
             "d'uso. Alternativa alla CILA (0.02)."},
    {"codice": "1.4", "categoria": "Pratiche e oneri", "um": "a corpo",
     "prezzo": 2500.0,
     "descrizione": "Direzione lavori",
     "nota": "Di prassi si tratta a percentuale sull'importo dei lavori: "
             "indicativamente 3-5% su una ristrutturazione completa. "
             "Rifai il conto quando il computo è chiuso."},
    {"codice": "1.5", "categoria": "Pratiche e oneri", "um": "a corpo",
     "prezzo": 1800.0,
     "descrizione": "Coordinamento della sicurezza (CSP e CSE)",
     "nota": "Obbligatorio quando in cantiere opera più di un'impresa, "
             "anche non contemporaneamente: nelle ristrutturazioni "
             "complete è quasi sempre il caso. Comprende il piano di "
             "sicurezza e coordinamento e la notifica preliminare."},
    {"codice": "1.6", "categoria": "Pratiche e oneri", "um": "a corpo",
     "prezzo": 500.0,
     "descrizione": "Oneri comunali, diritti di segreteria e bolli",
     "nota": "Variano da comune a comune: verificali sul portale del "
             "comune prima di fissare il numero."},
    {"codice": "1.7", "categoria": "Pratiche e oneri", "um": "a corpo",
     "prezzo": 600.0,
     "descrizione": "Relazioni tecniche e asseverazioni (termica, "
                    "acustica, statica)",
     "nota": "Quali servano dipende dall'intervento e dal comune: la "
             "relazione L.10 con la sostituzione dei serramenti o della "
             "caldaia, quella acustica e strutturale se si toccano "
             "tramezzi portanti o solai."},
    {"codice": "1.8", "categoria": "Pratiche e oneri", "um": "cad",
     "prezzo": 250.0,
     "descrizione": "APE — attestato di prestazione energetica",
     "nota": "Obbligatorio per la vendita. Uno per unità immobiliare: "
             "se ne rifai uno post-lavori, contane due."},
    {"codice": "1.9", "categoria": "Pratiche e oneri", "um": "cad",
     "prezzo": 450.0,
     "descrizione": "Variazione catastale (DOCFA)",
     "nota": "Serve quando cambiano la distribuzione interna, la "
             "consistenza o la categoria. Una per unità immobiliare."},
    {"codice": "1.10", "categoria": "Pratiche e oneri", "um": "utenza",
     "prezzo": 150.0,
     "descrizione": "Allacci, volture e attivazione utenze",
     "nota": "Luce, acqua e gas: contratti, volture e attivazioni. Una "
             "per utenza. Non è l'impianto (vedi capitolo Idraulico), è "
             "la pratica."},
    {"codice": "1.11", "categoria": "Pratiche e oneri", "um": "a corpo",
     "prezzo": 300.0,
     "descrizione": "Occupazione di suolo pubblico (cassone, ponteggio, "
                    "autoscala)",
     "nota": "Concessione comunale a giornata o a metro quadro. Serve "
             "quasi sempre per il cassone delle macerie se non c'è cortile."},

    # ------------------------------------------------------- 1 · Demolizioni
    {"codice": "2.1", "categoria": "Demolizioni", "um": "m²", "prezzo": 100.0,
     "descrizione": "Demolizione pavimenti (compresi discesa macerie, "
                    "cassone e smaltimento)",
     "nota": "Comprende demolizione, discesa macerie, noleggio/ritiro del "
             "cassone, montascale e smaltimento. Attorno ai muri demoliti "
             "considera ~1 m di pavimento per ogni metro lineare di muro.",
     "analisi": "**Analisi costi**: demolizione 20 €/m² · discesa macerie "
                "25 €/m² · consegna cassone (4-6 m³) 60 € · ritiro cassone "
                "e smaltimento 300 € · montascale mezza giornata 200 € · "
                "noleggio cassone 5 €/giorno."},
    {"codice": "2.2", "categoria": "Demolizioni", "um": "m²", "prezzo": 100.0,
     "descrizione": "Demolizione murature",
     "nota": "Quantità = lunghezza del muro × altezza (es. 5 m × 3 m = "
             "15 m²)."},
    {"codice": "2.3", "categoria": "Demolizioni", "um": "m²", "prezzo": 15.0,
     "descrizione": "Rimozione rivestimenti in piastrelle",
     "nota": "Cucina: lunghezza della fascia × ~0,8 m. Bagno: perimetro × "
             "altezza rivestimento esistente (spesso 1,8 m)."},
    {"codice": "2.4", "categoria": "Demolizioni", "um": "m²", "prezzo": 15.0,
     "descrizione": "Rimozione listelli in parquet",
     "nota": "Solo i listelli (spessore ~2 cm, inchiodati ai magatelli): "
             "non serve demolire il pavimento; poi si ridà quota con "
             "autolivellante."},
    {"codice": "2.5", "categoria": "Demolizioni", "um": "cad", "prezzo": 50.0,
     "descrizione": "Rimozione e smaltimento porte esistenti"},
    {"codice": "2.6", "categoria": "Demolizioni", "um": "m²", "prezzo": 15.0,
     "descrizione": "Demolizione cartongessi (compreso smaltimento)"},
    {"codice": "2.7", "categoria": "Demolizioni", "um": "m²", "prezzo": 5.0,
     "descrizione": "Rimozione tappezzeria / carta da parati",
     "nota": "Somma dei muri interessati × altezza."},
    {"codice": "2.8", "categoria": "Demolizioni", "um": "m²", "prezzo": 100.0,
     "descrizione": "Tracce a pavimento per impianti",
     "nota": "In demolizione parziale: ~10 m² per un trilocale, 13-14 m² "
             "per un quadrilocale, meno per un bilocale."},
    {"codice": "2.9", "categoria": "Demolizioni", "um": "cad", "prezzo": 100.0,
     "descrizione": "Smaltimento sanitari esistenti",
     "nota": "Conta doccia/vasca, WC, bidet, lavabo."},
    {"codice": "2.10", "categoria": "Demolizioni", "um": "ml", "prezzo": 2.0,
     "descrizione": "Rimozione zoccolini in marmo",
     "nota": "Come stima rapida: circa la metratura commerciale "
             "dell'appartamento (es. 80 m² → ~80 m)."},

    # ------------------------------------- 2 · Ricostruzioni e ripristini
    {"codice": "3.1", "categoria": "Ricostruzioni e ripristini", "um": "m²",
     "prezzo": 80.0,
     "descrizione": "Ricostruzione muri in mattoni forati posati di coltello"},
    {"codice": "3.2", "categoria": "Ricostruzioni e ripristini",
     "um": "a corpo", "prezzo": 650.0,
     "descrizione": "Ricostruzioni murarie di piccola entità (riprese di "
                    "soffitti e spigoli dopo demolizioni)",
     "nota": "Un artigiano in regola ≈ 200 €/giorno: per 1-1,5 giornate "
             "considera 600-700 € a corpo."},
    {"codice": "3.3", "categoria": "Ricostruzioni e ripristini", "um": "m²",
     "prezzo": 40.0,
     "descrizione": "Rifacimento massetto tradizionale a pavimento",
     "nota": "Dove hai demolito il pavimento (bagno, corridoio…)."},
    {"codice": "3.4", "categoria": "Ricostruzioni e ripristini", "um": "m²",
     "prezzo": 80.0,
     "descrizione": "Rifacimento parziale massetti per chiusura tracce",
     "nota": "Riprende la stessa quantità delle tracce a pavimento."},
    {"codice": "3.5", "categoria": "Ricostruzioni e ripristini",
     "um": "a corpo", "prezzo": 1000.0,
     "descrizione": "Chiusura tracce e predisposizioni a parete",
     "nota": "Tracce piccole da scanalatrice chiuse a malta: ~1.000 € a "
             "corpo su un trilocale."},
    {"codice": "3.6", "categoria": "Ricostruzioni e ripristini", "um": "m²",
     "prezzo": 25.0,
     "descrizione": "Rifacimento intonaci",
     "nota": "Dove sono stati rimossi i rivestimenti (bagno, fascia "
             "cucina): l'intonaco ridà planarità al muro scavato."},
    {"codice": "3.7", "categoria": "Ricostruzioni e ripristini", "um": "m²",
     "prezzo": 50.0,
     "descrizione": "Realizzazione controsoffitti in cartongesso",
     "nota": "Tipico: bagno e vecchio corridoio (aiuta luci e impianti)."},
    {"codice": "3.8", "categoria": "Ricostruzioni e ripristini", "um": "m²",
     "prezzo": 50.0,
     "descrizione": "Pareti in cartongesso"},
    {"codice": "3.9", "categoria": "Ricostruzioni e ripristini", "um": "ml",
     "prezzo": 70.0,
     "descrizione": "Veletta in cartongesso",
     "nota": "Ogni metro lineare conta circa come un metro quadrato."},
    {"codice": "3.10", "categoria": "Ricostruzioni e ripristini", "um": "m²",
     "prezzo": 55.0,
     "descrizione": "Fornitura e posa pavimenti in piastrelle (gres)",
     "nota": "Superficie netta calpestabile."},
    {"codice": "3.11", "categoria": "Ricostruzioni e ripristini", "um": "m²",
     "prezzo": 48.0,
     "descrizione": "Posa pavimentazione esterna (balconi e terrazzi) con "
                    "spessoratura",
     "nota": "I metri calpestabili delle zone disegnate come balcone, "
             "terrazzo o loggia. Lavorazione diversa da quella interna: "
             "spessoratura, pendenze e stuccatura per esterni. Se c'è da "
             "demolire anche il vecchio, c'è la 3.30."},
    {"codice": "3.12", "categoria": "Ricostruzioni e ripristini", "um": "m²",
     "prezzo": 55.0,
     "descrizione": "Fornitura e posa rivestimenti in piastrelle",
     "nota": "Perimetro dei locali spuntati «Rivestito» per l'altezza della "
             "fascia (~1,20 m; zona doccia ~2,40 m), meno vani porta e "
             "finestre. Il lato senza utenze può restare senza rivestimento."},
    {"codice": "3.13", "categoria": "Ricostruzioni e ripristini", "um": "m²",
     "prezzo": 18.0,
     "descrizione": "Sistemazione planarità con malta autolivellante",
     "nota": "Dove è stato tolto il parquet e sui raccordi tra massetti "
             "vecchi e nuovi."},
    {"codice": "3.14", "categoria": "Ricostruzioni e ripristini", "um": "ml",
     "prezzo": 16.0,
     "descrizione": "Profilo terminale in alluminio",
     "nota": "Chiude il bordo superiore del rivestimento (estetica)."},
    {"codice": "3.15", "categoria": "Ricostruzioni e ripristini", "um": "ml",
     "prezzo": 8.0,
     "descrizione": "Fornitura e posa battiscopa",
     "nota": "Stima rapida: ~metratura commerciale dell'appartamento."},
    {"codice": "3.16", "categoria": "Ricostruzioni e ripristini", "um": "m²",
     "prezzo": 45.0,
     "descrizione": "Fornitura e posa pavimenti LVT / a incastro"},
    {"codice": "3.17", "categoria": "Ricostruzioni e ripristini", "um": "m²",
     "prezzo": 15.0,
     "descrizione": "Fornitura e posa membrana desolidarizzante",
     "nota": "Serve se si ripavimenta sopra un parquet esistente (evita "
             "che la dilatazione termica crepi le piastrelle)."},
    {"codice": "3.18", "categoria": "Ricostruzioni e ripristini", "um": "m²",
     "prezzo": 12.0,
     "descrizione": "Rasatura muri e soffitti (2 mani, compresi materiali)",
     "nota": "Solo dove serve (es. dove c'era la carta da parati): somma "
             "muri × altezza."},
    {"codice": "3.19", "categoria": "Ricostruzioni e ripristini", "um": "m²",
     "prezzo": 8.0,
     "descrizione": "Tinteggiatura muri e soffitti (2 mani, compresi "
                    "materiali)",
     "nota": "Stima: m² commerciali × 3-3,5 (es. 80 m² → ~250 m²). In "
             "alternativa ~2.000 € a corpo per un trilocale già rasato."},
    {"codice": "3.20", "categoria": "Ricostruzioni e ripristini", "um": "cad",
     "prezzo": 150.0,
     "descrizione": "Sostituzione davanzali in marmo"},
    {"codice": "3.21", "categoria": "Ricostruzioni e ripristini", "um": "cad",
     "prezzo": 350.0,
     "descrizione": "Predisposizione porta scrigno su muratura"},
    {"codice": "3.22", "categoria": "Ricostruzioni e ripristini", "um": "cad",
     "prezzo": 350.0,
     "descrizione": "Predisposizione porta scrigno su cartongesso"},
    {"codice": "3.23", "categoria": "Ricostruzioni e ripristini", "um": "cad",
     "prezzo": 95.0,
     "descrizione": "Fornitura e posa controtelai in legno",
     "nota": "Uno per ogni porta interna prevista."},
    {"codice": "3.24", "categoria": "Ricostruzioni e ripristini", "um": "cad",
     "prezzo": 280.0,
     "descrizione": "Fornitura e posa porte interne"},
    # Nata come voce scritta a mano su ENI, e passata al listino per
    # ritrovarla in ogni progetto e agganciarla al disegno. Tiene il codice
    # che aveva là: vedi `assorbi_voci_tue`.
    {"codice": "3.30", "categoria": "Ricostruzioni e ripristini", "um": "m²",
     "prezzo": 0.0,
     "descrizione": "Demolizione e posa pavimentazione balconi e terrazze "
                    "con spessoratura e stuccatura finale compreso colle, "
                    "stucchi e se necessario massetto autolivellante e "
                    "impermeabilizzazione",
     "nota": "I metri calpestabili delle zone disegnate come balcone, "
             "terrazzo o loggia, come la 3.11 — che però è la sola posa: "
             "il disegno ne alimenta una delle due, quella che è nel "
             "computo. Nel computo di ENI il prezzo non c'era ancora: da "
             "stabilire."},

    # ----------------------------------------------------------- 3 · Idraulico
    {"codice": "4.1", "categoria": "Idraulico", "um": "utenza",
     "prezzo": 250.0,
     "descrizione": "Impianto idraulico: carico/scarico per utenza, "
                    "compresi smontaggio e montaggio sanitari",
     "nota": "Conta le utenze: cucina, lavastoviglie, lavatrice, boiler, "
             "WC, bidet, lavabo, doccia, rubinetto d'arresto contatore."},
    {"codice": "4.2", "categoria": "Idraulico", "um": "cad", "prezzo": 150.0,
     "descrizione": "Modifica radiatori su impianto esistente"},
    {"codice": "4.3", "categoria": "Idraulico", "um": "cad", "prezzo": 350.0,
     "descrizione": "Predisposizione split (climatizzazione)",
     "nota": "Tipico: living + camere (es. 3 in un trilocale)."},
    {"codice": "4.4", "categoria": "Idraulico", "um": "cad", "prezzo": 350.0,
     "descrizione": "Allacciamento / spostamento boiler a gas"},
    {"codice": "4.5", "categoria": "Idraulico", "um": "cad", "prezzo": 160.0,
     "descrizione": "Cassetta di risciacquo a incasso (Geberit)"},
    {"codice": "4.6", "categoria": "Idraulico", "um": "cad", "prezzo": 200.0,
     "descrizione": "Piatto doccia"},
    {"codice": "4.7", "categoria": "Idraulico", "um": "cad", "prezzo": 40.0,
     "descrizione": "Valvola d'arresto contatore"},
    {"codice": "4.8", "categoria": "Idraulico", "um": "cad", "prezzo": 350.0,
     "descrizione": "Rubinetteria completa (fascia media)"},
    {"codice": "4.9", "categoria": "Idraulico", "um": "cad", "prezzo": 150.0,
     "descrizione": "Termosifone (prezzo medio)"},
    {"codice": "4.10", "categoria": "Idraulico", "um": "cad", "prezzo": 800.0,
     "descrizione": "Boiler a gas (~17 litri)"},
    {"codice": "4.11", "categoria": "Idraulico", "um": "cad", "prezzo": 40.0,
     "descrizione": "Valvola contacalorie",
     "nota": "Con riscaldamento centralizzato: una per termosifone."},
    {"codice": "4.12", "categoria": "Idraulico", "um": "cad", "prezzo": 50.0,
     "descrizione": "Sifone doccia (Geberit)"},
    {"codice": "4.13", "categoria": "Idraulico", "um": "cad", "prezzo": 70.0,
     "descrizione": "Termoarredo bagno (~1,4 m)"},

    # -------------------------------------------------------- 4 · Elettricista
    {"codice": "5.1", "categoria": "Elettricista", "um": "cad",
     "prezzo": 650.0,
     "descrizione": "Fornitura e posa quadro elettrico (6 linee)"},
    {"codice": "5.2", "categoria": "Elettricista", "um": "punto",
     "prezzo": 73.0,
     "descrizione": "Impianto elettrico a punti (esecuzione tracce, "
                    "apparecchiature e placche comprese)",
     "nota": "Un trilocale richiede ~50-60 punti (prese, frutti, punti "
             "luce). Attenzione a non contare due volte le tracce già "
             "messe nelle demolizioni."},
    {"codice": "5.3", "categoria": "Elettricista", "um": "cad",
     "prezzo": 110.0,
     "descrizione": "Elettrificazione tapparelle"},
    {"codice": "5.4", "categoria": "Elettricista", "um": "cad",
     "prezzo": 100.0,
     "descrizione": "Fornitura e posa citofono"},
    {"codice": "5.5", "categoria": "Elettricista", "um": "cad",
     "prezzo": 20.0,
     "descrizione": "Fornitura e posa faretti in controsoffitto",
     "nota": "Circa un faretto ogni 80-100 cm nei controsoffitti (bagno, "
             "antibagno, corridoio, cucina)."},

    # ---------------------------------------------------------- 5 · Serramenti
    {"codice": "6.1", "categoria": "Serramenti", "um": "m²", "prezzo": 450.0,
     "descrizione": "Fornitura e posa serramenti a taglio termico "
                    "(compresi rimozione e smaltimento esistenti)",
     "nota": "Un trilocale ha in genere 12-15 m² di serramenti (K termico "
             "~1,3)."},
    {"codice": "6.2", "categoria": "Serramenti", "um": "cad", "prezzo": 150.0,
     "descrizione": "Fornitura e posa celini a slitta",
     "nota": "I celini sostengono le avvolgibili: contali dalla "
             "planimetria (uno per finestra con tapparella)."},
    {"codice": "6.3", "categoria": "Serramenti", "um": "cad", "prezzo": 100.0,
     "descrizione": "Fornitura e posa avvolgibili motorizzati"},
    {"codice": "6.4", "categoria": "Serramenti", "um": "cad",
     "prezzo": 1450.0,
     "descrizione": "Fornitura e posa porta blindata pantografata",
     "nota": "La pantografata replica i disegni del portoncino esistente "
             "(spesso richiesto dal condominio): 1.500-2.000 €."},
    {"codice": "6.5", "categoria": "Serramenti", "um": "cad", "prezzo": 250.0,
     "descrizione": "Posa in quota porta blindata"},

    # -------------------------------------------------------- 6 · Aree esterne
    {"codice": "7.1", "categoria": "Aree esterne", "um": "cad",
     "prezzo": 600.0,
     "descrizione": "Spostamento / eliminazione contatore gas"},
    {"codice": "7.2", "categoria": "Aree esterne", "um": "m²", "prezzo": 15.0,
     "descrizione": "Ripristino balconi",
     "nota": "Controlla dalle foto: infiorescenze, distacchi, frontalini."},

    # ------------------------------------------------------- 7 · Tetto
    {"codice": "8.1", "categoria": "Tetto", "um": "m²",
     "prezzo": 22.0,
     "descrizione": "Formazione di ponteggio con tubolari metallici da terra "
                    "ad un metro di altezza sopra la gronda, completo per ogni"
                    " impalcato di tavole fermapiede , correnti cancelletti "
                    "laterali teli antipolvere , parasassi scale, botola, "
                    "impianto di messa a terra, luci di ingombro, cartelli "
                    "segnaletici sia di pericolo che antinfortunistici, "
                    "ancoraggio ed ogni onere per dare il tutto in sicurezza e"
                    " a norma escluso l’onere dell’occupazione del suolo "
                    "pubblico. Per tutta la durata stimata del cantiere.",
     "nota": "Metri quadri di ponteggio: sviluppo delle facciate per l'altezza"
             " fino a un metro sopra la gronda. Scrivi le dimensioni in "
             "descrizione. L'occupazione di suolo pubblico è a parte (1.11)."},
    {"codice": "8.2", "categoria": "Tetto", "um": "a corpo",
     "prezzo": 1000.0,
     "descrizione": "Smontaggio di eventuali docce, canale e scossaline "
                    "ammalorate o non più idonee, compreso il calo in basso, "
                    "il carico ed il successivo smaltimento presso la pubblica"
                    " discarica."},
    {"codice": "8.3", "categoria": "Tetto", "um": "m²",
     "prezzo": 32.0,
     "descrizione": "Disfacimento del manto di copertura in laterizi, compreso"
                    " abbassamento dei materiali al piano di carico "
                    "dell'automezzo ed il successivo smaltimento presso la "
                    "pubblica discarica."},
    {"codice": "8.4", "categoria": "Tetto", "um": "m²",
     "prezzo": 25.0,
     "descrizione": "Sostituzione dell’orditura secondaria orditura (terzere, "
                    "con sezione superiore o uguale a 200 cmq) ove compromessa"
                    " in opera, compresi gli oneri per la rimozione e lo "
                    "smaltimento della struttura esistente. Ed eventuali "
                    "rinforzi con la fornitura e la messa in opera di piccoli "
                    "profilati in acciaio in corrispondenza dell’eventuale "
                    "orditura primaria ammalorata.",
     "nota": "Si sostituisce solo dove è compromessa: di solito si stima il "
             "35% della copertura."},
    {"codice": "8.5", "categoria": "Tetto", "um": "m²",
     "prezzo": 6.0,
     "descrizione": "Solo posa di membrana impermeabilizzante per la "
                    "formazione della barriera al vapore, costituita da un "
                    "tessuto composito rinforzato 005 (feltro di vetro con "
                    "poliestere) guaina traspirante."},
    {"codice": "8.6", "categoria": "Tetto", "um": "m²",
     "prezzo": 35.0,
     "descrizione": "Solo posa in opera di materiali per isolamento termico "
                    "(lana di vetro o di roccia, polistirolo, poliuretano, "
                    "materiali similari) sia in rotoli che in lastre di "
                    "dimensione adeguata che abbia comunque la trasmittanza "
                    "come richiesta dalla normativa vigente U (W/m2K) di 0.28."
                    " Compreso il carico, lo scarico, il trasporto e deposito "
                    "in copertura del fabbricato ed ogni onere/accessorio per "
                    "dare l’opera finita a regola d’arte."},
    {"codice": "8.7", "categoria": "Tetto", "um": "m²",
     "prezzo": 38.0,
     "descrizione": "eventuale - Fornitura e posa in opera di tavolato in "
                    "legno per copertura inclinata, realizzato con tavole in "
                    "legno di abete piallate, spessore minimo 20–25 mm, posate"
                    " accostate su struttura portante esistente costituita da "
                    "travetti in legno. L’intervento comprende il fissaggio "
                    "mediante chiodatura o viti idonee alla struttura "
                    "sottostante, eventuali tagli, adattamenti, sfridi, "
                    "allineamenti e la formazione di piano continuo di "
                    "supporto per la successiva posa degli strati di copertura"
                    " (barriera/freno al vapore e pannelli isolanti)."},
    {"codice": "8.8", "categoria": "Tetto", "um": "m²",
     "prezzo": 58.0,
     "descrizione": "Fornitura e posa di manto di copertura in embrici e coppi"
                    " nuovi, compreso la muratura della prima fila di gronda e"
                    " delle mantelline, pezzi di colmo, eventuali para passeri"
                    " e qualunque cosa per dare l’opera finita a regola d'arte"},
    {"codice": "8.9", "categoria": "Tetto", "um": "ml",
     "prezzo": 90.0,
     "descrizione": "Fornitura e messa in opera di canale di gronda in "
                    "alluminio sviluppo fino a 40/45 cm compreso gli ancoraggi"
                    " e ogni onere per dare l’opera finita a regola d’arte e "
                    "ricollocazione dei pluviali precedentemente rimossi."},
    {"codice": "8.10", "categoria": "Tetto", "um": "ml",
     "prezzo": 50.0,
     "descrizione": "Fornitura e messa in opera di scossaline in alluminio "
                    "compreso gli ancoraggi ed ogni onere per dare l’opera "
                    "finita a regola d’arte."},
    {"codice": "8.11", "categoria": "Tetto", "um": "a corpo",
     "prezzo": 0.0,
     "descrizione": "Installazione antenna centralizzata compreso filaggio "
                    "cavi fino al piano terra.",
     "nota": "Nel computo del tetto di ENI il prezzo non c'era: da chiedere "
             "all'impresa."},
    {"codice": "8.12", "categoria": "Tetto", "um": "a corpo",
     "prezzo": 4000.0,
     "descrizione": "Rinforzi sia murari per il sostentamento delle travi "
                    "principali ed il fissaggio delle stesse tra di loro (dove"
                    " necessita) tramite staffature e chiodature di acciaio"},
    {"codice": "8.13", "categoria": "Tetto", "um": "m²",
     "prezzo": 0.0,
     "descrizione": "Formazione di piano di calpestio in tavolato che andrà "
                    "recuperato a fine opere per la messa in sicurezza del "
                    "pavimento del sottotetto per le lavorazioni di smontaggio"
                    " e sistemazioni travi per la copertura.",
     "nota": "Nel computo del tetto di ENI il prezzo non c'era: da chiedere "
             "all'impresa. Il tavolato si recupera a fine lavori."},

    # ---------------------------------------------------- 8 · Facciata
    {"codice": "9.1", "categoria": "Facciata", "um": "a corpo",
     "prezzo": 2500.0,
     "descrizione": "Allestimento cantiere",
     "nota": "Se l'allestimento c'è già nel computo degli interni, non "
             "contarlo due volte."},
    {"codice": "9.2", "categoria": "Facciata", "um": "ml",
     "prezzo": 10.0,
     "descrizione": "Smontaggio di pluviali, canale e scossaline compreso il "
                    "calo in basso, il carico ed il successivo smaltimento "
                    "presso la pubblica discarica."},
    {"codice": "9.3", "categoria": "Facciata", "um": "m²",
     "prezzo": 25.0,
     "descrizione": "Asportazione tramite spicconatura con mezzo meccanico "
                    "leggero di tutto l'intonaco ammalorato di tutte le "
                    "facciate fatiscenti compreso gronde e sotto terrazzi o "
                    "distaccato sarà rimosso fino al vivo della muratura di "
                    "pietra, mattoni o mista. Distacco di cavi in facciata di "
                    "utenze ecc e successiva protezione. Successivo lavaggio "
                    "del paramento ed allargamento delle eventuali cavillature"
                    " mediante l'impiego di un impianto erogante acqua "
                    "nebulizzata in pressione. Comprensivo di abbassamento "
                    "delle macerie al piano di carico e trasporto alle PP.DD.",
     "nota": "Di solito il 20% della superficie di facciata (su 1.050 m² sono "
             "210 m²)."},
    {"codice": "9.4", "categoria": "Facciata", "um": "m²",
     "prezzo": 15.0,
     "descrizione": "Scarificazione della superficie ove necessario."},
    {"codice": "9.5", "categoria": "Facciata", "um": "m²",
     "prezzo": 35.0,
     "descrizione": "Ricostruzione e intonacatura di elementi di facciata "
                    "precedentemente asportati con malta a base calce "
                    "fibrorinzorzata, con rete strutturale in fibra di vetro "
                    "(in alternativa rete zincata). La dove è consentito dalle"
                    " normative vigenti, si deve prevedere anche il "
                    "posizionamento sottotraccia dei cavi utenze presenti in "
                    "facciata che risultano antiestetici.",
     "nota": "Di solito il 20% della superficie di facciata, come "
             "l'asportazione (9.3)."},
    {"codice": "9.6", "categoria": "Facciata", "um": "m²",
     "prezzo": 38.0,
     "descrizione": "Rasatura fibrorinforzata a base calce per "
                    "regolarizzazione di tutte le superfici della facciata. Al"
                    " fine di migliorare la resistenza alle tensioni "
                    "superficiali che potrebbero provocare nel tempo la "
                    "formazione di fessurazioni, si procederà anche con la "
                    "fornitura e la posa di una rete di supporto su tutta la "
                    "superficie. La rete deve essere inserita tra 1° e 2° mano"
                    " del prodotto rasante.",
     "nota": "In alternativa al cappotto (9.7), che la rasatura la comprende "
             "già."},
    {"codice": "9.7", "categoria": "Facciata", "um": "m²",
     "prezzo": 60.0,
     "descrizione": "eventuale - Realizzazione e fornitura di isolamento "
                    "termico a cappotto con lastre di EPS di qualsiasi "
                    "dimensione e spessore, compreso il carico, lo scarico, il"
                    " trasporto e deposito a qualsiasi piano del fabbricato. "
                    "Sono compresi inoltre gli oneri relativi a: incollaggio "
                    "e/o tassellatura e sagomatura dei pannelli, rasatura, "
                    "stesura di fissativo, applicazione del rasante a base di "
                    "calce idraulica naturale steso con spatola d'acciaio, "
                    "compresa la posa di rete d'armatura e di ogni altro onere"
                    " necessario per dare l'opera finita a perfetta regola "
                    "d'arte.",
     "nota": "Comprende già la rasatura: con il cappotto la 9.6 non serve."},
    {"codice": "9.8", "categoria": "Facciata", "um": "m²",
     "prezzo": 22.0,
     "descrizione": "Pitturazione a due mani previa stesura di prime, con "
                    "tempera silossanica. Il colore è da concordare con DD.LL."
                    " previa campionatura.",
     "nota": "In alternativa all'intonachino (9.9): 18 € basic o 25 € "
             "intonachino con colore premium."},
    {"codice": "9.9", "categoria": "Facciata", "um": "m²",
     "prezzo": 25.0,
     "descrizione": "Pitturazione con intonachino premiscelato",
     "nota": "In alternativa alla tempera silossanica (9.8): 18 € basic o 25 €"
             " intonachino con colore premium."},
    {"codice": "9.10", "categoria": "Facciata", "um": "ml",
     "prezzo": 50.0,
     "descrizione": "Fornitura e messa in opera di pluviali in alluminio "
                    "compreso gli ancoraggi ed ogni onere per dare l’opera "
                    "finita a regola d’arte."},
    {"codice": "9.11", "categoria": "Facciata", "um": "a corpo",
     "prezzo": 1500.0,
     "descrizione": "Installazione scala esterna"},
]


def voci_della_categoria(categoria):
    """Le voci del listino di una categoria, nell'ordine del listino."""
    return [v for v in VOCI if v["categoria"] == categoria]


def voce_per_codice(codice):
    """La voce con quel codice, o None se non esiste."""
    for voce in VOCI:
        if voce["codice"] == codice:
            return voce
    return None


def assorbi_voci_tue(dati):
    """Le voci tue di un progetto che nel frattempo sono entrate nel listino.

    Una voce scritta a mano in un progetto può passare al listino con lo
    stesso codice (la 3.30 di ENI), per ritrovarla in tutti i progetti e
    agganciarla al disegno. Il file però la tiene ancora fra le voci tue, e
    due voci con lo stesso codice nel computo non ci stanno: vince quella
    del listino, e l'altra resta nel file invisibile, con la quantità e il
    prezzo che ci erano stati scritti.

    Qui la voce tua diventa quella del listino: quantità e prezzo passano in
    `listino_stato`, descrizione e unità in `testi_voci` quando non sono
    quelle del listino — a video si legge quello che c'era scritto. Scelte,
    scarti e voci scritte a mano parlano già di quel codice e restano come
    sono. Solo a parità di categoria.

    ⚠️ Lo stesso codice può voler dire voci diverse in progetti diversi (la
    3.29 di ENI non è quella di Migliarina): prima di dare al listino un
    codice già usato da una voce tua, si guarda che sia la stessa voce
    ovunque. Qui il testo si conserva comunque, ma l'aggancio al disegno
    arriverebbe anche a quella che non c'entra.

    Ritorna una copia; i dati passati non si toccano.
    """
    voci_tue = (dati or {}).get("voci") or []
    if not any(voce_per_codice(r.get("codice")) for r in voci_tue):
        return dati
    dati = dict(dati)
    stato = dict(dati.get("listino_stato") or {})
    testi = dict(dati.get("testi_voci") or {})
    restano = []
    for riga in voci_tue:
        guida = voce_per_codice(riga.get("codice"))
        if guida is None or riga.get("categoria") != guida["categoria"]:
            restano.append(riga)
            continue
        codice = guida["codice"]
        stato.setdefault(codice, {
            "q": float(riga.get("quantita_manuale") or 0.0),
            "p": float(riga.get("prezzo") or 0.0)})
        descrizione = (riga.get("descrizione") or "").strip()
        um = riga.get("um") or ""
        testi.setdefault(codice, {
            "d": descrizione if descrizione != guida["descrizione"] else None,
            "u": um if um != guida["um"] else None})
    dati["voci"] = restano
    dati["listino_stato"] = stato
    dati["testi_voci"] = testi
    return dati
