"""Lo spessore dei muri nuovi: 10, 15 o 18 cm, e il segno sul disegno.

Un tramezzo in forati da 8+2 di intonaco, un muro da 12+3, una parete da 18:
sul disegno la differenza si deve vedere, perché in un corridoio stretto
decide se una porta ci sta. Lo spessore ce l'hanno solo i muri NUOVI — di
uno da demolire si sa già quanto è grosso (1/10/2026).
"""
import io

import pytest
from PIL import Image

import banco
from costanti import SPESSORE_PARETE_PREDEFINITO


def _png(larg=800, alt=600):
    buffer = io.BytesIO()
    Image.new("RGB", (larg, alt), "white").save(buffer, format="PNG")
    return buffer.getvalue()


_SEQ = iter(range(1, 10_000))


def _gesto(b, **ev):
    # ⚠️ Un contatore, non id(ev): il banco scarta i doppioni sul «seq», e
    # due dizionari diversi possono avere lo stesso id() se il primo e' gia'
    # stato buttato via. Il secondo muro spariva, e il test accusava il
    # programma di non ricordare lo spessore.
    ev.setdefault("seq", next(_SEQ))
    b.evento_tela(ev)
    b.giro()


def _muro(b, tipo, x=0):
    b.scegli_tipo_parete(tipo)
    _gesto(b, tipo="parete", p1=[x, 0], p2=[x + 200, 0])
    return b.dati["piante"][0]["pareti"][-1]


@pytest.fixture
def b():
    b = banco.Banco()
    b.nuovo()
    b.aggiungi_planimetrie(_png(), "piano.png")
    b.giro()
    _gesto(b, tipo="scala", p1=[0, 0], p2=[100, 0])
    b.imposta_scala(1)                                    # 1 px = 1 cm
    return b


def test_un_muro_nuovo_nasce_con_lo_spessore_scelto(b):
    assert _muro(b, "costruire")["spessore"] == SPESSORE_PARETE_PREDEFINITO
    b.scegli_spessore_parete(0.18)
    assert _muro(b, "costruire", x=300)["spessore"] == 0.18
    assert _muro(b, "cartongesso", x=600)["spessore"] == 0.18


def test_un_muro_da_demolire_non_ha_spessore(b):
    assert "spessore" not in _muro(b, "demolire")


def test_lo_spessore_si_cambia_sul_muro_gia_tracciato(b):
    muro = _muro(b, "costruire")
    b.sel_parete = muro["id"]
    b.spessore_parete_sel(0.15)
    assert muro["spessore"] == 0.15
    assert b.storia[-1]["descrizione"] == "cambio di spessore del muro"


def test_sul_muro_da_demolire_lo_spessore_non_si_sceglie(b):
    muro = _muro(b, "demolire")
    b.sel_parete = muro["id"]
    with pytest.raises(Exception):
        b.spessore_parete_sel(0.15)


def test_cambiando_tipo_lo_spessore_arriva_e_se_ne_va(b):
    muro = _muro(b, "demolire")
    b.sel_parete = muro["id"]
    b.tipo_parete_sel("costruire")
    assert muro["spessore"] == SPESSORE_PARETE_PREDEFINITO
    b.tipo_parete_sel("demolire")
    assert "spessore" not in muro


def test_una_misura_fuori_elenco_si_avvicina_a_quella_prevista(b):
    """Il disegno non è il posto dove si inventano muri da 13,7 cm."""
    b.scegli_spessore_parete(0.14)
    assert b.spessore_parete == 0.15
    b.scegli_spessore_parete(0.40)
    assert b.spessore_parete == 0.18


def test_la_tela_riceve_lo_spessore_in_metri(b):
    b.scegli_spessore_parete(0.18)
    _muro(b, "costruire")
    args = b.argomenti_tela()
    assert args["pareti"][0]["spessore"] == 0.18
    # e anche quello del muro che si sta per tracciare, per l'anteprima
    assert args["spessore_parete"] == 0.18
    b.scegli_tipo_parete("demolire")
    assert b.argomenti_tela()["spessore_parete"] == 0.0


def test_lo_spessore_resta_nel_file_salvato(b, tmp_path, monkeypatch):
    monkeypatch.setenv("CME_ARCHIVIO", str(tmp_path))
    b.scegli_spessore_parete(0.15)
    _muro(b, "costruire")
    b.dati["progetto"]["nome"] = "prova spessori"
    nome = b.salva()
    import json
    salvato = json.loads((tmp_path / f"{nome}.json").read_text(encoding="utf-8"))
    assert salvato["piante"][0]["pareti"][0]["spessore"] == 0.15


def test_anche_sulla_tavola_stampata_il_muro_e_grosso_quanto_e():
    """Il foglio che va in cantiere dice le stesse cose dello schermo."""
    import tavola
    from PIL import Image
    pianta = Image.new("RGB", (400, 200), "white")
    sottile = tavola.disegna(pianta, pareti=[
        {"p1": [50, 100], "p2": [350, 100], "colore": "#FFD400",
         "spessore": 0.10, "etichetta": ""}], mpp=0.01)
    grosso = tavola.disegna(pianta, pareti=[
        {"p1": [50, 100], "p2": [350, 100], "colore": "#FFD400",
         "spessore": 0.18, "etichetta": ""}], mpp=0.01)

    def gialli(img):
        px = img.convert("RGB").load()
        x = img.size[0] // 2
        return sum(1 for y in range(img.size[1])
                   if px[x, y][0] > 200 and px[x, y][1] > 150
                   and px[x, y][2] < 120)

    assert gialli(sottile) == 10          # 0,10 m ÷ 0,01 m/px
    assert gialli(grosso) == 18           # 0,18 m ÷ 0,01 m/px


def test_senza_spessore_la_tavola_usa_il_tratto_di_sempre():
    import tavola
    from PIL import Image
    pianta = Image.new("RGB", (400, 200), "white")
    img = tavola.disegna(pianta, pareti=[
        {"p1": [50, 100], "p2": [350, 100], "colore": "#E53935",
         "etichetta": ""}], mpp=0.01)
    px = img.convert("RGB").load()
    x = img.size[0] // 2
    rossi = sum(1 for y in range(img.size[1])
                if px[x, y][0] > 180 and px[x, y][1] < 110)
    assert rossi == tavola.SPESSORE_PARETE
