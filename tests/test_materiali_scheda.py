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
    {"capitolo": "BAGNO", "descrizione": "PIATTO DOCCIA", "um": "cad",
     "quantita": 1.0, "fornitore": "Ceramiche Rossi",
     "link": "https://esempio.it/piatto-doccia", "stato": "Ordinato",
     "note": ""},
    {"capitolo": "BAGNO", "descrizione": "BOX DOCCIA", "um": "cad",
     "quantita": None, "fornitore": "", "link": "", "stato": "Da ordinare",
     "note": ""},
    {"capitolo": "PAVIMENTI", "descrizione": "GRES 60x60", "um": "m²",
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


def test_il_bottone_rimette_le_voci_mancanti_senza_toccare_le_tue():
    """Aggiunge e basta: l'elenco svuotato per sbaglio si recupera, e
    quello che hai scritto tu non si perde per strada."""
    at = _avvia(df_materiali=tabelle.df_materiali_da_righe([
        {"capitolo": "CUCINA", "descrizione": "CUCINA SU MISURA",
         "fornitore": "Falegnameria Bianchi"}]))
    at.button(key="ripristina_materiali").click().run()
    assert not at.exception, [e.value for e in at.exception]
    righe = _materiali(at)
    mia = [r for r in righe if r["descrizione"] == "CUCINA SU MISURA"]
    assert mia and mia[0]["fornitore"] == "Falegnameria Bianchi"
    assert len(righe) == len(materiali.ELENCO_STANDARD) + 1


def test_il_bottone_non_duplica_quello_che_c_e_gia():
    at = _avvia()
    at.button(key="ripristina_materiali").click().run()
    assert len(_materiali(at)) == len(materiali.ELENCO_STANDARD)
    assert "è già tutto in tabella" in _testi(at)


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
