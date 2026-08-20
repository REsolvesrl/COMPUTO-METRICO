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
    return _apri_pool(at)


def _apri_pool(at):
    """Apre tutte le categorie del pool: i ＋ esistono solo se aperte."""
    import listino
    at.session_state["pool_aperte"] = set(listino.CATEGORIE)
    at.run()
    return at


def _prendibili(at):
    """I codici che il pool offre in questo momento."""
    return [b.key for b in at.button
            if (b.key or "").startswith("prendi_")]


def _avvia():
    at = AppTest.from_file(str(SORGENTE), default_timeout=240)
    at.run()
    return _apri_pool(at)


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


# --------------------------------------------- le voci scritte a mano

def _crea(at, categoria, descrizione, um, quantita=0.0, prezzo=0.0):
    """Compila il pannello «Aggiungi una voce» e preme il bottone."""
    at.selectbox(key="nuova_cat").set_value(categoria).run()
    at.selectbox(key="nuova_um").set_value(um).run()
    at.text_input(key="nuova_desc").set_value(descrizione).run()
    if quantita:
        at.number_input(key="nuova_qta").set_value(quantita).run()
    at.number_input(key="nuova_prezzo").set_value(prezzo).run()
    at.button(key="crea_voce").click().run()
    return at


def test_la_voce_scritta_a_mano_finisce_nel_computo():
    at = _avvia()
    _crea(at, "Idraulico", "Spostamento colonna di scarico", "cad", 2.0, 300.0)
    assert not at.exception, [e.value for e in at.exception]
    extra = at.session_state["voci_extra"]
    assert len(extra) == 1
    codice = next(iter(extra))
    assert extra[codice]["categoria"] == "Idraulico"
    assert codice in at.session_state["voci_scelte"]


def test_il_codice_lo_mette_l_app_nella_serie_della_categoria():
    """Idraulico è la quarta categoria (serie 3): 3.90, poi 3.91."""
    at = _avvia()
    _crea(at, "Idraulico", "Prima voce", "cad", 1.0, 100.0)
    _crea(at, "Idraulico", "Seconda voce", "cad", 1.0, 100.0)
    assert sorted(at.session_state["voci_extra"]) == ["3.90", "3.91"]


def test_il_codice_inventato_non_pesta_i_piedi_al_listino():
    """Da .90 in su: le voci del listino arrivano al massimo a .23."""
    at = _avvia()
    _crea(at, "Demolizioni", "Allestimento cantiere", "a corpo", prezzo=800.0)
    import listino
    codice = next(iter(at.session_state["voci_extra"]))
    assert listino.voce_per_codice(codice) is None


def test_a_corpo_propone_uno_senza_chiederlo():
    at = _avvia()
    _crea(at, "Demolizioni", "Allestimento cantiere", "a corpo", prezzo=800.0)
    codice = next(iter(at.session_state["voci_extra"]))
    assert at.session_state[f"q_{codice}"] == 1.0
    # e quindi l'importo è il prezzo: 800, non zero
    assert at.session_state[f"p_{codice}"] == 800.0


def test_a_corpo_riempie_la_casella_ma_non_la_blocca():
    """L'1 è una proposta: si vede nella casella e si può cambiare."""
    at = _avvia()
    at.selectbox(key="nuova_um").set_value("a corpo").run()
    assert at.session_state["nuova_qta"] == 1.0
    at.number_input(key="nuova_qta").set_value(2.0).run()
    at.text_input(key="nuova_desc").set_value("Due interventi").run()
    at.button(key="crea_voce").click().run()
    codice = next(iter(at.session_state["voci_extra"]))
    assert at.session_state[f"q_{codice}"] == 2.0


def test_a_corpo_non_calpesta_una_quantita_gia_scritta():
    """Prima si scrive 3, poi si sceglie «a corpo»: resta 3."""
    at = _avvia()
    at.number_input(key="nuova_qta").set_value(3.0).run()
    at.selectbox(key="nuova_um").set_value("a corpo").run()
    assert at.session_state["nuova_qta"] == 3.0


def test_nel_computo_a_corpo_propone_uno_solo_se_manca():
    at = _avvia()
    at.button(key="prendi_1.02").click().run()      # m², quantità a zero
    at.session_state["cat_aperte"] = {"Demolizioni"}
    at.run()
    at.text_input(key="u_1.02_w").set_value("a corpo").run()
    assert at.session_state["q_1.02"] == 1.0
    # e la casella resta scrivibile: 2 vale 2
    at.text_input(key="q_1.02_txt").set_value("2").run()
    assert at.session_state["q_1.02"] == 2.0


def test_nel_computo_a_corpo_non_cancella_la_quantita_che_ce():
    at = _avvia()
    at.button(key="prendi_1.02").click().run()
    at.session_state["cat_aperte"] = {"Demolizioni"}
    at.run()
    at.text_input(key="q_1.02_txt").set_value("120").run()
    at.text_input(key="u_1.02_w").set_value("a corpo").run()
    assert at.session_state["q_1.02"] == 120.0


def test_la_voce_a_mano_nasce_nel_computo_non_nel_pool():
    """Appena creata è già una riga del documento: nel pool ci finisce solo
    se la togli."""
    at = _avvia()
    _crea(at, "Idraulico", "Spostamento colonna", "cad", 1.0, 300.0)
    codice = next(iter(at.session_state["voci_extra"]))
    assert codice in at.session_state["voci_scelte"]
    assert f"prendi_{codice}" not in _prendibili(at)


def test_una_voce_senza_descrizione_non_si_crea():
    at = _avvia()
    at.selectbox(key="nuova_cat").set_value("Idraulico").run()
    at.number_input(key="nuova_prezzo").set_value(300.0).run()
    at.button(key="crea_voce").click().run()
    assert at.session_state["voci_extra"] == {}
    assert any("descrizione" in w.value for w in at.warning)


def test_la_x_su_una_voce_a_mano_la_rimanda_nel_pool():
    """Una voce tua non si perde togliendola: si mette da parte, come le
    altre. Prima la ✕ la cancellava, e per ripensarci si riscriveva."""
    at = _avvia()
    _crea(at, "Idraulico", "Spostamento colonna", "cad", 2.0, 300.0)
    codice = next(iter(at.session_state["voci_extra"]))
    at.session_state["cat_aperte"] = {"Idraulico"}
    at.run()
    at.button(key=f"togli_{codice}").click().run()
    assert codice not in at.session_state["voci_scelte"]
    assert codice in at.session_state["voci_extra"]
    assert f"prendi_{codice}" in _prendibili(at)


def test_la_voce_tua_ripescata_si_ritrova_com_era():
    at = _avvia()
    _crea(at, "Idraulico", "Spostamento colonna", "cad", 2.0, 300.0)
    codice = next(iter(at.session_state["voci_extra"]))
    at.session_state["cat_aperte"] = {"Idraulico"}
    at.run()
    at.button(key=f"togli_{codice}").click().run()
    at.button(key=f"prendi_{codice}").click().run()
    assert at.session_state["voci_scelte"] == [codice]
    assert at.session_state[f"q_{codice}"] == 2.0
    assert at.session_state[f"p_{codice}"] == 300.0


def test_il_cestino_toglie_una_voce_dal_pool():
    """Le voci che su questo cantiere non c'entrano si levano di mezzo."""
    at = _avvia()
    at.button(key="cestina_1.02").click().run()
    assert at.session_state["voci_scartate"] == ["1.02"]
    assert "prendi_1.02" not in _prendibili(at)


def test_scartare_non_tocca_il_listino():
    """È una scelta di questo progetto, non una modifica al catalogo."""
    import listino
    at = _avvia()
    at.button(key="cestina_1.02").click().run()
    assert listino.voce_per_codice("1.02") is not None


def test_si_scarta_anche_una_voce_tua():
    at = _avvia()
    _crea(at, "Idraulico", "Spostamento colonna", "cad", 2.0, 300.0)
    codice = next(iter(at.session_state["voci_extra"]))
    at.session_state["cat_aperte"] = {"Idraulico"}
    at.run()
    at.button(key=f"togli_{codice}").click().run()
    at.button(key=f"cestina_{codice}").click().run()
    assert f"prendi_{codice}" not in _prendibili(at)
    # la definizione resta: rimettendo gli scarti si ritrova
    assert codice in at.session_state["voci_extra"]


def test_gli_scarti_si_rimettono_tutti_insieme():
    """Nessun clic sbagliato perde una voce per sempre."""
    at = _avvia()
    at.button(key="cestina_1.02").click().run()
    at.button(key="cestina_1.03").click().run()
    at.button(key="ripristina_scarti").click().run()
    assert at.session_state["voci_scartate"] == []
    assert "prendi_1.02" in _prendibili(at)
    assert "prendi_1.03" in _prendibili(at)


def test_riprendere_una_voce_scartata_la_toglie_dagli_scarti():
    at = _avvia()
    at.button(key="cestina_1.02").click().run()
    at.session_state["voci_scartate"] = ["1.02"]
    at.session_state["voci_scelte"] = []
    at.run()
    at.button(key="ripristina_scarti").click().run()
    at.button(key="prendi_1.02").click().run()
    assert at.session_state["voci_scartate"] == []
    assert at.session_state["voci_scelte"] == ["1.02"]


def test_gli_scarti_viaggiano_col_progetto():
    at = _avvia()
    at.session_state["da_caricare"] = {
        **PROGETTO_VECCHIO,
        "voci_scelte": ["1.02"],
        "voci_scartate": ["1.03", "1.04"],
    }
    at.run()
    assert at.session_state["voci_scartate"] == ["1.03", "1.04"]
    assert "prendi_1.03" not in _prendibili(at)


def test_una_voce_tua_messa_da_parte_resta_da_parte_riaprendo():
    """Salvata fuori dal computo, non deve rientrarci da sola."""
    at = _avvia()
    at.session_state["da_caricare"] = {
        **PROGETTO_VECCHIO,
        "voci": [{"categoria": "Idraulico", "codice": "3.90",
                  "descrizione": "Spostamento colonna", "um": "cad",
                  "parti": None, "lunghezza": None, "larghezza": None,
                  "altezza": None, "quantita_manuale": 2.0,
                  "prezzo": 300.0}],
        "voci_scelte": ["1.02"],          # la voce tua NON è nel computo
    }
    at.run()
    assert at.session_state["voci_scelte"] == ["1.02"]
    assert "3.90" in at.session_state["voci_extra"]      # ma esiste ancora


def test_la_voce_a_mano_conta_nei_totali():
    at = _avvia()
    _crea(at, "Demolizioni", "Allestimento cantiere", "a corpo", prezzo=800.0)
    somma = [m for m in at.metric if m.label == "Somma parziali"]
    assert somma and somma[0].value == "800,00 €"


# ------------------------------------------------- il pool resta aperto

def test_prendere_una_voce_non_richiude_il_pool():
    """Ogni ＋ è una riesecuzione: la categoria deve restare dov'era."""
    at = _avvia()
    at.session_state["pool_aperte"] = {"Demolizioni"}
    at.run()
    at.button(key="prendi_1.01").click().run()
    assert at.session_state["pool_aperte"] == {"Demolizioni"}
    # e la voce dopo è lì, pronta da prendere senza riaprire niente
    assert "prendi_1.03" in _prendibili(at)


# ----------------------------------------- i vecchi progetti con la tabella

PROGETTO_CON_TABELLA = {
    **PROGETTO_VECCHIO,
    "voci": [{"categoria": "Demolizioni", "codice": None,
              "descrizione": "allestimento cantiere", "um": "a corpo",
              "parti": None, "lunghezza": None, "larghezza": None,
              "altezza": None, "quantita_manuale": 1.0, "prezzo": 800.0}],
}


def test_le_voci_libere_di_prima_diventano_voci_del_computo():
    at = _avvia()
    at.session_state["da_caricare"] = PROGETTO_CON_TABELLA
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    extra = at.session_state["voci_extra"]
    assert len(extra) == 1
    codice = next(iter(extra))
    assert extra[codice]["descrizione"] == "allestimento cantiere"
    assert extra[codice]["categoria"] == "Demolizioni"
    assert codice in at.session_state["voci_scelte"]
    assert at.session_state[f"q_{codice}"] == 1.0
