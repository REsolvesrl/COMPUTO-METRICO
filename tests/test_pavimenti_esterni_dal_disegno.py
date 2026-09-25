"""Balconi, terrazzi e logge: la 3.11 (solo posa) e la 3.30 (demolisci e riponi).

Le due voci prendono la stessa misura dal disegno — i metri delle zone
esterne con la spunta «Pavimento» — ma si escludono: il disegno ne alimenta
una sola, quella nel computo. E una voce scartata il disegno non la rimette
nel computo. La 3.30 è nata come voce tua su ENI: aprendo un progetto che la
tiene ancora fra le sue, diventa quella del listino.
"""
import io

import pytest
from PIL import Image

import banco
import listino
import planimetria


def _png(larg=800, alt=600):
    buffer = io.BytesIO()
    Image.new("RGB", (larg, alt), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def _gesto(b, **ev):
    ev.setdefault("seq", id(ev))
    b.evento_tela(ev)
    b.giro()


def _balcone(b, lato):
    """Un balcone quadrato di `lato` cm, col pavimento da rifare."""
    b.scegli_categoria_nuove("Balcone")
    _gesto(b, tipo="zona_chiusa",
           punti=[[0, 0], [lato, 0], [lato, lato], [0, lato]])
    zona = b.dati["piante"][0]["zone"][-1]
    b.spunta_locale(0, zona["id"], "pavimento", True)
    b.giro()


@pytest.fixture
def b():
    b = banco.Banco()
    b.nuovo()
    b.aggiungi_planimetrie(_png(), "piano primo.png")
    b.giro()
    _gesto(b, tipo="scala", p1=[0, 0], p2=[100, 0])
    b.imposta_scala(1)                                   # 1 px = 1 cm
    return b


# ------------------------------------------------------ la regola, da sola

def test_le_scartate_non_ricevono_la_misura():
    assert planimetria.voci_alimentate(
        ["2.1", "3.11"], scelte=["2.1"], scartate=["3.11"]) == ["2.1"]


def test_di_due_alternative_passa_quella_nel_computo():
    alt = [("3.11", "3.30")]
    assert planimetria.voci_alimentate(
        ["3.11", "3.30"], ["3.30"], (), alt) == ["3.30"]
    assert planimetria.voci_alimentate(
        ["3.11", "3.30"], ["3.11"], (), alt) == ["3.11"]


def test_se_nessuna_e_nel_computo_passa_la_prima_non_scartata():
    alt = [("3.11", "3.30")]
    assert planimetria.voci_alimentate(
        ["3.11", "3.30"], [], (), alt) == ["3.11"]
    assert planimetria.voci_alimentate(
        ["3.11", "3.30"], [], ["3.11"], alt) == ["3.30"]


def test_se_ci_sono_tutte_e_due_le_ha_volute_chi_lavora():
    assert planimetria.voci_alimentate(
        ["3.11", "3.30"], ["3.11", "3.30"], (), [("3.11", "3.30")]) \
        == ["3.11", "3.30"]


# --------------------------------------------------------- sul banco

def test_un_progetto_nuovo_resta_sulla_3_11(b):
    _balcone(b, 200)                                     # 4 m²
    assert b.quantita("3.11") == pytest.approx(4.0)
    assert "3.30" not in b.dati["voci_scelte"]
    assert b.quantita("3.30") == 0


def test_scartata_la_3_11_i_metri_vanno_nella_3_30_e_basta(b):
    _balcone(b, 200)
    b.scarta("3.11")
    b.porta_nel_computo("3.30")
    b.giro()
    assert b.quantita("3.30") == pytest.approx(4.0)
    # il disegno cambia: la 3.30 lo segue, la 3.11 non torna nel computo
    _balcone(b, 100)                                     # +1 m²
    assert b.quantita("3.30") == pytest.approx(5.0)
    assert "3.11" not in b.dati["voci_scelte"]
    assert "3.11" in b.dati["voci_scartate"]
    assert b.quantita("3.11") == pytest.approx(4.0)      # ferma dov'era
    assert [v["codice"] for v in b.voci_dal_disegno(b.grandezze())
            if v["grandezza"] == "pavimento_esterno"] == ["3.30"]


def test_la_loggia_senza_spunta_pavimento_resta_fuori(b):
    _balcone(b, 200)
    b.scegli_categoria_nuove("Loggia")
    _gesto(b, tipo="zona_chiusa",
           punti=[[0, 0], [300, 0], [300, 300], [0, 300]])
    assert b.grandezze()["pavimento_esterno"] == pytest.approx(4.0)


# ------------------------------------------- la voce tua passata al listino

def _progetto_con_la_3_30_tua(**cambi):
    riga = {"categoria": "Ricostruzioni e ripristini", "codice": "3.30",
            "descrizione": listino.voce_per_codice("3.30")["descrizione"],
            "um": "m²", "parti": None, "lunghezza": None, "larghezza": None,
            "altezza": None, "quantita_manuale": 12.5, "prezzo": 70.0}
    riga.update(cambi)
    return {"voci": [riga], "voci_scelte": ["3.30"], "voci_scartate": [],
            "listino_stato": {}, "testi_voci": {}}


def test_aprendo_la_voce_tua_diventa_quella_del_listino():
    b = banco.Banco()
    b.carica(_progetto_con_la_3_30_tua())
    assert not b.e_tua("3.30")
    assert not [v for v in b.dati["voci"] if v["codice"] == "3.30"]
    assert b.quantita("3.30") == 12.5 and b.prezzo("3.30") == 70.0
    assert "3.30" in b.scelte()
    assert "3.30" not in b.dati["testi_voci"]       # stesso testo: niente


def test_un_testo_diverso_resta_come_riscrittura():
    b = banco.Banco()
    b.carica(_progetto_con_la_3_30_tua(descrizione="Balconi rifatti"))
    assert b.testi("3.30") == ("Balconi rifatti", "m²")


def test_i_dati_passati_non_si_toccano():
    dati = _progetto_con_la_3_30_tua()
    listino.assorbi_voci_tue(dati)
    assert dati["voci"][0]["codice"] == "3.30" and dati["listino_stato"] == {}


def test_una_voce_tua_di_un_altra_categoria_resta_tua():
    dati = _progetto_con_la_3_30_tua(categoria="Superfici")
    assert listino.assorbi_voci_tue(dati)["voci"] == dati["voci"]

