"""La scheda planimetria nel banco: piante, gesti della tela, scala, annulla."""
import io

import pytest
from PIL import Image

import banco
from banco_disegno import ErroreDisegno


def _png(larg=800, alt=600):
    buffer = io.BytesIO()
    Image.new("RGB", (larg, alt), "white").save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def b():
    b = banco.Banco()
    b.nuovo()
    b.aggiungi_planimetrie(_png(), "piano terra.png")
    b.giro()
    return b


def _gesto(b, **ev):
    ev.setdefault("seq", id(ev))
    b.evento_tela(ev)
    b.giro()


def test_una_planimetria_caricata_prende_il_nome_del_file(b):
    assert [p["nome"] for p in b.dati["piante"]] == ["piano terra"]
    assert b.dati["piante"][0]["mpp"] is None


def test_un_immagine_troppo_larga_si_riduce_alla_misura_canonica():
    b = banco.Banco()
    b.aggiungi_planimetrie(_png(3000, 1500), "grande.png")
    assert b.immagine(0).size == (2000, 1000)


def test_un_file_illeggibile_lo_dice(b):
    with pytest.raises(ErroreDisegno):
        b.aggiungi_planimetrie(b"non sono un'immagine", "rotto.png")


def test_la_scala_si_imposta_dal_segmento(b):
    _gesto(b, tipo="scala", p1=[0, 0], p2=[100, 0])
    b.imposta_scala(5)
    assert b.dati["piante"][0]["mpp"] == pytest.approx(0.05)
    assert b.scala_temp is None


def test_una_scala_a_zero_non_si_imposta(b):
    _gesto(b, tipo="scala", p1=[0, 0], p2=[100, 0])
    with pytest.raises(ErroreDisegno):
        b.imposta_scala(0)


def test_un_area_disegnata_prende_la_categoria_scelta(b):
    b.scegli_categoria_nuove("Balcone")
    _gesto(b, tipo="zona_chiusa", punti=[[0, 0], [10, 0], [10, 10]])
    zona = b.dati["piante"][0]["zone"][0]
    assert zona["categoria"] == "Balcone" and zona["id"] == 1


def test_lo_stesso_evento_due_volte_vale_una(b):
    ev = {"tipo": "parete", "p1": [0, 0], "p2": [10, 0], "seq": 42}
    b.evento_tela(dict(ev))
    b.evento_tela(dict(ev))
    assert len(b.dati["piante"][0]["pareti"]) == 1


def test_l_annulla_riporta_indietro_anche_la_scala_e_lo_dice(b):
    _gesto(b, tipo="scala", p1=[0, 0], p2=[100, 0])
    b.imposta_scala(5)
    assert b.annulla_disegno() == "impostazione della scala"
    assert b.dati["piante"][0]["mpp"] is None and b.scala_persa


def test_i_muri_disegnati_arrivano_nel_computo_agganciato(b):
    _gesto(b, tipo="scala", p1=[0, 0], p2=[100, 0])
    b.imposta_scala(1)                      # 1 px = 1 cm
    b.scegli_tipo_parete("demolire")
    _gesto(b, tipo="parete", p1=[0, 0], p2=[500, 0])     # 5 m
    b.giro()
    assert "2.2" in b.dati["voci_scelte"]
    assert b.quantita("2.2") == pytest.approx(5 * 2.70, abs=0.01)
    # scritta a mano, il disegno non la tocca più
    b.scrivi_quantita("2.2", 20)
    _gesto(b, tipo="parete", p1=[0, 0], p2=[0, 300])
    assert b.quantita("2.2") == 20


def test_la_lunghezza_scritta_allunga_il_muro(b):
    _gesto(b, tipo="scala", p1=[0, 0], p2=[100, 0])
    b.imposta_scala(1)
    _gesto(b, tipo="parete", p1=[0, 0], p2=[300, 0])
    b.sel_parete = b.dati["piante"][0]["pareti"][0]["id"]
    b.lunghezza_parete(4)
    assert b.dati["piante"][0]["pareti"][0]["p2"] == pytest.approx([400, 0])


def test_una_zona_va_al_computo_nella_categoria_superfici(b):
    _gesto(b, tipo="scala", p1=[0, 0], p2=[100, 0])
    b.imposta_scala(1)
    b.scegli_categoria_nuove("Superficie interna")
    _gesto(b, tipo="zona_chiusa", punti=[[0, 0], [200, 0], [200, 100], [0, 100]])
    b.sel_zona = 1
    b.nome_zona("Cucina")
    b.zona_al_computo()
    voce = b.dati["voci"][-1]
    assert voce["categoria"] == "Superfici" and voce["quantita_manuale"] == 2.0
    assert voce["descrizione"] == "Cucina — piano terra"


def test_togliere_una_pianta_non_lascia_la_selezione_fuori_misura(b):
    b.aggiungi_planimetrie(_png(), "piano primo.png")
    assert b.pianta_idx == 1
    b.togli_pianta(1)
    assert b.pianta_idx == 0 and len(b.dati["piante"]) == 1


def test_il_pdf_delle_planimetrie_si_stampa(b):
    assert b.pdf_planimetrie()[:4] == b"%PDF"
    assert b.pdf_planimetrie(orizzontale=True)[:4] == b"%PDF"
