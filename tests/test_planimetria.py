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
    posiziona_etichette,
    punto_in_poligono,
    riepilogo_locali,
    riepilogo_pareti,
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


# ------------------------------------------------- locali (perimetri)

def test_punto_in_poligono():
    quadrato = [(0, 0), (10, 0), (10, 10), (0, 10)]
    assert punto_in_poligono((5, 5), quadrato)
    assert not punto_in_poligono((15, 5), quadrato)
    assert not punto_in_poligono((-1, -1), quadrato)


def test_etichette_fuori_dalle_zone():
    # due stanze affiancate al centro di un'immagine 1000×800
    zone = [
        {"id": 1, "punti": [[300, 200], [500, 200], [500, 600], [300, 600]]},
        {"id": 2, "punti": [[500, 200], [700, 200], [700, 600], [500, 600]]},
    ]
    posizioni = posiziona_etichette(zone, 1000, 800)
    assert set(posizioni) == {1, 2}
    for xy in posizioni.values():
        for z in zone:
            assert not punto_in_poligono(xy, z["punti"])
        assert 0 <= xy[0] <= 1000 and 0 <= xy[1] <= 800


def test_etichette_non_accavallate():
    zone = [
        {"id": 1, "punti": [[300, 200], [500, 200], [500, 400], [300, 400]]},
        {"id": 2, "punti": [[300, 400], [500, 400], [500, 600], [300, 600]]},
    ]
    posizioni = posiziona_etichette(zone, 1000, 800)
    (x1, y1), (x2, y2) = posizioni[1], posizioni[2]
    assert abs(x1 - x2) >= 1000 * 0.085 or abs(y1 - y2) >= 800 * 0.05


def test_etichette_rispetta_la_posizione_personalizzata():
    zone = [
        {"id": 1, "punti": [[0, 0], [100, 0], [100, 100], [0, 100]],
         "etichetta_pos": [50, 50]},
        {"id": 2, "punti": [[200, 0], [300, 0], [300, 100], [200, 100]]},
    ]
    posizioni = posiziona_etichette(zone, 1000, 800)
    assert 1 not in posizioni          # già personalizzata: non si tocca
    assert 2 in posizioni


def test_etichette_ripiego_al_baricentro():
    # zona che copre TUTTA l'immagine: nessun "fuori" possibile
    zone = [{"id": 1, "punti": [[0, 0], [100, 0], [100, 80], [0, 80]]}]
    posizioni = posiziona_etichette(zone, 100, 80)
    assert posizioni[1] == [50.0, 40.0]


def test_riepilogo_locali_superficie_e_perimetro():
    piante = [
        {"nome": "P1", "uid": 7, "mpp": 0.025, "zone": [
            {"id": 1, "categoria": "Superficie interna", "nome": "Cucina",
             "punti": QUADRATO_200},
            {"id": 2, "categoria": "Balcone scoperto", "nome": None,
             "punti": QUADRATO_200},
        ]},
        {"nome": "Senza scala", "mpp": None, "zone": [
            {"id": 3, "categoria": "Superficie interna",
             "punti": QUADRATO_200},
        ]},
    ]
    righe, senza = riepilogo_locali(piante)
    assert senza == ["Senza scala"]
    assert len(righe) == 2
    cucina = righe[0]
    assert cucina["nome"] == "Cucina"
    assert cucina["m2"] == 25.0            # 5 m × 5 m
    assert cucina["perimetro"] == 20.0     # 4 × 5 m
    assert cucina["uid"] == 7 and cucina["id"] == 1
    balcone = righe[1]
    assert balcone["nome"] == "Balcone scoperto"   # senza nome → categoria


# ------------------------------------------------- muri (demolire/costruire)

PIANTE_PARETI = [{
    "nome": "Piano terra", "mpp": 0.01,      # 1 px = 1 cm
    "pareti": [
        # 500 px = 5,00 m da demolire
        {"tipo": "demolire", "p1": [0, 0], "p2": [500, 0]},
        # 300 px = 3,00 m da demolire (verticale)
        {"tipo": "demolire", "p1": [0, 0], "p2": [0, 300]},
        # 400 px = 4,00 m da costruire
        {"tipo": "costruire", "p1": [0, 0], "p2": [400, 0]},
    ],
}]


def test_riepilogo_pareti_per_tipo():
    totali, senza = riepilogo_pareti(PIANTE_PARETI, altezza=2.7)
    assert senza == []
    assert totali["demolire"]["n"] == 2
    assert totali["demolire"]["ml"] == pytest.approx(8.0)      # 5 + 3
    assert totali["demolire"]["m2"] == pytest.approx(21.6)     # 8 x 2,7
    assert totali["costruire"]["ml"] == pytest.approx(4.0)
    assert totali["costruire"]["m2"] == pytest.approx(10.8)    # 4 x 2,7


def test_riepilogo_pareti_senza_scala_esclusa():
    piante = [{"nome": "Senza scala", "mpp": None,
               "pareti": [{"tipo": "demolire", "p1": [0, 0], "p2": [100, 0]}]}]
    totali, senza = riepilogo_pareti(piante, altezza=2.7)
    assert totali == {}
    assert senza == ["Senza scala"]


def test_riepilogo_pareti_senza_pareti():
    assert riepilogo_pareti([{"nome": "X", "mpp": 0.01, "pareti": []}], 2.7) \
        == ({}, [])


# ------------------------------- perimetro commerciale (fuori dai computi)

PIANTE_COMMERCIALE = [{
    "nome": "Piano", "mpp": 0.01,
    "zone": [
        {"id": 1, "categoria": "Superficie interna", "nome": "Cucina",
         "punti": [[0, 0], [300, 0], [300, 400], [0, 400]]},
        # il contorno commerciale: grande, comprende tutto
        {"id": 2, "categoria": "Superficie commerciale", "nome": None,
         "punti": [[0, 0], [600, 0], [600, 600], [0, 600]]},
    ],
}]


def test_riepilogo_locali_esclude_le_categorie_indicate():
    righe, _ = riepilogo_locali(PIANTE_COMMERCIALE,
                                escludi=["Superficie commerciale"])
    assert len(righe) == 1
    assert righe[0]["nome"] == "Cucina"


def test_riepilogo_locali_senza_esclusioni_le_prende_tutte():
    righe, _ = riepilogo_locali(PIANTE_COMMERCIALE)
    assert len(righe) == 2


def test_riepilogo_superfici_include_il_commerciale():
    # nel calcolo della superficie commerciale ci deve essere (e' il suo scopo)
    righe, tot, _, _ = riepilogo_superfici(
        PIANTE_COMMERCIALE, {"Superficie interna": 100.0,
                             "Superficie commerciale": 100.0})
    categorie = {r["categoria"] for r in righe}
    assert "Superficie commerciale" in categorie
    assert tot == pytest.approx(12.0 + 36.0)     # 3x4 + 6x6 m2


def test_etichette_ignorano_le_zone_trasparenti():
    # il contorno commerciale copre tutta l'immagine: senza trattarlo come
    # trasparente, nessuna etichetta troverebbe posto fuori dalle aree
    zone = [
        {"id": 1, "categoria": "Superficie interna",
         "punti": [[300, 300], [500, 300], [500, 500], [300, 500]]},
        {"id": 2, "categoria": "Superficie commerciale",
         "punti": [[0, 0], [1000, 0], [1000, 800], [0, 800]]},
    ]
    pos = posiziona_etichette(zone, 1000, 800,
                              trasparenti=["Superficie commerciale"])
    x, y = pos[1]
    # l'etichetta della stanza sta fuori dalla stanza (non sul baricentro)
    assert not punto_in_poligono((x, y), zone[0]["punti"])


def test_superfici_escludono_le_interne_niente_doppio_conteggio():
    # il perimetro commerciale (6x6=36) racchiude gia' la cucina (3x4=12):
    # contarle entrambe gonfierebbe la superficie vendibile
    perc = {"Superficie interna": 100.0, "Superficie commerciale": 100.0}
    _, tot, comm, _ = riepilogo_superfici(PIANTE_COMMERCIALE, perc,
                                          escludi=["Superficie interna"])
    assert tot == pytest.approx(36.0)      # solo il perimetro
    assert comm == pytest.approx(36.0)


def test_superfici_escluse_non_compaiono_tra_le_righe():
    righe, _, _, _ = riepilogo_superfici(
        PIANTE_COMMERCIALE, {"Superficie interna": 100.0},
        escludi=["Superficie interna"])
    assert all(r["categoria"] != "Superficie interna" for r in righe)
