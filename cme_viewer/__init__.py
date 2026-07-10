"""Componente Streamlit «cme_viewer».

Mostra un'immagine con **zoom a rotellina** (verso il cursore), **spostamento**
con il trascinamento e **click** che restituisce le coordinate nel sistema
dell'immagine originale. Lo zoom è solo visivo (lato browser): il server riceve
sempre coordinate "canoniche", quindi la calibrazione resta valida a ogni zoom.

Uso:
    from cme_viewer import image_viewer
    punto = image_viewer(immagine_pil, reset_token=n, key="...")
    # punto == {"x": ..., "y": ..., "unix_time": ...} oppure None
"""

import base64
from io import BytesIO
from pathlib import Path

import streamlit.components.v1 as components

_frontend = (Path(__file__).parent / "frontend").resolve()
_component = components.declare_component("cme_viewer", path=str(_frontend))


def image_viewer(image, reset_token=0, cursor="crosshair", key=None):
    """Restituisce il punto cliccato (coord. in pixel dell'immagine) o None.

    image: immagine PIL da mostrare (già con eventuali disegni sopra).
    reset_token: cambiando questo valore la vista torna adattata all'immagine
        (usato al caricamento di una nuova planimetria o col bottone «reimposta»).
    """
    buffer = BytesIO()
    image.save(buffer, format="PNG")
    src = "data:image/png;base64," + base64.b64encode(buffer.getvalue()).decode()
    return _component(src=src, reset_token=reset_token, cursor=cursor,
                      key=key, default=None)
