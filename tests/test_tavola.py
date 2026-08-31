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


# ------------------------------------------------- la barra di scala

def test_la_barra_vale_un_numero_tondo():
    """Una barra da «2,40 m» sarebbe esatta e inservibile: il senso e'
    appoggiarci sopra il pollice, non fare divisioni."""
    # 1200 px a 0,01 m/px = 12 m: un quinto e' 2,40, il passo tondo e' 2
    assert tavola.misura_barra(1200, 0.01) == 2
    # 600 px a 0,02 = 12 m: stessa storia, altra scansione
    assert tavola.misura_barra(600, 0.02) == 2
    # una pianta lunga: 4000 px a 0,01 = 40 m, un quinto e' 8 -> 5
    assert tavola.misura_barra(4000, 0.01) == 5


def test_senza_scala_niente_barra():
    """Una planimetria mai calibrata non ha nessuna distanza da dichiarare,
    e una barra inventata su un foglio di cantiere e' peggio del niente."""
    assert tavola.misura_barra(1200, None) is None
    assert tavola.misura_barra(1200, 0) is None
    tav = tavola.disegna(_pianta(400, 300))
    assert tav.size == (400, 300)           # nessuna striscia aggiunta


def test_un_disegno_troppo_piccolo_non_prende_la_barra():
    """Sotto il passo piu' corto (20 cm) la barra sarebbe un trattino."""
    assert tavola.misura_barra(50, 0.01) is None      # mezzo metro in tutto


def test_la_barra_si_prende_una_striscia_sua_in_fondo():
    """Dentro il disegno finirebbe sopra una stanza, e una scala che copre
    quello che serve a misurare e' peggio di nessuna scala."""
    senza = tavola.disegna(_pianta(1200, 800))
    con = tavola.disegna(_pianta(1200, 800), mpp=0.01)
    assert con.size[0] == senza.size[0]     # larga uguale
    assert con.size[1] > senza.size[1]      # e piu' alta: la striscia
    # la pianta e' intatta: la striscia sta SOTTO, non ci va sopra
    assert con.getpixel((600, 400)) == (255, 255, 255)


def test_la_barra_e_lunga_i_metri_che_dichiara():
    """E' l'unica cosa che deve essere vera: il PDF rimpicciolisce il
    disegno per farlo stare nel foglio, e una scala scritta «1:100» da quel
    momento e' falsa — la barra invece si rimpicciolisce insieme a lui."""
    metri, mpp = 2, 0.01
    tav = tavola.disegna(_pianta(1200, 800), mpp=mpp)
    assert tavola.misura_barra(1200, mpp) == metri
    # la riga a meta' altezza della barra: si contano i pixel scuri da
    # sinistra fino a dove finisce, campi vuoti compresi
    banda = tav.size[1] - 800
    y = 800 + round(banda * 0.28)
    scuri = [x for x in range(tav.size[0])
             if sum(tav.getpixel((x, y))) < 250]
    assert scuri, "la barra non e' stata disegnata"
    lunghezza = max(scuri) - min(scuri) + 1
    assert abs(lunghezza - metri / mpp) <= 4     # 200 px, a meno del tratto
