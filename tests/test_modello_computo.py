"""«Nuovo progetto» parte dalle voci dei nostri cantieri, non da un foglio bianco.

Dal 25/09/2026 sono le voci del listino che vengono da ENI o da La Spezia
Migliarina, tutte nel computo e a zero. Qui il modello in sé; quello che fa
«Nuovo progetto» sul banco sta in test_banco_computo.py.
"""
import listino
import modello_computo


def test_le_voci_del_modello_sono_quelle_dei_cantieri():
    """Ogni codice del modello esiste, e sono tutte e sole le nostre."""
    for codice in modello_computo.VOCI_SCELTE:
        assert listino.voce_per_codice(codice).get("cantieri"), codice
    assert len(modello_computo.VOCI_SCELTE) == len(
        [v for v in listino.VOCI if v.get("cantieri")])


def test_il_modello_parla_coi_numeri_nuovi():
    """Senza la chiave verrebbe preso per un file di prima, e tradotto."""
    assert modello_computo.progetto_nuovo()["listino"] == listino.VERSIONE


def test_ogni_progetto_nuovo_ha_la_sua_copia():
    """Il modello non si consuma: toccare un progetto non cambia il prossimo."""
    primo = modello_computo.progetto_nuovo()
    primo["voci_scelte"].clear()
    secondo = modello_computo.progetto_nuovo()
    assert secondo["voci_scelte"] == modello_computo.VOCI_SCELTE
