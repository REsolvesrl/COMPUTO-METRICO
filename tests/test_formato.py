import math

import pytest

from formato import colore_testo_su, euro, numero_da_it, numero_it


def test_numero_it_scambia_punto_e_virgola():
    assert numero_it(1234.5678) == "1.234,568"


def test_numero_it_decimali_su_richiesta():
    assert numero_it(1234.5678, 2) == "1.234,57"
    assert numero_it(1234.5678, 0) == "1.235"


def test_numero_it_migliaia_multiple():
    assert numero_it(1234567.89, 2) == "1.234.567,89"


def test_numero_it_negativo():
    assert numero_it(-1234.5, 2) == "-1.234,50"


def test_numero_it_senza_valore():
    assert numero_it(None) == ""
    assert numero_it(float("nan")) == ""


def test_euro_ha_la_sua_unita():
    assert euro(1234.56) == "1.234,56 €"
    assert euro(0) == "0,00 €"


def test_euro_senza_valore():
    assert euro(None) == ""
    assert euro(math.nan) == ""


def test_colore_testo_su_sfondo_chiaro_e_scuro():
    assert colore_testo_su("#FFD400") == "#1A2744"     # giallo: testo scuro
    assert colore_testo_su("#C0392B") == "#ECE7DA"     # rosso scuro: testo chiaro


def test_colore_testo_su_accetta_anche_senza_cancelletto():
    assert colore_testo_su("FFFFFF") == "#1A2744"
    assert colore_testo_su("000000") == "#ECE7DA"


# ---------------------------------- rileggere un numero scritto a mano

@pytest.mark.parametrize("scritto, atteso", [
    ("1.234,56", 1234.56),      # italiano completo
    ("1234,56", 1234.56),       # senza separatore di migliaia
    ("1.234", 1234.0),          # il punto raggruppa
    ("1.234.567", 1234567.0),   # due raggruppamenti
    ("1234", 1234.0),
    ("145000", 145000.0),
    ("1.234,56 €", 1234.56),    # con l'unità attaccata
    ("  300.000  ", 300000.0),  # con spazi
    ("0,80", 0.8),
    ("-1.234,56", -1234.56),
    ("1234.56", 1234.56),       # scritto all'inglese: il punto è decimale
    ("0", 0.0),
])
def test_numero_da_it_legge_come_scrive_una_persona(scritto, atteso):
    assert numero_da_it(scritto) == pytest.approx(atteso)


@pytest.mark.parametrize("scritto", ["", "   ", None, "abc", "€", "1,2,3",
                                     "--5"])
def test_numero_da_it_dice_di_no_a_cio_che_non_e_un_numero(scritto):
    assert numero_da_it(scritto) is None


def test_numero_da_it_e_numero_it_si_richiudono():
    """Quello che l'app scrive, l'app lo sa rileggere."""
    for valore in (0.0, 1234.56, 145000.0, 1234567.89, -42.5):
        assert numero_da_it(numero_it(valore, 2)) == pytest.approx(valore)


def test_numero_da_it_rilegge_anche_gli_euro_scritti_dall_app():
    assert numero_da_it(euro(242626.0)) == pytest.approx(242626.0)
