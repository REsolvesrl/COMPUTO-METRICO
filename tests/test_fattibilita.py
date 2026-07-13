import pytest

from fattibilita import (
    costi_acquisto,
    costi_vendita,
    iva_scorporata,
    matrice_sensitivita,
    riepilogo_per_categoria,
    stima_mca,
    studio_fattibilita,
    totale_spese,
)

# Parametri dell'operazione REALE nel file Excel dell'utente
# ("Business plan attuale.xlsx", scheda Studio fattibilità).
PARAMETRI_EXCEL = {
    "prezzo_acquisto": 300000.0,
    "prezzo_vendita": 460000.0,
    "imposta_pct": 9.0,
    "imposte_fisse": 0.0,
    "notaio": 3500.0,
    "agenzia_in_pct": 3.0,
    "agenzia_out_pct": 2.5,
    "iva_agenzia_pct": 22.0,
    "imprevisti": 15000.0,
    "spese_mutuo": 0.0,
    "ristrutturazione": 0.0,
    "mq": 192.0,
    "durata_mesi": 12,
}


def test_costi_acquisto_come_excel():
    acq = costi_acquisto(300000, imposta_pct=9.0, notaio=3500,
                         agenzia_pct=3.0, iva_agenzia_pct=22.0,
                         imprevisti=15000)
    assert acq["imposte"] == 27000.0          # U12
    assert acq["agenzia"] == 10980.0          # U20 = 300000 × 3% × 1,22
    assert acq["totale"] == 56480.0           # U22


def test_costi_vendita_come_excel():
    ven = costi_vendita(460000, agenzia_pct=2.5, iva_agenzia_pct=22.0)
    assert ven["totale"] == 14030.0           # U25 = 460000 × 3,05%


def test_studio_fattibilita_come_excel():
    esito = studio_fattibilita(PARAMETRI_EXCEL)
    assert esito["entry"] == 356480.0                       # C13
    assert esito["exit"] == 445970.0                        # C18
    assert esito["ebit"] == 89490.0                         # C24
    assert esito["multiplo"] == pytest.approx(1.2510379, abs=1e-6)  # C20
    assert esito["roe"] == pytest.approx(0.2510379, abs=1e-6)       # C21
    assert esito["eur_mq_acquisto"] == 1562.5               # D11
    assert esito["eur_mq_vendita"] == pytest.approx(2395.83, abs=0.01)


def test_roi_annualizzato():
    # su 12 mesi il rendimento annuo coincide col ROE
    esito = studio_fattibilita(PARAMETRI_EXCEL)
    assert esito["roi_annuo"] == pytest.approx(0.2510379, abs=1e-6)
    # su 24 mesi si dimezza (in senso composto)
    parametri = dict(PARAMETRI_EXCEL, durata_mesi=24)
    esito24 = studio_fattibilita(parametri)
    assert esito24["roi_annuo"] == pytest.approx(1.2510379 ** 0.5 - 1,
                                                 abs=1e-6)


def test_matrice_sensitivita_centro_e_dimensioni():
    prezzi_a, prezzi_v, matrice = matrice_sensitivita(
        PARAMETRI_EXCEL, 10000.0)
    assert len(prezzi_a) == 11 and len(prezzi_v) == 9
    assert prezzi_a[5] == 300000.0 and prezzi_v[4] == 460000.0
    # il centro della matrice è il caso base
    assert matrice[5][4] == pytest.approx(1.2510379, abs=1e-6)
    # il guadagno cresce con il prezzo di vendita
    _, _, guadagni = matrice_sensitivita(PARAMETRI_EXCEL, 10000.0,
                                         metrica="guadagno")
    assert guadagni[5][4] == pytest.approx(89490.0, abs=0.1)
    assert guadagni[5][5] > guadagni[5][4] > guadagni[5][3]


def test_matrice_esclude_prezzi_negativi():
    parametri = dict(PARAMETRI_EXCEL, prezzo_acquisto=20000.0)
    prezzi_a, _, _ = matrice_sensitivita(parametri, 10000.0)
    assert all(p > 0 for p in prezzi_a)


def test_stima_mca_come_excel():
    # i 5 comparabili del foglio "MCA sell", coi coefficienti complessivi
    comparabili = [
        {"nome": "C1", "prezzo": 310000, "mq": 100,
         "coeff": 1.2400430842800005},
        {"nome": "C2", "prezzo": 210000, "mq": 70, "coeff": 1.02221595},
        {"nome": "C3", "prezzo": 320000, "mq": 140,
         "coeff": 1.0736303759999999},
        {"nome": "C4", "prezzo": 200000, "mq": 71, "coeff": 1.1466},
        {"nome": "C5", "prezzo": 240000, "mq": 110,
         "coeff": 0.8787198557812502},
    ]
    esito = stima_mca(comparabili, coeff_soggetto=1.4750915150790005,
                      mq_soggetto=190, sconto_pct=13.0)
    assert esito["eur_mq_media"] == pytest.approx(2500.67, abs=0.01)  # P101
    assert esito["eur_mq_soggetto"] == pytest.approx(3688.72, abs=0.05)
    assert esito["eur_mq_probabile"] == pytest.approx(3209.19, abs=0.05)
    assert esito["valore"] == pytest.approx(609745.70, abs=15)       # O92


def test_stima_mca_ignora_comparabili_non_validi():
    comparabili = [
        {"nome": "ok", "prezzo": 300000, "mq": 100, "coeff": 1.0},
        {"nome": "senza mq", "prezzo": 300000, "mq": 0, "coeff": 1.0},
        {"nome": "senza prezzo", "prezzo": 0, "mq": 100, "coeff": 1.0},
    ]
    esito = stima_mca(comparabili, 1.0, 100, sconto_pct=0.0)
    assert len(esito["dettaglio"]) == 1
    assert esito["valore"] == 300000.0


def test_stima_mca_senza_comparabili():
    assert stima_mca([], 1.0, 100) is None


# ------------------------------------------------ spese a consuntivo

def test_iva_scorporata():
    # 122 € al 22% contengono 22 € di IVA
    assert iva_scorporata(122.0, 22.0) == 22.0
    # 110 € al 10% contengono 10 €
    assert iva_scorporata(110.0, 10.0) == 10.0


def test_iva_scorporata_aliquota_zero():
    assert iva_scorporata(1000.0, 0.0) == 0.0
    assert iva_scorporata(1000.0, None) == 0.0


def test_totale_spese():
    righe = [{"importo": 100.0}, {"importo": 250.5}, {"importo": 0.0}]
    assert totale_spese(righe) == 350.5


def test_riepilogo_per_categoria_aggrega_e_scorpora():
    righe = [
        {"categoria": "MATERIALE", "importo": 122.0, "aliquota_iva": 22.0},
        {"categoria": "MATERIALE", "importo": 110.0, "aliquota_iva": 10.0},
        {"categoria": "LAVORI", "importo": 1000.0, "aliquota_iva": 0.0},
    ]
    riep = riepilogo_per_categoria(righe)
    assert riep["MATERIALE"] == {"importo": 232.0, "iva": 32.0}
    assert riep["LAVORI"] == {"importo": 1000.0, "iva": 0.0}


def test_riepilogo_per_categoria_ordine_e_default():
    # categorie fuori elenco in coda; categoria vuota -> ALTRO
    righe = [
        {"categoria": "LAVORI", "importo": 10.0, "aliquota_iva": 0.0},
        {"categoria": "ACQUISTO", "importo": 20.0, "aliquota_iva": 0.0},
        {"categoria": "", "importo": 5.0, "aliquota_iva": 0.0},
    ]
    chiavi = list(riepilogo_per_categoria(righe))
    # ACQUISTO viene prima di LAVORI (ordine di CATEGORIE_SPESE)
    assert chiavi.index("ACQUISTO") < chiavi.index("LAVORI")
    assert "ALTRO" in chiavi