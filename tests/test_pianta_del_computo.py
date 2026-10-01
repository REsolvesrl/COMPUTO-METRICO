"""Da quale planimetria arrivano le misure del computo.

Due fogli dello stesso immobile — lo stato attuale e lo stato di progetto,
una scansione nuova, il piano gemello — e il computo li sommava tutti e due:
il doppio dei pavimenti, il doppio dei battiscopa. Ora si sceglie la pianta,
e la superficie commerciale resta invece il conto di tutto il fabbricato
(1/10/2026).
"""
import io

import pytest
from PIL import Image

import banco

_SEQ = iter(range(1, 10_000))


def _png(larg=800, alt=600):
    buffer = io.BytesIO()
    Image.new("RGB", (larg, alt), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def _gesto(b, **ev):
    ev.setdefault("seq", next(_SEQ))
    b.evento_tela(ev)
    b.giro()


def _stanza(b, lato):
    b.scegli_categoria_nuove("Superficie interna")
    _gesto(b, tipo="zona_chiusa",
           punti=[[0, 0], [lato, 0], [lato, lato], [0, lato]])


@pytest.fixture
def b():
    """Due piante identiche, 1 px = 1 cm: una stanza da 4 m² ciascuna."""
    b = banco.Banco()
    b.nuovo()
    for nome in ("stato attuale.png", "stato di progetto.png"):
        b.aggiungi_planimetrie(_png(), nome)
        b.giro()
        _gesto(b, tipo="scala", p1=[0, 0], p2=[100, 0])
        b.imposta_scala(1)
        _stanza(b, 200)
    return b


def test_di_norma_le_piante_si_sommano_ancora(b):
    assert b.dati["pianta_computo"] is None
    assert b.grandezze()["pavimento"] == pytest.approx(8.0)


def test_scegliendo_una_pianta_il_computo_prende_solo_quella(b):
    b.scegli_pianta_computo(1)
    b.giro()
    assert b.grandezze()["pavimento"] == pytest.approx(4.0)
    assert [r["pianta"] for r in b.locali()[0]] == ["stato di progetto"]


def test_tornando_a_tutte_si_somma_di_nuovo(b):
    b.scegli_pianta_computo(0)
    b.giro()
    assert b.grandezze()["pavimento"] == pytest.approx(4.0)
    b.scegli_pianta_computo(None)
    b.giro()
    assert b.grandezze()["pavimento"] == pytest.approx(8.0)


def test_i_muri_seguono_la_stessa_scelta(b):
    b.scegli_pianta(0)
    b.scegli_tipo_parete("demolire")
    _gesto(b, tipo="parete", p1=[0, 300], p2=[500, 300])     # 5 m
    b.scegli_pianta(1)
    _gesto(b, tipo="parete", p1=[0, 300], p2=[500, 300])     # altri 5 m
    assert b.muri()[0]["demolire"]["ml"] == pytest.approx(10.0)
    b.scegli_pianta_computo(0)
    assert b.muri()[0]["demolire"]["ml"] == pytest.approx(5.0)


def test_la_superficie_commerciale_guarda_sempre_tutto_il_fabbricato(b):
    """È il conto dell'immobile, non delle lavorazioni: un piano terra e un
    piano primo fanno una superficie sola."""
    b.scegli_categoria_nuove("Superficie commerciale")
    for i in (0, 1):
        b.scegli_pianta(i)
        _gesto(b, tipo="zona_chiusa",
               punti=[[0, 0], [300, 0], [300, 300], [0, 300]])    # 9 m²
    prima = b.mq_da_planimetria()
    b.scegli_pianta_computo(0)
    assert b.mq_da_planimetria() == prima == pytest.approx(18.0)


def test_la_scelta_si_salva_nel_progetto(b, tmp_path, monkeypatch):
    monkeypatch.setenv("CME_ARCHIVIO", str(tmp_path))
    b.scegli_pianta_computo(1)
    b.dati["progetto"]["nome"] = "due fogli"
    nome = b.salva()
    import json
    salvato = json.loads((tmp_path / f"{nome}.json").read_text(encoding="utf-8"))
    assert salvato["pianta_computo"] == 1
    altro = banco.Banco()
    altro.carica(salvato)
    assert altro.dati["pianta_computo"] == 1


def test_una_pianta_che_non_c_e_piu_torna_a_tutte(b):
    b.scegli_pianta_computo(1)
    b.togli_pianta(1)
    b.carica(b.dati)                      # come riaprendo il progetto
    assert b.dati["pianta_computo"] is None
    with pytest.raises(Exception):
        b.scegli_pianta_computo(5)
