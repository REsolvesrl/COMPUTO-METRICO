"""Le rotte del motore nuovo: la vista, i gesti, i file da scaricare."""
import json

import pytest
from fastapi.testclient import TestClient

import archivio_locale
import banco
import modello_computo
from server import principale


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setenv("CME_ARCHIVIO", str(tmp_path / "progetti"))
    monkeypatch.setattr(principale, "BANCO", banco.Banco())
    return TestClient(principale.app)


def _gesto(client, nome, **argomenti):
    r = client.post("/api/gesto", json={"nome": nome, "argomenti": argomenti})
    assert r.status_code == 200, r.text
    return r.json()


def test_la_salute_dice_su_quale_archivio_si_lavora(client, tmp_path):
    assert client.get("/api/salute").json()["archivio_progetti"] == \
        str(tmp_path / "progetti")


def test_senza_variabile_il_cantiere_lavora_nella_prova(monkeypatch):
    """Il sigillo: senza CME_ARCHIVIO non si tocca ~/CME/progetti."""
    import importlib
    monkeypatch.setenv("CME_ARCHIVIO", "")
    monkeypatch.delenv("CME_ARCHIVIO")
    monkeypatch.setenv("USO_DIR", "")
    monkeypatch.delenv("USO_DIR")
    importlib.reload(principale)
    assert archivio_locale.cartella().parts[-2:] == ("prova", "progetti")


def test_all_avvio_si_riapre_l_ultimo_salvato(client):
    dati = modello_computo.progetto_nuovo()
    dati["progetto"] = {"nome": "Ultimo"}
    archivio_locale.salva_progetto("Ultimo", json.dumps(dati))
    vista = client.get("/api/vista").json()
    assert vista["ripreso"]["nome"] == "Ultimo"
    assert vista["testata"]["nome"] == "Ultimo"
    # il banner si dice una volta sola
    assert client.get("/api/vista").json()["ripreso"] is None


def test_un_gesto_torna_la_vista_ricalcolata(client):
    _gesto(client, "nuovo")
    r = _gesto(client, "quantita", codice="2.1", valore=10)
    riga = next(v for c in r["vista"]["computo"]["categorie"]
                for v in c["voci"] if v["codice"] == "2.1")
    assert riga["quantita"] == 10 and riga["a_mano"]
    assert r["vista"]["computo"]["riepilogo"]["totale"] == riga["parziale"]


def test_un_gesto_che_non_si_puo_fare_lo_dice(client):
    r = _gesto(client, "crea_voce", categoria="Idraulico", descrizione=" ",
               um="cad", quantita=1, prezzo=10)
    assert r["esito"]["tipo"] == "errore"


def test_un_gesto_sconosciuto_non_passa(client):
    r = client.post("/api/gesto", json={"nome": "rm_rf", "argomenti": {}})
    assert r.status_code == 400


def test_salva_scrive_nell_archivio_e_la_testata_lo_dice(client, tmp_path):
    _gesto(client, "nuovo")
    _gesto(client, "imposta_progetto", campo="nome", valore="Via Roma")
    r = _gesto(client, "salva")
    assert r["esito"]["tipo"] == "ok"
    assert r["vista"]["testata"]["stato"] == "pari"
    assert (tmp_path / "progetti" / "Via Roma.json").is_file()
    r = _gesto(client, "prezzo", codice="2.1", valore=99)
    assert r["vista"]["testata"]["stato"] == "modificato"


@pytest.mark.parametrize("che_cosa,tipo", [
    ("json", "application/json"), ("pdf", "application/pdf"),
    ("pdf_senza_prezzi", "application/pdf"),
    ("xlsx", "application/vnd.openxmlformats"), ("csv", "text/csv"),
    ("allegato_materiali", "application/pdf")])
def test_i_file_si_scaricano(client, che_cosa, tipo):
    _gesto(client, "nuovo")
    _gesto(client, "quantita", codice="2.1", valore=10)
    r = client.get(f"/api/scarica/{che_cosa}")
    assert r.status_code == 200
    assert r.headers["content-type"].startswith(tipo)
    assert len(r.content) > 100


def test_il_json_scaricato_si_riapre_uguale(client):
    _gesto(client, "nuovo")
    _gesto(client, "quantita", codice="2.1", valore=10)
    contenuto = client.get("/api/scarica/json").content
    r = client.post("/api/apri_file",
                    files={"file": ("p.json", contenuto, "application/json")})
    assert principale.BANCO.quantita("2.1") == 10
    assert r.json()["vista"]["testata"]["stato"] == "mai"


def test_i_materiali_tornano_normalizzati(client):
    _gesto(client, "nuovo")
    r = _gesto(client, "materiali", righe=[
        {"capitolo": "BAGNO", "descrizione": " Lavabo ", "stato": None},
        {"capitolo": None, "descrizione": ""}])
    righe = r["vista"]["materiali"]["righe"]
    assert [m["descrizione"] for m in righe] == ["Lavabo"]
    assert righe[0]["stato"] == "Da ordinare"


def test_una_planimetria_si_carica_e_si_vede(client):
    import io
    from PIL import Image
    buffer = io.BytesIO()
    Image.new("RGB", (300, 200), "white").save(buffer, format="PNG")
    r = client.post("/api/planimetrie",
                    files={"file": ("terra.png", buffer.getvalue(), "image/png")})
    pl = r.json()["vista"]["planimetria"]
    assert [p["nome"] for p in pl["piante"]] == ["terra"]
    assert client.get(pl["tela"]["src"]).headers["content-type"] == "image/jpeg"
    assert client.get("/api/piante/0/miniatura").status_code == 200
    assert client.get("/api/piante/7/immagine").status_code == 404
    r = client.get("/api/scarica/pdf_planimetrie")
    assert r.content[:4] == b"%PDF"


def test_la_tela_e_quella_del_programma_vecchio(client):
    r = client.get("/tela/index.html")
    assert r.status_code == 200 and "streamlit-component-lib.js" in r.text
    assert client.get("/tela/main.js").status_code == 200
