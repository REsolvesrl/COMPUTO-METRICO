"""All'avvio l'app riprende da sola dov'era rimasta.

⚠️ SOLO i salvataggi fatti col tasto Salva. Il ripristino automatico resta
la rete di sicurezza per il blocco o la chiusura per sbaglio — si prende a
mano dal pannello del progetto — ma non si apre mai da solo: sono arrivati
ripristini automatici incompleti (la planimetria che non tornava), e un
avvio che riapre qualcosa di monco è peggio di un avvio vuoto.
"""
import json
import os
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import archivio_locale

SORGENTE = Path(__file__).resolve().parent.parent / "streamlit_app.py"


def _avvia():
    at = AppTest.from_file(str(SORGENTE), default_timeout=300)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _progetto(nome, quantita):
    return {
        "progetto": {"nome": nome, "committente": "", "oggetto": "",
                     "data": "2026-08-11", "aliquota_iva": 10.0,
                     "imprevisti": 10.0},
        "voci": [], "piante": [],
        "listino_stato": {"1.02": {"q": quantita, "p": 100.0}},
    }


def test_senza_niente_da_riprendere_si_parte_puliti():
    at = _avvia()
    assert at.session_state["prg_nome"] == ""


def test_riprende_l_ultimo_progetto_archiviato():
    archivio_locale.salva_progetto(
        "La Spezia", json.dumps(_progetto("La Spezia", 42.0)).encode("utf-8"))
    at = _avvia()
    assert at.session_state["prg_nome"] == "La Spezia"
    assert at.session_state["q_1.02"] == 42.0


def test_lo_dice_che_cosa_ha_ripreso():
    """Un'app che si apre già piena senza spiegare da dove viene fa paura."""
    archivio_locale.salva_progetto(
        "Via Roma", json.dumps(_progetto("Via Roma", 7.0)).encode("utf-8"))
    at = _avvia()
    assert any("Ripreso" in str(i.value) and "Via Roma" in str(i.value)
               for i in at.info)


def test_l_autosalvataggio_non_si_apre_mai_da_solo(tmp_path):
    """Nemmeno se e' piu' recente del progetto salvato a mano."""
    import time
    archivio_locale.salva_progetto(
        "Salvato a mano",
        json.dumps(_progetto("Salvato a mano", 1.0)).encode("utf-8"))
    time.sleep(0.01)      # le date sui file hanno la risoluzione dei millesimi
    Path(os.environ["CME_AUTOSALVA"]).write_text(
        json.dumps(_progetto("Automatico", 99.0)), encoding="utf-8")
    at = _avvia()
    assert at.session_state["prg_nome"] == "Salvato a mano"


def test_col_solo_autosalvataggio_si_parte_puliti():
    """C'e' un ripristino automatico ma nessun salvataggio: non si apre."""
    Path(os.environ["CME_AUTOSALVA"]).write_text(
        json.dumps(_progetto("Solo automatico", 5.0)), encoding="utf-8")
    at = _avvia()
    assert at.session_state["prg_nome"] == ""


def test_fra_due_salvataggi_vince_il_piu_recente():
    import time
    archivio_locale.salva_progetto(
        "Prima", json.dumps(_progetto("Prima", 5.0)).encode("utf-8"))
    time.sleep(0.01)
    archivio_locale.salva_progetto(
        "Dopo", json.dumps(_progetto("Dopo", 8.0)).encode("utf-8"))
    at = _avvia()
    assert at.session_state["prg_nome"] == "Dopo"


def test_un_file_illeggibile_non_impedisce_l_avvio():
    """Meglio partire vuoti che non partire."""
    archivio_locale.salva_progetto("Rovinato", b"{non e' json")
    at = _avvia()
    assert at.session_state["prg_nome"] == ""


def test_la_ripresa_avviene_una_volta_sola():
    """Riaperto il progetto, l'app non deve riproporlo a ogni giro."""
    archivio_locale.salva_progetto(
        "Unico", json.dumps(_progetto("Unico", 3.0)).encode("utf-8"))
    at = _avvia()
    assert at.session_state["prg_nome"] == "Unico"
    at.run()
    assert not any("Ripreso" in str(i.value) for i in at.info)


@pytest.mark.parametrize("chiave", ["prg_nome", "q_1.02"])
def test_il_progetto_ripreso_e_completo(chiave):
    archivio_locale.salva_progetto(
        "Completo", json.dumps(_progetto("Completo", 12.0)).encode("utf-8"))
    at = _avvia()
    atteso = {"prg_nome": "Completo", "q_1.02": 12.0}[chiave]
    assert at.session_state[chiave] == atteso


def test_il_ripristino_automatico_resta_disponibile_a_mano():
    """La rete di sicurezza c'e' ancora: si prende dal pannello progetto."""
    Path(os.environ["CME_AUTOSALVA"]).write_text(
        json.dumps(_progetto("Da recuperare", 6.0)), encoding="utf-8")
    at = _avvia()
    assert any("salvataggio automatico" in str(c.value) for c in at.caption)
    at.button(key="recupera_autosalva").click().run()
    assert at.session_state["prg_nome"] == "Da recuperare"
    assert at.session_state["q_1.02"] == 6.0
