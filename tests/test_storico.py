from datetime import date

import pytest

import storico


@pytest.fixture
def archivio(tmp_path, monkeypatch):
    file = tmp_path / "storico_operazioni.json"
    monkeypatch.setenv("CME_STORICO", str(file))
    return file


OPERAZIONE = {"nome": "Via Roma 12", "contratto": 60000.0, "extra": 7200.0,
              "scostamento": 12.0, "mq_calpestabili": 110.0, "eur_mq": 611.0}


def test_prima_della_prima_chiusura_e_vuoto(archivio):
    assert storico.carica() == []


def test_registra_e_rilegge(archivio):
    storico.registra(OPERAZIONE, quando=date(2026, 8, 9))
    righe = storico.carica()
    assert len(righe) == 1
    assert righe[0]["nome"] == "Via Roma 12"
    assert righe[0]["scostamento"] == 12.0
    assert righe[0]["chiusa_il"] == "2026-08-09"


def test_richiudere_la_stessa_operazione_la_corregge(archivio):
    """Capita di sbagliare gli extra e di rimetterli a posto il giorno dopo."""
    storico.registra(OPERAZIONE)
    storico.registra({**OPERAZIONE, "extra": 9000.0, "scostamento": 15.0})
    righe = storico.carica()
    assert len(righe) == 1
    assert righe[0]["extra"] == 9000.0


def test_operazioni_diverse_convivono(archivio):
    storico.registra(OPERAZIONE, quando=date(2026, 1, 5))
    storico.registra({**OPERAZIONE, "nome": "Corso Italia 3",
                      "scostamento": 6.0}, quando=date(2026, 6, 1))
    assert [r["nome"] for r in storico.carica()] == ["Corso Italia 3",
                                                     "Via Roma 12"]


def test_senza_nome_non_si_perde(archivio):
    storico.registra({"contratto": 1000.0})
    assert storico.carica()[0]["nome"] == "Operazione senza nome"


def test_elimina(archivio):
    storico.registra(OPERAZIONE)
    assert storico.elimina("Via Roma 12") is True
    assert storico.carica() == []
    assert storico.elimina("Via Roma 12") is False


def test_uno_storico_rovinato_non_pianta_l_app(archivio):
    archivio.write_text("{non e' json", encoding="utf-8")
    assert storico.carica() == []


def test_scostamenti_e_costi_al_mq(archivio):
    storico.registra(OPERAZIONE, quando=date(2026, 1, 1))
    storico.registra({**OPERAZIONE, "nome": "Due", "scostamento": 8.0,
                      "eur_mq": 540.0}, quando=date(2026, 2, 1))
    assert sorted(storico.scostamenti()) == [8.0, 12.0]
    assert sorted(storico.costi_al_mq()) == [540.0, 611.0]


def test_le_operazioni_senza_scostamento_non_falsano_la_media(archivio):
    storico.registra(OPERAZIONE, quando=date(2026, 1, 1))
    storico.registra({"nome": "In corso", "contratto": 50000.0},
                     quando=date(2026, 2, 1))
    assert storico.scostamenti() == [12.0]
    assert storico.media(storico.scostamenti()) == 12.0


def test_media():
    assert storico.media([9.0, 14.0, 7.0]) == 10.0
    assert storico.media([]) is None
    assert storico.media(None) is None


def test_non_restano_file_parziali(archivio):
    storico.registra(OPERAZIONE)
    assert list(archivio.parent.glob("*.parziale")) == []
