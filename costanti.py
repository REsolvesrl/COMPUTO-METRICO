"""Le costanti dell'interfaccia, fuori da Streamlit.

Colori del Campionario, categorie di superficie, tipi di muro, unita' di
misura, impostazioni predefinite del business plan: sono scritte in
`streamlit_app.py`, che non si puo' importare senza far partire la pagina.
Qui ce n'e' una copia per il motore nuovo (`server/`).

⚠️ Una copia, non una seconda verita': `tests/test_costanti.py` rilegge
`streamlit_app.py` e pretende che ogni valore qui sia identico al suo.
Finche' convivono, chi cambia un colore o una percentuale di la' lo deve
cambiare anche qui, e il test lo ricorda.
"""
import merito

ARDESIA = "#1A2744"

ARDESIA_CHIARA = "#243352"

OTTONE = "#C9A96A"

TRAVERTINO = "#ECE7DA"

COTTO = "#C1502E"

CEMENTO = "#6E7377"

GRES = "#4E7A5E"

COLORI_CATEGORIE = {
    # travertino: è l'unico capitolo che non è materia da cantiere ma carta,
    # e nel campionario la carta ha il colore della carta
    "Pratiche e oneri": ("#ECE7DA", "gray"),
    "Demolizioni": ("#E57373", "red"),
    "Ricostruzioni e ripristini": ("#66BB6A", "green"),
    "Idraulico": ("#64B5F6", "blue"),
    "Elettricista": ("#F0A840", "orange"),
    "Serramenti": ("#9575CD", "violet"),
    "Aree esterne": ("#B0BEC5", "gray"),
    "Tetto": ("#B8735A", "red"),          # cotto dei coppi
    "Facciata": ("#D9C7A7", "gray"),      # intonaco a calce
}

VOCI_DA_SUPERFICI = [
    # ⚠️ «pavimento» sono le stanze e basta: balconi, terrazzi e logge
    # stanno in «pavimento_esterno» e vanno nella 3.11 o nella 3.30, che
    # sono un'altra lavorazione. Una demolizione di pavimenti interni non
    # deve portarsi dentro i metri del balcone.
    ("2.1", "pavimento", True),           # demolizione pavimenti
    ("2.10", "battiscopa", False),        # rimozione zoccolini
    ("3.3", "pavimento", False),          # rifacimento massetto
    ("3.10", "pavimento", True),          # posa gres
    ("3.12", "rivestimenti", True),       # rivestimenti (fascia dei bagni)
    ("3.11", "pavimento_esterno", True),  # pavimentazione di balconi e terrazzi
    ("3.30", "pavimento_esterno", True),  # la stessa, demolendo la vecchia
    ("3.15", "battiscopa", True),         # posa battiscopa
    ("3.18", "rasatura", False),          # rasatura: le facce dei muri nuovi
    ("3.19", "tinteggiatura", True),      # tinteggiatura muri e soffitti
    # dai muri tracciati sulla planimetria (lunghezza × altezza)
    ("2.2", "muri_demolire", True),       # demolizione murature
    ("3.1", "muri_costruire", True),      # ricostruzione muri in forati
    ("3.8", "muri_cartongesso", True),    # pareti in cartongesso
]

ALTERNATIVE_DAL_DISEGNO = [
    # stessa misura, lavorazioni che si escludono: il disegno ne alimenta
    # una sola (planimetria.voci_alimentate)
    ("3.11", "3.30"),
]

COLORE_CATEGORIA_SPESA = {
    "ACQUISTO": "#FF8A70",         # 🔴 corallo
    "LAVORI": "#F4C143",           # 🟡 giallo
    "MATERIALE": "#78C46E",        # 🟢 verde
    "ARCHITETTO": "#F0982E",       # 🟠 arancio
    "COSTI INDIRETTI": "#D9DCE0",  # ⚪ grigio chiaro
    "AGENZIA": "#B49BE0",          # 🟣 viola
    "ALTRO": "#C0392B",            # 🟤 rosso scuro
}

IMPOSTAZIONI_BP = {
    "bp_acquisto": 0.0, "bp_vendita": 0.0, "bp_mq": 0.0,
    "bp_imposta": 9.0, "bp_imposte_fisse": 0.0, "bp_notaio": 3500.0,
    "bp_ag_in": 3.0, "bp_ag_out": 2.5, "bp_iva_ag": 22.0,
    "bp_imprevisti_pct": 10.0, "bp_imprevisti": 0.0, "bp_mutuo": 0.0, "bp_durata": 12,
    "bp_ristr": 0.0, "bp_passo": 10000.0,
    # Aliquote IVA, una per voce: l'imposta di registro non ne ha (e' gia'
    # un'imposta), notaio e servizi stanno al 22%, i lavori edili al 10%.
    # Imprevisti e condominio partono da ZERO: e' una riserva, non una
    # fattura, e le spese condominiali non portano IVA da scorporare. Chi ci
    # mette dentro qualcosa che ce l'ha cambia l'aliquota sulla riga.
    "bp_iva_imposta": 0.0, "bp_iva_imposte_fisse": 0.0,
    "bp_iva_notaio": 22.0, "bp_iva_mutuo": 22.0,
    "bp_iva_imprevisti": 0.0, "bp_iva_ristr": 10.0,
    "bp_iva_ag_in": 22.0, "bp_iva_ag_out": 22.0,
    "bp_coeff_sogg": 0.0, "bp_sconto": 13.0,
    # Correzione per il taglio: i tagli piccoli costano di piu' al metro.
    # E' l'unica voce della stima che non sta nella griglia dei coefficienti
    # perche' non si sceglie da una tendina — si ricava dalla superficie, che
    # e' gia' in tabella. A zero e' spenta. Vedi merito.coefficiente_taglio
    # per il perche' di 0,15 e per il perche' NON dell'ottimo statistico.
    "bp_taglio": 0.15,
    # Il costo dei lavori e la quota che il mercato ne riconosce: da questi
    # due si ricava di quanto deve allargarsi la voce «stato dell'unita'»,
    # perche' il salto fra il finito e il da-rifare E' il costo dei lavori,
    # meno quello che il mercato non paga. Vedi merito.scala_stato_unita.
    "bp_costo_ristr_mq": 900.0, "bp_quota_mercato": 85.0,
}

PREDEFINITI_SOGGETTO = {
    "stato_edificio": "Normale",
    "eta_edificio": "20-40 anni",
    "stato_unita": "Finemente ristrutturato",
    "finiture": "Civili",
    "balconi": "Sì",
    "giardino": "No",
    "terrazzo": "No",
    "luce_vista": "Esterna e luminosa",
    "spazi_comuni": "Assenti",
    "parcheggio": "Assente",
    "riscaldamento": "Autonomo",
}

SOGGETTO_MCA = {
    f"sog_{campo}": PREDEFINITI_SOGGETTO.get(
        campo, False if campo == "ascensore" else None)
    for campo in merito.CAMPI
}

TENDINE_MERITO = {
    "stato_edificio": ("Stato edificio", merito.STATI_EDIFICIO),
    "eta_edificio": ("Età edificio", merito.FASCE_ETA),
    "stato_unita": ("Stato dell'unità", tuple(merito.STATO_UNITA)),
    "finiture": ("Finiture", tuple(merito.FINITURE)),
    "piano": ("Piano", merito.LIVELLI_PIANO),
    "balconi": ("Balconi", tuple(merito.BALCONI)),
    "giardino": ("Giardino", tuple(merito.GIARDINO)),
    "terrazzo": ("Terrazzo", tuple(merito.TERRAZZO)),
    "luce_vista": ("Luce e vista", tuple(merito.LUCE_VISTA)),
    "spazi_comuni": ("Spazi comuni", tuple(merito.SPAZI_COMUNI)),
    "parcheggio": ("Parcheggio", tuple(merito.PARCHEGGIO)),
    "riscaldamento": ("Riscaldamento", tuple(merito.RISCALDAMENTO)),
}

GRIGLIA = "#3C4C6E"

ETICHETTE = "#A9B4C9"

CANON_MAX = 2000

PALETTE_ZONE = ["#E57373", "#F0A840", "#E8D44D", "#66BB6A", "#4DB6AC",
                "#64B5F6", "#9575CD", "#F06292"]

CATEGORIE_DEFAULT = [
    {"nome": "Superficie commerciale", "percento": 100.0},
    {"nome": "Superficie interna", "percento": 100.0},
    {"nome": "Balcone", "percento": 30.0},
    {"nome": "Terrazzo", "percento": 35.0},
    {"nome": "Loggia", "percento": 40.0},
    {"nome": "Giardino", "percento": 15.0, "soglia": 25.0, "oltre": 5.0},
    {"nome": "Garage / Box", "percento": 50.0},
    {"nome": "Cantina", "percento": 30.0},
    {"nome": "Vano scale", "percento": 50.0},
]

COLORE_CATEGORIA_SUP = {
    "Superficie commerciale": "#7E57C2",   # viola — solo contorno
    "Superficie interna": "#E57373",       # rosso
    "Balcone": "#F0A840",                  # arancio
    "Terrazzo": "#E8D44D",                 # giallo
    "Loggia": "#4DB6AC",                   # verde acqua
    "Giardino": "#4CAF50",                 # verde: è il giardino
    "Garage / Box": "#64B5F6",             # azzurro
    "Cantina": "#9575CD",                  # lilla
    "Vano scale": "#64B5F6",               # azzurro, come il garage
    # categorie di lavori precedenti: stesso colore dell'equivalente
    # attuale, così un disegno vecchio non cambia aspetto
    "Balcone scoperto": "#F0A840",
    "Balcone coperto": "#F0A840",
    "Balcone / Lastrico solare": "#F0A840",
    "Terrazzo di attico (a tasca)": "#E8D44D",
    "Portico / Patio": "#E8D44D",
    "Corte / Cortile": "#BCAAA4",
    "Giardino di appartamento": "#4CAF50",
    "Giardino di villa o villino": "#558B2F",
    "Cantina / Soffitta": "#9575CD",
}

PERCENTUALI_STORICHE = {
    "Cantina / Soffitta": 25.0,
    "Balcone scoperto": 30.0,
    "Balcone coperto": 35.0,
    "Balcone / Lastrico solare": 25.0,
    "Terrazzo di attico (a tasca)": 40.0,
    "Portico / Patio": 35.0,
    "Corte / Cortile": 10.0,
    "Giardino di appartamento": {"percento": 15.0, "soglia": 25.0,
                                 "oltre": 5.0},
    "Giardino di villa o villino": {"percento": 10.0, "soglia": 25.0,
                                    "oltre": 2.0},
}

CATEGORIE_INVOLUCRO = ("Superficie commerciale",)

CATEGORIE_ESTERNE = (
    "Balcone", "Terrazzo", "Loggia",
    # categorie di lavori precedenti, che restano valide dove sono usate
    "Balcone scoperto", "Balcone coperto", "Balcone / Lastrico solare",
    "Terrazzo di attico (a tasca)", "Portico / Patio",
)

CATEGORIE_SOLO_COMPUTO = ("Superficie interna",)

CATEGORIA_STANZE = "Superficie interna"

TIPI_PARETE = {
    "esistente": {"nome": "Esistente", "colore": "#C9A96A"},
    "demolire": {"nome": "Da demolire", "colore": "#E53935"},
    "costruire": {"nome": "Da costruire", "colore": "#FFD400"},
    # Il cartongesso è un'altra lavorazione dal muro in forati: altro
    # prezzo, altra impresa spesso, e sul disegno si distingue a colpo
    # d'occhio — verde.
    "cartongesso": {"nome": "Da costruire in cartongesso",
                    "colore": "#43A047"},
}

TIPI_PARETE_SCELTA = ["demolire", "costruire", "cartongesso"]

FILTRO_TUTTI = "Tutti gli stati"

UNITA_MISURA = ["m²", "ml", "m³", "cad", "punto", "a corpo"]

UM_A_CORPO = "a corpo"

UNITA_DELLA_CATEGORIA = {
    "Elettricista": "punto luce",
    "Idraulico": "punto acqua",
}

UM_A_PASSI = {UM_A_CORPO, "cad", "punto", "punto luce", "punto acqua",
              "utenza"}

PASSI_STORIA_COMPUTO = 15

VOCI_CON_IVA = (
    ("bp_imposta_eur", "bp_iva_imposta"),
    ("bp_imposte_fisse", "bp_iva_imposte_fisse"),
    ("bp_notaio", "bp_iva_notaio"),
    ("bp_mutuo", "bp_iva_mutuo"),
    ("bp_imprevisti", "bp_iva_imprevisti"),
    ("bp_ag_in_eur", "bp_iva_ag_in"),
)

CAMPI_NUMERO_IT = {
    "bp_acquisto": (0, "bp_ricalcola_euro", 0.0),
    "bp_vendita": (0, "bp_ricalcola_euro", 0.0),
    # il passo delle matrici non può essere zero: le colonne diventerebbero
    # tutte lo stesso prezzo
    "bp_passo": (0, None, 1000.0),
    "bp_imposta_eur": (2, "bp_pct_da_euro_imposta", 0.0),
    "bp_imposte_fisse": (2, None, 0.0),
    "bp_notaio": (2, None, 0.0),
    "bp_mutuo": (2, None, 0.0),
    "bp_imprevisti": (2, "bp_pct_da_euro_imprevisti", 0.0),
    "bp_ag_in_eur": (2, "bp_pct_da_euro_ag_in", 0.0),
    "bp_ag_out_eur": (2, "bp_pct_da_euro_ag_out", 0.0),
    "bp_ristr": (2, None, 0.0),
    "cant_contratto": (2, None, 0.0),
    "cant_extra": (2, None, 0.0),
}

PASSI_STORIA = 25

DA_ANNULLARE = {
    "zona_chiusa": "disegno dell'area",
    "zona_modificata": "modifica dell'area",
    "zona_eliminata": "eliminazione dell'area",
    "parete": "tracciamento del muro",
    "parete_modificata": "modifica del muro",
    "parete_eliminata": "eliminazione del muro",
    "rinomina": "rinomina del locale",
}
