"""Rilevamento automatico (beta) delle stanze da una planimetria.

Visione classica con OpenCV, niente AI. Il metodo:
1. si binarizza il disegno (muri e linee = "inchiostro");
2. si CANCELLANO le scritte (testi, quote, simboli): componenti d'inchiostro
   piccole e isolate, che altrimenti disturbano il riconoscimento;
3. si DILATANO i muri di mezzo vano-porta, così i varchi delle porte si
   sigillano e ogni stanza diventa una regione bianca isolata;
4. ogni regione che non tocca il bordo (quella è l'esterno) è una stanza
   candidata, ma rimpicciolita dalla dilatazione: la si "ricostruisce"
   facendola ricrescere passo-passo dentro lo spazio libero originale,
   fermandosi contro i muri veri (ricostruzione geodetica);
5. il contorno ricostruito, semplificato, è il poligono proposto.

Se la scala è impostata, l'ampiezza del varco-porta da sigillare si calcola
in metri (≈ 1 m); senza scala si provano più ampiezze e si tiene il
tentativo che trova più stanze.

Le proposte vanno sempre rifinite dall'utente con gli strumenti di
modifica. Funzioni pure e testabili: immagine PIL in ingresso, poligoni in
uscita (coordinate in pixel dell'immagine, come le zone disegnate a mano).
"""

import cv2
import numpy as np


def _binarizza(immagine):
    """Immagine PIL → maschera 0/255 dell'"inchiostro" (muri e linee)."""
    rgb = np.asarray(immagine.convert("RGB"))
    grigio = cv2.cvtColor(rgb, cv2.COLOR_RGB2GRAY)
    alt, larg = grigio.shape
    sfocata = cv2.GaussianBlur(grigio, (3, 3), 0)
    blocco = max(15, (min(larg, alt) // 40) | 1)   # dimensione dispari
    return cv2.adaptiveThreshold(
        sfocata, 255, cv2.ADAPTIVE_THRESH_MEAN_C,
        cv2.THRESH_BINARY_INV, blocco, 12)


def _rimuovi_scritte(inchiostro, soglia_px):
    """Cancella testi, quote e simboletti dall'inchiostro.

    Le scritte sono componenti connesse PICCOLE e isolate (ogni lettera è un
    blob a sé); i muri appartengono sempre a strutture grandi e collegate.
    Si rimuove quindi ogni componente il cui ingombro massimo è sotto la
    soglia (≈ mezzo metro): senza questa pulizia, il testo "ingrassato"
    dalla dilatazione spezza o erode le stanze.
    """
    n_comp, etichette, stats, _ = cv2.connectedComponentsWithStats(
        inchiostro, 8)
    pulito = inchiostro.copy()
    for i in range(1, n_comp):
        x, y, bw, bh, _area = stats[i]
        if max(bw, bh) < soglia_px:
            ritaglio = pulito[y:y + bh, x:x + bw]
            ritaglio[etichette[y:y + bh, x:x + bw] == i] = 0
    return pulito


def _ricostruisci(maschera, spazio_libero, passi):
    """Fa ricrescere la regione dentro lo spazio libero, contro i muri.

    Una dilatazione 3×3 per passo (1 px alla volta), sempre intersecata con
    lo spazio libero originale: i muri la bloccano, e oltre le porte può
    sconfinare al massimo di `passi` pixel.
    """
    kernel = np.ones((3, 3), np.uint8)
    for _ in range(passi):
        maschera = cv2.bitwise_and(cv2.dilate(maschera, kernel),
                                   spazio_libero)
    return maschera


def _stanze_con_porta(inchiostro, spazio_libero, porta_px,
                      area_min, area_max):
    """Stanze [(area, poligono), ...] sigillando varchi larghi ≤ porta_px."""
    alt, larg = inchiostro.shape
    raggio = porta_px // 2 + 2

    kern = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                     (2 * raggio + 1, 2 * raggio + 1))
    muri_dilatati = cv2.dilate(inchiostro, kern)
    libero_ristretto = cv2.bitwise_not(muri_dilatati)
    n_comp, etichette, stats, _ = cv2.connectedComponentsWithStats(
        libero_ristretto, 8)

    trovate = []
    for i in range(1, n_comp):
        x, y, bw, bh, area = stats[i]
        if x <= 1 or y <= 1 or x + bw >= larg - 1 or y + bh >= alt - 1:
            continue                            # tocca il bordo: è l'esterno
        if area < max(64, area_min * 0.1):
            continue                            # briciola: inutile ricostruire

        # ricostruzione geodetica, lavorando solo sul riquadro interessato
        margine = raggio + 4
        x0, y0 = max(0, x - margine), max(0, y - margine)
        x1 = min(larg, x + bw + margine)
        y1 = min(alt, y + bh + margine)
        maschera = np.uint8(etichette[y0:y1, x0:x1] == i) * 255
        maschera = _ricostruisci(maschera, spazio_libero[y0:y1, x0:x1],
                                 raggio + 2)
        area_vera = int(cv2.countNonZero(maschera))
        if area_vera < area_min or area_vera > area_max:
            continue

        # contorno esterno → poligono semplificato
        contorni, _ = cv2.findContours(maschera, cv2.RETR_EXTERNAL,
                                       cv2.CHAIN_APPROX_SIMPLE)
        if not contorni:
            continue
        contorno = max(contorni, key=cv2.contourArea)
        eps = 0.01 * cv2.arcLength(contorno, True)
        approssimato = cv2.approxPolyDP(contorno, eps, True)
        if len(approssimato) > 40:
            approssimato = cv2.approxPolyDP(contorno, 2.5 * eps, True)
        if len(approssimato) < 3:
            continue
        poligono = [[float(p[0][0] + x0), float(p[0][1] + y0)]
                    for p in approssimato]
        trovate.append((area_vera, poligono))
    return trovate


def rileva_stanze(immagine, mpp=None, max_stanze=30):
    """Propone i poligoni delle stanze trovate sull'immagine.

    immagine: PIL (RGB o convertibile); mpp: metri per pixel, None se la
    scala non è impostata. Restituisce una lista di poligoni [[x, y], ...]
    ordinati per area decrescente, al massimo max_stanze.
    """
    inchiostro = _binarizza(immagine)
    alt, larg = inchiostro.shape

    if mpp:
        porte = [int(round(1.0 / mpp))]
        area_min = 2.0 / (mpp * mpp)           # niente stanze sotto i 2 m²
        soglia_testo = int(round(0.45 / mpp))  # scritte ≈ sotto il mezzo metro
    else:
        porte = [larg // 40, larg // 24, larg // 14]
        area_min = larg * alt * 0.002
        soglia_testo = larg // 45
    porte = sorted({int(max(5, min(p, larg // 8))) for p in porte})
    area_max = larg * alt * 0.45               # via lo "sfondo" gigante

    soglia_testo = max(6, min(soglia_testo, larg // 10))
    inchiostro = _rimuovi_scritte(inchiostro, soglia_testo)
    spazio_libero = cv2.bitwise_not(inchiostro)

    migliori = []
    for porta_px in porte:
        trovate = _stanze_con_porta(inchiostro, spazio_libero, porta_px,
                                    area_min, area_max)
        if len(trovate) > len(migliori):
            migliori = trovate

    migliori.sort(key=lambda t: t[0], reverse=True)
    return [poligono for _, poligono in migliori[:max_stanze]]
