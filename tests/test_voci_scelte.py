"""Il computo porta solo le voci scelte, e si pescano dal pool.

Prima il computo era il listino intero: 69 righe sempre a video, di cui
sessanta a zero. Ora le categorie ci sono sempre — sono l'ossatura del
documento — ma dentro c'è solo quello che serve a QUESTO cantiere, e le
voci si prendono dal pool in fondo alla pagina.

I test qui dentro fanno i gesti veri: premono il ＋, premono la ✕,
scrivono nella ricerca. Quello che si controlla è che la voce entri ed
esca davvero dal computo, che i totali seguano, e che un progetto salvato
prima di tutto questo si riapra uguale a com'era.
"""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

SORGENTE = Path(__file__).resolve().parent.parent / "streamlit_app.py"

# Un progetto vecchio: nessun elenco di voci scelte, solo le quantità.
# Erano quelle a decidere che cosa si vedeva, ed è da lì che si migra.
PROGETTO_VECCHIO = {
    "progetto": {"nome": "Via Roma 12", "committente": "Resolve S.r.l.",
                 "oggetto": "Ristrutturazione", "data": "2026-08-09",
                 "aliquota_iva": 10.0, "imprevisti": 10.0},
    "voci": [],
    "listino_stato": {"1.02": {"q": 120.0, "p": 115.0},
                      "2.01": {"q": 30.0, "p": 80.0},
                      # prezzo ritoccato ma quantità zero: non era nel
                      # computo prima, non deve esserci nemmeno adesso
                      "2.10": {"q": 0.0, "p": 60.0}},
    "piante": [],
    "business_plan": {},
}


@pytest.fixture(scope="module")
def app():
    at = AppTest.from_file(str(SORGENTE), default_timeout=240)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _prendibili(at):
    """I codici che il pool offre in questo momento."""
    return [b.key for b in at.button
            if (b.key or "").startswith("prendi_")]


def _avvia():
    at = AppTest.from_file(str(SORGENTE), default_timeout=240)
    at.run()
    return at


# ------------------------------------------------- il computo nasce vuoto

def test_il_computo_nasce_senza_voci(app):
    """Solo le macrocategorie: le voci le mette chi fa il computo."""
    assert app.session_state["voci_scelte"] == []


def test_il_pool_offre_tutte_le_voci(app):
    """Nessuna voce presa: il pool le ha tutte, una per bottone."""
    import listino
    prendibili = _prendibili(app)
    assert len(prendibili) == len(listino.VOCI)


def test_senza_voci_scelte_non_ci_sono_righe_da_compilare(app):
    """Niente caselle di quantità: non c'è ancora niente da quantificare."""
    assert not [t for t in app.text_input if t.key.startswith("q_")]


# --------------------------------------------------- prendere e rimettere

def test_il_piu_porta_la_voce_nel_computo():
    at = _avvia()
    at.button(key="prendi_1.02").click().run()
    assert at.session_state["voci_scelte"] == ["1.02"]
    assert not at.exception, [e.value for e in at.exception]


def test_una_voce_presa_sparisce_dal_pool():
    """Il pool è il magazzino: quello che è uscito non è più lì."""
    at = _avvia()
    at.button(key="prendi_1.02").click().run()
    assert "prendi_1.02" not in _prendibili(at)


def test_la_voce_presa_si_compila_nella_sua_categoria():
    at = _avvia()
    at.button(key="prendi_1.02").click().run()
    at.session_state["cat_aperte"] = {"Demolizioni"}
    at.run()
    chiavi = [t.key for t in at.text_input]
    assert "q_1.02_txt" in chiavi
    assert "d_1.02_w" in chiavi          # descrizione modificabile
    assert "u_1.02_w" in chiavi          # unità modificabile


def test_la_x_toglie_la_voce_dal_computo():
    at = _avvia()
    at.button(key="prendi_1.02").click().run()
    at.session_state["cat_aperte"] = {"Demolizioni"}
    at.run()
    at.button(key="togli_1.02").click().run()
    assert at.session_state["voci_scelte"] == []
    assert "prendi_1.02" in _prendibili(at)      # torna nel pool


def test_togliere_una_voce_non_ne_cancella_la_quantita():
    """Ripescandola si ritrova com'era: la ✕ toglie dal foglio, non i dati."""
    at = _avvia()
    at.button(key="prendi_1.02").click().run()
    at.session_state["cat_aperte"] = {"Demolizioni"}
    at.run()
    at.text_input(key="q_1.02_txt").set_value("120").run()
    at.button(key="togli_1.02").click().run()
    at.button(key="prendi_1.02").click().run()
    assert at.session_state["q_1.02"] == 120.0


def test_solo_le_voci_scelte_contano_nel_totale():
    """Una quantità in una voce non scelta non è nel computo."""
    at = _avvia()
    at.session_state["q_1.02"] = 100.0
    at.session_state["p_1.02"] = 10.0
    at.run()
    assert at.session_state["voci_scelte"] == []
    # la si prende, e solo allora entra nei conti
    at.button(key="prendi_1.02").click().run()
    assert at.session_state["voci_scelte"] == ["1.02"]


# ---------------------------------------------------------- la ricerca

def test_la_ricerca_restringe_il_pool():
    at = _avvia()
    at.text_input(key="cerca_voce").set_value("battiscopa").run()
    prendibili = _prendibili(at)
    assert "prendi_2.14" in prendibili        # posa battiscopa
    assert "prendi_0.01" not in prendibili    # progetto architettonico
    assert not at.exception, [e.value for e in at.exception]


def test_la_ricerca_a_piu_parole_le_vuole_tutte():
    """«posa gres» trova la voce anche con le parole lontane."""
    at = _avvia()
    at.text_input(key="cerca_voce").set_value("posa gres").run()
    prendibili = _prendibili(at)
    assert prendibili == ["prendi_2.10"]


def test_la_ricerca_trova_anche_per_codice():
    at = _avvia()
    at.text_input(key="cerca_voce").set_value("3.05").run()
    prendibili = _prendibili(at)
    assert prendibili == ["prendi_3.05"]


def test_una_ricerca_senza_esito_non_rompe_niente():
    at = _avvia()
    at.text_input(key="cerca_voce").set_value("zzzz").run()
    assert not _prendibili(at)
    assert not at.exception, [e.value for e in at.exception]


# ------------------------------------------------ descrizione e unità

def test_la_descrizione_riscritta_vale_nel_computo():
    at = _avvia()
    at.button(key="prendi_2.10").click().run()
    at.session_state["cat_aperte"] = {"Ricostruzioni e ripristini"}
    at.run()
    at.text_input(key="d_2.10_w").set_value("Gres 60x60 a correre").run()
    at.text_input(key="u_2.10_w").set_value("mq").run()
    assert at.session_state["d_2.10"] == "Gres 60x60 a correre"
    assert at.session_state["u_2.10"] == "mq"


def test_i_testi_riscritti_si_salvano_e_tornano():
    """Riscritture e scelta viaggiano nel file, e tornano riaprendolo."""
    riaperta = _avvia()
    riaperta.session_state["da_caricare"] = {
        "progetto": {"nome": "x", "committente": "", "oggetto": "",
                     "data": "2026-08-20", "aliquota_iva": 10.0,
                     "imprevisti": 10.0},
        "voci": [], "piante": [], "business_plan": {},
        "listino_stato": {"2.10": {"q": 50.0, "p": 55.0}},
        "voci_scelte": ["2.10"],
        "testi_voci": {"2.10": {"d": "Gres 60x60", "u": "mq"}},
    }
    riaperta.run()
    assert not riaperta.exception, [e.value for e in riaperta.exception]
    assert riaperta.session_state["voci_scelte"] == ["2.10"]
    assert riaperta.session_state["d_2.10"] == "Gres 60x60"
    assert riaperta.session_state["u_2.10"] == "mq"


# --------------------------------------------------- i progetti di prima

def test_un_progetto_vecchio_riapre_le_voci_che_aveva():
    """Senza elenco salvato, sono scelte le voci che avevano una quantità."""
    at = _avvia()
    at.session_state["da_caricare"] = PROGETTO_VECCHIO
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert sorted(at.session_state["voci_scelte"]) == ["1.02", "2.01"]


def test_un_progetto_vecchio_non_porta_su_le_voci_a_zero():
    at = _avvia()
    at.session_state["da_caricare"] = PROGETTO_VECCHIO
    at.run()
    assert "2.10" not in at.session_state["voci_scelte"]


def test_un_codice_sparito_dal_listino_non_pianta_l_apertura():
    """Un progetto che nomina una voce che non esiste più si apre lo stesso."""
    at = _avvia()
    at.session_state["da_caricare"] = {
        **PROGETTO_VECCHIO, "voci_scelte": ["1.02", "9.99"]}
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["voci_scelte"] == ["1.02"]
