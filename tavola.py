"""La planimetria disegnata, per la stampa.

Sullo schermo il disegno lo fa il browser: la tela del componente
`cme_viewer` conosce zone, pareti ed etichette e le ridisegna a ogni gesto.
In un PDF quel canvas non c'è, e la stessa pianta va ricostruita qui — a
partire dall'immagine caricata e dalle stesse coordinate in pixel.

Nessuna dipendenza da Streamlit: entrano un'immagine e due elenchi, esce
un'immagine. Così la tavola si prova con pytest senza aprire l'app.

⚠️ Le coordinate sono quelle dell'IMMAGINE, non dello schermo: il
componente lavora già in quel sistema, quindi qui non c'è nessuna
conversione da rifare — ed è il motivo per cui il disegno stampato combacia
con quello a video invece di somigliargli.
"""

from PIL import Image, ImageDraw, ImageFont

# Il carattere: si prova a prenderne uno vero dal sistema, in ordine di
# preferenza. Senza, PIL ripiega su una bitmap minuscola che su una
# planimetria in A4 non si legge — meglio saperlo che scoprirlo in stampa.
CARATTERI = (
    "C:/Windows/Fonts/segoeui.ttf",
    "C:/Windows/Fonts/arial.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
)

# Quanto si vede della tinta: il riempimento è un velo, il contorno è pieno.
# Una zona piena coprirebbe il disegno sotto, che è quello che dà il senso
# alle misure.
VELO = 60           # 0-255
SPESSORE_ZONA = 3
SPESSORE_PARETE = 6
SPESSORE_RICHIAMO = 2

# I metri che una barra di scala può valere: la solita successione 1-2-5,
# quella dei righelli. Una barra da «3,70 m» sarebbe esatta e inutilizzabile
# — il senso è poterci appoggiare sopra il pollice e leggere una distanza
# senza fare divisioni.
PASSI_SCALA = (0.2, 0.5, 1, 2, 5, 10, 20, 50, 100, 200, 500)
INCHIOSTRO = (30, 30, 30)


def _carattere(dimensione):
    for percorso in CARATTERI:
        try:
            return ImageFont.truetype(percorso, dimensione)
        except OSError:
            continue
    return ImageFont.load_default()


def _rgb(colore):
    """«#RRGGBB» → (r, g, b). Il grigio se non si capisce."""
    testo = (colore or "").lstrip("#")
    if len(testo) != 6:
        return (158, 158, 158)
    try:
        return tuple(int(testo[i:i + 2], 16) for i in (0, 2, 4))
    except ValueError:
        return (158, 158, 158)


def _baricentro(punti):
    return (sum(p[0] for p in punti) / len(punti),
            sum(p[1] for p in punti) / len(punti))


def _aggancio(punti, verso):
    """Il punto del contorno più vicino all'etichetta.

    L'etichetta sta fuori dall'area: il segmento di richiamo deve arrivare
    sul BORDO che le sta davanti, non sul baricentro — se no attraversa
    mezza stanza e taglia in due il disegno che dovrebbe indicare.
    """
    candidati = list(punti)
    # anche i punti di mezzo dei lati: su una stanza lunga il vertice più
    # vicino può essere lontanissimo dal lato che guarda l'etichetta
    for i, punto in enumerate(punti):
        dopo = punti[(i + 1) % len(punti)]
        candidati.append(((punto[0] + dopo[0]) / 2, (punto[1] + dopo[1]) / 2))
    return min(candidati,
               key=lambda p: (p[0] - verso[0]) ** 2 + (p[1] - verso[1]) ** 2)


def _scrivi(disegno, pos, testo, carattere, colore):
    """Testo su una targhetta chiara: sopra una planimetria fotocopiata il
    testo nudo sparisce dentro le linee del disegno."""
    if not testo:
        return
    righe = testo.split("\n")
    larghezza = max(disegno.textlength(r, font=carattere) for r in righe)
    alto = carattere.size + 3
    x, y = pos
    x -= larghezza / 2
    y -= alto * len(righe) / 2
    disegno.rectangle(
        [x - 6, y - 4, x + larghezza + 6, y + alto * len(righe) + 2],
        fill=(255, 255, 255, 225), outline=colore, width=2)
    for n, riga in enumerate(righe):
        disegno.text((x, y + n * alto), riga, font=carattere, fill=(30, 30, 30))


def misura_barra(larghezza_px, mpp):
    """Quanti metri far valere la barra di scala: un numero tondo.

    Si punta a circa un quinto della larghezza del foglio — abbastanza da
    misurarci sopra, non tanto da attraversare il disegno — e da lì si
    scende al passo tondo più vicino. Torna None se la pianta non ha scala:
    senza mpp non c'è nessuna distanza da dichiarare.
    """
    if not mpp or mpp <= 0 or larghezza_px <= 0:
        return None
    obiettivo = larghezza_px * mpp / 5.0
    tondi = [passo for passo in PASSI_SCALA if passo <= obiettivo]
    if not tondi:
        return None          # un disegno che non arriva a 20 cm di larghezza
    return tondi[-1]


def _barra_scala(disegno, sinistra, base, metri, mpp, carattere):
    """La barra graduata, in basso a sinistra, con la sua misura scritta.

    ⚠️ GRAFICA, non «1:100», e non è una scelta di gusto: il PDF rimpicciolisce
    il disegno finché non entra nel foglio, e chi stampa può rimpicciolirlo
    ancora. Una scala scritta in cifre da quel momento è FALSA — dice 1:100 e
    sul foglio è 1:137 — mentre la barra si rimpicciolisce insieme al disegno
    e resta vera in ogni fotocopia. In cantiere qualcuno il metro sopra il
    foglio ce lo appoggia davvero.

    Quattro campi alternati pieni e vuoti, come sulle carte: si contano a
    colpo d'occhio e danno anche il quarto della misura.
    """
    lunghezza = metri / mpp
    alta = max(4, round(carattere.size * 0.45))
    campo = lunghezza / 4.0
    for n in range(4):
        x0 = sinistra + n * campo
        riquadro = [x0, base, x0 + campo, base + alta]
        disegno.rectangle(riquadro,
                          fill=INCHIOSTRO + (255,) if n % 2 == 0 else None,
                          outline=INCHIOSTRO + (255,), width=2)
    # le cifre sotto la barra: lo zero all'inizio, la misura in fondo, così
    # si legge come un righello invece che come una didascalia
    disegno.text((sinistra, base + alta + 4), "0", font=carattere,
                 fill=INCHIOSTRO + (255,))
    testo = (f"{metri:g}".replace(".", ",") + " m")
    disegno.text((sinistra + lunghezza - disegno.textlength(
        testo, font=carattere), base + alta + 4), testo, font=carattere,
        fill=INCHIOSTRO + (255,))


def _sposta_punto(punto, scarto):
    if punto is None:
        return None
    return (punto[0] + scarto[0], punto[1] + scarto[1])


def _sposta(punti, scarto):
    return [_sposta_punto(p, scarto) for p in (punti or [])]


def _margini(dimensione, zone, pareti, corpo):
    """Quanto allargare il foglio perché le etichette ci stiano dentro.

    Ritorna (sinistra, sopra, destra, sotto). Si guarda dove cadono le
    etichette, non solo il disegno: sono loro a sporgere.
    """
    larghezza, altezza = dimensione
    # mezza targhetta per lato: la posizione è il CENTRO del testo
    mezzo_x, mezzo_y = 9 * corpo, 3 * corpo
    sx = sopra = dx = sotto = 0
    posizioni = [z.get("etichetta_pos") for z in zone]
    posizioni += [p.get("etichetta_pos") for p in pareti]
    for pos in posizioni:
        if not pos:
            continue
        sx = max(sx, round(mezzo_x - pos[0]))
        sopra = max(sopra, round(mezzo_y - pos[1]))
        dx = max(dx, round(pos[0] + mezzo_x - larghezza))
        sotto = max(sotto, round(pos[1] + mezzo_y - altezza))
    return (max(0, sx), max(0, sopra), max(0, dx), max(0, sotto))


def disegna(immagine, zone=(), pareti=(), dimensione_testo=None, mpp=None):
    """La planimetria con sopra zone, pareti e le loro misure.

    immagine: la pianta caricata (PIL).
    zone: [{"punti", "colore", "etichetta", "etichetta_pos"}] — chi chiama
        decide quali passare: il perimetro commerciale, per esempio, sulla
        tavola dei lavori non ci va.
    pareti: [{"p1", "p2", "colore", "etichetta"}].
    dimensione_testo: in pixel; se manca si sceglie sulla larghezza della
        pianta, così una scansione grande e una piccola stampano etichette
        della stessa grandezza sul foglio.
    mpp: metri per pixel della pianta. Se c'è, in basso a sinistra compare
        la barra di scala; se manca — planimetria mai calibrata — non
        compare, perché non c'è nessuna distanza da dichiarare.

    Ritorna una nuova immagine RGB: l'originale non si tocca.
    """
    pianta = immagine.convert("RGBA")
    # Il corpo si misura sulla pianta, non sul foglio: una scansione grande
    # e una piccola devono stampare etichette della stessa grandezza. Il
    # rapporto è tarato perché su un A4 escano circa sette punti — sotto,
    # in fotocopia, i metri quadri non si leggono più.
    corpo = dimensione_testo or max(15, round(pianta.size[0] / 45))
    carattere = _carattere(corpo)

    # ⚠️ LE ETICHETTE STANNO FUORI DALL'IMMAGINE, e non per sbaglio: l'app
    # le mette a lato delle aree, non sopra, così non coprono il disegno —
    # e per le zone che toccano il bordo «a lato» vuol dire oltre il foglio
    # (posizioni negative, o maggiori della larghezza). Sullo schermo si
    # vedono lo stesso, perché la tela è più grande della pianta. Qui il
    # foglio se lo deve fare: si misura quanto sporgono e si allarga.
    margine = _margini(pianta.size, zone, pareti, corpo)
    # La barra vuole una striscia sua in fondo al foglio: dentro il disegno
    # finirebbe sopra una stanza, e una scala che copre quello che serve a
    # misurare è peggio di nessuna scala.
    metri_barra = misura_barra(pianta.size[0], mpp)
    banda = round(corpo * 2.6) if metri_barra else 0
    margine = (margine[0], margine[1], margine[2], margine[3] + banda)
    base = Image.new("RGBA", (pianta.size[0] + margine[0] + margine[2],
                              pianta.size[1] + margine[1] + margine[3]),
                     (255, 255, 255, 255))
    base.paste(pianta, (margine[0], margine[1]))
    scarto = (margine[0], margine[1])
    zone = [dict(z, punti=_sposta(z.get("punti"), scarto),
                 etichetta_pos=_sposta_punto(z.get("etichetta_pos"), scarto))
            for z in zone]
    pareti = [dict(p, p1=_sposta_punto(p["p1"], scarto),
                   p2=_sposta_punto(p["p2"], scarto),
                   etichetta_pos=_sposta_punto(p.get("etichetta_pos"), scarto))
              for p in pareti]

    strato = Image.new("RGBA", base.size, (0, 0, 0, 0))
    disegno = ImageDraw.Draw(strato)

    for zona in zone:
        punti = [tuple(p) for p in (zona.get("punti") or [])]
        if len(punti) < 3:
            continue
        colore = _rgb(zona.get("colore"))
        disegno.polygon(punti, fill=colore + (VELO,))
        disegno.line(punti + [punti[0]], fill=colore + (255,),
                     width=SPESSORE_ZONA, joint="curve")

    for parete in pareti:
        p1, p2 = tuple(parete["p1"]), tuple(parete["p2"])
        colore = _rgb(parete.get("colore"))
        disegno.line([p1, p2], fill=colore + (255,), width=SPESSORE_PARETE)

    # Le etichette per ultime: devono stare SOPRA a tutte le campiture, se no
    # una zona disegnata dopo ne coprirebbe una scritta prima.
    for zona in zone:
        punti = [tuple(p) for p in (zona.get("punti") or [])]
        if len(punti) < 3:
            continue
        pos = tuple(zona.get("etichetta_pos") or _baricentro(punti))
        colore = _rgb(zona.get("colore"))
        # Il richiamo si disegna PRIMA della targhetta, così il tratto che
        # finirebbe sotto il testo lo copre la targhetta stessa: senza, una
        # riga di etichette a lato del disegno non dice a quale stanza
        # appartiene nessuna delle misure.
        if zona.get("etichetta"):
            disegno.line([pos, _aggancio(punti, pos)], fill=colore + (255,),
                         width=SPESSORE_RICHIAMO)
        _scrivi(disegno, pos, zona.get("etichetta"), carattere, colore)
    for parete in pareti:
        p1, p2 = tuple(parete["p1"]), tuple(parete["p2"])
        pos = parete.get("etichetta_pos") or ((p1[0] + p2[0]) / 2,
                                              (p1[1] + p2[1]) / 2)
        _scrivi(disegno, tuple(pos), parete.get("etichetta"), carattere,
                _rgb(parete.get("colore")))

    if metri_barra:
        _barra_scala(disegno, margine[0], base.size[1] - banda + corpo * 0.4,
                     metri_barra, mpp, carattere)

    return Image.alpha_composite(base, strato).convert("RGB")
