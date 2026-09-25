"""Un comparabile salvato senza la spunta dell'ascensore si riapre.

Guardia contro un difetto che faceva cadere TUTTA la pagina (2026-09-23):
i progetti salvati prima che l'ascensore entrasse nella griglia hanno i
comparabili senza la chiave «ascensore». Al caricamento il reindex creava
la colonna tutta NaN — cioe' float — e il data_editor della scheda MCA,
che su quella colonna ha una casella di spunta, rifiutava il tipo con una
StreamlitAPIException. Lo stesso per le note, se nessun comparabile ne
aveva una. Non si vedeva un errore nella scheda: non si vedeva
piu' niente.

Qui il progetto si apre sul banco e la scheda MCA si calcola per intero.
"""
import pandas as pd
import pytest

import banco
import tabelle
from server.vista_bp import vista_bp

PROGETTO = {
    "progetto": {"nome": "Comparabili vecchi", "data": "2026-09-23"},
    "voci": [],
    "piante": [],
    "mca_comparabili": [{"nome": "C1", "prezzo": 250000, "mq": 90,
                         "condizioni": "Buone"}],
}


@pytest.fixture(scope="module")
def progetto_aperto():
    b = banco.Banco()
    b.carica(PROGETTO)
    return b


def test_la_scheda_si_calcola(progetto_aperto):
    assert vista_bp(progetto_aperto)


def test_la_spunta_mancante_torna_come_non_spuntata(progetto_aperto):
    righe = progetto_aperto.dati["mca_comparabili"]
    assert [r["ascensore"] for r in righe] == [False]
    # e il comparabile c'e' ancora, con i suoi numeri
    assert [(r["nome"], r["prezzo"]) for r in righe] == [("C1", 250000.0)]


@pytest.mark.parametrize("valori, attesi", [
    ([None, True, False], [False, True, False]),
    ([float("nan"), 1, 0], [False, True, False]),
])
def test_normalizzare_rende_booleana_la_spunta(valori, attesi):
    """NaN e None sono «non spuntato». bool(NaN) e' True: il fillna non
    e' un dettaglio, e' la differenza fra «senza ascensore» e «con»."""
    df = pd.DataFrame({"nome": ["A", "B", "C"], "ascensore": valori})
    df = tabelle.df_mca_normalizzato(df)
    assert df["ascensore"].dtype == bool
    assert df["ascensore"].tolist() == attesi
    assert list(df.columns) == tabelle.COLONNE_MCA


def test_normalizzare_non_lascia_float_le_colonne_di_testo():
    """Anche «note» mancante in tutte le righe faceva cadere la pagina:
    la colonna di testo, tutta NaN, arrivava all'editor come float."""
    df = tabelle.df_mca_normalizzato(pd.DataFrame([{"nome": "C1"}]))
    for col in tabelle.COLONNE_MCA:
        if col not in tabelle.COLONNE_MCA_NUM + tabelle.COLONNE_MCA_BOOL:
            assert df[col].dtype == object, col


def test_mca_vuoto_ha_la_spunta_booleana():
    assert tabelle.df_mca_vuoto()["ascensore"].dtype == bool
