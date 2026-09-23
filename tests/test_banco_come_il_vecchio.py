"""Aperto e salvato dal banco nuovo = aperto e salvato dal programma vecchio.

È il patto fra le due versioni finché convivono: lo stesso file, aperto e
risalvato da una parte o dall'altra, deve uscire uguale. Qui lo si prova
per davvero: il programma vecchio gira (AppTest), carica il progetto,
preme «Salva»; il banco nuovo fa lo stesso; i due file si confrontano.

Le immagini delle planimetrie sono l'unica eccezione dichiarata: il vecchio
le decodifica e le ricodifica in JPEG a ogni apertura (perdendo un po' di
qualità ogni volta), il nuovo le lascia com'erano. Si confronta tutto il
resto della pianta.

Oltre al progetto di prova scritto qui, se sul computo ci sono i progetti
della copia di prova (`~/CME/prova/progetti`) si confrontano anche quelli:
sono i file veri, con le loro stranezze.
"""
import base64
import io
import json
from pathlib import Path

import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

import archivio_locale
import banco

SORGENTE = Path(__file__).resolve().parent.parent / "streamlit_app.py"
PROVA_VERA = Path.home() / "CME" / "prova" / "progetti"


def _png_b64():
    buffer = io.BytesIO()
    Image.new("RGB", (40, 30), "white").save(buffer, format="JPEG")
    return base64.b64encode(buffer.getvalue()).decode()


# Un progetto scritto apposta per passare dai rami vecchi del caricamento:
# una voce libera senza codice, niente «voci_scelte», spese nel registro
# unico, comparabili con la griglia di prima, niente materiali.
VECCHIO = {
    "progetto": {"nome": "Prova vecchia", "committente": "RESolve srl",
                 "oggetto": "Ristrutturazione", "data": "2026-03-01",
                 "aliquota_iva": 22.0},
    "voci": [{"categoria": "Idraulico", "descrizione": " Voce libera ",
              "um": "a corpo", "quantita_manuale": 2, "prezzo": 150}],
    "listino_stato": {"2.1": {"q": 10, "p": 30}, "2.2": {"q": 0, "p": 100},
                      "3.10": {"q": 0, "p": 55}},
    "testi_voci": {"2.1": {"d": "Pavimento riscritto", "u": ""}},
    "business_plan": {"bp_acquisto": 145000, "bp_durata": 18},
    "spese": [{"importo": 1220, "aliquota_iva": 22, "categoria": "🟡 LAVORI",
               "stato": "Sostenuta", "fornitore": "Edil"},
              {"importo": 500, "aliquota_iva": 10, "categoria": "MATERIALE",
               "stato": "Da sostenere", "oggetto": "Piastrelle"}],
    "mca_comparabili": [{"nome": "C1", "prezzo": 250000, "mq": 90,
                         "condizioni": "Buone", "ascensore": False}],
    "finiture": {"porta_n": 5},
    "piante": [{"nome": "Piano terra", "mpp": 0.01,
                "zone": [{"id": 1, "categoria": "Balcone scoperto",
                          "nome": None,
                          "punti": [[0, 0], [10, 0], [10, 10]]},
                         {"id": 2, "categoria": "Superficie interna",
                          "nome": "Soggiorno",
                          "punti": [[0, 0], [500, 0], [500, 400], [0, 400]]},
                         {"id": 3, "categoria": "Superficie interna",
                          "nome": "Bagno", "pittura": False,
                          "punti": [[0, 0], [200, 0], [200, 250], [0, 250]]},
                         {"id": 4, "categoria": "Superficie commerciale",
                          "nome": None,
                          "punti": [[0, 0], [900, 0], [900, 900], [0, 900]]}],
                "pareti": [{"id": 5, "tipo": "demolire",
                            "p1": [0, 0], "p2": [300, 0]},
                           {"id": 6, "tipo": "costruire",
                            "p1": [0, 0], "p2": [0, 280]}],
                "immagine": _png_b64()}],
}


def _senza_immagini(dati):
    dati = json.loads(json.dumps(dati))
    for p in dati.get("piante") or []:
        p.pop("immagine", None)
    return dati


def _salvato_dal_vecchio(dati, cartella, monkeypatch):
    monkeypatch.setenv("CME_ARCHIVIO", str(cartella / "vecchio"))
    at = AppTest.from_file(str(SORGENTE), default_timeout=300)
    at.run()
    at.session_state["da_caricare"] = json.loads(json.dumps(dati))
    at.run()
    at.button(key="salva_testata").click().run()
    nome = (dati.get("progetto") or {}).get("nome") or "Progetto senza nome"
    return json.loads(archivio_locale.carica_progetto(nome) and
                      (cartella / "vecchio" / f"{nome}.json")
                      .read_text(encoding="utf-8"))


def _salvato_dal_nuovo(dati, cartella, monkeypatch):
    monkeypatch.setenv("CME_ARCHIVIO", str(cartella / "nuovo"))
    b = banco.Banco()
    b.carica(json.loads(json.dumps(dati)))
    nome = b.salva()
    return json.loads((cartella / "nuovo" / f"{nome}.json")
                      .read_text(encoding="utf-8"))


def _confronta(dati, tmp_path, monkeypatch):
    vecchio = _salvato_dal_vecchio(dati, tmp_path, monkeypatch)
    nuovo = _salvato_dal_nuovo(dati, tmp_path, monkeypatch)
    v, n = _senza_immagini(vecchio), _senza_immagini(nuovo)
    assert set(n) == set(v)
    for chiave in v:
        assert n[chiave] == v[chiave], chiave


def test_un_progetto_dei_formati_vecchi_esce_uguale(tmp_path, monkeypatch):
    _confronta(VECCHIO, tmp_path, monkeypatch)


def test_il_modello_di_un_progetto_nuovo_esce_uguale(tmp_path, monkeypatch):
    import modello_computo
    dati = modello_computo.progetto_nuovo()
    dati["progetto"] = {"nome": "Modello", "data": "2026-09-01"}
    _confronta(dati, tmp_path, monkeypatch)


@pytest.mark.parametrize("file", sorted(PROVA_VERA.glob("*.json"))
                         if PROVA_VERA.is_dir() else [],
                         ids=lambda f: f.stem)
def test_i_progetti_veri_escono_uguali(file, tmp_path, monkeypatch):
    _confronta(json.loads(file.read_text(encoding="utf-8")), tmp_path,
               monkeypatch)
