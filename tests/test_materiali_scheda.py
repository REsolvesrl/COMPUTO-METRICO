"""La linguetta «Materiali» dentro la scheda Computo.

Qui non si prova il modulo puro — quello sta in test_materiali.py — ma le
tre cose che vivono solo nell'interfaccia e che, se si rompono, si rompono
in silenzio:

- l'elenco **nasce pieno** delle voci standard, e un progetto che l'ha
  svuotato **deve restare svuotato** quando lo riapri;
- il computo non deve accorgersi che questa sezione esiste: il totale dei
  lavori e il contratto d'appalto restano quello che si firma con l'impresa;
- fornitore e link si salvano, perché sono la ragione per cui uno riempie
  la tabella invece di tenere l'elenco su un foglio.
"""
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import listino
import materiali
import tabelle

SORGENTE = Path(__file__).resolve().parent.parent / "streamlit_app.py"

# Una voce di computo qualsiasi, presa dal listino invece che scritta a mano:
# i codici sono già stati rinumerati una volta, e un test che ne inchioda uno
# si rompe alla prossima — su un difetto che col computo non c'entra nulla.
VOCE = next(v for v in listino.VOCI if v["categoria"] == "Demolizioni")

ELENCO = [
    {"capitolo": "BAGNO", "descrizione": "PIATTO DOCCIA",
     "quantita": 1.0, "fornitore": "Ceramiche Rossi",
     "link": "https://esempio.it/piatto-doccia", "stato": "Ordinato",
     "note": ""},
    {"capitolo": "BAGNO", "descrizione": "BOX DOCCIA",
     "quantita": None, "fornitore": "", "link": "", "stato": "Da ordinare",
     "note": ""},
    {"capitolo": "PAVIMENTI", "descrizione": "GRES 60x60",
     "quantita": 100.0, "fornitore": "", "link": "", "stato": "Consegnato",
     "note": "posa a correre"},
]


def _avvia(**stato):
    at = AppTest.from_file(str(SORGENTE), default_timeout=300)
    at.run()
    for chiave, valore in stato.items():
        at.session_state[chiave] = valore
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _testi(at):
    pezzi = []
    for elenco in (at.markdown, at.caption, at.warning, at.info, at.error,
                   at.subheader, at.metric):
        for elemento in elenco:
            pezzi.append(str(getattr(elemento, "value", "")))
            pezzi.append(str(getattr(elemento, "label", "")))
    return "\n".join(pezzi)


def _materiali(at):
    return tabelle.materiali_da_df(at.session_state["df_materiali"])


def _tabella(at):
    """La tabella dei materiali, trovata per NOME e non per posizione.

    at.dataframe[1] funzionava per caso: l'indice cambia appena la scheda
    disegna un elemento in piu' o in meno, e il test finiva a guardare il
    registro delle spese senza accorgersene.
    """
    for d in at.dataframe:
        if "editor_materiali" in str(getattr(d.proto, "id", "")):
            return d
    raise AssertionError("la tabella dei materiali non c'e'")


def _elenco_vero(at):
    """L'elenco INTERO, non quello che si vede: col filtro attivo sono
    due cose diverse, ed e' il primo a non dover perdere righe."""
    df = at.session_state["df_materiali"]
    if "df_materiali_live" in at.session_state:
        df = at.session_state["df_materiali_live"]
    return tabelle.materiali_da_df(df)


# ------------------------------------------------- l'elenco di partenza

def test_una_sessione_nuova_nasce_con_l_elenco_standard():
    """«Tanto quelle vanno sicuramente acquistate»: si sfoltisce un elenco,
    non se ne riscrive uno da capo trenta righe per volta."""
    at = _avvia()
    assert _materiali(at) == materiali.elenco_standard()


def test_le_voci_del_foglio_firmato_sono_a_video():
    at = _avvia()
    metriche = {m.label: m.value for m in at.metric}
    assert metriche["Voci in elenco"] == str(len(materiali.ELENCO_STANDARD))
    assert metriche["Da ordinare"] == str(len(materiali.ELENCO_STANDARD))


def test_i_conteggi_per_stato_seguono_la_tabella():
    at = _avvia(df_materiali=tabelle.df_materiali_da_righe(ELENCO))
    metriche = {m.label: m.value for m in at.metric}
    assert metriche["Voci in elenco"] == "3"
    assert metriche["Da ordinare"] == "1"
    assert metriche["Ordinato"] == "1"
    assert metriche["Consegnato"] == "1"


def test_a_elenco_svuotato_c_e_lo_stato_vuoto():
    at = _avvia(df_materiali=tabelle.df_materiali_vuoto())
    assert "Nessun materiale in elenco" in _testi(at)


def test_le_voci_portano_il_pallino_del_loro_capitolo():
    """Il data_editor e' su tela grafica e ignora il CSS: il colore arriva
    incollato al testo che finisce in tabella, non come sfondo di cella."""
    at = _avvia()
    df = at.session_state["df_materiali"]
    assert df["capitolo"].iloc[0] == "🟦 BAGNO"


# ------------------------------------------------------- l'ordinamento

def _con_stati(cambi):
    """L'elenco standard con qualche stato/fornitore cambiato a mano.

    `cambi` e' {posizione: {campo: valore}} — un dizionario normale, non
    argomenti con la stella: le chiavi devono restare NUMERI, e con `**`
    Python le trasformerebbe in stringhe.
    """
    righe = materiali.elenco_standard()
    for indice, campi in cambi.items():
        righe[indice].update(campi)
    return tabelle.df_materiali_da_righe(righe)


def test_ordina_per_stato_mette_in_cima_quello_da_fare():
    """Rosso, giallo, verde: quello che ti resta da comprare per primo."""
    at = _avvia(df_materiali=_con_stati(
        {0: {"stato": "Consegnato"}, 1: {"stato": "Ordinato"}}))
    at.button(key="ord_mat_stato").click().run()
    assert not at.exception, [e.value for e in at.exception]
    righe = _materiali(at)
    posizioni = [materiali.STATI.index(r["stato"]) for r in righe]
    assert posizioni == sorted(posizioni)
    assert righe[-1]["stato"] == "Consegnato"


def test_ordinare_non_perde_ne_duplica_righe():
    at = _avvia(df_materiali=_con_stati({3: {"stato": "Ordinato"}}))
    at.button(key="ord_mat_stato").click().run()
    assert len(_materiali(at)) == len(materiali.ELENCO_STANDARD)


def test_l_ordinamento_e_stabile_e_non_disfa_l_ordine_del_foglio():
    """Dentro il gruppo resta l'ordine dell'allegato firmato — piatto
    doccia, box doccia, mobile — che un alfabetico distruggerebbe."""
    at = _avvia(df_materiali=_con_stati({0: {"stato": "Consegnato"}}))
    at.button(key="ord_mat_stato").click().run()
    da_ordinare = [r["descrizione"] for r in _materiali(at)
                   if r["stato"] == "Da ordinare"]
    standard = [r["descrizione"] for r in materiali.elenco_standard()
                if r["descrizione"] != "PIATTO DOCCIA"]
    assert da_ordinare == standard


def test_ordina_per_fornitore_manda_in_fondo_chi_non_ce_l_ha():
    """La cima della lista e' il posto di quello che e' gia' deciso."""
    at = _avvia(df_materiali=_con_stati({5: {"fornitore": "Bricoman"}}))
    at.button(key="ord_mat_fornitore").click().run()
    righe = _materiali(at)
    assert righe[0]["fornitore"] == "Bricoman"
    assert righe[-1]["fornitore"] == ""


def test_ordina_per_capitolo_segue_l_ordine_dell_allegato():
    at = _avvia(df_materiali=tabelle.df_materiali_da_righe(
        list(reversed(materiali.elenco_standard()))))
    at.button(key="ord_mat_capitolo").click().run()
    capitoli = [materiali.CAPITOLI.index(r["capitolo"])
                for r in _materiali(at)]
    assert capitoli == sorted(capitoli)


def test_ordinare_un_elenco_vuoto_non_esplode():
    at = _avvia(df_materiali=tabelle.df_materiali_vuoto())
    at.button(key="ord_mat_stato").click().run()
    assert not at.exception, [e.value for e in at.exception]
    assert _materiali(at) == []


# ----------------------------------------------------------- il filtro

def test_il_filtro_mostra_solo_lo_stato_scelto():
    at = _avvia(df_materiali=_con_stati(
        {0: {"stato": "Ordinato"}, 1: {"stato": "Ordinato"}}))
    at.selectbox(key="mat_filtro_w").select("🟨 Ordinato").run()
    assert not at.exception, [e.value for e in at.exception]
    vista = _tabella(at).value
    assert len(vista) == 2
    assert {tabelle.stato_pulito(v) for v in vista["stato"]} == {"Ordinato"}


def test_le_righe_nascoste_dal_filtro_NON_spariscono():
    """Il difetto da cui questo test guarda le spalle: il data_editor
    riceve solo le righe viste, e prendere il suo ritorno per l'elenco
    intero cancellerebbe tutte le altre senza che nessuno l'abbia
    chiesto."""
    at = _avvia(df_materiali=_con_stati({0: {"stato": "Ordinato"}}))
    at.selectbox(key="mat_filtro_w").select("🟨 Ordinato").run()
    assert not at.exception, [e.value for e in at.exception]
    # l'elenco vero resta intero, anche se a video se ne vede una sola
    assert len(_elenco_vero(at)) == len(materiali.ELENCO_STANDARD)


def test_col_filtro_attivo_non_si_aggiungono_righe():
    """Con l'aggiunta accesa il ritorno cambierebbe numero di righe, e
    rimetterle al loro posto nell'elenco intero sarebbe un indovinello."""
    at = _avvia(df_materiali=_con_stati({0: {"stato": "Ordinato"}}))
    at.selectbox(key="mat_filtro_w").select("🟨 Ordinato").run()
    assert _tabella(at).proto.editing_mode == 1     # FIXED


def test_senza_filtro_si_torna_a_poter_aggiungere():
    at = _avvia()
    assert _tabella(at).proto.editing_mode == 2     # DYNAMIC


def test_il_filtro_dice_quante_voci_sta_nascondendo():
    at = _avvia(df_materiali=_con_stati({0: {"stato": "Ordinato"}}))
    at.selectbox(key="mat_filtro_w").select("🟨 Ordinato").run()
    testo = _testi(at)
    assert "Filtro attivo" in testo
    assert f"**{len(materiali.ELENCO_STANDARD) - 1}** sono nascoste" in testo


def test_i_conteggi_restano_su_tutto_l_elenco_anche_filtrando():
    """I riquadri sotto contano l'elenco, non la vista: sono il riassunto
    di quello che devi comprare, non di quello che stai guardando."""
    at = _avvia(df_materiali=_con_stati({0: {"stato": "Ordinato"}}))
    at.selectbox(key="mat_filtro_w").select("🟨 Ordinato").run()
    metriche = {m.label: m.value for m in at.metric}
    assert metriche["Voci in elenco"] == str(len(materiali.ELENCO_STANDARD))


def test_aprire_un_progetto_spegne_il_filtro():
    """Un progetto appena aperto non deve mostrarsi a meta' per un filtro
    scelto su un altro lavoro."""
    at = _avvia(df_materiali=_con_stati({0: {"stato": "Ordinato"}}))
    at.selectbox(key="mat_filtro_w").select("🟨 Ordinato").run()
    at.session_state["da_caricare"] = {"progetto": {"nome": "Nuovo"}}
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert ("mat_filtro_w" not in at.session_state
            or at.session_state["mat_filtro_w"] == "Tutti gli stati")
    assert len(_tabella(at).value) == len(materiali.ELENCO_STANDARD)


# --------------------------------------------------------------- il confine

@pytest.fixture(scope="module")
def con_computo():
    """Una voce di computo accanto all'elenco dei materiali."""
    at = AppTest.from_file(str(SORGENTE), default_timeout=300)
    at.run()
    at.session_state["pool_aperte"] = {"Demolizioni"}
    at.run()
    at.button(key=f"prendi_{VOCE['codice']}").click().run()
    at.session_state[f"q_{VOCE['codice']}"] = 10.0
    at.session_state[f"p_{VOCE['codice']}"] = 100.0
    at.session_state["df_materiali"] = tabelle.df_materiali_da_righe(ELENCO)
    at.session_state["df_spese"] = tabelle.df_spese_da_righe(
        [{"importo": 1000.0, "aliquota_iva": 10.0, "categoria": "LAVORI",
          "oggetto": "Acconto impresa"}], tabelle.COLONNE_SPESE)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_il_totale_dei_lavori_resta_quello_del_computo(con_computo):
    """È tutta la ragione della sezione: il computo è il documento
    dell'impresa, e questa roba dalla sua fattura non passa."""
    metriche = {m.label: m.value for m in con_computo.metric}
    assert metriche["Totale lavori (IVA esclusa)"] == "1.000,00 €"


def test_il_preventivo_del_confronto_resta_il_computo(con_computo):
    """L'elenco materiali non porta prezzi: nel business plan non ha
    niente da aggiungere, e la scheda non deve fingere di sì."""
    metriche = {m.label: m.value for m in con_computo.metric}
    assert metriche["Preventivo (computo)"] == "1.000,00 €"


def test_il_contratto_d_appalto_e_il_computo_nudo(con_computo):
    bottoni = [b for b in con_computo.button if b.key == "cant_da_computo"]
    assert bottoni, "il bottone del contratto non c'è"
    assert bottoni[0].label == "Usa il computo: 1.000,00 €"


def test_la_scheda_avverte_di_dove_mettere_il_budget_materiali(con_computo):
    """Il confronto col cantiere conta le spese MATERIALE da una parte e
    non dall'altra: se non lo dice, sembra uno sforamento."""
    assert "spese da sostenere" in _testi(con_computo)


# ------------------------------------------------- salvataggio e riapertura

@pytest.fixture(scope="module")
def giro(tmp_path_factory, monkeypatch_module):
    """Scrivi i materiali, salva, riapri: non deve perdersene nessuno."""
    cartella = tmp_path_factory.mktemp("archivio_mat") / "progetti"
    monkeypatch_module.setenv("CME_ARCHIVIO", str(cartella))

    at = AppTest.from_file(str(SORGENTE), default_timeout=300)
    at.run()
    at.session_state["prg_nome"] = "Migliarina"
    at.session_state["prg_luogo"] = "La Spezia"
    at.session_state["df_materiali"] = tabelle.df_materiali_da_righe(ELENCO)
    at.run()
    at.button(key="salva_testata").click().run()
    assert not at.exception, [e.value for e in at.exception]

    file = cartella / "Migliarina.json"
    assert file.is_file(), "il salvataggio non ha scritto nessun file"
    salvato = json.loads(file.read_text(encoding="utf-8"))

    riaperta = AppTest.from_file(str(SORGENTE), default_timeout=300)
    riaperta.run()
    riaperta.session_state["da_caricare"] = salvato
    riaperta.run()
    assert not riaperta.exception, [e.value for e in riaperta.exception]
    return salvato, riaperta


@pytest.fixture(scope="module")
def monkeypatch_module():
    from _pytest.monkeypatch import MonkeyPatch
    mp = MonkeyPatch()
    yield mp
    mp.undo()


def test_il_file_salvato_contiene_i_materiali(giro):
    salvato, _ = giro
    assert salvato["materiali"] == ELENCO


def test_fornitore_e_link_si_salvano(giro):
    """Sono la ragione per cui uno riempie la tabella invece di tenere
    l'elenco su un foglio: sei mesi dopo si torna su QUEL modello."""
    salvato, _ = giro
    piatto = salvato["materiali"][0]
    assert piatto["fornitore"] == "Ceramiche Rossi"
    assert piatto["link"] == "https://esempio.it/piatto-doccia"


def test_i_materiali_non_finiscono_fra_le_voci_del_computo(giro):
    """Un elenco a parte deve restare a parte anche nel file: se finissero
    in «voci» rientrerebbero dalla finestra nei totali del computo."""
    salvato, _ = giro
    descrizioni = [v.get("descrizione") for v in salvato.get("voci") or []]
    assert "PIATTO DOCCIA" not in descrizioni


def test_il_luogo_della_firma_si_salva(giro):
    salvato, _ = giro
    assert salvato["progetto"]["luogo"] == "La Spezia"


def test_riaprendo_i_materiali_tornano(giro):
    _, riaperta = giro
    assert _materiali(riaperta) == ELENCO
    assert riaperta.session_state["prg_luogo"] == "La Spezia"


def test_un_progetto_svuotato_resta_svuotato():
    """ASSENTE e VUOTO sono due cose diverse: `[]` vuol dire che l'utente
    l'elenco l'ha tolto, e rimetterglielo a ogni riapertura sarebbe
    disfargli il lavoro."""
    at = AppTest.from_file(str(SORGENTE), default_timeout=300)
    at.run()
    at.session_state["da_caricare"] = {"progetto": {"nome": "Spoglio"},
                                       "materiali": []}
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert _materiali(at) == []


def test_un_progetto_vecchio_riceve_l_elenco_standard():
    """Salvato prima che questa sezione esistesse: la chiave non c'è
    proprio, e quelle voci servivano anche a lui."""
    at = AppTest.from_file(str(SORGENTE), default_timeout=300)
    at.run()
    at.session_state["da_caricare"] = {"progetto": {"nome": "Vecchio"}}
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert _materiali(at) == materiali.elenco_standard()
