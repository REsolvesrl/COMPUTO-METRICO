"""Scrivi → salva → riapri: nulla deve perdersi per strada.

Questo test esiste per una ragione precisa: perdere i dati inseriti è il
difetto peggiore che questo programma possa avere, e ne sono passati tre di
seguito, tutti diversi nel sintomo e tutti figli dello stesso punto debole —
gli importi si scrivono in caselle di TESTO (servono le migliaia col punto) e
il testo va convertito in numero, mentre tutto il resto è già numero.

I tre difetti, per non ripeterli:

1. il testo della sessione precedente riscriveva i valori appena caricati →
   riaprire un progetto lo svuotava;
2. il testo vecchio vinceva sul valore calcolato da una percentuale → le
   percentuali tornavano indietro da sole;
3. il bottone Salva gira come callback, cioè PRIMA che lo script converta le
   caselle → si salvava il valore di prima, e i prezzi non si salvavano
   mentre le percentuali sì.

Il giro completo passa dagli stessi gesti dell'utente: si scrive nei campi
(non si scrive in session_state), si preme il bottone che preme lui, si
rilegge il file che finisce sul disco.
"""
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

SORGENTE = Path(__file__).resolve().parent.parent / "streamlit_app.py"

# quello che l'utente scrive, campo per campo
IMPORTI = {                      # caselle di testo (la parte fragile)
    "bp_acquisto": "145000",
    "bp_vendita": "300000",
    "bp_ristr": "65000",
    "bp_notaio": "4200",
    "bp_mutuo": "1500",
}
PERCENTUALI = {                  # campi numerici
    "bp_imposta": 9.0,
    "bp_ag_in": 4.0,
    "bp_ag_out": 3.0,
    "bp_imprevisti_pct": 10.0,
}
ATTESI = {
    "bp_acquisto": 145000.0, "bp_vendita": 300000.0, "bp_ristr": 65000.0,
    "bp_notaio": 4200.0, "bp_mutuo": 1500.0,
    "bp_imposta": 9.0, "bp_ag_in": 4.0, "bp_ag_out": 3.0,
    "bp_imprevisti_pct": 10.0,
}


@pytest.fixture(scope="module")
def giro(tmp_path_factory, monkeypatch_module):
    """Compila tutto, salva col bottone in testata, riapre il file."""
    cartella = tmp_path_factory.mktemp("archivio") / "progetti"
    monkeypatch_module.setenv("CME_ARCHIVIO", str(cartella))

    at = AppTest.from_file(str(SORGENTE), default_timeout=300)
    at.run()
    at.session_state["prg_nome"] = "Giro completo"
    at.session_state["prg_committente"] = "Resolve S.r.l."
    for chiave, testo in IMPORTI.items():
        at.text_input(key=f"{chiave}_txt").set_value(testo).run()
    for chiave, valore in PERCENTUALI.items():
        at.number_input(key=chiave).set_value(valore).run()
    # una voce di computo, per coprire anche quantità e prezzi del listino
    at.session_state["cat_aperte"] = {"Demolizioni"}
    at.run()
    at.text_input(key="q_1.02_txt").set_value("120").run()
    at.text_input(key="p_1.02_txt").set_value("115").run()

    at.button(key="salva_testata").click().run()
    assert not at.exception, [e.value for e in at.exception]

    file = cartella / "Giro completo.json"
    assert file.is_file(), "il salvataggio non ha scritto nessun file"
    salvato = json.loads(file.read_text(encoding="utf-8"))

    # e ora si riapre, in una sessione che ha già dentro altri valori
    riaperta = AppTest.from_file(str(SORGENTE), default_timeout=300)
    riaperta.run()
    riaperta.text_input(key="bp_acquisto_txt").set_value("999").run()
    riaperta.session_state["da_caricare"] = salvato
    riaperta.run()
    assert not riaperta.exception, [e.value for e in riaperta.exception]
    return salvato, riaperta


@pytest.fixture(scope="module")
def monkeypatch_module():
    from _pytest.monkeypatch import MonkeyPatch
    mp = MonkeyPatch()
    yield mp
    mp.undo()


@pytest.mark.parametrize("chiave, atteso", sorted(ATTESI.items()))
def test_il_file_salvato_contiene_quello_che_ho_scritto(giro, chiave, atteso):
    salvato, _ = giro
    assert salvato["business_plan"][chiave] == atteso


def test_il_file_salvato_contiene_il_computo(giro):
    salvato, _ = giro
    assert salvato["listino_stato"]["1.02"]["q"] == 120.0
    assert salvato["listino_stato"]["1.02"]["p"] == 115.0


def test_il_file_salvato_contiene_i_dati_del_progetto(giro):
    salvato, _ = giro
    assert salvato["progetto"]["nome"] == "Giro completo"
    assert salvato["progetto"]["committente"] == "Resolve S.r.l."


@pytest.mark.parametrize("chiave, atteso", sorted(ATTESI.items()))
def test_riaprendo_i_valori_tornano(giro, chiave, atteso):
    _, riaperta = giro
    assert riaperta.session_state[chiave] == atteso


def test_riaprendo_torna_anche_il_computo(giro):
    _, riaperta = giro
    assert riaperta.session_state["q_1.02"] == 120.0
    assert riaperta.session_state["p_1.02"] == 115.0


def test_riaprendo_le_caselle_mostrano_i_valori(giro):
    """Non basta lo stato: dev'esserci nel campo che si guarda."""
    _, riaperta = giro
    assert riaperta.text_input(key="bp_acquisto_txt").value == "145.000"
    assert riaperta.text_input(key="bp_vendita_txt").value == "300.000"


def test_i_calcoli_che_dipendono_dai_campi_sono_fatti(giro):
    """9% di 145.000 = 13.050: se il netto e' zero, il giro non serve."""
    _, riaperta = giro
    assert riaperta.session_state["bp_imposta_eur"] == 13050.0
    assert riaperta.session_state["bp_imprevisti"] == 6500.0
