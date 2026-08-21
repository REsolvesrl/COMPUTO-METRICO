"""I numeri scritti a mano restano scritti.

⚠️ **Streamlit cancella lo stato dei widget che non ridisegna.** Molti campi
del business plan sono `st.number_input` che usano la chiave come valore, e
quella chiave è dello widget: basta che un errore fermi lo script prima
della scheda fattibilità — o che quella scheda per un giro non venga
disegnata — e quei valori spariscono. Al giro dopo i predefiniti tornano al
loro posto, senza ricaricare niente e senza che nessuno lo dica.

È successo davvero, due volte: l'utente aveva forzato 6.000 € su Agenzia IN
e 2% su Agenzia OUT, e se li è ritrovati a 3,00% e 2,50%. Nello stesso
momento la ristrutturazione scritta a mano (65.000 €) era ancora al suo
posto — perché quella passa da `campo_numero_it`, dove il valore vero sta in
`chiave` e il widget è `chiave_txt`. Questa è la differenza, ed è quella che
`salva_e_ripristina_bp` porta anche alle percentuali.

La funzione si prova con dizionari normali: sparire dallo stato è
esattamente ciò che fa Streamlit col widget non ridisegnato, e in una
funzione pura quel caso si scrive in una riga invece di doverlo provocare.
"""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import streamlit_app

SORGENTE = Path(__file__).resolve().parent.parent / "streamlit_app.py"
PREDEFINITI = {"bp_ag_in": 3.0, "bp_ag_out": 2.5, "bp_durata": 12}


def _avvia():
    at = AppTest.from_file(str(SORGENTE), default_timeout=300)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


# ------------------------------------------------- la regola, in isolamento

def test_alla_prima_apertura_valgono_i_predefiniti():
    stato, copia = {}, {}
    streamlit_app.salva_e_ripristina_bp(stato, copia, PREDEFINITI)
    assert stato == PREDEFINITI


def test_il_valore_scritto_a_mano_finisce_nella_copia():
    stato, copia = {"bp_ag_out": 2.0}, {}
    streamlit_app.salva_e_ripristina_bp(stato, copia, PREDEFINITI)
    assert copia["bp_ag_out"] == 2.0


def test_il_valore_sparito_torna_dalla_copia_non_dal_predefinito():
    """Il cuore della faccenda: la chiave non c'e' piu' perche' Streamlit
    l'ha buttata via col widget, e quello che deve tornare e' il 2% scritto
    dall'utente, non il 2,5% di fabbrica."""
    stato, copia = {"bp_ag_out": 2.0}, {}
    streamlit_app.salva_e_ripristina_bp(stato, copia, PREDEFINITI)
    del stato["bp_ag_out"]                 # il widget non e' stato ridisegnato
    streamlit_app.salva_e_ripristina_bp(stato, copia, PREDEFINITI)
    assert stato["bp_ag_out"] == 2.0


def test_sopravvive_anche_a_piu_interruzioni_di_fila():
    stato, copia = {"bp_ag_in": 4.285714}, {}
    for _ in range(5):
        streamlit_app.salva_e_ripristina_bp(stato, copia, PREDEFINITI)
        del stato["bp_ag_in"]
    streamlit_app.salva_e_ripristina_bp(stato, copia, PREDEFINITI)
    assert stato["bp_ag_in"] == 4.285714


def test_la_copia_insegue_i_valori_invece_di_congelarli():
    """Non deve diventare una prigione: se il campo cambia, cambia anche lei,
    o dopo un «Progetto nuovo» rimetterebbe in tavola i numeri di prima."""
    stato, copia = {"bp_ag_out": 2.0}, {}
    streamlit_app.salva_e_ripristina_bp(stato, copia, PREDEFINITI)
    stato["bp_ag_out"] = 4.0                       # l'utente lo cambia ancora
    streamlit_app.salva_e_ripristina_bp(stato, copia, PREDEFINITI)
    del stato["bp_ag_out"]
    streamlit_app.salva_e_ripristina_bp(stato, copia, PREDEFINITI)
    assert stato["bp_ag_out"] == 4.0


def test_i_predefiniti_veri_dell_app_sono_tutti_coperti():
    """Se domani qualcuno aggiunge un campo a IMPOSTAZIONI_BP, la
    protezione deve valere anche per quello senza doverci pensare."""
    stato, copia = {}, {}
    streamlit_app.salva_e_ripristina_bp(stato, copia)
    for chiave in streamlit_app.IMPOSTAZIONI_BP:
        assert chiave in stato
    assert "bp_usa_consuntivo" in stato


# --------------------------------------------------- e dentro l'app vera

@pytest.mark.parametrize("chiave, scritto", [
    ("bp_ag_out", 2.0), ("bp_ag_in", 4.285714), ("bp_imposta", 2.0),
    ("bp_imprevisti_pct", 5.0), ("bp_iva_notaio", 4.0),
    ("bp_durata", 8),            # anche la durata: e' un widget come gli altri
    ("bp_mq", 131.73), ("bp_coeff_sogg", 1.35), ("bp_sconto", 8.0),
])
def test_l_app_tiene_da_parte_quello_che_scrivi(chiave, scritto):
    at = _avvia()
    at.session_state[chiave] = scritto
    at.run()
    assert at.session_state["_bp_copia"][chiave] == scritto


def test_la_durata_resta_quella_che_imposti():
    """Segnalata a parte: «torna automaticamente a 12». È lo stesso difetto
    delle percentuali — `bp_durata` è un `number_input` che usa la chiave
    come valore — ma va provata dal vivo, perché è un intero e i predefiniti
    la convertono con `int()`."""
    at = _avvia()
    at.number_input(key="bp_durata").set_value(8).run()
    for _ in range(3):
        at.run()
    assert at.session_state["bp_durata"] == 8
    assert at.session_state["_bp_copia"]["bp_durata"] == 8


def test_l_iva_di_imprevisti_e_condominio_parte_da_zero():
    """Una riserva non è una fattura, e le spese condominiali non portano
    IVA da scorporare."""
    assert streamlit_app.IMPOSTAZIONI_BP["bp_iva_imprevisti"] == 0.0


def test_un_progetto_nuovo_riporta_i_predefiniti():
    """⚠️ Il rovescio della medaglia, e va provato: una protezione che
    rimettesse in tavola i valori di prima anche dopo «Progetto nuovo»
    sarebbe un difetto peggiore di quello che cura."""
    at = _avvia()
    at.session_state["bp_ag_out"] = 2.0
    at.run()
    at.session_state["da_caricare"] = {}          # è ciò che fa azzera_progetto
    at.run()
    assert at.session_state["bp_ag_out"] == 2.5
    at.run()                                      # e non torna indietro dopo
    assert at.session_state["bp_ag_out"] == 2.5


# --------------------------- i comandi del computo restano raggiungibili

def test_l_iva_si_comanda_dal_riepilogo_costi():
    """È uscita dal pannello «Dati del progetto» — non era anagrafica — ed
    è andata accanto alle righe che governa. È l'UNICO comando di quella
    percentuale: se sparisse, la coda del computo si congelerebbe sul
    predefinito."""
    at = _avvia()
    chiavi = [w.key for w in at.number_input]
    assert "iva" in chiavi


def test_gli_imprevisti_non_sono_piu_nel_computo():
    """Il computo è il documento dei lavori. La riserva è una scelta di chi
    paga e vive nel business plan: tenerla in due posti voleva dire, prima o
    poi, contarla due volte."""
    at = _avvia()
    chiavi = [w.key for w in at.number_input]
    assert "imprevisti" not in chiavi
    etichette = [m.label for m in at.metric]
    assert not [e for e in etichette if e.startswith("Imprevisti")]


def test_cambiare_l_iva_muove_il_totale():
    """La prova che il comando e' ancora collegato ai conti, non solo
    presente sullo schermo.

    Serve un computo con dentro qualcosa: su un totale di zero, il 10% e il
    22% danno lo stesso numero e la prova non proverebbe niente.
    """
    at = _avvia()
    at.session_state["voci_extra"] = {"1.90": {
        "codice": "1.90", "categoria": "Demolizioni",
        "descrizione": "voce di prova", "um": "a corpo", "prezzo": 10000.0}}
    at.session_state["voci_scelte"] = ["1.90"]
    at.session_state["q_1.90"] = 1.0
    at.session_state["p_1.90"] = 10000.0
    at.run()
    at.number_input(key="iva").set_value(10.0).run()
    dieci = {m.label: m.value for m in at.metric}
    at.number_input(key="iva").set_value(22.0).run()
    ventidue = {m.label: m.value for m in at.metric}
    assert dieci["IVA 10%"] == "1.000,00 €"
    assert ventidue["IVA 22%"] == "2.200,00 €"
    # e i lavori restano quelli: l'IVA non li tocca
    assert dieci["Totale lavori (IVA esclusa)"] == "10.000,00 €"
    assert ventidue["Totale lavori (IVA esclusa)"] == "10.000,00 €"
