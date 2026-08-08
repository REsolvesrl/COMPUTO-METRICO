import json

import pytest

import archivio_locale
from archivio_locale import _chiave


@pytest.fixture
def archivio(tmp_path, monkeypatch):
    """Archivio in una cartella temporanea, diversa per ogni test."""
    monkeypatch.setenv("CME_ARCHIVIO", str(tmp_path / "progetti"))
    return tmp_path / "progetti"


def test_chiave_aggiunge_estensione():
    assert _chiave("Via Roma 1") == "Via Roma 1.json"


def test_chiave_non_raddoppia_estensione():
    assert _chiave("progetto.json") == "progetto.json"


def test_chiave_rimuove_caratteri_pericolosi():
    # niente percorsi risaliti o caratteri che Windows rifiuta
    assert _chiave('a/b:c*?"<>|d') == "abcd.json"
    assert _chiave("../../fuori") == "....fuori.json"


def test_elenco_vuoto_se_la_cartella_non_esiste(archivio):
    # l'app deve partire anche prima del primo salvataggio
    assert not archivio.exists()
    assert archivio_locale.elenco_progetti() == []


def test_salva_crea_la_cartella_e_il_file(archivio):
    archivio_locale.salva_progetto("Villa", b'{"progetto": {"nome": "Villa"}}')
    assert (archivio / "Villa.json").is_file()
    assert archivio_locale.elenco_progetti() == ["Villa"]


def test_giro_completo_salva_carica(archivio):
    dati = {"progetto": {"nome": "Via Roma 1"}, "voci": [1, 2, 3]}
    archivio_locale.salva_progetto("Via Roma 1",
                                   json.dumps(dati).encode("utf-8"))
    assert archivio_locale.carica_progetto("Via Roma 1") == dati


def test_salva_sovrascrive_senza_lasciare_residui(archivio):
    archivio_locale.salva_progetto("X", b'{"v": 1}')
    archivio_locale.salva_progetto("X", b'{"v": 2}')
    assert archivio_locale.carica_progetto("X") == {"v": 2}
    # il file temporaneo del salvataggio non deve restare in giro
    assert [f.name for f in archivio.iterdir()] == ["X.json"]


def test_elenco_ordinato_senza_distinzione_maiuscole(archivio):
    for nome in ("villa", "Appartamento", "Bifamiliare"):
        archivio_locale.salva_progetto(nome, b"{}")
    assert archivio_locale.elenco_progetti() == [
        "Appartamento", "Bifamiliare", "villa"]


def test_elimina(archivio):
    archivio_locale.salva_progetto("Da buttare", b"{}")
    archivio_locale.elimina_progetto("Da buttare")
    assert archivio_locale.elenco_progetti() == []


def test_carica_inesistente_spiega_il_problema(archivio):
    with pytest.raises(RuntimeError, match="non è in archivio"):
        archivio_locale.carica_progetto("mai visto")


def test_elimina_inesistente_spiega_il_problema(archivio):
    with pytest.raises(RuntimeError, match="non è in archivio"):
        archivio_locale.elimina_progetto("mai visto")


def test_variabile_ambiente_decide_la_cartella(tmp_path, monkeypatch):
    monkeypatch.setenv("CME_ARCHIVIO", str(tmp_path / "altrove"))
    assert archivio_locale.cartella() == tmp_path / "altrove"


def test_cartella_predefinita_sotto_la_home(monkeypatch):
    monkeypatch.delenv("CME_ARCHIVIO", raising=False)
    from pathlib import Path
    assert archivio_locale.cartella() == Path.home() / "CME" / "progetti"
