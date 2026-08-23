"""All'avvio l'app riprende da sola dov'era rimasta.

⚠️ SOLO i salvataggi fatti col tasto Salva, che dal 12/08/2026 sono anche
gli unici che esistono: il salvataggio automatico è stato tolto del tutto.
Scriveva un'istantanea presa in un momento qualunque, e quel momento poteva
essere uno in cui i valori dei widget erano già stati cancellati da
Streamlit — così il «ripristino» rimetteva in tavola i predefiniti al posto
dei numeri scritti a mano. Una rete di sicurezza che restituisce dati
sbagliati è peggio di nessuna rete: quella la si guarda con sospetto,
questa convince di aver recuperato.

Un salvataggio è un gesto: quel momento lo sceglie una persona, e quello
che c'era dentro andava bene.
"""
import json
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
        "listino_stato": {"2.2": {"q": quantita, "p": 100.0}},
    }


def test_senza_niente_da_riprendere_si_parte_puliti():
    at = _avvia()
    assert at.session_state["prg_nome"] == ""


def test_riprende_l_ultimo_progetto_archiviato():
    archivio_locale.salva_progetto(
        "La Spezia", json.dumps(_progetto("La Spezia", 42.0)).encode("utf-8"))
    at = _avvia()
    assert at.session_state["prg_nome"] == "La Spezia"
    assert at.session_state["q_2.2"] == 42.0


def test_lo_dice_che_cosa_ha_ripreso():
    """Un'app che si apre già piena senza spiegare da dove viene fa paura."""
    archivio_locale.salva_progetto(
        "Via Roma", json.dumps(_progetto("Via Roma", 7.0)).encode("utf-8"))
    at = _avvia()
    assert any("Ripreso" in str(i.value) and "Via Roma" in str(i.value)
               for i in at.info)




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


@pytest.mark.parametrize("chiave", ["prg_nome", "q_2.2"])
def test_il_progetto_ripreso_e_completo(chiave):
    archivio_locale.salva_progetto(
        "Completo", json.dumps(_progetto("Completo", 12.0)).encode("utf-8"))
    at = _avvia()
    atteso = {"prg_nome": "Completo", "q_2.2": 12.0}[chiave]
    assert at.session_state[chiave] == atteso


# --------------------------- il salvataggio automatico non deve tornare

def test_l_app_non_scrive_nessun_file_di_ripristino(tmp_path, monkeypatch):
    """Non basta aver tolto la fascia: deve sparire la SCRITTURA.

    Finche' un file di appoggio esiste, prima o poi qualcuno lo ripropone —
    e quel file puo' contenere una fotografia gia' svuotata, che e' come il
    difetto si e' manifestato. Qui l'app lavora, si guarda la cartella
    temporanea, e non deve esserci comparso niente.
    """
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    monkeypatch.setenv("TEMP", str(tmp_path))
    monkeypatch.setenv("TMP", str(tmp_path))
    at = _avvia()
    at.text_input(key="bp_acquisto_txt").set_value("140.000").run()
    at.number_input(key="bp_durata").set_value(8).run()
    for _ in range(3):
        at.run()
    comparsi = [f.name for f in tmp_path.rglob("*") if f.is_file()]
    assert comparsi == [], comparsi


def test_nel_sorgente_non_c_e_piu_nessun_autosalvataggio():
    """La guardia contro il ripensamento distratto: se qualcuno rimette in
    piedi il meccanismo, questo test glielo dice."""
    sorgente = SORGENTE.read_text(encoding="utf-8")
    for parola in ("AUTOSALVA_FILE", "def autosalva", "cme_ripristino"):
        assert parola not in sorgente, parola

