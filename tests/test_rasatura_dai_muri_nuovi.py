"""La rasatura non e' la tinteggiatura: nasce dai muri nuovi.

Per anni la 3.18 prendeva la stessa identica quantita' della 3.19 —
`tinteggiatura`, cioe' pareti + soffitti di tutto l'appartamento. Acceso
quel flag si rasava tutto: i soffitti, che non si rasano, e le pareti in
cartongesso, che si stuccano ai giunti e si tinteggiano.

La quantita' proposta e' ora il minimo che serve di sicuro: le DUE facce
dei muri nuovi in forati, che si tirano su grezzi. La voce del muro (3.1)
conta la superficie una volta sola — e' il muro — mentre le facce da
rasare sono il doppio. Dove si rasa dell'altro il numero si scrive a mano,
e da quel momento il disegno non ci mette piu' bocca.

Il giro intero, perche' la catena e' lunga e ogni anello puo' rompersi in
silenzio:

    parete «costruire» → riepilogo_pareti → grandezze["rasatura"]
    → VOCI_DA_SUPERFICI → q_3.18
"""
import base64
import io
from pathlib import Path

import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

SORGENTE = Path(__file__).resolve().parent.parent / "streamlit_app.py"

MPP = 0.01          # 100 px = 1 m
ALTEZZA = 3.0


def _immagine():
    buffer = io.BytesIO()
    Image.new("RGB", (600, 600), "white").save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def _progetto(pareti, voci_scelte=("3.18",), aperture_cos=0):
    return {
        "progetto": {"nome": "Muri", "committente": "", "oggetto": "",
                     "data": "2026-08-31", "aliquota_iva": 10.0},
        "voci": [], "business_plan": {}, "listino_stato": {},
        "voci_scelte": list(voci_scelte),
        "altezza_locali": ALTEZZA,
        "finiture": {"porta_larg": 0.80, "porta_alt": 2.10, "porta_n": 0,
                     "porta_n_est": 0, "riv_alt": 1.20, "riv_porte_n": 0,
                     "riv_finestre_n": 0, "fin_n": 0, "fin_larg": 0.60,
                     "fin_alt": 0.60, "pf_n": 0, "pf_larg": 1.20,
                     "pf_alt": 2.30, "apert_dem_n": 0,
                     "apert_cos_n": aperture_cos, "apert_car_n": 0,
                     "apert_larg": 0.80, "apert_alt": 2.10},
        "piante": [{"nome": "Piano", "mpp": MPP, "immagine": _immagine(),
                    "zone": [], "pareti": list(pareti)}],
    }


def _apri(progetto):
    """Apre il progetto e accende la spunta della 3.18.

    La rasatura nasce spenta di proposito — non e' detto che si rasi — e
    finche' non la si spunta nessuna quantita' arriva nella voce. Qui la
    accendiamo, perche' e' proprio la quantita' che vogliamo guardare.
    """
    at = AppTest.from_file(str(SORGENTE), default_timeout=300)
    at.run()
    at.session_state["da_caricare"] = progetto
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    at.session_state["supvoce_3.18"] = True
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


MURO_5M = {"id": 1, "tipo": "costruire", "p1": [0, 100], "p2": [500, 100]}
CARTONGESSO_4M = {"id": 2, "tipo": "cartongesso",
                  "p1": [0, 200], "p2": [400, 200]}


def test_la_rasatura_sono_le_due_facce_del_muro_nuovo():
    """Muro di 5 m per 3,00 di altezza = 15 m2; da rasare 30, non 15."""
    at = _apri(_progetto([MURO_5M]))
    assert at.session_state["q_3.1"] == 15.0        # il muro, una volta
    assert at.session_state["q_3.18"] == 30.0       # le sue due facce


def test_il_cartongesso_resta_fuori_dalla_rasatura():
    """Si stucca ai giunti e si tinteggia: rasato non va."""
    at = _apri(_progetto([MURO_5M, CARTONGESSO_4M]))
    assert at.session_state["q_3.8"] == 12.0        # 4 x 3, lastrato
    assert at.session_state["q_3.18"] == 30.0       # solo i forati


def test_senza_muri_nuovi_la_rasatura_non_arriva():
    """Niente muri da tirare su, niente quantita' minima da proporre: la
    3.18 resta a zero e la si scrive a mano dove serve davvero."""
    at = _apri(_progetto([{"id": 3, "tipo": "demolire",
                           "p1": [0, 0], "p2": [300, 0]}]))
    assert at.session_state["q_2.2"] == 9.0        # il muro buttato giu' c'e'
    assert at.session_state["q_3.18"] == 0.0       # da rasare, niente


def test_dove_c_e_un_vano_non_c_e_muro_da_rasare():
    """L'apertura si toglie prima, e le facce sono il doppio del netto:
    15 m2 di muro − 1,68 di vano = 13,32, per due = 26,64."""
    at = _apri(_progetto([MURO_5M], aperture_cos=1))
    assert at.session_state["q_3.1"] == 13.32
    assert at.session_state["q_3.18"] == 26.64
