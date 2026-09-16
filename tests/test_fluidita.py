"""La pagina che risponde subito.

Ogni clic che cambia qualcosa ricalcola l'app e rimanda al browser quello
che c'è a video. Qui si controlla che non viaggi niente di pesante che non
serve: la tela della planimetria con la scheda chiusa, un giro doppio per
aprire una categoria, un file Excel costruito prima che qualcuno lo chieda,
chiavi vuote che rallentano ogni campo della pagina.
"""
import io
import sys
from pathlib import Path

import openpyxl
import pandas as pd
from streamlit.testing.v1 import AppTest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_rivestimenti_dal_disegno import _con_balcone, _progetto  # noqa: E402

import streamlit_app  # noqa: E402

SORGENTE = Path(__file__).resolve().parent.parent / "streamlit_app.py"
PLANIMETRIA = "📐 Misura da planimetria"


def _apri(progetto):
    at = AppTest.from_file(str(SORGENTE), default_timeout=300)
    at.run()
    at.session_state["da_caricare"] = progetto
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _tele(at):
    return len(at.get("component_instance"))


# ------------------------------------------------- la tela della planimetria

def test_la_tela_non_viaggia_se_la_planimetria_e_chiusa():
    """Porta con sé l'immagine intera: su ENI 782 KB a ogni clic."""
    assert _tele(_apri(_progetto(rivestito=True))) == 0


def test_la_tela_c_e_con_la_planimetria_aperta():
    at = _apri(_progetto(rivestito=True))
    at.session_state["scheda_attiva"] = PLANIMETRIA
    at.run()
    assert _tele(at) == 1
    assert not at.exception, [e.value for e in at.exception]


def test_la_tela_torna_dopo_essere_passati_dal_computo():
    at = _apri(_progetto(rivestito=True))
    for scheda, tele in ((PLANIMETRIA, 1), ("📝 Computo metrico", 0),
                         (PLANIMETRIA, 1)):
        at.session_state["scheda_attiva"] = scheda
        at.run()
        assert _tele(at) == tele, scheda
    assert not at.exception, [e.value for e in at.exception]


def test_senza_tela_il_disegno_alimenta_lo_stesso_il_computo():
    """La tela è solo la vista: i conti dal disegno si fanno lo stesso."""
    at = _apri(_progetto(rivestito=True))
    assert _tele(at) == 0
    assert at.session_state["q_3.12"] == 13.44


# ------------------------------------------------- le categorie del computo

def test_la_categoria_si_apre_e_si_chiude_col_suo_bottone():
    at = _apri({"voci_scelte": ["2.2"], "listino_stato": {"2.2": {"q": 5}}})

    def demolizioni():
        return next(b for b in at.button
                    if (b.key or "").startswith("apri_")
                    and "Demolizioni" in b.label)

    demolizioni().click().run()
    assert "Demolizioni" in at.session_state["cat_aperte"]
    assert "q_2.2_txt" in [t.key for t in at.text_input]
    demolizioni().click().run()
    assert "Demolizioni" not in at.session_state["cat_aperte"]
    assert "q_2.2_txt" not in [t.key for t in at.text_input]


def test_il_pool_si_apre_col_suo_bottone():
    at = _apri({})
    bottone = next(b for b in at.button
                   if (b.key or "").startswith("pool_")
                   and "Demolizioni" in b.label)
    bottone.click().run()
    assert "Demolizioni" in at.session_state["pool_aperte"]
    assert "prendi_2.2" in [b.key for b in at.button]


# ------------------------------------------------- chiavi vuote

def test_i_testi_non_riscritti_non_diventano_chiavi_vuote():
    at = _apri({"voci_scelte": ["3.10"],
                "testi_voci": {"3.10": {"d": "Gres 60x60", "u": None}}})
    assert at.session_state["d_3.10"] == "Gres 60x60"
    assert "u_3.10" not in at.session_state
    assert "d_2.2" not in at.session_state


def test_svuotare_una_descrizione_torna_al_listino():
    at = _apri({"voci_scelte": ["3.10"],
                "testi_voci": {"3.10": {"d": "Gres 60x60", "u": None}}})
    at.session_state["cat_aperte"] = {"Ricostruzioni e ripristini"}
    at.run()
    at.text_area(key="d_3.10_w").set_value("").run()
    # niente chiave vuota: chi la legge ricade sulla voce del listino
    assert "d_3.10" not in at.session_state
    assert not at.exception, [e.value for e in at.exception]


# ------------------------------------------------- l'Excel al clic

def test_l_excel_si_costruisce_con_tutti_i_fogli():
    """Ora si compone al clic, fuori dal giro della pagina: materiali e
    superfici li ricava da sé dai dati che riceve."""
    # col balcone c'è una superficie commerciale, e quindi il suo foglio
    pianta = streamlit_app.pianta_da_json(_con_balcone()["piante"][0])
    df = pd.DataFrame([{"categoria": "Demolizioni", "codice": "2.2",
                        "descrizione": "Demolizione murature", "um": "m²",
                        "quantita": 10.0, "prezzo": 100.0,
                        "importo": 1000.0}])
    materiali = pd.DataFrame([{"capitolo": "Bagno",
                               "descrizione": "Piatto doccia"}])
    dati = streamlit_app.excel_computo_bytes(
        df, pd.DataFrame({"Categoria": ["x"], "Importo": [1.0]}),
        pd.DataFrame({"Campo": ["Nome"], "Valore": ["Prova"]}),
        materiali, [pianta], {})
    fogli = openpyxl.load_workbook(io.BytesIO(dati)).sheetnames
    assert fogli == ["Computo", "Riepilogo", "Materiali", "Superfici",
                     "Dati progetto"]
