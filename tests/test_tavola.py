"""La planimetria disegnata per la stampa.

Sullo schermo il disegno lo fa il browser; nel PDF va rifatto qui, dalle
stesse coordinate. Il rischio non è che si veda «brutto»: è che una zona o
una quota SPARISCANO dal foglio che si porta in cantiere, e che nessuno se
ne accorga finché non serve.
"""
from PIL import Image

import tavola


def _pianta(larghezza=400, altezza=300):
    return Image.new("RGB", (larghezza, altezza), "white")


QUADRATO = [[50, 50], [150, 50], [150, 150], [50, 150]]


def test_il_disegno_non_tocca_l_immagine_di_partenza():
    """L'originale resta quello caricato: la tavola è una copia."""
    pianta = _pianta()
    prima = pianta.tobytes()
    tavola.disegna(pianta, [{"punti": QUADRATO, "colore": "#E57373",
                             "etichetta": "Camera"}])
    assert pianta.tobytes() == prima


def test_la_zona_si_vede_ma_non_copre_il_disegno_sotto():
    """Il riempimento è un velo: sotto c'è la pianta, ed è quella che dà
    senso alle misure."""
    tav = tavola.disegna(_pianta(), [{"punti": QUADRATO, "colore": "#FF0000",
                                      "etichetta": ""}])
    dentro = tav.getpixel((100, 100))
    assert dentro != (255, 255, 255)        # la tinta si vede
    assert min(dentro) > 120                # ma resta un velo, non un muro


def test_le_etichette_fuori_dall_immagine_allargano_il_foglio():
    """L'app mette le etichette A LATO delle aree, e per una zona che tocca
    il bordo «a lato» vuol dire oltre il foglio: posizioni negative o più
    grandi della larghezza. Senza allargare, quelle quote sparirebbero."""
    tav = tavola.disegna(
        _pianta(400, 300),
        [{"punti": QUADRATO, "colore": "#E57373", "etichetta": "Camera",
          "etichetta_pos": [-120, 150]}])
    assert tav.size[0] > 400                # il foglio è cresciuto a sinistra


def test_una_tavola_senza_etichette_fuori_resta_della_sua_misura():
    tav = tavola.disegna(
        _pianta(400, 300),
        [{"punti": QUADRATO, "colore": "#E57373", "etichetta": "Camera",
          "etichetta_pos": [200, 150]}])
    assert tav.size == (400, 300)


def test_la_parete_si_disegna_del_suo_colore():
    tav = tavola.disegna(_pianta(), pareti=[
        {"p1": [10, 200], "p2": [390, 200], "colore": "#43A047",
         "etichetta": ""}])
    r, g, b = tav.getpixel((200, 200))
    assert g > r and g > b                  # verde: il cartongesso


def test_senza_niente_da_disegnare_esce_la_pianta_e_basta():
    tav = tavola.disegna(_pianta(200, 100))
    assert tav.size == (200, 100)
    assert tav.getpixel((100, 50)) == (255, 255, 255)


def test_un_colore_illeggibile_non_fa_saltare_la_stampa():
    """Meglio una zona grigia che un PDF che non esce."""
    tav = tavola.disegna(_pianta(), [{"punti": QUADRATO, "colore": "verdino",
                                      "etichetta": "x"}])
    assert tav.size == (400, 300)


def test_il_richiamo_unisce_la_targhetta_alla_sua_area():
    """L'etichetta sta FUORI dall'area: senza il segmento, una fila di
    misure a lato del disegno non dice a quale stanza appartiene nessuna."""
    tav = tavola.disegna(_pianta(), [{"punti": QUADRATO, "colore": "#E57373",
                                      "etichetta": "Camera",
                                      "etichetta_pos": [300, 100]}])
    # a metà strada fra il bordo destro del quadrato (x=150) e la targhetta
    r, g, b = tav.getpixel((225, 100))
    assert r > g and r > b                  # il rosso della zona


def test_il_richiamo_arriva_sul_bordo_che_guarda_l_etichetta():
    """Sul baricentro attraverserebbe la stanza e taglierebbe in due il
    disegno che dovrebbe indicare."""
    lungo = [[50, 50], [350, 50], [350, 100], [50, 100]]
    assert tavola._aggancio([tuple(p) for p in lungo], (350, 200)) == (350, 100)
