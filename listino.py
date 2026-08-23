"""Listino voci guida per ristrutturazioni residenziali.

Voci pronte all'uso con prezzi medi indicativi (fonte: prassi corrente di
mercato per ristrutturazioni complete di appartamenti), organizzate nelle
categorie tipiche di un computo: demolizioni → ricostruzioni e ripristini →
impianti → serramenti → aree esterne.

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
]

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
             "spessoratura, pendenze e stuccatura per esterni."},
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
