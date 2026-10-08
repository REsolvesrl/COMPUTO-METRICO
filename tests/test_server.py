"""Le rotte del motore nuovo: la vista, i gesti, i file da scaricare."""
import json
from datetime import date

import fitz
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


def test_senza_variabile_si_lavora_sull_archivio_vero(monkeypatch):
    """Dal 24/09/2026 il motore non dirotta piu' niente: ~/CME/progetti."""
    import importlib
    from pathlib import Path
    monkeypatch.setenv("CME_ARCHIVIO", "")
    monkeypatch.delenv("CME_ARCHIVIO")
    importlib.reload(principale)
    assert archivio_locale.cartella() == Path.home() / "CME" / "progetti"


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


def test_l_indirizzo_del_cantiere_si_scrive_e_arriva_sul_computo(client):
    """La via del cantiere fa tutto il giro: gesto, vista, file salvato e
    PDF. E' un dato contrattuale — se si perde per strada, il foglio dice
    su quale immobile si lavora e sbaglia."""
    _gesto(client, "nuovo")
    via = "Via del Canaletto 170, La Spezia"
    r = _gesto(client, "imposta_progetto", campo="indirizzo", valore=via)
    assert r["vista"]["progetto"]["indirizzo"] == via

    contenuto = client.get("/api/scarica/json").content
    assert json.loads(contenuto)["progetto"]["indirizzo"] == via
    client.post("/api/apri_file",
                files={"file": ("p.json", contenuto, "application/json")})
    assert principale.BANCO.dati["progetto"]["indirizzo"] == via

    for rotta in ("pdf", "pdf_senza_prezzi"):
        pdf = fitz.open(stream=client.get(f"/api/scarica/{rotta}").content,
                        filetype="pdf")
        testo = "".join(pagina.get_text() for pagina in pdf)
        assert via in testo, rotta
        assert "ALLEGATO A AL CONTRATTO DI APPALTO" in testo, rotta


def test_i_documenti_portano_la_data_di_oggi(client):
    """Computo, foglio senza prezzi, allegato materiali e tavole si firmano
    il giorno che portano scritto: la data del progetto puo' essere di tre
    mesi prima, e sui fogli da firmare non ci va."""
    _gesto(client, "nuovo")
    _gesto(client, "imposta_progetto", campo="data", valore="2026-08-09")
    _gesto(client, "imposta_progetto", campo="luogo", valore="La Spezia")
    oggi = date.today().strftime("%d/%m/%Y")
    for rotta in ("pdf", "pdf_senza_prezzi", "allegato_materiali"):
        pdf = fitz.open(stream=client.get(f"/api/scarica/{rotta}").content,
                        filetype="pdf")
        testo = "".join(pagina.get_text() for pagina in pdf)
        assert f"La Spezia, lì {oggi}" in testo, rotta
        assert "2026-08-09" not in testo and "09/08/2026" not in testo, rotta


def test_la_data_del_progetto_resta_quella_che_hai_scritto(client):
    """Sui fogli c'e' la data di oggi, ma il progetto tiene la sua: e'
    quella dell'archivio e dell'Excel, e stampare non la cambia."""
    _gesto(client, "nuovo")
    r = _gesto(client, "imposta_progetto", campo="data", valore="2026-08-09")
    assert r["vista"]["progetto"]["data"] == "2026-08-09"
    client.get("/api/scarica/pdf")
    assert principale.BANCO.dati["progetto"]["data"] == "2026-08-09"


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


def test_i_file_della_pagina_si_ricontrollano_sempre(client):
    """Senza, il browser teneva i moduli vecchi e le correzioni sparivano."""
    for indirizzo in ("/", "/statico/app.js", "/tela/main.js"):
        assert client.get(indirizzo).headers["cache-control"] == "no-cache"


# ------------------------------------------------- le fatture del cantiere
# Il documento caricato resta accanto al progetto che l'ha ricevuto, e la
# riga di spesa lo riapre da qui (2/10/2026).

FATTURA_XML = """<?xml version="1.0" encoding="UTF-8"?>
<p:FatturaElettronica xmlns:p="http://x">
  <FatturaElettronicaBody>
    <DatiGenerali><DatiGeneraliDocumento>
      <TipoDocumento>TD01</TipoDocumento><Data>2026-01-15</Data>
      <Numero>123/2026</Numero>
      <ImportoTotaleDocumento>122.00</ImportoTotaleDocumento>
    </DatiGeneraliDocumento></DatiGenerali>
  </FatturaElettronicaBody>
</p:FatturaElettronica>"""


def _carica_fattura(client, nome="fattura.xml"):
    _gesto(client, "imposta_progetto", campo="nome", valore="Via Roma 12")
    r = client.post("/api/fatture",
                    files={"file": (nome, FATTURA_XML, "application/xml")})
    assert r.status_code == 200, r.text
    righe = r.json()["vista"]["bp"]["spese"]["fatture_lette"]["righe"]
    return _gesto(client, "aggiungi_fatture", righe=righe)


def test_la_fattura_caricata_si_riapre_dalla_sua_riga(client):
    vista = _carica_fattura(client)["vista"]
    spesa = vista["bp"]["spese"]["sostenute"][-1]
    assert spesa["file"] == "fattura.xml"
    assert vista["bp"]["spese"]["fatture_archivio"]["quante"] == 1
    r = client.get("/api/fattura/fattura.xml")
    assert r.status_code == 200
    assert r.content.decode("utf-8") == FATTURA_XML


def test_una_fattura_che_non_c_e_lo_dice_e_non_apre_niente(client):
    _carica_fattura(client)
    assert client.get("/api/fattura/mai vista.pdf").status_code == 404
    # e un nome che prova a uscire dalla cartella del cantiere nemmeno
    assert client.get("/api/fattura/..%2F..%2Fsegreto.json").status_code == 404


def test_le_fatture_di_un_altro_cantiere_non_si_aprono(client):
    _carica_fattura(client)
    _gesto(client, "imposta_progetto", campo="nome", valore="Migliarina")
    assert client.get("/api/fattura/fattura.xml").status_code == 404
