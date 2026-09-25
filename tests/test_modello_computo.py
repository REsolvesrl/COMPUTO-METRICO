"""«Nuovo progetto» parte dalle voci di Migliarina, non da un foglio bianco.

Le voci, i testi riscritti e i prezzi sono quelli del cantiere di La Spezia
Migliarina; le quantità no, perché sono del cantiere nuovo. Qui il modello
in sé; quello che fa «Nuovo progetto» sul banco sta in test_banco_computo.py.
"""
import listino
import modello_computo


# ------------------------------------------------- il modello in sé

def test_le_voci_del_modello_esistono():
    """Ogni codice scelto è del listino o è una voce scritta a mano: un
    codice orfano sparirebbe in silenzio al caricamento."""
    tue = {v["codice"] for v in modello_computo.VOCI_TUE}
    for codice in modello_computo.VOCI_SCELTE:
        assert listino.voce_per_codice(codice) or codice in tue, codice


def test_prezzi_e_testi_riguardano_voci_del_listino():
    """Se il listino guida venisse rinumerato, qui un prezzo finirebbe
    appeso alla voce sbagliata: meglio saperlo da un test."""
    for codice in [*modello_computo.PREZZI, *modello_computo.TESTI]:
        assert listino.voce_per_codice(codice), codice


def test_le_voci_tue_non_pestano_i_piedi_al_listino():
    for voce in modello_computo.VOCI_TUE:
        assert listino.voce_per_codice(voce["codice"]) is None, voce["codice"]


def test_ogni_progetto_nuovo_ha_la_sua_copia():
    """Il modello non si consuma: toccare un progetto non cambia il prossimo."""
    primo = modello_computo.progetto_nuovo()
    primo["voci_scelte"].clear()
    primo["testi_voci"]["3.1"]["d"] = "altro"
    secondo = modello_computo.progetto_nuovo()
    assert secondo["voci_scelte"] == modello_computo.VOCI_SCELTE
    assert secondo["testi_voci"]["3.1"]["d"] != "altro"
