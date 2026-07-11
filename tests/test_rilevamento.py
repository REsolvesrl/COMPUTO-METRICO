import numpy as np
import pytest
from PIL import Image, ImageDraw

from planimetria import area_poligono_pixel
from rilevamento import rileva_stanze


def maschera_poligono(poligono, dimensioni=(800, 600)):
    """Rasterizza un poligono in una maschera booleana (per i confronti)."""
    img = Image.new("L", dimensioni, 0)
    ImageDraw.Draw(img).polygon([(x, y) for x, y in poligono], fill=255)
    return np.asarray(img) > 0

# Porta di 40 px ≈ 0,90 m → mpp 0,0225
MPP = 0.0225


def pianta_sintetica():
    """Planimetria di prova: due stanze divise da un tramezzo con porta.

    Perimetro esterno da (50,50) a (750,550) con muri spessi 10 px;
    tramezzo verticale a x=400 con un varco (porta) da y=250 a y=290.
    Interni attesi: sinistra 60..395 × 60..540, destra 405..740 × 60..540
    → due stanze da 335 × 480 px.
    """
    img = Image.new("RGB", (800, 600), "white")
    dis = ImageDraw.Draw(img)
    dis.rectangle([50, 50, 750, 550], outline="black", width=10)
    dis.rectangle([395, 50, 405, 250], fill="black")
    dis.rectangle([395, 290, 405, 550], fill="black")
    return img


def test_rileva_le_due_stanze():
    poligoni = rileva_stanze(pianta_sintetica(), MPP)
    assert len(poligoni) >= 2
    aree = sorted((area_poligono_pixel(p) for p in poligoni), reverse=True)
    attesa = 335 * 480          # interno di ciascuna stanza, in px²
    assert aree[0] == pytest.approx(attesa, rel=0.15)
    assert aree[1] == pytest.approx(attesa, rel=0.15)


def test_le_stanze_sono_dentro_i_muri():
    # nessun poligono deve rappresentare l'esterno del fabbricato
    for poligono in rileva_stanze(pianta_sintetica(), MPP):
        for x, y in poligono:
            assert 55 <= x <= 745
            assert 55 <= y <= 545


def test_funziona_anche_senza_scala():
    assert len(rileva_stanze(pianta_sintetica(), None)) >= 2


def test_ordinati_per_area_decrescente():
    poligoni = rileva_stanze(pianta_sintetica(), MPP)
    aree = [area_poligono_pixel(p) for p in poligoni]
    assert aree == sorted(aree, reverse=True)


def test_immagine_vuota_nessuna_stanza():
    # senza muri non ci sono regioni chiuse: lo sfondo tocca i bordi
    img = Image.new("RGB", (400, 300), "white")
    assert rileva_stanze(img, 0.02) == []


def test_stanza_minuscola_scartata():
    # un quadratino 20×20 px (0,45 m × 0,45 m) è sotto i 2 m² minimi
    img = Image.new("RGB", (400, 300), "white")
    dis = ImageDraw.Draw(img)
    dis.rectangle([100, 100, 130, 130], outline="black", width=5)
    assert rileva_stanze(img, MPP) == []


def test_le_scritte_dentro_le_stanze_non_disturbano():
    # come la pianta pulita, ma piena di testi (nomi stanze, quote…)
    img = pianta_sintetica()
    dis = ImageDraw.Draw(img)
    for y in (120, 240, 360, 480):
        dis.text((150, y), "CUCINA 4,20 x 3,80", fill="black")
        dis.text((500, y), "CAMERA H=2,80", fill="black")
    con_testo = rileva_stanze(img, MPP)
    pulita = rileva_stanze(pianta_sintetica(), MPP)
    assert len(con_testo) == len(pulita)
    aree_testo = sorted(area_poligono_pixel(p) for p in con_testo)
    aree_pulita = sorted(area_poligono_pixel(p) for p in pulita)
    for a, b in zip(aree_testo, aree_pulita):
        assert a == pytest.approx(b, rel=0.03)   # il testo non erode le aree


def test_parola_intera_rimossa():
    # sulle foto le lettere si fondono: simuliamo una "parola" compatta
    # (60×12 px ≈ 1,35 m × 0,27 m) in mezzo alla stanza sinistra
    img = pianta_sintetica()
    dis = ImageDraw.Draw(img)
    dis.rectangle([150, 280, 210, 292], fill="black")
    con_parola = rileva_stanze(img, MPP)
    pulita = rileva_stanze(pianta_sintetica(), MPP)
    assert len(con_parola) == len(pulita)
    aree_parola = sorted(area_poligono_pixel(p) for p in con_parola)
    aree_pulita = sorted(area_poligono_pixel(p) for p in pulita)
    for a, b in zip(aree_parola, aree_pulita):
        assert a == pytest.approx(b, rel=0.05)


def test_le_proposte_non_si_sovrappongono():
    poligoni = rileva_stanze(pianta_sintetica(), MPP)
    assert len(poligoni) >= 2
    maschere = [maschera_poligono(p) for p in poligoni]
    for i in range(len(maschere)):
        for j in range(i + 1, len(maschere)):
            comune = int((maschere[i] & maschere[j]).sum())
            minore = min(int(maschere[i].sum()), int(maschere[j].sum()))
            assert comune <= 0.02 * minore   # sovrapposizione trascurabile


def test_rispetta_le_zone_esistenti():
    # la stanza sinistra è già stata disegnata: non va riproposta
    esistente = [[60, 60], [395, 60], [395, 540], [60, 540]]
    poligoni = rileva_stanze(pianta_sintetica(), MPP,
                             zone_esistenti=[esistente])
    assert len(poligoni) == 1
    # l'unica proposta è la stanza destra (baricentro a destra del tramezzo)
    xs = [x for x, _ in poligoni[0]]
    assert min(xs) >= 395 - 30
