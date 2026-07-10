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
