import math

import pytest

from planimetria import (
    area_poligono_pixel,
    area_reale_m2,
    calibra_da_due_punti,
    distanza_pixel,
    metri_per_pixel,
    perimetro_poligono_pixel,
    perimetro_reale_m,
    riepilogo_superfici,
)


# ------------------------------------------------------------ distanza / scala

def test_distanza_pixel():
    assert distanza_pixel((0, 0), (3, 4)) == 5.0


def test_metri_per_pixel():
    # 100 pixel valgono 4,50 m → 0,045 m/pixel
    assert metri_per_pixel(100, 4.5) == 0.045


def test_metri_per_pixel_lunghezza_nulla():
    with pytest.raises(ValueError):
        metri_per_pixel(0, 4.5)


def test_metri_per_pixel_misura_negativa():
    with pytest.raises(ValueError):
        metri_per_pixel(100, -1)


def test_calibra_da_due_punti():
    # segmento orizzontale di 200 pixel = 5,00 m reali
    mpp = calibra_da_due_punti((10, 50), (210, 50), 5.0)
    assert mpp == pytest.approx(0.025)


# --------------------------------------------------------------------- aree

def test_area_quadrato():
    # quadrato 10×10 pixel
    punti = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert area_poligono_pixel(punti) == 100.0


def test_area_indipendente_dal_verso():
    orario = [(0, 0), (10, 0), (10, 10), (0, 10)]
    antiorario = list(reversed(orario))
    assert area_poligono_pixel(orario) == area_poligono_pixel(antiorario)


def test_area_triangolo():
    # base 4, altezza 3 → area 6
    assert area_poligono_pixel([(0, 0), (4, 0), (0, 3)]) == 6.0


def test_area_poligono_a_l():
    # forma a "L": quadrato 4×4 meno un morso 2×2 in alto a destra
    punti = [(0, 0), (4, 0), (4, 2), (2, 2), (2, 4), (0, 4)]
    assert area_poligono_pixel(punti) == 12.0


def test_area_meno_di_tre_punti():
    assert area_poligono_pixel([(0, 0), (1, 1)]) == 0.0


def test_area_reale_m2():
    # quadrato 200×200 pixel, scala 0,025 m/pixel → lato 5 m → 25 m²
    punti = [(0, 0), (200, 0), (200, 200), (0, 200)]
    assert area_reale_m2(punti, 0.025) == 25.0


# ---------------------------------------------------------------- perimetro

def test_perimetro_quadrato():
    punti = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert perimetro_poligono_pixel(punti) == 40.0


def test_perimetro_reale_m():
    punti = [(0, 0), (200, 0), (200, 200), (0, 200)]
    # lato 5 m × 4 = 20 m
    assert perimetro_reale_m(punti, 0.025) == 20.0


def test_integrazione_stanza_reale():
    # stanza rettangolare 5,20 m × 4,10 m disegnata a scala 0,02 m/pixel
    # → 260 px × 205 px
    mpp = 0.02
    punti = [(0, 0), (260, 0), (260, 205), (0, 205)]
    assert area_reale_m2(punti, mpp) == pytest.approx(21.32, abs=0.01)


# ------------------------------------------------------ superfici commerciali

# quadrato 200×200 px: con mpp 0,025 vale 5 m × 5 m = 25 m²
QUADRATO_200 = [(0, 0), (200, 0), (200, 200), (0, 200)]


def test_riepilogo_superfici_pesi_e_totali():
    piante = [
        {"nome": "Piano terra", "mpp": 0.025, "zone": [
            {"categoria": "Superficie interna", "punti": QUADRATO_200},
            {"categoria": "Balcone scoperto", "punti": QUADRATO_200},
        ]},
        {"nome": "Piano primo", "mpp": 0.025, "zone": [
            {"categoria": "Superficie interna", "punti": QUADRATO_200},
        ]},
    ]
    percentuali = {"Superficie interna": 100.0, "Balcone scoperto": 30.0}
    righe, totale, commerciale, senza = riepilogo_superfici(piante, percentuali)
    assert totale == 75.0                       # 25 + 25 + 25
    assert commerciale == 57.5                  # 25 + 7,5 + 25
    assert senza == []
    balcone = next(r for r in righe if r["categoria"] == "Balcone scoperto")
    assert balcone["m2"] == 25.0
    assert balcone["m2_commerciale"] == 7.5
    assert balcone["percento"] == 30.0


def test_riepilogo_raggruppa_zone_della_stessa_categoria():
    piante = [{"nome": "P", "mpp": 0.025, "zone": [
        {"categoria": "Superficie interna", "punti": QUADRATO_200},
        {"categoria": "Superficie interna", "punti": QUADRATO_200},
    ]}]
    righe, totale, _, _ = riepilogo_superfici(
        piante, {"Superficie interna": 100.0})
    assert len(righe) == 1
    assert righe[0]["zone"] == 2
    assert righe[0]["m2"] == 50.0
    assert totale == 50.0


def test_riepilogo_esclude_le_piante_senza_scala():
    piante = [{"nome": "Senza scala", "mpp": None, "zone": [
        {"categoria": "Superficie interna", "punti": QUADRATO_200},
    ]}]
    righe, totale, commerciale, senza = riepilogo_superfici(piante, {})
    assert righe == []
    assert totale == 0.0
    assert commerciale == 0.0
    assert senza == ["Senza scala"]


def test_riepilogo_categoria_sconosciuta_vale_100():
    piante = [{"nome": "P", "mpp": 0.025, "zone": [
        {"categoria": "Categoria inventata", "punti": QUADRATO_200},
    ]}]
    righe, _, commerciale, _ = riepilogo_superfici(piante, {})
    assert righe[0]["percento"] == 100.0
    assert commerciale == 25.0


def test_riepilogo_ignora_le_piante_senza_zone():
    piante = [{"nome": "Vuota", "mpp": 0.02, "zone": []}]
    righe, totale, commerciale, senza = riepilogo_superfici(piante, {})
    assert righe == [] and totale == 0.0 and commerciale == 0.0 and senza == []
