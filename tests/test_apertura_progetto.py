"""Aprire un progetto salvato deve riportare i suoi numeri. Tutti.

Guardia contro un difetto costato caro (2026-08-09): gli importi si
scrivono in caselle di TESTO — servono le migliaia col punto — e il testo
della sessione precedente riscriveva il valore appena caricato. Un
progetto con 145.000 € di acquisto, riaperto, tornava a zero: sembrava che
il salvataggio non funzionasse.

Questo test fa la cosa vera: avvia l'app, sporca la sessione, apre un
progetto e controlla che i numeri ci siano. È lento (qualche secondo)
perché esegue l'intero script — ed è l'unico modo per accorgersi in
anticipo che riaprire un progetto ne perde il contenuto.
"""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

SORGENTE = Path(__file__).resolve().parent.parent / "streamlit_app.py"

PROGETTO = {
    "progetto": {"nome": "Via Roma 12", "committente": "Resolve S.r.l.",
                 "oggetto": "Ristrutturazione", "data": "2026-08-09",
                 "aliquota_iva": 10.0, "imprevisti": 10.0},
    "voci": [],
    "listino_stato": {"1.02": {"q": 120.0, "p": 115.0}},
    "piante": [],
    "business_plan": {"bp_acquisto": 145000.0, "bp_vendita": 300000.0,
                      "bp_ristr": 65000.0, "bp_notaio": 4200.0,
                      "bp_mutuo": 1500.0, "bp_imposte_fisse": 900.0},
}


def _app_avviata():
    at = AppTest.from_file(str(SORGENTE), default_timeout=240)
    at.run()
    return at


@pytest.fixture(scope="module")
def progetto_riaperto():
    """L'app con una sessione già sporca, in cui si apre un progetto."""
    at = _app_avviata()
    # la sessione ha i campi a zero e le caselle col loro testo: è la
    # condizione in cui si apre un progetto dopo averne fatto un altro
    at.session_state["da_caricare"] = PROGETTO
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


@pytest.mark.parametrize("chiave, atteso", [
    ("bp_acquisto", 145000.0),
    ("bp_vendita", 300000.0),
    ("bp_ristr", 65000.0),
    ("bp_notaio", 4200.0),
    ("bp_mutuo", 1500.0),
    ("bp_imposte_fisse", 900.0),
])
def test_gli_importi_del_business_plan_tornano(progetto_riaperto, chiave,
                                               atteso):
    assert progetto_riaperto.session_state[chiave] == atteso


def test_le_caselle_mostrano_i_valori_caricati(progetto_riaperto):
    """Non basta lo stato: dev'esserci anche nel campo che si guarda."""
    assert progetto_riaperto.text_input(
        key="bp_acquisto_txt").value == "145.000"
    assert progetto_riaperto.text_input(
        key="bp_ristr_txt").value == "65.000,00"


def test_tornano_anche_quantita_e_prezzi_del_listino(progetto_riaperto):
    assert progetto_riaperto.session_state["q_1.02"] == 120.0
    assert progetto_riaperto.session_state["p_1.02"] == 115.0


def test_torna_il_nome_del_progetto(progetto_riaperto):
    assert progetto_riaperto.session_state["prg_nome"] == "Via Roma 12"


def test_un_valore_scritto_a_mano_resta():
    """L'altra faccia: il testo dell'utente non deve essere buttato."""
    at = _app_avviata()
    at.text_input(key="bp_acquisto_txt").set_value("145000").run()
    assert at.session_state["bp_acquisto"] == 145000.0
    assert at.text_input(key="bp_acquisto_txt").value == "145.000"
    assert not at.exception, [e.value for e in at.exception]
