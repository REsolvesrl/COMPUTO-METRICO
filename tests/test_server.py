"""Le rotte del cantiere: quello che il browser chiede e cosa finisce su disco.

⚠️ La prova che conta è l'ultima: un progetto scritto dalle rotte nuove
deve riaprirsi con le stesse funzioni che usa il programma vecchio, con
tutto quello che le rotte non conoscono ancora intatto. Finché i due
convivono, questo è il patto.
"""
import json

import pytest
from fastapi.testclient import TestClient

import archivio_locale
import computo
import listino
from server.principale import app

PROGETTO = {
    "progetto": {"nome": "Prova", "committente": "RESolve srl",
                 "oggetto": "Ristrutturazione", "luogo": "", "data": "2026-09-23",
                 "aliquota_iva": 10.0},
    "voci": [{"categoria": "Idraulico", "codice": "4.90",
              "descrizione": "Voce scritta a mano", "um": "a corpo",
              "parti": None, "lunghezza": None, "larghezza": None,
              "altezza": None, "quantita_manuale": 2.0, "prezzo": 100.0}],
    "listino_stato": {"2.1": {"q": 10.0, "p": 30.0}},
    "voci_scelte": ["4.90", "2.1", "2.2", "9.11"],
    "voci_scartate": [], "voci_a_mano": [], "lavori_facoltativi": [],
    "testi_voci": {"2.1": {"d": "Demolizione pavimento riscritta", "u": None}},
    # quello che il cantiere non sa ancora leggere, e non deve rovinare
    "planimetrie": [{"nome": "Piano terra", "immagine": "AAAA"}],
    "business_plan": {"bp_prezzo_acquisto": 123456.0},
}


def _guida(codice):
    return listino.voce_per_codice(codice)["prezzo"]


@pytest.fixture
def archivio(tmp_path, monkeypatch):
    monkeypatch.setenv("CME_ARCHIVIO", str(tmp_path))
    archivio_locale.salva_progetto("Prova", json.dumps(PROGETTO))
    return tmp_path


@pytest.fixture
def client(archivio):
    return TestClient(app)


def test_la_salute_dice_su_quale_archivio_si_lavora(client, archivio):
    dati = client.get("/api/salute").json()
    assert dati["archivio_progetti"] == str(archivio)
    assert dati["progetti"] == 1


def test_senza_variabile_il_cantiere_usa_la_copia(monkeypatch):
    """Il sigillo: senza CME_ARCHIVIO non si tocca ~/CME/progetti."""
    import importlib
    import server.principale as principale
    # setenv prima di delenv: così monkeypatch si segna com'era e lo
    # rimette, anche se il reload lo riscrive con setdefault
    monkeypatch.setenv("CME_ARCHIVIO", "")
    monkeypatch.delenv("CME_ARCHIVIO")
    importlib.reload(principale)
    assert archivio_locale.cartella().name == "progetti-prova"


def test_l_elenco_porta_i_progetti_salvati(client):
    elenco = client.get("/api/progetti").json()
    assert [p["nome"] for p in elenco] == ["Prova"]
    assert elenco[0]["ultimo"]


def test_il_computo_segue_il_file(client):
    vista = client.get("/api/progetti/Prova").json()
    righe = {r["codice"]: r for r in vista["righe"]}
    # la facciata è spenta: 9.11 non c'è
    assert set(righe) == {"4.90", "2.1", "2.2"}
    assert righe["2.1"]["descrizione"] == "Demolizione pavimento riscritta"
    assert righe["2.1"]["importo"] == 300.0
    assert righe["4.90"]["a_mano"] and righe["4.90"]["importo"] == 200.0
    assert righe["2.2"]["da_quantificare"]
    # Demolizioni prima di Idraulico, come nel listino
    assert [r["codice"] for r in vista["righe"]][-1] == "4.90"
    assert vista["totali"]["totale"] == 500.0
    assert vista["totali"]["totale_con_iva"] == 550.0


def test_un_progetto_che_non_c_e_e_un_404(client):
    assert client.get("/api/progetti/Nessuno").status_code == 404


def test_la_prova_non_scrive(client, archivio):
    prima = (archivio / "Prova.json").read_bytes()
    vista = client.post("/api/progetti/Prova/prova", json={"modifiche": [
        {"codice": "2.2", "quantita": 4}]}).json()
    assert vista["totali"]["totale"] == 500.0 + 4 * _guida("2.2")
    assert (archivio / "Prova.json").read_bytes() == prima


def test_salvare_rispetta_il_formato_del_programma_vecchio(client):
    client.patch("/api/progetti/Prova", json={"modifiche": [
        {"codice": "2.2", "quantita": 4},
        {"codice": "2.1", "quantita": 0, "prezzo": _guida("2.1")},
        {"codice": "4.90", "prezzo": 150},
    ]})
    # riletto con la stessa funzione che usa streamlit_app.py
    dati = archivio_locale.carica_progetto("Prova")
    # 2.1 torna alla guida: sparisce da listino_stato, come fa il vecchio
    assert dati["listino_stato"] == {"2.2": {"q": 4.0, "p": _guida("2.2")}}
    assert dati["voci"][0]["prezzo"] == 150.0
    # quello che il cantiere non conosce passa intatto
    for chiave in ("planimetrie", "business_plan", "testi_voci",
                   "voci_scelte", "progetto"):
        assert dati[chiave] == PROGETTO[chiave]
    # e il salvataggio ha messo da parte la versione di prima
    assert len(archivio_locale.versioni("Prova")) == 1


def test_una_voce_fuori_dal_computo_non_si_scrive():
    dati = json.loads(json.dumps(PROGETTO))
    assert not computo.scrivi(dati, "1.1", quantita=3)
    assert "1.1" not in dati["listino_stato"]
