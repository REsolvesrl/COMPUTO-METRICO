"""Geometria pura per la misura delle superfici da planimetria.

Nessuna dipendenza da Streamlit o da immagini: solo coordinate in pixel
e conversioni in metri. Tutta la logica misurabile vive qui; l'interfaccia
(upload, disegno, overlay) sta in streamlit_app.py.

Convenzioni:
- un punto è una coppia (x, y) in pixel;
- "metri per pixel" (mpp) è il fattore di scala: metri_reali = pixel × mpp;
  di conseguenza le aree si convertono con mpp² (metri quadri = pixel² × mpp²).
"""

import math


def distanza_pixel(p1, p2):
    """Distanza euclidea in pixel tra due punti (x, y)."""
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


def metri_per_pixel(lunghezza_pixel, lunghezza_reale_m):
    """Fattore di scala a partire da una misura nota.

    lunghezza_pixel: lunghezza in pixel del segmento tracciato sul disegno.
    lunghezza_reale_m: quanto vale quel segmento nella realtà, in metri.
    """
    if lunghezza_pixel <= 0:
        raise ValueError("La lunghezza in pixel deve essere positiva.")
    if lunghezza_reale_m <= 0:
        raise ValueError("La misura reale deve essere positiva.")
    return lunghezza_reale_m / lunghezza_pixel


def calibra_da_due_punti(p1, p2, lunghezza_reale_m):
    """Metri per pixel calibrando su un segmento noto (due punti cliccati)."""
    return metri_per_pixel(distanza_pixel(p1, p2), lunghezza_reale_m)


def area_poligono_pixel(punti):
    """Area di un poligono in pixel² con la formula di Gauss ("shoelace").

    Il poligono si intende chiuso (l'ultimo punto si ricollega al primo);
    non serve ripetere il primo punto in fondo. Restituisce sempre un valore
    non negativo, indipendentemente dal verso (orario/antiorario) dei punti.
    """
    if len(punti) < 3:
        return 0.0
    somma = 0.0
    for i in range(len(punti)):
        x1, y1 = punti[i]
        x2, y2 = punti[(i + 1) % len(punti)]
        somma += x1 * y2 - x2 * y1
    return abs(somma) / 2.0


def perimetro_poligono_pixel(punti):
    """Perimetro di un poligono chiuso, in pixel."""
    if len(punti) < 2:
        return 0.0
    return sum(
        distanza_pixel(punti[i], punti[(i + 1) % len(punti)])
        for i in range(len(punti))
    )


def area_reale_m2(punti, mpp):
    """Superficie reale in m² del poligono, dato il fattore di scala mpp."""
    return round(area_poligono_pixel(punti) * mpp * mpp, 3)


def perimetro_reale_m(punti, mpp):
    """Perimetro reale in metri del poligono, dato il fattore di scala mpp."""
    return round(perimetro_poligono_pixel(punti) * mpp, 3)


def punto_in_poligono(punto, punti):
    """True se il punto (x, y) cade dentro il poligono (ray casting)."""
    x, y = punto
    dentro = False
    n = len(punti)
    j = n - 1
    for i in range(n):
        xi, yi = punti[i][0], punti[i][1]
        xj, yj = punti[j][0], punti[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            dentro = not dentro
        j = i
    return dentro


def posiziona_etichette(zone, larghezza, altezza):
    """Posizioni predefinite delle etichette: FUORI dalle aree, ma vicine.

    zone: [{"id", "punti", "etichetta_pos" (opzionale)}, ...]. Per ogni zona
    senza posizione personalizzata si prova, in ordine, un punto a destra,
    sinistra, sopra, sotto e agli angoli del suo riquadro: vince il primo
    che non cade dentro NESSUNA zona, resta nell'immagine e non si accavalla
    alle etichette già piazzate. Se nessun candidato va bene si ripiega sul
    baricentro (dentro l'area).

    Ritorna {id: [x, y]} solo per le zone senza posizione personalizzata.
    """
    piazzate = [tuple(z["etichetta_pos"]) for z in zone
                if z.get("etichetta_pos")]
    distacco_x = larghezza * 0.05
    distacco_y = altezza * 0.055
    dx_min = larghezza * 0.085          # ingombro tipico di un'etichetta
    dy_min = altezza * 0.05
    margine = larghezza * 0.01
    risultato = {}

    for zona in zone:
        if zona.get("etichetta_pos"):
            continue
        punti = zona.get("punti") or []
        if len(punti) < 3:
            continue
        xs = [p[0] for p in punti]
        ys = [p[1] for p in punti]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        candidati = [
            (x1 + distacco_x, cy), (x0 - distacco_x, cy),
            (cx, y0 - distacco_y), (cx, y1 + distacco_y),
            (x1 + distacco_x, y0), (x0 - distacco_x, y0),
            (x1 + distacco_x, y1), (x0 - distacco_x, y1),
        ]

        def valido(px, py, controlla_distanza):
            if not (margine <= px <= larghezza - margine
                    and margine <= py <= altezza - margine):
                return False
            if any(punto_in_poligono((px, py), q.get("punti") or [])
                   for q in zone if len(q.get("punti") or []) >= 3):
                return False
            if controlla_distanza and any(
                    abs(px - ox) < dx_min and abs(py - oy) < dy_min
                    for ox, oy in piazzate):
                return False
            return True

        scelto = None
        for con_distanza in (True, False):
            for px, py in candidati:
                if valido(px, py, con_distanza):
                    scelto = (px, py)
                    break
            if scelto:
                break
        if scelto is None:
            scelto = (cx, cy)
        risultato[zona["id"]] = [round(scelto[0], 1), round(scelto[1], 1)]
        piazzate.append(scelto)
    return risultato


def riepilogo_locali(piante):
    """Elenco per-locale (zona) delle piante con scala: superficie e perimetro.

    Serve per battiscopa (metri lineari) e tinteggiature (perimetro × altezza
    per le pareti, superficie calpestabile per i soffitti).

    Ritorna (righe, senza_scala). Ogni riga: {"pianta", "uid", "id", "nome",
    "categoria", "m2", "perimetro"} — nome = nome della zona o, se assente,
    la categoria. Le piante senza scala finiscono in senza_scala.
    """
    righe = []
    senza_scala = []
    for pianta in piante:
        zone = pianta.get("zone") or []
        if not zone:
            continue
        mpp = pianta.get("mpp")
        nome_pianta = pianta.get("nome") or "Planimetria"
        if not mpp:
            senza_scala.append(nome_pianta)
            continue
        for zona in zone:
            punti = zona.get("punti") or []
            righe.append({
                "pianta": nome_pianta,
                "uid": pianta.get("uid"),
                "id": zona.get("id"),
                "nome": zona.get("nome") or zona.get("categoria") or "Zona",
                "categoria": zona.get("categoria") or "",
                "m2": area_reale_m2(punti, mpp),
                "perimetro": perimetro_reale_m(punti, mpp),
            })
    return righe, senza_scala


def riepilogo_superfici(piante, percentuali):
    """Riepilogo delle superfici di tutte le planimetrie di un progetto.

    piante: elenco di dizionari {"nome", "mpp", "zone": [{"categoria", "punti"}]}.
    percentuali: {nome_categoria: percento} — il peso "commerciale" di ogni
        categoria (es. balcone 30). Le categorie sconosciute valgono 100.

    Ritorna (righe, totale_m2, totale_commerciale, senza_scala):
    - righe: aggregate per (pianta, categoria) con numero di zone, m² reali,
      percento e m² commerciali (reali × percento / 100);
    - senza_scala: nomi delle piante con zone ma senza scala impostata,
      escluse dai totali.
    """
    righe = []
    totale_m2 = 0.0
    totale_comm = 0.0
    senza_scala = []
    for pianta in piante:
        nome = pianta.get("nome") or "Planimetria"
        mpp = pianta.get("mpp")
        zone = pianta.get("zone") or []
        if not zone:
            continue
        if not mpp:
            senza_scala.append(nome)
            continue
        gruppi = {}
        for zona in zone:
            categoria = zona.get("categoria") or "Senza categoria"
            gruppo = gruppi.setdefault(categoria, {"zone": 0, "m2": 0.0})
            gruppo["zone"] += 1
            gruppo["m2"] += area_reale_m2(zona.get("punti") or [], mpp)
        for categoria, gruppo in gruppi.items():
            percento = float(percentuali.get(categoria, 100.0))
            m2 = round(gruppo["m2"], 3)
            m2_comm = round(m2 * percento / 100.0, 3)
            righe.append({
                "pianta": nome,
                "categoria": categoria,
                "zone": gruppo["zone"],
                "percento": percento,
                "m2": m2,
                "m2_commerciale": m2_comm,
            })
            totale_m2 += m2
            totale_comm += m2_comm
    return righe, round(totale_m2, 2), round(totale_comm, 2), senza_scala
