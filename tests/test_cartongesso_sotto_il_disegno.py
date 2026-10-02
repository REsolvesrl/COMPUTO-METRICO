"""Il cartongesso nella riga dei totali sotto la planimetria.

Le pareti in cartongesso nel computo ci andavano (voce 3.3) e sulla tavola
stampata pure, ma nella riga di campioni sotto il disegno no: c'erano i muri
da demolire e quelli da costruire, e il cartongesso spariva. Chi controllava
i totali a colpo d'occhio trovava i muri senza le pareti in cartongesso, che
sono un'altra lavorazione ma sono muri uguali (2/10/2026).
"""
import io

import pytest
from PIL import Image

import banco
from server import vista


def _png(larg=800, alt=600):
    buffer = io.BytesIO()
    Image.new("RGB", (larg, alt), "white").save(buffer, format="PNG")
    return buffer.getvalue()


_SEQ = iter(range(1, 10_000))


def _gesto(b, **ev):
    ev.setdefault("seq", next(_SEQ))
    b.evento_tela(ev)
    b.giro()


@pytest.fixture
def b():
    b = banco.Banco()
    b.nuovo()
    b.aggiungi_planimetrie(_png(), "piano.png")
    b.giro()
    _gesto(b, tipo="scala", p1=[0, 0], p2=[100, 0])
    b.imposta_scala(1)                                    # 1 px = 1 cm
    return b


def _campioni(b):
    return {c["nome"]: c["valore"]
            for c in vista.vista(b)["planimetria"]["vicino"]}


def test_il_cartongesso_sta_nella_riga_dei_totali(b):
    b.scegli_tipo_parete("cartongesso")
    _gesto(b, tipo="parete", p1=[0, 0], p2=[400, 0])       # 4 m
    # 4 m per l'altezza dei locali, senza aperture dichiarate
    atteso = round(4 * b.dati["altezza_locali"], 2)
    assert _campioni(b)["Muri in cartongesso"] == atteso


def test_senza_cartongesso_la_cella_non_c_e(b):
    b.scegli_tipo_parete("demolire")
    _gesto(b, tipo="parete", p1=[0, 0], p2=[400, 0])
    campioni = _campioni(b)
    assert "Muri da demolire" in campioni
    assert "Muri in cartongesso" not in campioni


def test_le_tre_lavorazioni_restano_separate(b):
    for tipo, y in (("demolire", 0), ("costruire", 100), ("cartongesso", 200)):
        b.scegli_tipo_parete(tipo)
        _gesto(b, tipo="parete", p1=[0, y], p2=[200, y])   # 2 m ciascuno
    campioni = _campioni(b)
    due_metri = round(2 * b.dati["altezza_locali"], 2)
    assert campioni["Muri da demolire"] == due_metri
    assert campioni["Muri da costruire"] == due_metri
    assert campioni["Muri in cartongesso"] == due_metri
