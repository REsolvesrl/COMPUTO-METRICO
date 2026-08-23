import json
from datetime import date

import pytest

import listino_personale as lp

VOCI = [
    {"codice": "2.1", "prezzo": 100.0},
    {"codice": "2.2", "prezzo": 100.0},
    {"codice": "3.10", "prezzo": 45.0},
]


@pytest.fixture
def archivio(tmp_path, monkeypatch):
    """Il listino personale in una cartella usa e getta."""
    file = tmp_path / "listino_personale.json"
    monkeypatch.setenv("CME_LISTINO", str(file))
    return file


# ------------------------------------------------- quali prezzi sono «miei»

def test_scostamenti_prende_solo_i_prezzi_cambiati():
    prezzi = {"2.1": 115.0, "2.2": 100.0, "3.10": 52.5}
    assert lp.scostamenti(VOCI, prezzi) == {"2.1": 115.0, "3.10": 52.5}


def test_scostamenti_ignora_le_briciole():
    """Un centesimo di differenza non e' una scelta di prezzo."""
    assert lp.scostamenti(VOCI, {"2.1": 100.001}) == {}


def test_scostamenti_non_salva_i_campi_svuotati():
    assert lp.scostamenti(VOCI, {"2.1": 0.0, "2.2": -5.0}) == {}


def test_scostamenti_senza_prezzi():
    assert lp.scostamenti(VOCI, {}) == {}


# ------------------------------------------------ quali prezzi si riapplicano

def test_da_applicare_riporta_i_prezzi_salvati():
    assert lp.da_applicare({"2.1": 115.0}, VOCI) == {"2.1": 115.0}


def test_da_applicare_scarta_i_codici_spariti_dal_listino():
    """Una voce tolta o rinumerata non deve tornare in vita."""
    assert lp.da_applicare({"9.99": 50.0, "2.1": 115.0}, VOCI) \
        == {"2.1": 115.0}


def test_da_applicare_salta_quelli_gia_a_posto():
    salvati = {"2.1": 115.0, "3.10": 52.5}
    correnti = {"2.1": 115.0, "3.10": 45.0}
    assert lp.da_applicare(salvati, VOCI, correnti) == {"3.10": 52.5}


def test_da_applicare_niente_da_fare_e_dizionario_vuoto():
    correnti = {"2.1": 115.0}
    assert lp.da_applicare({"2.1": 115.0}, VOCI, correnti) == {}


def test_da_applicare_senza_listino_salvato():
    assert lp.da_applicare(None, VOCI) == {}
    assert lp.da_applicare({}, VOCI) == {}


# ----------------------------------------------------------- il file su disco

def test_salva_e_ricarica(archivio):
    lp.salva({"2.1": 115.0, "3.10": 52.5}, quando=date(2026, 8, 9))
    prezzi, quando = lp.carica()
    assert prezzi == {"2.1": 115.0, "3.10": 52.5}
    assert quando == "2026-08-09"


def test_prima_del_primo_salvataggio_non_esiste(archivio):
    assert not lp.esiste()
    assert lp.carica() == ({}, None)


def test_dopo_il_salvataggio_esiste(archivio):
    lp.salva({"2.1": 115.0})
    assert lp.esiste()
    assert archivio.is_file()


def test_la_cartella_nasce_al_salvataggio(tmp_path, monkeypatch):
    file = tmp_path / "mai" / "vista" / "listino.json"
    monkeypatch.setenv("CME_LISTINO", str(file))
    lp.salva({"2.1": 115.0})
    assert file.is_file()


def test_un_file_rovinato_non_pianta_l_app(archivio):
    archivio.write_text("{questo non e' json", encoding="utf-8")
    assert lp.carica() == ({}, None)


def test_un_file_senza_prezzi_e_come_non_averlo(archivio):
    archivio.write_text(json.dumps({"aggiornato": "2026-08-09"}),
                        encoding="utf-8")
    assert lp.carica() == ({}, "2026-08-09")


def test_salvare_di_nuovo_sostituisce(archivio):
    lp.salva({"2.1": 115.0})
    lp.salva({"3.10": 52.5})
    prezzi, _ = lp.carica()
    assert prezzi == {"3.10": 52.5}


def test_elimina(archivio):
    lp.salva({"2.1": 115.0})
    assert lp.elimina() is True
    assert not lp.esiste()
    assert lp.elimina() is False


def test_non_restano_file_parziali(archivio):
    lp.salva({"2.1": 115.0})
    parziali = list(archivio.parent.glob("*.parziale"))
    assert parziali == []
