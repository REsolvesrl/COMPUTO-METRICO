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
    # il file temporaneo del salvataggio non deve restare in giro (la
    # sottocartella delle versioni si', quella e' il passato del progetto)
    assert [f.name for f in archivio.iterdir() if f.is_file()] == ["X.json"]
    assert not list(archivio.glob("*.parziale"))


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


# --------------------------- l'ultimo progetto, per riaprire dov'eravamo

def test_ultimo_progetto_senza_archivio(tmp_path, monkeypatch):
    monkeypatch.setenv("CME_ARCHIVIO", str(tmp_path / "mai_creata"))
    assert archivio_locale.ultimo_progetto() == (None, None)


def test_ultimo_progetto_e_il_piu_recente(tmp_path, monkeypatch):
    import os
    import time
    monkeypatch.setenv("CME_ARCHIVIO", str(tmp_path))
    archivio_locale.salva_progetto("Vecchio", b'{"a": 1}')
    archivio_locale.salva_progetto("Nuovo", b'{"a": 2}')
    # la data di modifica decide, non il nome
    vecchio = tmp_path / "Vecchio.json"
    os.utime(vecchio, (time.time() - 3600, time.time() - 3600))
    nome, quando = archivio_locale.ultimo_progetto()
    assert nome == "Nuovo"
    assert quando is not None


def test_ultimo_progetto_con_un_solo_file(tmp_path, monkeypatch):
    monkeypatch.setenv("CME_ARCHIVIO", str(tmp_path))
    archivio_locale.salva_progetto("Unico", b'{"a": 1}')
    assert archivio_locale.ultimo_progetto()[0] == "Unico"


# ------------------------------------------------- le versioni precedenti

def _salva(nome, contenuto, quando=None):
    """Un salvataggio, eventualmente datato (per non dipendere dall'orologio)."""
    import archivio_locale as al
    if quando is None:
        return al.salva_progetto(nome, contenuto)
    # si passa dalla messa da parte con una data scelta, poi si scrive
    cart = al.cartella()
    cart.mkdir(parents=True, exist_ok=True)
    finale = cart / al._chiave(nome)
    al._metti_da_parte(finale, quando=quando)
    finale.write_bytes(contenuto)
    return finale


def _versione(n):
    return json.dumps({"progetto": {"nome": "Villa"}, "giro": n}).encode()


def test_il_primo_salvataggio_non_ha_un_prima(archivio):
    archivio_locale.salva_progetto("Villa", _versione(1))
    assert archivio_locale.versioni("Villa") == []


def test_il_secondo_salvataggio_mette_da_parte_il_primo(archivio):
    from datetime import datetime
    _salva("Villa", _versione(1))
    _salva("Villa", _versione(2), quando=datetime(2026, 8, 12, 10, 0, 0))
    precedenti = archivio_locale.versioni("Villa")
    assert len(precedenti) == 1
    assert archivio_locale.carica_versione(precedenti[0])["giro"] == 1
    # e il progetto attuale e' il secondo
    assert archivio_locale.carica_progetto("Villa")["giro"] == 2


def test_restano_tre_versioni_in_tutto_e_la_piu_vecchia_esce(archivio):
    """Tre CONTANDO quella attuale: il file del progetto piu' due indietro."""
    from datetime import datetime
    for giro in range(1, 6):
        _salva("Villa", _versione(giro),
               quando=datetime(2026, 8, 12, 10, giro, 0))
    precedenti = archivio_locale.versioni("Villa")
    assert len(precedenti) == archivio_locale.VERSIONI_TENUTE - 1
    # le due precedenti sono il quarto e il terzo giro, dalla piu' recente
    assert [archivio_locale.carica_versione(v)["giro"] for v in precedenti] \
        == [4, 3]
    assert archivio_locale.carica_progetto("Villa")["giro"] == 5


def test_le_versioni_non_compaiono_fra_i_progetti(archivio):
    """Sono il passato di un progetto, non progetti da aprire."""
    from datetime import datetime
    _salva("Villa", _versione(1))
    _salva("Villa", _versione(2), quando=datetime(2026, 8, 12, 10, 0, 0))
    assert archivio_locale.elenco_progetti() == ["Villa"]
    assert archivio_locale.ultimo_progetto()[0] == "Villa"


def test_ogni_progetto_ha_le_sue(archivio):
    from datetime import datetime
    for nome in ("Villa", "Attico"):
        _salva(nome, _versione(1))
        _salva(nome, _versione(2), quando=datetime(2026, 8, 12, 10, 0, 0))
    assert len(archivio_locale.versioni("Villa")) == 1
    assert len(archivio_locale.versioni("Attico")) == 1


def test_eliminando_il_progetto_se_ne_vanno_anche_le_versioni(archivio):
    """Altrimenti «elimina» non elimina davvero."""
    from datetime import datetime
    _salva("Villa", _versione(1))
    _salva("Villa", _versione(2), quando=datetime(2026, 8, 12, 10, 0, 0))
    archivio_locale.elimina_progetto("Villa")
    assert archivio_locale.versioni("Villa") == []


def test_due_salvataggi_nello_stesso_secondo_non_fanno_fallire_niente(archivio):
    from datetime import datetime
    stesso = datetime(2026, 8, 12, 10, 0, 0)
    _salva("Villa", _versione(1))
    _salva("Villa", _versione(2), quando=stesso)
    _salva("Villa", _versione(3), quando=stesso)
    assert len(archivio_locale.versioni("Villa")) == 1
    assert archivio_locale.carica_progetto("Villa")["giro"] == 3


def test_la_data_si_legge_dal_nome_della_versione(archivio):
    from datetime import datetime
    _salva("Villa", _versione(1))
    _salva("Villa", _versione(2), quando=datetime(2026, 8, 12, 15, 30, 45))
    versione = archivio_locale.versioni("Villa")[0]
    assert archivio_locale.quando_versione(versione) == \
        datetime(2026, 8, 12, 15, 30, 45)


def test_se_la_copia_non_riesce_il_salvataggio_avviene_lo_stesso(
        archivio, monkeypatch):
    """⚠️ Perdere la cronologia e' un dispiacere, perdere il lavoro no."""
    archivio_locale.salva_progetto("Villa", _versione(1))

    def _rotto(*_a, **_k):
        raise OSError("disco pieno")

    monkeypatch.setattr(archivio_locale, "_metti_da_parte", _rotto)
    archivio_locale.salva_progetto("Villa", _versione(2))
    assert archivio_locale.carica_progetto("Villa")["giro"] == 2
