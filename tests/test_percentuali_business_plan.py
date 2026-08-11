"""Il netto DEVE essere la percentuale del suo prezzo. Sempre, non «quando cambia».

Il difetto che questo test impedisce: la colonna dei netti si calcolava solo
in reazione a un cambiamento. Se lo stato arrivava già storto — un progetto
salvato da una versione difettosa, un giro interrotto a metà — restava storto
per sempre, e riscrivere la stessa percentuale non serviva a niente, perché
per Streamlit riscrivere 9 dove c'è già 9 non è un cambiamento. Si vedeva
«9,00 %» accanto a «0,00 €» senza modo di uscirne.

Ora il riallineamento gira a ogni esecuzione della pagina. Questi test
partono da stati storti di proposito: è lì che il difetto viveva.
"""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

SORGENTE = Path(__file__).resolve().parent.parent / "streamlit_app.py"


def _app():
    at = AppTest.from_file(str(SORGENTE), default_timeout=300)
    at.run()
    return at


@pytest.fixture(scope="module")
def stato_storto():
    """Percentuali presenti, netti a zero: nessuno tocca niente."""
    at = _app()
    at.session_state["bp_acquisto"] = 145000.0
    at.session_state["bp_vendita"] = 300000.0
    at.session_state["bp_imposta"] = 9.0
    at.session_state["bp_ag_in"] = 4.0
    at.session_state["bp_ag_out"] = 3.0
    at.session_state["bp_imposta_eur"] = 0.0
    at.session_state["bp_ag_in_eur"] = 0.0
    at.session_state["bp_ag_out_eur"] = 0.0
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


@pytest.mark.parametrize("chiave, atteso", [
    ("bp_imposta_eur", 13050.0),          # 9% di 145.000
    # le provvigioni sono IMPONIBILI: l'IVA sta nella sua colonna
    ("bp_ag_in_eur", 5800.0),             # 4% di 145.000
    ("bp_ag_out_eur", 9000.0),            # 3% di 300.000
])
def test_un_netto_a_zero_si_ricalcola_da_solo(stato_storto, chiave, atteso):
    assert stato_storto.session_state[chiave] == atteso


def test_il_netto_si_vede_nel_campo(stato_storto):
    assert stato_storto.text_input(
        key="bp_imposta_eur_txt").value == "13.050,00"


def test_cambiare_la_percentuale_rifa_il_netto():
    at = _app()
    at.text_input(key="bp_acquisto_txt").set_value("145000").run()
    at.number_input(key="bp_imposta").set_value(4.0).run()
    assert at.session_state["bp_imposta_eur"] == 5800.0
    assert at.text_input(key="bp_imposta_eur_txt").value == "5.800,00"


def test_cambiare_il_prezzo_rifa_i_netti():
    at = _app()
    at.text_input(key="bp_acquisto_txt").set_value("200000").run()
    assert at.session_state["bp_imposta_eur"] == 18000.0     # 9% di 200.000


def test_scrivere_il_netto_a_mano_aggiusta_la_percentuale():
    """La direzione inversa non deve essersi rotta per strada."""
    at = _app()
    at.text_input(key="bp_acquisto_txt").set_value("145000").run()
    at.text_input(key="bp_imposta_eur_txt").set_value("14.500,00").run()
    assert at.session_state["bp_imposta"] == 10.0
    assert at.session_state["bp_imposta_eur"] == 14500.0


def test_gli_imprevisti_seguono_l_importo_dei_lavori():
    at = _app()
    at.text_input(key="bp_ristr_txt").set_value("65000").run()
    assert at.session_state["bp_imprevisti"] == 6500.0       # 10% dei lavori


def test_senza_prezzo_il_netto_e_zero_e_l_app_lo_dice():
    """Zero è la risposta giusta, ma non deve restare muto."""
    at = _app()
    at.number_input(key="bp_imposta").set_value(9.0).run()
    assert at.session_state["bp_imposta_eur"] == 0.0
    assert any("restano a zero" in str(c.value) for c in at.caption)


def test_le_provvigioni_mostrano_l_iva_a_parte():
    """Imponibile nella colonna Netto, imposta nella colonna IVA.

    Prima l'IVA stava dentro l'importo della provvigione: il totale era
    giusto ma l'imposta non si vedeva, proprio dove serve contarla.
    """
    at = _app()
    at.text_input(key="bp_acquisto_txt").set_value("145000").run()
    assert at.session_state["bp_ag_in_eur"] == 4350.0       # 3% imponibile
    assert at.session_state["bp_iva_ag_in"] == 22.0


def test_l_iva_delle_provvigioni_entra_nei_totali():
    at = _app()
    at.text_input(key="bp_acquisto_txt").set_value("145000").run()
    # 3% di 145.000 = 4.350 imponibile, IVA 22% = 957
    import fattibilita
    assert fattibilita.iva_su(at.session_state["bp_ag_in_eur"],
                              at.session_state["bp_iva_ag_in"]) == 957.0
