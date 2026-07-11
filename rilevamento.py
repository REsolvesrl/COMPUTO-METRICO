"""Rilevamento automatico (beta) delle stanze da una planimetria.

Visione classica con OpenCV, niente AI. Il metodo:
1. si binarizza il disegno (muri e linee = "inchiostro");
2. si CANCELLANO le scritte (testi, quote, simboli): componenti d'inchiostro
   piccole o dal riquadro minuto — sulle foto le lettere si fondono in
   "parole", per questo si valuta sia l'ingombro sia l'area del riquadro;
3. si DILATANO i muri di mezzo vano-porta, così i varchi delle porte si
   sigillano e ogni stanza diventa una regione bianca isolata;
4. le regioni che non toccano il bordo (quella è l'esterno) sono le stanze,
   ma rimpicciolite dalla dilatazione: si fanno RICRESCERE TUTTE INSIEME,
   un pixel per passo, dentro lo spazio libero (crescita "in competizione":
   ogni pixel va a una sola stanza, i confini si incontrano a metà varco —
   niente sovrapposizioni);
5. il contorno di ogni stanza, semplificato, è il poligono proposto. Le
   proposte che ricadono su zone già disegnate vengono scartate.

Se la scala è impostata si provano varchi-porta di ~0,8 e ~1,15 m; senza
scala si provano più ampiezze relative. Vince il tentativo che trova più
stanze. Le proposte vanno sempre rifinite dall'utente.

Funzioni pure e testabili: immagine PIL in ingresso, poligoni in uscita
(coordinate in pixel dell'immagine, come le zone disegnate a mano).
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


def _rimuovi_scritte(inchiostro, soglia_dim, soglia_area):
    """Cancella testi, quote e simboli dall'inchiostro.

    Via ogni componente connessa con ingombro massimo sotto soglia_dim
    (lettere, simboli) O con riquadro sotto soglia_area (parole intere,
    strette e lunghe). I muri sopravvivono perché formano strutture grandi
    e collegate fra loro.
    """
    n_comp, etichette, stats, _ = cv2.connectedComponentsWithStats(
        inchiostro, 8)
    pulito = inchiostro.copy()
    for i in range(1, n_comp):
        x, y, bw, bh, _area = stats[i]
        if max(bw, bh) < soglia_dim or bw * bh < soglia_area:
            ritaglio = pulito[y:y + bh, x:x + bw]
            ritaglio[etichette[y:y + bh, x:x + bw] == i] = 0
    return pulito


def _stanze_con_porta(inchiostro, spazio_libero, porta_px,
                      area_min, area_max, occupato):
    """Stanze [(area, poligono), ...] sigillando varchi larghi ≤ porta_px."""
    alt, larg = inchiostro.shape
    raggio = porta_px // 2 + 2

    kern = cv2.getStructuringElement(cv2.MORPH_ELLIPSE,
                                     (2 * raggio + 1, 2 * raggio + 1))
    muri_dilatati = cv2.dilate(inchiostro, kern)
    libero_ristretto = cv2.bitwise_not(muri_dilatati)
    n_comp, etichette, stats, _ = cv2.connectedComponentsWithStats(
        libero_ristretto, 8)

    validi = []
    for i in range(1, n_comp):
        x, y, bw, bh, area = stats[i]
        if x <= 1 or y <= 1 or x + bw >= larg - 1 or y + bh >= alt - 1:
            continue                            # tocca il bordo: è l'esterno
        if area < max(64, area_min * 0.1):
            continue                            # briciola: inutile farla crescere
        validi.append(i)
    if not validi:
        return []

    # crescita in competizione: tutte le stanze ricrescono insieme, un pixel
    # per passo, solo dentro lo spazio libero (e fuori dalle zone esistenti);
    # ogni pixel conquistato appartiene a UNA sola stanza.
    semi = np.where(np.isin(etichette, validi), etichette, 0)
    crescita = semi.astype(np.float32)
    conquistabile = spazio_libero > 0
    if occupato is not None:
        conquistabile &= occupato == 0
    kern3 = np.ones((3, 3), np.uint8)
    for _ in range(raggio + 2):
        dilatata = cv2.dilate(crescita, kern3)
        crescita = np.where((crescita == 0) & conquistabile,
                            dilatata, crescita)
    finali = crescita.astype(np.int32)

    trovate = []
    for i in validi:
        maschera = np.uint8(finali == i) * 255
        area_vera = int(cv2.countNonZero(maschera))
        if area_vera < area_min or area_vera > area_max:
            continue
        if occupato is not None:
            sovrapposta = int(cv2.countNonZero(
                cv2.bitwise_and(maschera, occupato)))
            if sovrapposta > 0.25 * area_vera:
                continue                        # già coperta da una zona
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
        poligono = [[float(p[0][0]), float(p[0][1])] for p in approssimato]
        trovate.append((area_vera, poligono))
    return trovate


def rileva_stanze(immagine, mpp=None, max_stanze=30, zone_esistenti=None):
    """Propone i poligoni delle stanze trovate sull'immagine.

    immagine: PIL (RGB o convertibile); mpp: metri per pixel (None se la
    scala non è impostata); zone_esistenti: elenco di poligoni già disegnati
    ([[x, y], ...]) da rispettare — le proposte non li sovrappongono.
    Restituisce poligoni [[x, y], ...] ordinati per area decrescente.
    """
    inchiostro = _binarizza(immagine)
    alt, larg = inchiostro.shape

    if mpp:
        porte = [int(round(0.8 / mpp)), int(round(1.15 / mpp))]
        area_min = 1.0 / (mpp * mpp)            # niente stanze sotto 1 m²
        soglia_dim = int(round(0.9 / mpp))      # lettere e simboli
        soglia_area = 0.8 / (mpp * mpp)         # parole (riquadri minuti)
    else:
        porte = [larg // 40, larg // 24, larg // 14]
        area_min = larg * alt * 0.002
        soglia_dim = larg // 35
        soglia_area = 2.0 * soglia_dim * soglia_dim
    porte = sorted({int(max(5, min(p, larg // 8))) for p in porte})
    area_max = larg * alt * 0.55                # via lo "sfondo" gigante
    soglia_dim = max(6, min(soglia_dim, larg // 8))

    inchiostro = _rimuovi_scritte(inchiostro, soglia_dim, soglia_area)
    spazio_libero = cv2.bitwise_not(inchiostro)

    occupato = None
    if zone_esistenti:
        occupato = np.zeros((alt, larg), np.uint8)
        for punti in zone_esistenti:
            if len(punti) >= 3:
                pts = np.array([[int(round(x)), int(round(y))]
                                for x, y in punti], np.int32)
                cv2.fillPoly(occupato, [pts], 255)

    migliori = []
    for porta_px in porte:
        trovate = _stanze_con_porta(inchiostro, spazio_libero, porta_px,
                                    area_min, area_max, occupato)
        if len(trovate) > len(migliori):
            migliori = trovate

    migliori.sort(key=lambda t: t[0], reverse=True)
    return [poligono for _, poligono in migliori[:max_stanze]]
