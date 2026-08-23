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
    "listino_stato": {"2.2": {"q": 120.0, "p": 115.0},
                      "3.1": {"q": 30.0, "p": 80.0},
                      # prezzo ritoccato ma quantità zero: non era nel
                      # computo prima, non deve esserci nemmeno adesso
                      "3.10": {"q": 0.0, "p": 60.0}},
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
    at.button(key="prendi_2.2").click().run()
    assert at.session_state["voci_scelte"] == ["2.2"]
    assert not at.exception, [e.value for e in at.exception]


def test_una_voce_presa_sparisce_dal_pool():
    """Il pool è il magazzino: quello che è uscito non è più lì."""
    at = _avvia()
    at.button(key="prendi_2.2").click().run()
    assert "prendi_2.2" not in _prendibili(at)


def test_la_voce_presa_si_compila_nella_sua_categoria():
    at = _avvia()
    at.button(key="prendi_2.2").click().run()
    at.session_state["cat_aperte"] = {"Demolizioni"}
    at.run()
    assert "q_2.2_txt" in [t.key for t in at.text_input]
    # la descrizione è un'area: va a capo su due righe
    assert "d_2.2_w" in [t.key for t in at.text_area]
    # l'unità è una tendina: le unità di un computo sono sei o sette, e
    # scriverle a mano vuol dire ritrovarsi «mq», «m2» e «m²» sulla stessa
    # stampa
    assert "u_2.2_w" in [s.key for s in at.selectbox]


def test_la_x_toglie_la_voce_dal_computo():
    at = _avvia()
    at.button(key="prendi_2.2").click().run()
    at.session_state["cat_aperte"] = {"Demolizioni"}
    at.run()
    at.button(key="togli_2.2").click().run()
    assert at.session_state["voci_scelte"] == []
    assert "prendi_2.2" in _prendibili(at)      # torna nel pool


def test_togliere_una_voce_non_ne_cancella_la_quantita():
    """Ripescandola si ritrova com'era: la ✕ toglie dal foglio, non i dati."""
    at = _avvia()
    at.button(key="prendi_2.2").click().run()
    at.session_state["cat_aperte"] = {"Demolizioni"}
    at.run()
    at.text_input(key="q_2.2_txt").set_value("120").run()
    at.button(key="togli_2.2").click().run()
    at.button(key="prendi_2.2").click().run()
    assert at.session_state["q_2.2"] == 120.0


def test_solo_le_voci_scelte_contano_nel_totale():
    """Una quantità in una voce non scelta non è nel computo."""
    at = _avvia()
    at.session_state["q_2.2"] = 100.0
    at.session_state["p_2.2"] = 10.0
    at.run()
    assert at.session_state["voci_scelte"] == []
    # la si prende, e solo allora entra nei conti
    at.button(key="prendi_2.2").click().run()
    assert at.session_state["voci_scelte"] == ["2.2"]


# ---------------------------------------------------------- la ricerca

def test_la_ricerca_restringe_il_pool():
    at = _avvia()
    at.text_input(key="cerca_voce").set_value("battiscopa").run()
    prendibili = _prendibili(at)
    assert "prendi_3.15" in prendibili        # posa battiscopa
    assert "prendi_1.1" not in prendibili    # progetto architettonico
    assert not at.exception, [e.value for e in at.exception]


def test_la_ricerca_a_piu_parole_le_vuole_tutte():
    """«posa gres» trova la voce anche con le parole lontane."""
    at = _avvia()
    at.text_input(key="cerca_voce").set_value("posa gres").run()
    prendibili = _prendibili(at)
    assert prendibili == ["prendi_3.10"]


def test_la_ricerca_trova_anche_per_codice():
    at = _avvia()
    at.text_input(key="cerca_voce").set_value("4.5").run()
    prendibili = _prendibili(at)
    assert prendibili == ["prendi_4.5"]


def test_una_ricerca_senza_esito_non_rompe_niente():
    at = _avvia()
    at.text_input(key="cerca_voce").set_value("zzzz").run()
    assert not _prendibili(at)
    assert not at.exception, [e.value for e in at.exception]


# ------------------------------------------------ descrizione e unità

def test_la_descrizione_riscritta_vale_nel_computo():
    at = _avvia()
    at.button(key="prendi_3.10").click().run()
    at.session_state["cat_aperte"] = {"Ricostruzioni e ripristini"}
    at.run()
    at.text_area(key="d_3.10_w").set_value("Gres 60x60 a correre").run()
    at.selectbox(key="u_3.10_w").set_value("ml").run()
    assert at.session_state["d_3.10"] == "Gres 60x60 a correre"
    assert at.session_state["u_3.10"] == "ml"


def test_i_testi_riscritti_si_salvano_e_tornano():
    """Riscritture e scelta viaggiano nel file, e tornano riaprendolo."""
    riaperta = _avvia()
    riaperta.session_state["da_caricare"] = {
        "progetto": {"nome": "x", "committente": "", "oggetto": "",
                     "data": "2026-08-20", "aliquota_iva": 10.0,
                     "imprevisti": 10.0},
        "voci": [], "piante": [], "business_plan": {},
        "listino_stato": {"3.10": {"q": 50.0, "p": 55.0}},
        "voci_scelte": ["3.10"],
        "testi_voci": {"3.10": {"d": "Gres 60x60", "u": "mq"}},
    }
    riaperta.run()
    assert not riaperta.exception, [e.value for e in riaperta.exception]
    assert riaperta.session_state["voci_scelte"] == ["3.10"]
    assert riaperta.session_state["d_3.10"] == "Gres 60x60"
    assert riaperta.session_state["u_3.10"] == "mq"


# --------------------------------------------------- i progetti di prima

def test_un_progetto_vecchio_riapre_le_voci_che_aveva():
    """Senza elenco salvato, sono scelte le voci che avevano una quantità."""
    at = _avvia()
    at.session_state["da_caricare"] = PROGETTO_VECCHIO
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert sorted(at.session_state["voci_scelte"]) == ["2.2", "3.1"]


def test_un_progetto_vecchio_non_porta_su_le_voci_a_zero():
    at = _avvia()
    at.session_state["da_caricare"] = PROGETTO_VECCHIO
    at.run()
    assert "3.10" not in at.session_state["voci_scelte"]


def test_un_codice_sparito_dal_listino_non_pianta_l_apertura():
    """Un progetto che nomina una voce che non esiste più si apre lo stesso."""
    at = _avvia()
    at.session_state["da_caricare"] = {
        **PROGETTO_VECCHIO, "voci_scelte": ["2.2", "9.99"]}
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["voci_scelte"] == ["2.2"]


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
    """Idraulico è la quarta categoria e ha 13 voci di listino: la prima
    scritta a mano prende 4.14, la seconda 4.15. Non piu' un blocco a
    parte (le vecchie 3.90): la numerazione continua, senza buchi."""
    at = _avvia()
    _crea(at, "Idraulico", "Prima voce", "cad", 1.0, 100.0)
    _crea(at, "Idraulico", "Seconda voce", "cad", 1.0, 100.0)
    assert sorted(at.session_state["voci_extra"]) == ["4.14", "4.15"]


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
    at.button(key="prendi_2.2").click().run()      # m², quantità a zero
    at.session_state["cat_aperte"] = {"Demolizioni"}
    at.run()
    at.selectbox(key="u_2.2_w").set_value("a corpo").run()
    assert at.session_state["q_2.2"] == 1.0
    # e la quantità resta scrivibile: con «a corpo» è la casella a frecce
    at.number_input(key="qn_2.2_w").set_value(2.0).run()
    assert at.session_state["q_2.2"] == 2.0


def test_nel_computo_a_corpo_non_cancella_la_quantita_che_ce():
    at = _avvia()
    at.button(key="prendi_2.2").click().run()
    at.session_state["cat_aperte"] = {"Demolizioni"}
    at.run()
    at.text_input(key="q_2.2_txt").set_value("120").run()
    at.selectbox(key="u_2.2_w").set_value("a corpo").run()
    assert at.session_state["q_2.2"] == 120.0


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
    at.button(key="cestina_2.2").click().run()
    assert at.session_state["voci_scartate"] == ["2.2"]
    assert "prendi_2.2" not in _prendibili(at)


def test_scartare_non_tocca_il_listino():
    """È una scelta di questo progetto, non una modifica al catalogo."""
    import listino
    at = _avvia()
    at.button(key="cestina_2.2").click().run()
    assert listino.voce_per_codice("2.2") is not None


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
    at.button(key="cestina_2.2").click().run()
    at.button(key="cestina_2.3").click().run()
    at.button(key="ripristina_scarti").click().run()
    assert at.session_state["voci_scartate"] == []
    assert "prendi_2.2" in _prendibili(at)
    assert "prendi_2.3" in _prendibili(at)


def test_riprendere_una_voce_scartata_la_toglie_dagli_scarti():
    at = _avvia()
    at.button(key="cestina_2.2").click().run()
    at.session_state["voci_scartate"] = ["2.2"]
    at.session_state["voci_scelte"] = []
    at.run()
    at.button(key="ripristina_scarti").click().run()
    at.button(key="prendi_2.2").click().run()
    assert at.session_state["voci_scartate"] == []
    assert at.session_state["voci_scelte"] == ["2.2"]


def test_gli_scarti_viaggiano_col_progetto():
    at = _avvia()
    at.session_state["da_caricare"] = {
        **PROGETTO_VECCHIO,
        "voci_scelte": ["2.2"],
        "voci_scartate": ["2.3", "2.4"],
    }
    at.run()
    assert at.session_state["voci_scartate"] == ["2.3", "2.4"]
    assert "prendi_2.3" not in _prendibili(at)


def test_una_voce_tua_messa_da_parte_resta_da_parte_riaprendo():
    """Salvata fuori dal computo, non deve rientrarci da sola."""
    at = _avvia()
    at.session_state["da_caricare"] = {
        **PROGETTO_VECCHIO,
        "voci": [{"categoria": "Idraulico", "codice": "4.14",
                  "descrizione": "Spostamento colonna", "um": "cad",
                  "parti": None, "lunghezza": None, "larghezza": None,
                  "altezza": None, "quantita_manuale": 2.0,
                  "prezzo": 300.0}],
        "voci_scelte": ["2.2"],          # la voce tua NON è nel computo
    }
    at.run()
    assert at.session_state["voci_scelte"] == ["2.2"]
    assert "4.14" in at.session_state["voci_extra"]     # ma esiste ancora


def test_la_voce_a_mano_conta_nei_totali():
    at = _avvia()
    _crea(at, "Demolizioni", "Allestimento cantiere", "a corpo", prezzo=800.0)
    lavori = [m for m in at.metric
              if m.label == "Totale lavori (IVA esclusa)"]
    assert lavori and lavori[0].value == "800,00 €"


# ------------------------------------------------- il pool resta aperto

def test_prendere_una_voce_non_richiude_il_pool():
    """Ogni ＋ è una riesecuzione: la categoria deve restare dov'era."""
    at = _avvia()
    at.session_state["pool_aperte"] = {"Demolizioni"}
    at.run()
    at.button(key="prendi_2.1").click().run()
    assert at.session_state["pool_aperte"] == {"Demolizioni"}
    # e la voce dopo è lì, pronta da prendere senza riaprire niente
    assert "prendi_2.3" in _prendibili(at)


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


# ------------------------------------- spostare una voce tua di categoria

def test_una_voce_tua_si_sposta_di_categoria():
    """Sbagliata la casa: si cambia, e il codice cambia con lei."""
    at = _avvia()
    _crea(at, "Ricostruzioni e ripristini", "Assistenza muraria", "a corpo",
          prezzo=7000.0)
    assert "3.25" in at.session_state["voci_extra"]
    at.session_state["cat_aperte"] = {"Ricostruzioni e ripristini"}
    at.run()
    at.selectbox(key="spostacat_3.25").set_value("Demolizioni").run()
    at.button(key="sposta_3.25").click().run()
    extra = at.session_state["voci_extra"]
    assert "3.25" not in extra
    assert extra["2.11"]["categoria"] == "Demolizioni"
    assert extra["2.11"]["descrizione"] == "Assistenza muraria"


def test_spostando_una_voce_prezzo_e_quantita_la_seguono():
    at = _avvia()
    _crea(at, "Ricostruzioni e ripristini", "Assistenza muraria", "a corpo",
          prezzo=7000.0)
    at.session_state["cat_aperte"] = {"Ricostruzioni e ripristini"}
    at.run()
    at.selectbox(key="spostacat_3.25").set_value("Demolizioni").run()
    at.button(key="sposta_3.25").click().run()
    assert at.session_state["q_2.11"] == 1.0
    assert at.session_state["p_2.11"] == 7000.0
    assert "q_3.25" not in at.session_state
    # e il totale non si muove: è la stessa voce, in un'altra casa
    lavori = [m for m in at.metric
              if m.label == "Totale lavori (IVA esclusa)"]
    assert lavori and lavori[0].value == "7.000,00 €"


def test_la_voce_spostata_resta_al_suo_posto_nell_ordine():
    """Spostare non è togliere e rimettere in fondo."""
    at = _avvia()
    _crea(at, "Ricostruzioni e ripristini", "Prima", "a corpo", prezzo=100.0)
    _crea(at, "Idraulico", "Seconda", "a corpo", prezzo=200.0)
    at.session_state["cat_aperte"] = {"Ricostruzioni e ripristini"}
    at.run()
    at.selectbox(key="spostacat_3.25").set_value("Demolizioni").run()
    at.button(key="sposta_3.25").click().run()
    assert at.session_state["voci_scelte"] == ["2.11", "4.14"]


def test_le_voci_del_listino_non_cambiano_categoria():
    """Il listino è il catalogo: la 1.02 sta nelle demolizioni e basta."""
    at = _avvia()
    at.button(key="prendi_2.2").click().run()
    at.session_state["cat_aperte"] = {"Demolizioni"}
    at.run()
    assert "spostacat_2.2" not in [s.key for s in at.selectbox]


# --------------------------------- unità: tendina, e quella giusta per casa

def test_le_quantita_delle_voci_a_mano_si_possono_modificare():
    """Il difetto: la rilettura del testo digitato girava sulle sole voci di
    listino, e quelle scritte a mano restavano fuori. Si scriveva 2, si
    premeva invio, e al giro dopo tornava 1."""
    at = _avvia()
    _crea(at, "Demolizioni", "Allestimento cantiere", "a corpo", prezzo=800.0)
    codice = next(iter(at.session_state["voci_extra"]))
    at.session_state["cat_aperte"] = {"Demolizioni"}
    at.run()
    at.number_input(key=f"qn_{codice}_w").set_value(2.0).run()
    assert at.session_state[f"q_{codice}"] == 2.0
    lavori = [m for m in at.metric
              if m.label == "Totale lavori (IVA esclusa)"]
    assert lavori and lavori[0].value == "1.600,00 €"


def test_anche_il_prezzo_di_una_voce_a_mano_si_modifica():
    at = _avvia()
    _crea(at, "Demolizioni", "Allestimento cantiere", "a corpo", prezzo=800.0)
    codice = next(iter(at.session_state["voci_extra"]))
    at.session_state["cat_aperte"] = {"Demolizioni"}
    at.run()
    at.text_input(key=f"p_{codice}_txt").set_value("2.500").run()
    assert at.session_state[f"p_{codice}"] == 2500.0


def test_dall_elettricista_l_unita_di_casa_e_il_punto_luce():
    at = _avvia()
    at.selectbox(key="nuova_cat").set_value("Elettricista").run()
    assert at.selectbox(key="nuova_um").value == "punto luce"


def test_dall_idraulico_l_unita_di_casa_e_il_punto_acqua():
    at = _avvia()
    at.selectbox(key="nuova_cat").set_value("Idraulico").run()
    assert at.selectbox(key="nuova_um").value == "punto acqua"


def test_cambiando_categoria_l_unita_non_fa_saltare_l_app():
    """«punto luce» non esiste fra le demolizioni: il valore deve ricadere
    sul primo dell'elenco invece di far sollevare un errore."""
    at = _avvia()
    at.selectbox(key="nuova_cat").set_value("Elettricista").run()
    at.selectbox(key="nuova_cat").set_value("Demolizioni").run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.selectbox(key="nuova_um").value == "m²"


def test_la_quantita_a_frecce_solo_dove_si_contano_pezzi():
    """Su «a corpo» le frecce; sui metri quadri la casella scritta."""
    at = _avvia()
    at.button(key="prendi_2.2").click().run()       # m²
    at.session_state["cat_aperte"] = {"Demolizioni"}
    at.run()
    assert "qn_2.2_w" not in [n.key for n in at.number_input]
    assert "q_2.2_txt" in [t.key for t in at.text_input]
    at.selectbox(key="u_2.2_w").set_value("cad").run()
    assert "qn_2.2_w" in [n.key for n in at.number_input]
    assert "q_2.2_txt" not in [t.key for t in at.text_input]


def test_nella_riga_l_unita_di_casa_e_in_testa_alla_tendina():
    """La 4.02 è dell'elettricista: «punto luce» è la prima da scegliere,
    anche se la voce oggi porta ancora il generico «punto»."""
    at = _avvia()
    at.button(key="prendi_5.2").click().run()
    at.session_state["cat_aperte"] = {"Elettricista"}
    at.run()
    tendina = at.selectbox(key="u_5.2_w")
    assert tendina.options[0] == "punto luce"
    assert tendina.value == "punto"          # quella che la voce ha oggi


def test_il_battiscopa_si_misura_in_metri_lineari():
    at = _avvia()
    at.button(key="prendi_3.15").click().run()
    at.session_state["cat_aperte"] = {"Ricostruzioni e ripristini"}
    at.run()
    assert at.selectbox(key="u_3.15_w").value == "ml"


# ------------------------------------------------- l'ordine delle righe

def _tre_demolizioni(at):
    """Tre voci di demolizione, nell'ordine in cui sono state prese."""
    for codice in ("2.1", "2.2", "2.3"):
        at.button(key=f"prendi_{codice}").click().run()
    at.session_state["cat_aperte"] = {"Demolizioni"}
    at.run()
    return at


def test_una_voce_si_sposta_su():
    at = _tre_demolizioni(_avvia())
    assert at.session_state["voci_scelte"] == ["2.1", "2.2", "2.3"]
    at.button(key="su_2.3").click().run()
    assert at.session_state["voci_scelte"] == ["2.1", "2.3", "2.2"]


def test_una_voce_si_sposta_giu():
    at = _tre_demolizioni(_avvia())
    at.button(key="giu_2.1").click().run()
    assert at.session_state["voci_scelte"] == ["2.2", "2.1", "2.3"]


def test_la_prima_non_scappa_di_sopra():
    """«Su» dalla prima non deve portarla in un'altra categoria."""
    at = _tre_demolizioni(_avvia())
    at.button(key="su_2.1").click().run()
    assert at.session_state["voci_scelte"] == ["2.1", "2.2", "2.3"]


def test_l_ultima_non_scappa_di_sotto():
    at = _tre_demolizioni(_avvia())
    at.button(key="giu_2.3").click().run()
    assert at.session_state["voci_scelte"] == ["2.1", "2.2", "2.3"]


def test_l_ordine_si_muove_solo_dentro_la_categoria():
    """Fra le demolizioni c'è una voce di un'altra categoria: «su» deve
    scavalcarla, non fermarsi né mescolare le due tabelle."""
    at = _avvia()
    at.button(key="prendi_2.1").click().run()
    at.button(key="prendi_3.10").click().run()      # ricostruzioni, in mezzo
    at.button(key="prendi_2.2").click().run()
    at.session_state["cat_aperte"] = {"Demolizioni"}
    at.run()
    at.button(key="su_2.2").click().run()
    assert at.session_state["voci_scelte"] == ["2.2", "3.10", "2.1"]


def test_l_ordine_si_salva_e_torna():
    at = _tre_demolizioni(_avvia())
    at.button(key="su_2.3").click().run()
    ordine = list(at.session_state["voci_scelte"])
    riaperta = _avvia()
    riaperta.session_state["da_caricare"] = {
        **PROGETTO_VECCHIO, "voci_scelte": ordine}
    riaperta.run()
    assert riaperta.session_state["voci_scelte"] == ordine


def test_la_tendina_delle_unita_non_offre_kg_ne_utenza():
    """Non capitano in un computo di ristrutturazione: la tendina e' corta
    apposta, si sceglie senza leggere."""
    at = _avvia()
    assert "kg" not in at.selectbox(key="nuova_um").options
    assert "utenza" not in at.selectbox(key="nuova_um").options


def test_una_voce_che_ha_gia_utenza_se_la_tiene():
    """La 3.01 del listino si misura a utenza: toglierla dalle proposte non
    deve cambiare l'unita' di chi ce l'ha gia' — ne' far saltare la
    tendina, che il valore da mostrare deve contenerlo."""
    at = _avvia()
    at.button(key="prendi_4.1").click().run()
    at.session_state["cat_aperte"] = {"Idraulico"}
    at.run()
    tendina = at.selectbox(key="u_4.1_w")
    assert tendina.value == "utenza"
    assert "utenza" in tendina.options
    assert not at.exception, [e.value for e in at.exception]
