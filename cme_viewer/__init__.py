"""Componente Streamlit «cme_viewer».

Visualizzatore di planimetrie in stile CAD leggero:
- **zoom con la rotellina** (verso il cursore) e **spostamento** col trascinamento;
- **barra strumenti** flottante sul disegno: Sposta, Area, Modifica, Scala, Parete,
  zoom +/− e adatta;
- disegno di **zone** (poligoni) colorate con etichetta, **modifica** (vertici,
  spostamento, eliminazione), **vettore di scala** e **misura pareti**.

Tutte le coordinate scambiate col server sono nel sistema dell'immagine
originale ("canoniche"): lo zoom è solo visivo e non altera mai la scala.

Lo strumento 📏 Misura è solo locale (browser): le misure al volo non
generano eventi e spariscono con Esc o cambiando strumento. Le etichette di
zone e pareti si trascinano (in Sposta e Modifica) per non coprire il disegno.

Il componente restituisce eventi come dizionari con un campo `seq` progressivo
(per scartare i duplicati dovuti ai rerun) e un campo `tipo`:
- {"tipo": "zona_chiusa", "punti": [[x, y], ...]}
- {"tipo": "zona_modificata", "id": n, "punti": [[x, y], ...]}
- {"tipo": "zona_eliminata", "id": n}
- {"tipo": "selezione", "zona": n | None, "parete": n | None}
- {"tipo": "etichetta_spostata", "elemento": "zona" | "parete",
   "id": n, "pos": [x, y]}
- {"tipo": "scala", "p1": [x, y], "p2": [x, y]}
- {"tipo": "parete", "p1": [x, y], "p2": [x, y]}
- {"tipo": "parete_eliminata", "id": n}
"""

import base64
from io import BytesIO
from pathlib import Path

import streamlit.components.v1 as components

_frontend = (Path(__file__).parent / "frontend").resolve()
_component = components.declare_component("cme_viewer", path=str(_frontend))


def pil_a_src(image, qualita=85):
    """Codifica un'immagine PIL come data-URL JPEG (da fare una volta sola)."""
    buffer = BytesIO()
    image.save(buffer, format="JPEG", quality=qualita)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode()


def image_viewer(src, zone=(), pareti=(), scala_temp=None,
                 colore_attivo="#E57373", mpp=0.0, font_px=14, key=None):
    """Mostra la planimetria e restituisce l'ultimo evento (o None).

    src: data-URL dell'immagine (usa pil_a_src una sola volta per pianta).
    zone: [{"id", "punti", "colore", "etichetta"}] — poligoni già disegnati.
    pareti: [{"id", "p1", "p2", "etichetta"}] — pareti misurate.
    scala_temp: {"p1", "p2"} — vettore di scala in attesa della misura reale.
    colore_attivo: colore della zona in corso di disegno (categoria scelta).
    mpp: metri per pixel (0 = scala non impostata) — per le misure "live".
    font_px: dimensione del carattere delle etichette.
    """
    return _component(src=src, zone=list(zone), pareti=list(pareti),
                      scala_temp=scala_temp, colore_attivo=colore_attivo,
                      mpp=float(mpp or 0.0), font_px=int(font_px),
                      key=key, default=None)
