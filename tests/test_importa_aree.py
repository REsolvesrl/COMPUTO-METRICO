"""Importare in una planimetria tutte le aree di un'altra.

Due fogli dello stesso immobile — lo stato attuale e lo stato di progetto,
una scansione nuova, il piano gemello — e le stesse aree da ridisegnare da
capo. Qui si copiano: con le loro categorie, i loro nomi e le loro spunte,
e soprattutto con le MISURE REALI intatte, che i due fogli possono essere
disegnati a scale diverse. Arrivano attaccate fra loro e si spostano tutte
insieme finché non le si lascia lì (1/10/2026).
"""
import io

import pytest
from PIL import Image

import banco
import planimetria


def _png(larg, alt):
    buffer = io.BytesIO()
    Image.new("RGB", (larg, alt), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def _gesto(b, **ev):
    ev.setdefault("seq", id(ev))
    b.evento_tela(ev)
    b.giro()


def _quadrato(b, lato, categoria="Superficie interna", nome=None, x=0, y=0):
    b.scegli_categoria_nuove(categoria)
    _gesto(b, tipo="zona_chiusa",
           punti=[[x, y], [x + lato, y], [x + lato, y + lato], [x, y + lato]])
    zona = b.dati["piante"][b.pianta_idx]["zone"][-1]
    if nome:
        b.sel_zona = zona["id"]
        b.nome_zona(nome)
    return zona


@pytest.fixture
def b():
    """Due piante: la prima a 1 px = 1 cm, la seconda a 1 px = 2 cm."""
    b = banco.Banco()
    b.nuovo()
    b.aggiungi_planimetrie(_png(800, 600), "stato attuale.png")
    b.giro()
    _gesto(b, tipo="scala", p1=[0, 0], p2=[100, 0])
    b.imposta_scala(1)                                    # 1 px = 1 cm
    b.aggiungi_planimetrie(_png(400, 300), "stato di progetto.png")
    b.giro()
    _gesto(b, tipo="scala", p1=[0, 0], p2=[100, 0])
    b.imposta_scala(2)                                    # 1 px = 2 cm
    b.scegli_pianta(0)
    return b


def _aree(b, i):
    pianta = b.dati["piante"][i]
    return [planimetria.area_reale_m2(z["punti"], pianta["mpp"])
            for z in pianta["zone"]]


def test_le_aree_arrivano_con_le_stesse_misure_reali(b):
    _quadrato(b, 200, nome="Cucina")                      # 2 × 2 m = 4 m²
    _quadrato(b, 300, categoria="Balcone")                # 3 × 3 m = 9 m²
    b.scegli_pianta(1)
    assert b.importa_zone(0) == 2
    b.giro()
    assert _aree(b, 1) == [4.0, 9.0]                      # non 1 e 2,25
    # categorie, nomi e spunte seguono l'area
    arrivate = b.dati["piante"][1]["zone"]
    assert [z["categoria"] for z in arrivate] == ["Superficie interna",
                                                  "Balcone"]
    assert arrivate[0]["nome"] == "Cucina"
    assert arrivate[0]["pavimento"] is True
    # l'originale resta dov'è, e gli id non si pestano i piedi
    assert len(b.dati["piante"][0]["zone"]) == 2
    assert len({z["id"] for z in arrivate}) == 2


def test_senza_scala_i_punti_si_copiano_come_stanno(b):
    _quadrato(b, 200)
    b.dati["piante"][1]["mpp"] = None
    b.scegli_pianta(1)
    b.importa_zone(0)
    assert b.importate["senza_scala"] is True


def test_le_aree_importate_si_spostano_tutte_insieme(b):
    _quadrato(b, 200)
    _quadrato(b, 100, x=400, y=300)
    b.scegli_pianta(1)
    b.importa_zone(0)
    b.giro()
    prima = [list(map(list, z["punti"])) for z in b.dati["piante"][1]["zone"]]
    _gesto(b, tipo="gruppo_spostato", dx=25, dy=-10)
    dopo = [z["punti"] for z in b.dati["piante"][1]["zone"]]
    for punti_prima, punti_dopo in zip(prima, dopo):
        assert punti_dopo == [[x + 25, y - 10] for x, y in punti_prima]


def test_lasciandole_li_tornano_indipendenti(b):
    _quadrato(b, 200)
    _quadrato(b, 100, x=400, y=300)
    b.scegli_pianta(1)
    b.importa_zone(0)
    b.giro()
    b.fine_importazione()
    prima = [list(map(list, z["punti"])) for z in b.dati["piante"][1]["zone"]]
    _gesto(b, tipo="gruppo_spostato", dx=25, dy=-10)
    assert [z["punti"] for z in b.dati["piante"][1]["zone"]] == prima


def test_il_gruppo_si_scioglie_cambiando_planimetria(b):
    _quadrato(b, 200)
    b.scegli_pianta(1)
    b.importa_zone(0)
    b.scegli_pianta(0)
    b.scegli_pianta(1)
    assert b.importate is None
    assert all(not z.get("gruppo") for z in b.argomenti_tela()["zone"])


def test_la_tela_le_segna_come_gruppo(b):
    _quadrato(b, 200)
    b.scegli_pianta(1)
    b.importa_zone(0)
    b.giro()
    assert [z["gruppo"] for z in b.argomenti_tela()["zone"]] == [True]


def test_si_possono_togliere_tutte_insieme(b):
    _quadrato(b, 200)
    _quadrato(b, 100, x=400, y=300)
    b.scegli_pianta(1)
    b.importa_zone(0)
    b.giro()
    assert b.annulla_importazione() == 2
    assert b.dati["piante"][1]["zone"] == []
    assert b.importate is None


def test_annullare_riporta_la_pianta_com_era(b):
    _quadrato(b, 200)
    b.scegli_pianta(1)
    _quadrato(b, 50)                       # una sua, che deve restare
    b.importa_zone(0)
    b.giro()
    assert len(b.dati["piante"][1]["zone"]) == 2
    b.annulla_disegno()
    assert len(b.dati["piante"][1]["zone"]) == 1


def test_non_si_importa_da_se_stessa_ne_dal_vuoto(b):
    _quadrato(b, 200)
    b.scegli_pianta(1)
    with pytest.raises(Exception):
        b.importa_zone(1)                  # è quella aperta
    b.scegli_pianta(0)
    with pytest.raises(Exception):
        b.importa_zone(1)                  # non ha aree


# ------------------- i segmenti delle misure note si possono spegnere

def test_i_segmenti_della_scala_nascono_nascosti(b):
    """All'apertura la scala è già tarata: quei tratti neri sono solo
    righe ferme in mezzo al disegno."""
    assert b.argomenti_tela()["scale"] == []          # sul disegno, niente
    # ma la scala resta tarata, e la misura resta in elenco
    assert b.dati["piante"][0]["mpp"]
    assert len(b.dati["piante"][0]["scale"]) == 1
    b.mostra_le_scale(True)
    assert len(b.argomenti_tela()["scale"]) == 1
    b.mostra_le_scale(False)
    assert b.argomenti_tela()["scale"] == []


def test_una_quota_che_non_torna_si_vede_anche_da_nascosta(b):
    """L'avviso dice «controllale sul disegno, sono in rosso»: se restassero
    nascoste manderebbe a cercare una cosa che non c'è."""
    _gesto(b, tipo="scala", p1=[0, 200], p2=[100, 200])
    b.imposta_scala(3)                 # tre metri dove la prima ne diceva uno
    assert any(m["non_torna"] for m in b.argomenti_tela()["scale"])
    assert len(b.argomenti_tela()["scale"]) == 2
