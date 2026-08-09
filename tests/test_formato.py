import math

from formato import colore_testo_su, euro, numero_it


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
