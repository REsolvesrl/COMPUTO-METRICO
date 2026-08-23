"""La sottosezione «Materiali» dentro la scheda Computo.

Qui non si prova l'aritmetica — quella sta in test_materiali.py — ma il
confine, che è la cosa per cui la sezione esiste: i materiali a cura del
committente **non** devono entrare nel totale dei lavori né nel contratto
d'appalto, e **devono** entrare nel costo dell'operazione. Sono due errori
speculari, tutti e due silenziosi: nel primo caso si chiede a un'impresa il
prezzo di roba che compri tu, nel secondo si crede di aver speso meno di
quanto si è speso.

Girano sull'app vera con AppTest: il confine vive nell'interfaccia, e le
funzioni pure da sole non lo dimostrerebbero.
"""
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import materiali
import tabelle

SORGENTE = Path(__file__).resolve().parent.parent / "streamlit_app.py"

ELENCO = [
    {"capitolo": "BAGNO", "descrizione": "PIATTO DOCCIA", "um": "cad",
     "quantita": 1.0, "prezzo": 320.0, "fornitore": "Ceramiche Rossi",
     "stato": "Ordinato", "note": ""},
    {"capitolo": "BAGNO", "descrizione": "BOX DOCCIA", "um": "cad",
     "quantita": None, "prezzo": None, "fornitore": "", "stato": "Da ordinare",
     "note": ""},
    {"capitolo": "PAVIMENTI", "descrizione": "GRES 60x60", "um": "m²",
     "quantita": 100.0, "prezzo": 22.0, "fornitore": "", "stato": "Consegnato",
     "note": "posa a correre"},
]
TOTALE_ELENCO = 320.0 + 2200.0          # il box doccia non ha prezzo


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


@pytest.fixture(scope="module")
def con_materiali():
    """Un computo con una voce e un elenco materiali accanto."""
    at = AppTest.from_file(str(SORGENTE), default_timeout=300)
    at.run()
    at.session_state["pool_aperte"] = {"Demolizioni"}
    at.run()
    at.button(key="prendi_2.2").click().run()
    at.session_state["q_2.2"] = 10.0
    at.session_state["p_2.2"] = 100.0
    at.session_state["df_materiali"] = tabelle.df_materiali_da_righe(ELENCO)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


# --------------------------------------------------------------- il confine

def test_i_materiali_non_entrano_nel_totale_dei_lavori(con_materiali):
    """È tutta la ragione della sezione: il computo è il documento
    dell'impresa, e questi soldi dalla sua fattura non passano."""
    metriche = {m.label: m.value for m in con_materiali.metric}
    assert metriche["Totale lavori (IVA esclusa)"] == "1.000,00 €"


def test_il_totale_materiali_sta_per_conto_suo(con_materiali):
    metriche = {m.label: m.value for m in con_materiali.metric}
    assert metriche["Totale materiali (IVA esclusa)"] == "2.520,00 €"


def test_la_sezione_dice_quante_voci_sono_ancora_da_quotare(con_materiali):
    """Un totale che tace i pezzi non quotati mente verso il basso, e lo fa
    proprio finché mancano quelli più cari."""
    testo = _testi(con_materiali)
    assert "1 voce senza prezzo" in testo
    assert "parziale" in testo


def test_la_sezione_tira_la_somma_dell_intervento(con_materiali):
    testo = _testi(con_materiali)
    assert "intervento completo 3.520,00 €" in testo


def test_lo_stato_dell_acquisto_si_vede(con_materiali):
    """È il numero per cui esiste la colonna: quanto hai già impegnato."""
    metriche = {m.label: m.value for m in con_materiali.metric}
    assert metriche["Ordinato"] == "320,00 €"
    assert metriche["Consegnato"] == "2.200,00 €"
    assert metriche["Da ordinare"] == "0,00 €"


def test_a_elenco_vuoto_c_e_lo_stato_vuoto_e_non_i_totali():
    at = _avvia()
    testo = _testi(at)
    assert "Nessun materiale in elenco" in testo
    assert "Totale materiali" not in testo


# ------------------------------------------- il costo dell'operazione

@pytest.fixture(scope="module")
def con_consuntivo():
    """Come sopra, più una fattura di cantiere: apre il confronto."""
    at = AppTest.from_file(str(SORGENTE), default_timeout=300)
    at.run()
    at.session_state["pool_aperte"] = {"Demolizioni"}
    at.run()
    at.button(key="prendi_2.2").click().run()
    at.session_state["q_2.2"] = 10.0
    at.session_state["p_2.2"] = 100.0
    at.session_state["df_materiali"] = tabelle.df_materiali_da_righe(ELENCO)
    at.session_state["df_spese"] = tabelle.df_spese_da_righe(
        [{"importo": 1000.0, "aliquota_iva": 10.0, "categoria": "LAVORI",
          "oggetto": "Acconto impresa"}], tabelle.COLONNE_SPESE)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def test_il_preventivo_del_confronto_comprende_i_materiali(con_consuntivo):
    """L'operazione li paga, e il consuntivo li conta già: le spese
    MATERIALE stanno in CATEGORIE_CANTIERE. Senza l'allegato dall'altra
    parte, ogni cantiere in cui le finiture le compri tu risultava sforato
    del loro intero importo — uno sforamento che non c'è mai stato."""
    metriche = {m.label: m.value for m in con_consuntivo.metric}
    assert metriche["Preventivo (computo + materiali)"] == "3.520,00 €"


def test_il_contratto_d_appalto_resta_il_computo_nudo(con_consuntivo):
    """Il bottone che riempie l'importo di contratto propone quello che
    firmi con l'IMPRESA: metterci i materiali a cura tua cancellerebbe con
    un clic il confine che l'allegato traccia."""
    bottoni = [b for b in con_consuntivo.button
               if b.key == "cant_da_computo"]
    assert bottoni, "il bottone del contratto non c'è"
    assert bottoni[0].label == "Usa il computo: 1.000,00 €"


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
    righe = tabelle.materiali_da_df(riaperta.session_state["df_materiali"])
    assert righe == ELENCO
    assert riaperta.session_state["prg_luogo"] == "La Spezia"


def test_un_progetto_senza_materiali_si_riapre_lo_stesso():
    """I salvataggi fatti prima non hanno la chiave: la tabella nasce
    vuota e il computo resta identico a com'era."""
    at = AppTest.from_file(str(SORGENTE), default_timeout=300)
    at.run()
    at.session_state["da_caricare"] = {"progetto": {"nome": "Vecchio"}}
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert tabelle.materiali_da_df(at.session_state["df_materiali"]) == []


def test_materiali_e_totale_restano_allineati():
    """La somma della sezione è la stessa che il modulo puro calcola: se
    un giorno divergessero, la scheda direbbe un numero e l'allegato un
    altro."""
    calcolate = materiali.calcola_elenco(ELENCO)
    assert materiali.totale(calcolate) == TOTALE_ELENCO
