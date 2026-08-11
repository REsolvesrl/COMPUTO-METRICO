"""Quello che il Business plan DICE dei suoi numeri.

Gli altri test provano che i conti tornano. Questi provano che la scheda
non li nomina male — che è un difetto altrettanto costoso, e più difficile
da vedere: un numero giusto sotto un'etichetta sbagliata non stona, e
finisce lo stesso in una decisione d'acquisto.

Le tre famiglie sorvegliate qui:

- una **stima su tre comparabili** quando in tabella ce ne sono cinque non
  deve sembrare la stessa cosa di una stima su cinque;
- il **confronto col preventivo** non deve comparire prima che esista una
  spesa di cantiere: senza, urlava «−100 %» sul computo intero;
- un **contratto pagato oltre il suo importo** deve vedersi, invece di
  fermarsi a un residuo di zero.

Girano sull'app vera con AppTest: le etichette vivono nell'interfaccia, e
leggere il sorgente qui non basterebbe.
"""
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

SORGENTE = Path(__file__).resolve().parent.parent / "streamlit_app.py"


def _avvia(**stato):
    """L'app eseguita una volta, con la sessione preparata."""
    at = AppTest.from_file(str(SORGENTE), default_timeout=300)
    at.run()
    for chiave, valore in stato.items():
        at.session_state[chiave] = valore
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _testi(at):
    """Tutto il testo della pagina, in un unico blocco da cercare dentro."""
    pezzi = []
    for elenco in (at.markdown, at.caption, at.warning, at.info, at.error,
                   at.subheader, at.metric):
        for elemento in elenco:
            pezzi.append(str(getattr(elemento, "value", "")))
            pezzi.append(str(getattr(elemento, "label", "")))
    return "\n".join(pezzi)


# --------------------------------------------------------------------- MCA

@pytest.fixture(scope="module")
def mca_con_scarti():
    """Due comparabili buoni e due incompleti nella stessa tabella."""
    return _avvia(df_mca=pd.DataFrame([
        {"nome": "C1", "prezzo": 300000.0, "mq": 100.0, "coeff": 1.0,
         "note": ""},
        {"nome": "C2", "prezzo": 260000.0, "mq": 100.0, "coeff": 1.0,
         "note": ""},
        {"nome": "senza coefficiente", "prezzo": 300000.0, "mq": 100.0,
         "coeff": 0.0, "note": ""},
        {"nome": "senza mq", "prezzo": 300000.0, "mq": 0.0, "coeff": 1.0,
         "note": ""},
    ]), bp_mq=100.0)


def test_i_comparabili_scartati_non_spariscono_in_silenzio(mca_con_scarti):
    testo = _testi(mca_con_scarti)
    assert "2 comparabile/i" in testo
    assert "non entra/entrano" in testo


def test_la_media_dichiara_su_quanti_e_fatta(mca_con_scarti):
    """«€/mq medio» senza il numero di comparabili è mezza informazione."""
    etichette = [m.label for m in mca_con_scarti.metric]
    assert "€/mq medio normalizzato (su 2)" in etichette, etichette


def test_la_media_dichiara_di_essere_aritmetica(mca_con_scarti):
    """Un bilocale pesa quanto un quadrilocale: va detto, non dedotto."""
    assert "aritmetica" in _testi(mca_con_scarti)


def test_i_mq_dei_comparabili_e_del_soggetto_sono_la_stessa_grandezza():
    """Commerciali di qua, commerciali di là: se le basi differiscono
    l'errore non si vede mai, si porta dentro il prezzo di vendita."""
    at = _avvia(bp_mq=120.0)
    etichette = [m.label for m in at.metric]
    assert any("Mq commerciali del soggetto" in e for e in etichette)


# ------------------------------------------- confronto col preventivo

def _computo_da(totale):
    """Un computo di una riga sola, che vale esattamente `totale`."""
    return pd.DataFrame([{
        "categoria": "1 · Demolizioni", "codice": "X.01",
        "descrizione": "voce di prova", "um": "a corpo",
        "parti": None, "lunghezza": None, "larghezza": None, "altezza": None,
        "quantita_manuale": 1.0, "prezzo": float(totale),
    }])


def _spesa(categoria, importo):
    return {"importo": importo, "aliquota_iva": 22.0, "data": "",
            "nr_fattura": "", "oggetto": "acconto",
            "categoria": categoria, "note": ""}


def test_senza_spese_di_cantiere_non_si_confronta_niente():
    """Bastava la provvigione dell'agenzia e il blocco compariva con
    «−100 %»: il computo intero dato per non speso, a cantiere chiuso."""
    at = _avvia(df_spese=pd.DataFrame(
        [_spesa("🔴 ACQUISTO", 20000.0), _spesa("🟣 AGENZIA", 7320.0)]))
    assert "prova del cantiere" not in _testi(at)


def test_con_una_spesa_di_cantiere_il_confronto_compare():
    at = _avvia(df_spese=pd.DataFrame([_spesa("🟡 LAVORI", 5000.0)]))
    assert "prova del cantiere" in _testi(at)


def test_speso_e_da_sostenere_restano_distinti():
    """«Consuntivo» vuol dire soldi usciti: le previsioni stanno a parte."""
    at = _avvia(df_spese=pd.DataFrame([_spesa("🟡 LAVORI", 5000.0)]),
                df_spese_prev=pd.DataFrame([_spesa("🟢 MATERIALE", 3000.0)]))
    # Le etichette qui sono in tondo: il maiuscoletto lo fa il CSS.
    metriche = {m.label: m.value for m in at.metric}
    assert metriche["Speso davvero (fatture)"] == "5.000,00 €"
    assert metriche["Ancora da sostenere (stime)"] == "3.000,00 €"


def test_lo_scostamento_e_una_percentuale_non_la_stessa_cifra_due_volte():
    """Valore grande e delta erano gli stessi euro; la percentuale — quella
    con cui lo storico tara gli imprevisti — non c'era.

    Serve un computo vero da confrontare: senza preventivo non esiste una
    percentuale, e la scheda scrive «—» (che è la cosa giusta).
    """
    at = _avvia(df_voci=_computo_da(10000.0),
                df_spese=pd.DataFrame([_spesa("🟡 LAVORI", 5000.0)]))
    scostamento = [m for m in at.metric
                   if m.label == "Scostamento sul preventivo"]
    assert scostamento, [m.label for m in at.metric]
    assert "-50,0 %" == scostamento[0].value
    assert "-5.000,00 €" == scostamento[0].delta


def test_senza_preventivo_lo_scostamento_non_inventa_una_percentuale():
    at = _avvia(df_spese=pd.DataFrame([_spesa("🟡 LAVORI", 5000.0)]))
    scostamento = [m for m in at.metric
                   if m.label == "Scostamento sul preventivo"]
    assert scostamento[0].value == "—"


# ------------------------------------------------ contratto e SAL

def test_il_registro_spese_non_si_chiama_costo_delloperazione():
    """ACQUISTO e AGENZIA qui dentro sono già contati nell'entry: due
    totali che si sovrappongono, e quello col nome più grosso era il meno
    vero dei due."""
    at = _avvia(df_spese=pd.DataFrame([_spesa("🔴 ACQUISTO", 20000.0)]))
    testo = _testi(at)
    assert "Totale del registro spese" in testo
    assert "Costi totali dell'operazione" not in testo


def test_ancora_da_pagare_dichiara_di_essere_il_residuo():
    """Senza extra sono lo stesso numero sotto due nomi, e due nomi sullo
    stesso numero si leggono come due conferme indipendenti."""
    at = _avvia(cant_contratto=60000.0, cant_extra=0.0,
                cant_sal=[{"percento": 20.0, "pagato": True},
                          {"percento": 80.0, "pagato": False}])
    etichette = [m.label for m in at.metric]
    assert any("= il residuo" in e for e in etichette), etichette


def test_con_gli_extra_ancora_da_pagare_torna_a_essere_se_stesso():
    at = _avvia(cant_contratto=60000.0, cant_extra=5000.0,
                cant_sal=[{"percento": 20.0, "pagato": True},
                          {"percento": 80.0, "pagato": False}])
    etichette = [m.label for m in at.metric]
    assert "Ancora da pagare" in etichette
    assert not any("= il residuo" in e for e in etichette)


def test_il_totale_a_fine_cantiere_non_si_chiama_totale_finale():
    """Nel computo «TOTALE FINALE» è la card d'ottone dei lavori."""
    at = _avvia(cant_contratto=60000.0,
                cant_sal=[{"percento": 100.0, "pagato": False}])
    etichette = [m.label for m in at.metric]
    assert "Totale a fine cantiere" in etichette
    assert "Totale finale" not in etichette


def test_aver_pagato_oltre_il_contratto_si_vede():
    """Quote che fanno 110 e tutte saldate: prima il residuo si fermava a
    zero e non lo diceva nessuno."""
    at = _avvia(cant_contratto=60000.0,
                cant_sal=[{"percento": 20.0, "pagato": True},
                          {"percento": 30.0, "pagato": True},
                          {"percento": 30.0, "pagato": True},
                          {"percento": 30.0, "pagato": True}])
    avvisi = "\n".join(a.value for a in at.warning)
    assert "6.000,00 € in più" in avvisi
    metriche = {m.label: m.value for m in at.metric}
    assert metriche["Residuo di contratto"] == "-6.000,00 €"
    assert metriche["Saldato"] == "66.000,00 €"
