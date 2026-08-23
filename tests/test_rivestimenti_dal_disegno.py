"""La fascia dei bagni arriva davvero nella 2.11.

I rivestimenti sono l'unica quantità del disegno che per anni è esistita
solo come DETRAZIONE: la fascia piastrellata si scontava dalla
tinteggiatura e poi spariva, senza diventare mai una riga da pagare a
qualcuno. Ora alimenta la 2.11, e questo test fa il giro intero — dal
poligono disegnato alla quantità scritta nella voce — perché la catena
è lunga e ogni anello può rompersi in silenzio:

    zona spuntata «Rivestito» → riepilogo_locali → quantita_finiture
    → grandezze["rivestimenti"] → VOCI_DA_SUPERFICI → q_3.12

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
        "versione_codici": 2,
        "progetto": {"nome": "Bagno", "committente": "", "oggetto": "",
                     "data": "2026-08-21", "aliquota_iva": 10.0},
        "voci": [], "business_plan": {},
        "listino_stato": {},
        "voci_scelte": ["3.12"],
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


def _con_balcone():
    """Il bagno di sempre, più un balcone di 2 × 2 m (4 m²)."""
    progetto = _progetto(rivestito=False)
    progetto["voci_scelte"] = ["2.1", "3.11"]
    progetto["piante"][0]["zone"].append({
        "id": 2, "categoria": "Balcone", "nome": "Balcone",
        "punti": [[0.0, 0.0], [200.0, 0.0], [200.0, 200.0], [0.0, 200.0]],
        "pavimento": True, "battiscopa": False, "pittura": False,
        "rivestito": False})
    return progetto


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
    assert bagno_rivestito.session_state["q_3.12"] == 13.44


def test_il_vano_porta_si_toglie_solo_per_l_altezza_della_fascia():
    """Con la porta il conto scende di 0,96, non di 1,68."""
    senza = _apri(_progetto(rivestito=True, riv_porte=0))
    assert senza.session_state["q_3.12"] == 14.4


def test_anche_la_finestra_del_bagno_si_toglie():
    """Finestra 0,60 × 0,60, tutta dentro la fascia: −0,36."""
    at = _apri(_progetto(rivestito=True, riv_finestre=1))
    assert at.session_state["q_3.12"] == 13.08     # 13,44 − 0,36


def test_senza_locali_rivestiti_la_2_11_resta_a_zero():
    """E non deve diventare negativa per via del vano porta."""
    at = _apri(_progetto(rivestito=False))
    assert at.session_state["q_3.12"] == 0.0


def test_la_fascia_si_toglie_ancora_dalla_tinteggiatura(bagno_rivestito):
    """La stessa superficie non si tinteggia: pareti 12 × 3 = 36 m²
    lorde, meno 14,40 di fascia = 21,60, più 9 m² di soffitto."""
    assert bagno_rivestito.session_state["q_3.19"] == 30.6


def test_il_bagno_rivestito_non_prende_battiscopa(bagno_rivestito):
    """Un locale piastrellato non ha zoccolino: la 2.14 resta fuori."""
    assert bagno_rivestito.session_state["q_3.15"] == 0.0


# ------------------- la tabella dei locali segue il disegno, sempre
# La tabella si ricostruisce solo quando cambia la sua «impronta», per non
# perdere il primo clic sulle spunte. Finché l'impronta era il solo elenco
# degli id, ogni modifica che non fosse aggiungere o togliere una zona la
# lasciava indietro — e i metri quadri fermi lì dentro sono quelli che
# finiscono nel computo.

def _con_una_zona():
    at = AppTest.from_file(str(SORGENTE), default_timeout=300)
    at.run()
    at.session_state["da_caricare"] = _progetto(rivestito=True)
    at.run()
    return at


def test_rinominare_un_locale_si_vede_subito_in_tabella():
    at = _con_una_zona()
    at.session_state["piante"][0]["zone"][0]["nome"] = "bagno trilo"
    at.run()
    assert list(at.session_state["loc_base_df"]["Locale"]) == ["bagno trilo"]


def test_allargare_una_stanza_aggiorna_i_mq_del_computo():
    """Il difetto grosso: la stanza cresceva e il computo restava fermo."""
    at = _con_una_zona()
    assert at.session_state["q_3.10"] == 9.0
    # da 300 a 500 px di lato: 9 m² diventano 25
    at.session_state["piante"][0]["zone"][0]["punti"] = [
        [0.0, 0.0], [500.0, 0.0], [500.0, 500.0], [0.0, 500.0]]
    at.run()
    assert list(at.session_state["loc_base_df"]["Superficie (m²)"]) == [25.0]
    assert at.session_state["q_3.10"] == 25.0
    # e la fascia segue il perimetro nuovo: 20 m × 1,20 − 0,96 = 23,04
    assert at.session_state["q_3.12"] == 23.04


def test_una_zona_nuova_compare_in_tabella():
    at = _con_una_zona()
    at.session_state["piante"][0]["zone"].append({
        "id": 2, "categoria": "Superficie interna", "nome": "bagno trilo",
        "punti": [[0.0, 0.0], [200.0, 0.0], [200.0, 200.0], [0.0, 200.0]]})
    at.run()
    assert list(at.session_state["loc_base_df"]["Locale"]) == ["Bagno",
                                                              "bagno trilo"]
    assert at.session_state["q_3.10"] == 13.0        # 9 + 4


def test_le_spunte_non_rifanno_la_tabella():
    """Se l'impronta cambiasse anche per le spunte, il primo clic su una
    casella andrebbe perso: bisognava cliccare due volte."""
    at = _con_una_zona()
    prima = at.session_state["loc_base_chiave"]
    at.session_state["piante"][0]["zone"][0]["pavimento"] = False
    at.run()
    assert at.session_state["loc_base_chiave"] == prima


# ------------------- la demolizione dei pavimenti è quella DENTRO casa

def test_la_demolizione_pavimenti_non_prende_i_balconi():
    """1.01 sono le stanze; il balcone è un'altra lavorazione (2.24)."""
    at = _apri(_con_balcone())
    assert at.session_state["q_2.1"] == 9.0     # solo il bagno 3 × 3
    assert at.session_state["q_3.11"] == 4.0     # il balcone, per conto suo


def test_la_1_01_arriva_da_sola_senza_spuntare_niente():
    """È accesa di default nel ponte con la planimetria: appena c'è un
    pavimento misurato, la quantità è già lì."""
    at = _apri(_progetto(rivestito=False))
    assert at.session_state["q_2.1"] == 9.0


# ------------------- la quantita' scritta a mano vince sul disegno

def _con_pavimento():
    """Il bagno di sempre, con la 2.10 nel computo: 9 m² dal disegno."""
    progetto = _progetto(rivestito=False)
    progetto["voci_scelte"] = ["3.10"]
    return progetto


def test_il_disegno_alimenta_la_voce_finche_nessuno_la_tocca():
    at = _apri(_con_pavimento())
    assert at.session_state["q_3.10"] == 9.0


def test_la_quantita_scritta_a_mano_non_viene_riscritta():
    """Il difetto: si correggeva un metro quadro e al giro dopo tornava
    quello misurato, senza che niente lo spiegasse."""
    at = _apri(_con_pavimento())
    at.session_state["cat_aperte"] = {"Ricostruzioni e ripristini"}
    at.run()
    at.text_input(key="q_3.10_txt").set_value("12").run()
    assert at.session_state["q_3.10"] == 12.0
    assert "3.10" in at.session_state["voci_a_mano"]
    at.run()                      # un altro giro: il disegno non la tocca
    at.run()
    assert at.session_state["q_3.10"] == 12.0


def test_riagganciare_rida_il_comando_al_disegno():
    at = _apri(_con_pavimento())
    at.session_state["cat_aperte"] = {"Ricostruzioni e ripristini"}
    at.run()
    at.text_input(key="q_3.10_txt").set_value("12").run()
    at.button(key="riaggancia_tutte").click().run()
    assert at.session_state["voci_a_mano"] == []
    at.run()
    assert at.session_state["q_3.10"] == 9.0


def test_la_scelta_a_mano_si_salva_col_progetto():
    at = _apri({**_con_pavimento(), "voci_a_mano": ["3.10"],
                "listino_stato": {"3.10": {"q": 12.0, "p": 55.0}}})
    assert at.session_state["voci_a_mano"] == ["3.10"]
    at.run()
    assert at.session_state["q_3.10"] == 12.0
