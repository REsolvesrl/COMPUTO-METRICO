from calcoli import (
    SENZA_CATEGORIA,
    calcola_computo,
    calcola_voce,
    incidenze_percentuali,
    quantita_voce,
    totale_con_imprevisti,
    totale_con_iva,
    totale_generale,
    totali_per_categoria,
)


# ---------------------------------------------------------------- quantità

def test_quantita_tutte_le_dimensioni():
    # 2 parti × 4,00 m × 3,00 m × 0,50 m = 12 m³
    assert quantita_voce(2, 4.0, 3.0, 0.5) == 12.0


def test_quantita_dimensioni_parziali():
    # solo lunghezza × larghezza: le caselle vuote non contano
    assert quantita_voce(None, 4.0, 3.0, None) == 12.0


def test_quantita_solo_parti():
    assert quantita_voce(5, None, None, None) == 5.0


def test_quantita_manuale_quando_dimensioni_vuote():
    assert quantita_voce(quantita_manuale=7.5) == 7.5


def test_dimensioni_prevalgono_su_quantita_manuale():
    assert quantita_voce(2, 3.0, None, None, quantita_manuale=99.0) == 6.0


def test_quantita_tutto_vuoto():
    assert quantita_voce() == 0.0


def test_detrazione_con_parti_negative():
    # es. scomputo del vano porta da una parete
    assert quantita_voce(-1, 2.0, 1.0, None) == -2.0


def test_quantita_arrotondata_a_tre_decimali():
    # 1,111 × 1,111 = 1,234321 → 1,234
    assert quantita_voce(1, 1.111, 1.111, None) == 1.234


# ---------------------------------------------------------------- importi

def test_calcola_voce_importo():
    voce = {
        "descrizione": "Massetto di sottofondo",
        "parti": 1,
        "lunghezza": 5.0,
        "larghezza": 4.0,
        "prezzo": 18.5,
    }
    risultato = calcola_voce(voce)
    assert risultato["quantita"] == 20.0
    assert risultato["importo"] == 370.0
    # la voce originale non viene modificata
    assert "importo" not in voce


def test_calcola_voce_senza_prezzo():
    assert calcola_voce({"parti": 3})["importo"] == 0.0


def test_calcola_computo_elenco():
    voci = [
        {"prezzo": 10.0, "quantita_manuale": 2.0},
        {"prezzo": 5.0, "parti": 8},
    ]
    importi = [v["importo"] for v in calcola_computo(voci)]
    assert importi == [20.0, 40.0]


# ---------------------------------------------------------------- totali

VOCI_CALCOLATE = [
    {"categoria": "Demolizioni", "importo": 1000.0},
    {"categoria": "Demolizioni", "importo": 500.0},
    {"categoria": "Pavimenti", "importo": 2500.0},
    {"categoria": None, "importo": 100.0},
]


def test_totali_per_categoria():
    totali = totali_per_categoria(VOCI_CALCOLATE)
    assert totali["Demolizioni"] == 1500.0
    assert totali["Pavimenti"] == 2500.0


def test_voce_senza_categoria():
    totali = totali_per_categoria(VOCI_CALCOLATE)
    assert totali[SENZA_CATEGORIA] == 100.0


def test_totale_generale():
    assert totale_generale(VOCI_CALCOLATE) == 4100.0


def test_incidenze_percentuali():
    totali = {"A": 750.0, "B": 250.0}
    incidenze = incidenze_percentuali(totali, 1000.0)
    assert incidenze == {"A": 75.0, "B": 25.0}


def test_incidenze_con_totale_zero():
    assert incidenze_percentuali({"A": 0.0}, 0.0) == {"A": 0.0}


def test_totale_con_iva():
    iva, totale = totale_con_iva(100.0, 22.0)
    assert iva == 22.0
    assert totale == 122.0


def test_totale_con_iva_al_dieci_percento():
    # aliquota agevolata ristrutturazioni
    iva, totale = totale_con_iva(1234.56, 10.0)
    assert iva == 123.46
    assert totale == 1358.02


def test_totale_con_imprevisti():
    # come nell'esempio del computo: 41.503,20 + 5% = 43.578,36
    imprevisti, totale = totale_con_imprevisti(41503.20, 5.0)
    assert imprevisti == 2075.16
    assert totale == 43578.36


def test_totale_con_imprevisti_a_zero():
    imprevisti, totale = totale_con_imprevisti(1000.0, 0.0)
    assert imprevisti == 0.0
    assert totale == 1000.0
