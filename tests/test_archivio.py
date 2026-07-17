import archivio
from archivio import _chiave, configurato


class _RispostaFinta:
    def __init__(self, ok=True, status=200, dati=None, testo=""):
        self.ok = ok
        self.status_code = status
        self._dati = dati
        self.text = testo

    def json(self):
        return self._dati


class _RequestsFinto:
    """Registra le chiamate e restituisce risposte predefinite."""
    def __init__(self, get=None, post=None, delete=None):
        self.chiamate = []
        self._get, self._post, self._delete = get, post, delete

    def get(self, url, **k):
        self.chiamate.append(("get", url, k))
        return self._get

    def post(self, url, **k):
        self.chiamate.append(("post", url, k))
        return self._post

    def delete(self, url, **k):
        self.chiamate.append(("delete", url, k))
        return self._delete


def test_chiave_aggiunge_estensione():
    assert _chiave("Via Roma 1") == "Via Roma 1.json"


def test_chiave_non_raddoppia_estensione():
    assert _chiave("progetto.json") == "progetto.json"
    assert _chiave("Progetto.JSON") == "Progetto.json"


def test_chiave_rimuove_caratteri_pericolosi():
    assert _chiave('a/b:c*?"<>|d') == "abcd.json"


def test_chiave_vuota_ha_ripiego():
    assert _chiave("") == "progetto.json"
    assert _chiave(None) == "progetto.json"
    assert _chiave("   ") == "progetto.json"


def test_non_configurato_senza_secrets():
    # senza secrets di Supabase, l'archivio si dichiara non configurato
    # (non solleva) così l'app funziona lo stesso
    assert configurato() is False


CFG_FINTA = ("https://demo.supabase.co/storage/v1", "chiave-x", "progetti")


def test_elenco_progetti_parsa_e_ordina(monkeypatch):
    monkeypatch.setattr(archivio, "_cfg", lambda: CFG_FINTA)
    risposta = _RispostaFinta(dati=[
        {"name": "Villa.json"}, {"name": "appartamento.json"},
        {"name": ".emptyFolderPlaceholder"},  # da ignorare
    ])
    monkeypatch.setattr(archivio, "requests", _RequestsFinto(post=risposta))
    # ordinamento case-insensitive, senza estensione, scarta i non-.json
    assert archivio.elenco_progetti() == ["appartamento", "Villa"]


def test_salva_progetto_usa_upsert_e_percorso(monkeypatch):
    monkeypatch.setattr(archivio, "_cfg", lambda: CFG_FINTA)
    finto = _RequestsFinto(post=_RispostaFinta())
    monkeypatch.setattr(archivio, "requests", finto)
    archivio.salva_progetto("Via Roma 1", b"{}")
    metodo, url, k = finto.chiamate[0]
    assert metodo == "post"
    assert url.endswith("/object/progetti/Via%20Roma%201.json")
    assert k["headers"]["x-upsert"] == "true"
    assert k["data"] == b"{}"


def test_carica_progetto_ritorna_dict(monkeypatch):
    monkeypatch.setattr(archivio, "_cfg", lambda: CFG_FINTA)
    risposta = _RispostaFinta(dati={"progetto": {"nome": "X"}})
    monkeypatch.setattr(archivio, "requests", _RequestsFinto(get=risposta))
    assert archivio.carica_progetto("X")["progetto"]["nome"] == "X"


def test_errore_http_solleva(monkeypatch):
    monkeypatch.setattr(archivio, "_cfg", lambda: CFG_FINTA)
    risposta = _RispostaFinta(ok=False, status=404, testo="Not found")
    monkeypatch.setattr(archivio, "requests", _RequestsFinto(get=risposta))
    try:
        archivio.carica_progetto("inesistente")
        assert False, "doveva sollevare"
    except RuntimeError as e:
        assert "404" in str(e)
