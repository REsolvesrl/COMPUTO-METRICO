"""All'avvio l'app riprende da sola dov'era rimasta.

Due sorgenti, e la scelta fra loro è il punto delicato: l'ultimo progetto
ARCHIVIATO (quello salvato apposta) e il SALVATAGGIO AUTOMATICO, che
contiene anche il lavoro che nessuno ha salvato. Vince il più recente —
aprire sempre l'archivio sarebbe più semplice e butterebbe via mezz'ora di
lavoro ogni volta che ci si dimentica di premere Salva.
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


def test_fra_archivio_e_autosalvataggio_vince_il_piu_recente(tmp_path):
    """Il lavoro NON salvato non deve essere buttato via."""
    import time
    archivio_locale.salva_progetto(
        "Vecchio", json.dumps(_progetto("Vecchio", 1.0)).encode("utf-8"))
    time.sleep(0.01)      # le date sui file hanno la risoluzione dei millesimi
    autosalva = Path(os.environ["CME_AUTOSALVA"])
    autosalva.write_text(json.dumps(_progetto("Lavoro non salvato", 99.0)),
                         encoding="utf-8")
    # l'autosalvataggio è stato scritto dopo: è lui il più recente
    at = _avvia()
    assert at.session_state["prg_nome"] == "Lavoro non salvato"
    assert at.session_state["q_1.02"] == 99.0


def test_se_l_archivio_e_piu_recente_vince_lui():
    autosalva = Path(os.environ["CME_AUTOSALVA"])
    autosalva.write_text(json.dumps(_progetto("Bozza vecchia", 5.0)),
                         encoding="utf-8")
    import time
    time.sleep(0.01)
    archivio_locale.salva_progetto(
        "Salvato dopo",
        json.dumps(_progetto("Salvato dopo", 8.0)).encode("utf-8"))
    at = _avvia()
    assert at.session_state["prg_nome"] == "Salvato dopo"


def test_un_file_illeggibile_non_impedisce_l_avvio():
    """Meglio partire vuoti che non partire."""
    Path(os.environ["CME_AUTOSALVA"]).write_text("{non e' json",
                                                 encoding="utf-8")
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


def test_a_parita_di_orario_vince_il_lavoro_non_salvato():
    """Salvare e chiudere nello stesso istante non deve costare il lavoro.

    Le date sui file hanno la risoluzione dei millesimi: se archivio e
    autosalvataggio risultano coetanei, deve vincere l'autosalvataggio —
    e' l'unico dei due che puo' contenere qualcosa in piu'.
    """
    autosalva = Path(os.environ["CME_AUTOSALVA"])
    autosalva.write_text(json.dumps(_progetto("Non salvato", 4.0)),
                         encoding="utf-8")
    archivio_locale.salva_progetto(
        "Archiviato", json.dumps(_progetto("Archiviato", 2.0)).encode("utf-8"))
    # stessa identica data su entrambi
    quando = autosalva.stat().st_mtime
    os.utime(archivio_locale.percorso("Archiviato"), (quando, quando))
    at = _avvia()
    assert at.session_state["prg_nome"] == "Non salvato"
