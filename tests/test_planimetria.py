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
    quantita_finiture,
    riepilogo_locali,
    muri_al_netto,
    riepilogo_pareti,
    voci_da_riscrivere,
    riepilogo_superfici,
    superficie_commerciale,
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


# ---------------------- il computo che si aggancia da sé al disegno

MAPPA = [("1.02", "muri_demolire"), ("2.01", "muri_costruire")]


def test_voci_da_riscrivere_porta_le_misure_nuove():
    """Muri appena tracciati: il computo era vuoto, ora ha le due voci."""
    proposte = voci_da_riscrivere(
        MAPPA, {"muri_demolire": 21.6, "muri_costruire": 10.8}, {})
    assert proposte == {"1.02": 21.6, "2.01": 10.8}


def test_voci_da_riscrivere_tace_se_e_gia_a_posto():
    """Il dizionario vuoto è il segnale che NON serve rifare il giro."""
    assert voci_da_riscrivere(
        MAPPA, {"muri_demolire": 21.6, "muri_costruire": 10.8},
        {"1.02": 21.6, "2.01": 10.8}) == {}


def test_voci_da_riscrivere_ignora_i_centesimi():
    """Sotto la tolleranza non si riscrive: sarebbe una rincorsa infinita."""
    assert voci_da_riscrivere(MAPPA, {"muri_demolire": 21.6},
                              {"1.02": 21.603}) == {}


def test_voci_da_riscrivere_sostituisce_non_somma():
    """Spostato un muro, la quantità vale quella nuova, non la somma."""
    proposte = voci_da_riscrivere(MAPPA, {"muri_demolire": 15.0},
                                  {"1.02": 21.6})
    assert proposte == {"1.02": 15.0}


def test_voci_da_riscrivere_non_cancella_i_numeri_a_mano():
    """Nessun muro tracciato: la voce compilata a mano resta dov'è."""
    assert voci_da_riscrivere(MAPPA, {"muri_demolire": 0.0},
                              {"1.02": 30.0}) == {}
    assert voci_da_riscrivere(MAPPA, {}, {"1.02": 30.0}) == {}


def test_voci_da_riscrivere_lascia_stare_le_voci_escluse():
    """Voce col libretto misure: la quantità la decide quello."""
    proposte = voci_da_riscrivere(
        MAPPA, {"muri_demolire": 21.6, "muri_costruire": 10.8}, {},
        escluse=["1.02"])
    assert proposte == {"2.01": 10.8}


def test_voci_da_riscrivere_arrotonda_ai_centesimi():
    assert voci_da_riscrivere(MAPPA, {"muri_demolire": 21.6666}, {}) \
        == {"1.02": 21.67}


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


# --------------------------- superfici di ornamento (scaglione dei giardini)

def test_superficie_commerciale_senza_soglia():
    # balcone: 40 m2 al 25% = 10 m2, nessuno scaglione
    assert superficie_commerciale(40, 25) == pytest.approx(10.0)


def test_superficie_commerciale_sotto_la_soglia():
    # giardino di 20 m2 al 15%: tutto pieno
    assert superficie_commerciale(20, 15, soglia=25, percento_oltre=5) \
        == pytest.approx(3.0)


def test_superficie_commerciale_con_eccedenza():
    # giardino di appartamento 100 m2: 25 al 15% + 75 al 5%
    assert superficie_commerciale(100, 15, soglia=25, percento_oltre=5) \
        == pytest.approx(25 * 0.15 + 75 * 0.05)      # 3,75 + 3,75 = 7,5


def test_superficie_commerciale_villa_eccedenza_al_due():
    # giardino di villa 525 m2: 25 al 10% + 500 al 2%
    assert superficie_commerciale(525, 10, soglia=25, percento_oltre=2) \
        == pytest.approx(2.5 + 10.0)


def test_riepilogo_superfici_applica_lo_scaglione():
    piante = [{"nome": "P", "mpp": 0.1, "zone": [      # 1 px = 10 cm
        # 100 m2 di giardino: 10 m x 10 m = 100 px x 100 px
        {"id": 1, "categoria": "Giardino di appartamento",
         "punti": [[0, 0], [100, 0], [100, 100], [0, 100]]},
    ]}]
    regole = {"Giardino di appartamento": {"percento": 15.0, "soglia": 25.0,
                                           "oltre": 5.0}}
    righe, tot, comm, _ = riepilogo_superfici(piante, regole)
    assert tot == pytest.approx(100.0)
    assert comm == pytest.approx(7.5)
    assert righe[0]["m2_commerciale"] == pytest.approx(7.5)


# ------------------------- detrazioni di porte e rivestimenti (finiture)

# soggiorno 5,00x4,00 (20 m2, perim. 18) + bagno 3,00x2,00 (6 m2, perim. 10)
LOCALI = [
    {"m2": 20.0, "perimetro": 18.0, "pavimento": True, "battiscopa": True,
     "pittura": True, "rivestito": False},
    {"m2": 6.0, "perimetro": 10.0, "pavimento": True, "battiscopa": True,
     "pittura": True, "rivestito": True},
]


def test_finiture_senza_detrazioni():
    q = quantita_finiture(LOCALI, altezza=2.7)
    assert q["pavimento"] == pytest.approx(26.0)
    # il bagno e' rivestito: niente battiscopa nemmeno senza porte
    assert q["battiscopa"] == pytest.approx(18.0)
    # pareti lorde 28 m di perimetro x 2,7 = 75,6
    assert q["pareti_lorde"] == pytest.approx(75.6)


def test_finiture_bagno_rivestito_fuori_dal_battiscopa():
    q = quantita_finiture(LOCALI, altezza=2.7)
    assert q["battiscopa_lordo"] == pytest.approx(18.0)   # solo il soggiorno


def test_finiture_detrae_la_fascia_rivestita():
    q = quantita_finiture(LOCALI, altezza=2.7, altezza_rivestimento=1.2)
    # bagno: 10 m di perimetro x 1,20 = 12 m2 che non si tinteggiano
    assert q["detr_rivestimenti"] == pytest.approx(12.0)
    assert q["pareti"] == pytest.approx(75.6 - 12.0)


def test_finiture_porta_interna_conta_due_lati():
    # 5 porte interne = 10 lati: il vano interrompe il battiscopa di qua e
    # di la', e toglie superficie a due pareti
    q = quantita_finiture(LOCALI, altezza=2.7, larghezza_porta=0.8,
                          altezza_porta=2.1, n_porte=5)
    assert q["lati_porta"] == 10
    assert q["detr_porte_ml"] == pytest.approx(8.0)        # 0,8 x 10
    assert q["detr_porte_m2"] == pytest.approx(16.8)       # 0,8 x 2,1 x 10
    assert q["battiscopa"] == pytest.approx(18.0 - 8.0)
    assert q["pareti"] == pytest.approx(75.6 - 16.8)


def test_finiture_porta_esterna_conta_un_lato():
    q = quantita_finiture(LOCALI, altezza=2.7, larghezza_porta=0.9,
                          altezza_porta=2.1, n_porte=0, n_porte_esterne=1)
    assert q["lati_porta"] == 1
    assert q["detr_porte_ml"] == pytest.approx(0.9)


def test_finiture_interne_ed_esterne_insieme():
    q = quantita_finiture(LOCALI, altezza=2.7, larghezza_porta=1.0,
                          altezza_porta=2.0, n_porte=3, n_porte_esterne=1)
    assert q["lati_porta"] == 7                            # 3 x 2 + 1
    assert q["detr_porte_ml"] == pytest.approx(7.0)


def test_finiture_tutte_le_detrazioni_insieme():
    q = quantita_finiture(LOCALI, altezza=2.7, larghezza_porta=0.8,
                          altezza_porta=2.1, n_porte=5,
                          altezza_rivestimento=1.2)
    assert q["battiscopa"] == pytest.approx(10.0)          # 18 - 8
    assert q["pareti"] == pytest.approx(75.6 - 12.0 - 16.8)  # 46,8
    assert q["soffitti"] == pytest.approx(26.0)            # i soffitti restano


def test_finiture_non_scendono_sotto_zero():
    q = quantita_finiture(LOCALI, altezza=2.7, larghezza_porta=0.9,
                          altezza_porta=2.1, n_porte=100)
    assert q["battiscopa"] == 0.0
    assert q["pareti"] == 0.0


# ------------------------------ finestre e porte finestra (un solo lato)

FINESTRA = {"n": 3, "larghezza": 1.2, "altezza": 1.4, "battiscopa": False}
PORTA_FINESTRA = {"n": 2, "larghezza": 1.2, "altezza": 2.3,
                  "battiscopa": True}


def test_finestra_toglie_parete_ma_non_battiscopa():
    """Il davanzale sta in alto: sotto la finestra il battiscopa passa."""
    q = quantita_finiture(LOCALI, altezza=2.7, aperture=[FINESTRA])
    assert q["detr_aperture_m2"] == pytest.approx(5.04)    # 1,2 x 1,4 x 3
    assert q["detr_aperture_ml"] == 0.0
    assert q["battiscopa"] == pytest.approx(18.0)          # intatto
    assert q["pareti"] == pytest.approx(75.6 - 5.04)


def test_porta_finestra_toglie_anche_il_battiscopa():
    """Arriva a terra, quindi interrompe lo zoccolino."""
    q = quantita_finiture(LOCALI, altezza=2.7, aperture=[PORTA_FINESTRA])
    assert q["detr_aperture_m2"] == pytest.approx(5.52)    # 1,2 x 2,3 x 2
    assert q["detr_aperture_ml"] == pytest.approx(2.4)     # 1,2 x 2
    assert q["battiscopa"] == pytest.approx(18.0 - 2.4)
    assert q["pareti"] == pytest.approx(75.6 - 5.52)


def test_aperture_valgono_un_lato_solo():
    """Stanno su un muro perimetrale: di la' non c'e' un altro locale."""
    q = quantita_finiture(LOCALI, altezza=2.7, aperture=[
        {"n": 1, "larghezza": 1.0, "altezza": 1.0, "battiscopa": True}])
    assert q["detr_aperture_m2"] == pytest.approx(1.0)     # non 2,0
    assert q["detr_aperture_ml"] == pytest.approx(1.0)


def test_aperture_insieme_a_porte_e_rivestimenti():
    q = quantita_finiture(LOCALI, altezza=2.7, larghezza_porta=0.8,
                          altezza_porta=2.1, n_porte=5,
                          altezza_rivestimento=1.2,
                          aperture=[FINESTRA, PORTA_FINESTRA])
    assert q["battiscopa"] == pytest.approx(18.0 - 8.0 - 2.4)
    assert q["pareti"] == pytest.approx(75.6 - 12.0 - 16.8 - 5.04 - 5.52)
    assert q["soffitti"] == pytest.approx(26.0)            # i soffitti restano


def test_aperture_a_zero_non_cambiano_niente():
    senza = quantita_finiture(LOCALI, altezza=2.7)
    con = quantita_finiture(LOCALI, altezza=2.7, aperture=[
        {"n": 0, "larghezza": 1.2, "altezza": 1.4, "battiscopa": True}])
    assert con["battiscopa"] == senza["battiscopa"]
    assert con["pareti"] == senza["pareti"]


# ------------------------------- aperture nei muri da demolire/costruire

def test_muri_al_netto_toglie_i_vani():
    # 21,60 m2 di muro con dentro una porta da 0,80 x 2,10 = 1,68 m2
    assert muri_al_netto(21.6, 1.68) == pytest.approx(19.92)


def test_muri_al_netto_senza_aperture():
    assert muri_al_netto(21.6, 0.0) == pytest.approx(21.6)


def test_muri_al_netto_non_scende_sotto_zero():
    """Apertura piu' grande del muro: errore di battitura, non un negativo."""
    assert muri_al_netto(10.0, 50.0) == 0.0
