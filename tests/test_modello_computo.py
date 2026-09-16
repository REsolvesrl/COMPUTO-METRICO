"""«Nuovo progetto» parte dalle voci di Migliarina, non da un foglio bianco.

Le voci, i testi riscritti e i prezzi sono quelli del cantiere di La Spezia
Migliarina; le quantità no, perché sono del cantiere nuovo. I test premono
il bottone vero, come farebbe chi lavora.
"""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import listino
import modello_computo

SORGENTE = Path(__file__).resolve().parent.parent / "streamlit_app.py"


def _nuovo_progetto(at):
    at.checkbox(key="conf_nuovo_progetto").check().run()
    at.button(key="nuovo_progetto").click().run()
    assert not at.exception, [e.value for e in at.exception]
    return at


@pytest.fixture(scope="module")
def nuovo():
    at = AppTest.from_file(str(SORGENTE), default_timeout=240)
    at.run()
    return _nuovo_progetto(at)


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


# ------------------------------------------------- premendo il bottone

def test_il_progetto_nuovo_porta_le_voci_di_migliarina(nuovo):
    assert nuovo.session_state["voci_scelte"] == modello_computo.VOCI_SCELTE


def test_le_descrizioni_sono_quelle_di_migliarina(nuovo):
    assert (nuovo.session_state["d_3.1"]
            == modello_computo.TESTI["3.1"]["d"])
    assert nuovo.session_state["u_4.1"] == "punto acqua"


def test_i_prezzi_sono_quelli_di_migliarina(nuovo):
    assert nuovo.session_state["p_3.1"] == 120.0
    assert nuovo.session_state["p_3.10"] == 48.0
    # una voce che su Migliarina aveva il prezzo della guida lo tiene
    assert nuovo.session_state["p_1.2"] == listino.voce_per_codice(
        "1.2")["prezzo"]


def test_le_voci_scritte_a_mano_arrivano_coi_loro_testi(nuovo):
    voce = nuovo.session_state["voci_extra"]["5.6"]
    assert voce["descrizione"].startswith("Realizzazione nr. 1 impianti")
    assert nuovo.session_state["p_5.6"] == 60.0


def test_le_voci_messe_da_parte_restano_nel_pool(nuovo):
    """Su Migliarina «ventilazione bagno cieco» non era nel computo: nel
    progetto nuovo c'è, ma da ripescare."""
    assert "4.15" in nuovo.session_state["voci_extra"]
    assert "4.15" not in nuovo.session_state["voci_scelte"]


def test_le_quantita_partono_da_zero(nuovo):
    for codice in modello_computo.VOCI_SCELTE:
        assert not nuovo.session_state[f"q_{codice}"], codice


def test_il_computo_nuovo_non_vale_niente_finche_non_lo_quantifichi(nuovo):
    """Le voci a zero stanno a video ma fuori dai totali: il modello non
    mette un euro nel computo da solo."""
    assert nuovo.session_state["voci_a_mano"] == []
    assert not [c for c in nuovo.session_state["voci_scelte"]
                if nuovo.session_state[f"q_{c}"]]


def test_le_quantita_del_progetto_di_prima_non_passano_al_nuovo():
    at = AppTest.from_file(str(SORGENTE), default_timeout=240)
    at.run()
    at.session_state["da_caricare"] = {
        "progetto": {"nome": "Vecchio"},
        "listino_stato": {"3.1": {"q": 40.0, "p": 95.0}},
        "voci_scelte": ["3.1"],
        "testi_voci": {"3.1": {"d": "Testo del cantiere vecchio", "u": ""}},
    }
    at.run()
    _nuovo_progetto(at)
    assert not at.session_state["q_3.1"]
    assert at.session_state["p_3.1"] == 120.0
    assert at.session_state["d_3.1"] == modello_computo.TESTI["3.1"]["d"]
    assert at.session_state["prg_nome"] == ""


def test_aprendo_l_app_non_si_carica_il_modello():
    """Solo «Nuovo progetto» lo carica. All'avvio la sessione resta vuota,
    o l'app non offrirebbe più di riaprire l'ultimo lavoro."""
    at = AppTest.from_file(str(SORGENTE), default_timeout=240)
    at.run()
    assert at.session_state["voci_scelte"] == []
