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


def disegna(immagine, zone=(), pareti=(), dimensione_testo=None):
    """La planimetria con sopra zone, pareti e le loro misure.

    immagine: la pianta caricata (PIL).
    zone: [{"punti", "colore", "etichetta", "etichetta_pos"}] — chi chiama
        decide quali passare: il perimetro commerciale, per esempio, sulla
        tavola dei lavori non ci va.
    pareti: [{"p1", "p2", "colore", "etichetta"}].
    dimensione_testo: in pixel; se manca si sceglie sulla larghezza della
        pianta, così una scansione grande e una piccola stampano etichette
        della stessa grandezza sul foglio.

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
        pos = zona.get("etichetta_pos") or _baricentro(punti)
        _scrivi(disegno, tuple(pos), zona.get("etichetta"), carattere,
                _rgb(zona.get("colore")))
    for parete in pareti:
        p1, p2 = tuple(parete["p1"]), tuple(parete["p2"])
        pos = parete.get("etichetta_pos") or ((p1[0] + p2[0]) / 2,
                                              (p1[1] + p2[1]) / 2)
        _scrivi(disegno, tuple(pos), parete.get("etichetta"), carattere,
                _rgb(parete.get("colore")))

    return Image.alpha_composite(base, strato).convert("RGB")
