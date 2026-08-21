"""La fascia dei bagni arriva davvero nella 2.11.

I rivestimenti sono l'unica quantità del disegno che per anni è esistita
solo come DETRAZIONE: la fascia piastrellata si scontava dalla
tinteggiatura e poi spariva, senza diventare mai una riga da pagare a
qualcuno. Ora alimenta la 2.11, e questo test fa il giro intero — dal
poligono disegnato alla quantità scritta nella voce — perché la catena
è lunga e ogni anello può rompersi in silenzio:

    zona spuntata «Rivestito» → riepilogo_locali → quantita_finiture
    → grandezze["rivestimenti"] → VOCI_DA_SUPERFICI → q_2.11

Il bagno del test è un quadrato di 3 × 3 m: perimetro 12 m, che per una
fascia da 1,20 m fa 14,40 m² lordi, meno 0,96 m² di vano porta.
"""
import base64
import io
from pathlib import Path

import pytest
from PIL import Image
from streamlit.testing.v1 import AppTest

SORGENTE = Path(__file__).resolve().parent.parent / "streamlit_app.py"

# 3 × 3 m con mpp 0,01: 300 px di lato. Area 9 m², perimetro 12 m.
LATO_PX = 300.0
MPP = 0.01


def _immagine():
    """Una planimetria finta: serve solo che l'immagine si apra."""
    buffer = io.BytesIO()
    Image.new("RGB", (600, 600), "white").save(buffer, format="PNG")
    return base64.b64encode(buffer.getvalue()).decode()


def _progetto(rivestito, riv_porte=1, riv_finestre=0):
    quadrato = [[0.0, 0.0], [LATO_PX, 0.0], [LATO_PX, LATO_PX],
                [0.0, LATO_PX]]
    return {
        "progetto": {"nome": "Bagno", "committente": "", "oggetto": "",
                     "data": "2026-08-21", "aliquota_iva": 10.0},
        "voci": [], "business_plan": {},
        "listino_stato": {},
        "voci_scelte": ["2.11"],
        "altezza_locali": 3.0,
        "finiture": {"porta_larg": 0.80, "porta_alt": 2.10, "porta_n": 0,
                     "porta_n_est": 0, "riv_alt": 1.20,
                     "riv_porte_n": riv_porte, "riv_finestre_n": riv_finestre,
                     "fin_n": 0, "fin_larg": 0.60, "fin_alt": 0.60,
                     "pf_n": 0, "pf_larg": 1.20, "pf_alt": 2.30,
                     "apert_dem_n": 0, "apert_cos_n": 0,
                     "apert_larg": 0.80, "apert_alt": 2.10},
        "piante": [{
            "nome": "Piano", "mpp": MPP, "immagine": _immagine(),
            "pareti": [],
            "zone": [{"id": 1, "categoria": "Superficie interna",
                      "nome": "Bagno", "punti": quadrato,
                      "pavimento": True, "battiscopa": False,
                      "pittura": True, "rivestito": rivestito}],
        }],
    }


def _apri(progetto):
    at = AppTest.from_file(str(SORGENTE), default_timeout=300)
    at.run()
    at.session_state["da_caricare"] = progetto
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


@pytest.fixture(scope="module")
def bagno_rivestito():
    return _apri(_progetto(rivestito=True))


def test_la_2_11_riceve_la_fascia_del_bagno(bagno_rivestito):
    """14,40 m² lordi (12 × 1,20) − 0,96 di vano porta = 13,44."""
    assert bagno_rivestito.session_state["q_2.11"] == 13.44


def test_il_vano_porta_si_toglie_solo_per_l_altezza_della_fascia():
    """Con la porta il conto scende di 0,96, non di 1,68."""
    senza = _apri(_progetto(rivestito=True, riv_porte=0))
    assert senza.session_state["q_2.11"] == 14.4


def test_anche_la_finestra_del_bagno_si_toglie():
    """Finestra 0,60 × 0,60, tutta dentro la fascia: −0,36."""
    at = _apri(_progetto(rivestito=True, riv_finestre=1))
    assert at.session_state["q_2.11"] == 13.08     # 13,44 − 0,36


def test_senza_locali_rivestiti_la_2_11_resta_a_zero():
    """E non deve diventare negativa per via del vano porta."""
    at = _apri(_progetto(rivestito=False))
    assert at.session_state["q_2.11"] == 0.0


def test_la_fascia_si_toglie_ancora_dalla_tinteggiatura(bagno_rivestito):
    """La stessa superficie non si tinteggia: pareti 12 × 3 = 36 m²
    lorde, meno 14,40 di fascia = 21,60, più 9 m² di soffitto."""
    assert bagno_rivestito.session_state["q_2.18"] == 30.6


def test_il_bagno_rivestito_non_prende_battiscopa(bagno_rivestito):
    """Un locale piastrellato non ha zoccolino: la 2.14 resta fuori."""
    assert bagno_rivestito.session_state["q_2.14"] == 0.0
