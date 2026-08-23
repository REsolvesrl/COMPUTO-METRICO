"""Le conversioni fra tabella e dati: vivevano nell'interfaccia, senza test.

Le regole che qui si controllano non sono formali: una cella vuota che
diventa 0 mette nel computo una quantità che nessuno ha deciso, e una
colonna di testo nata numerica fa rifiutare la tabella dall'editor.
"""
import pandas as pd
import pytest

import materiali
import merito
import tabelle


# ------------------------------------------------------- voci del computo

def test_df_vuoto_ha_le_colonne_e_i_tipi_giusti():
    df = tabelle.df_vuoto()
    assert list(df.columns) == tabelle.COLONNE
    assert df["descrizione"].dtype == object
    assert df["prezzo"].dtype == "float64"
    assert len(df) == 0


def test_voci_da_df_legge_le_righe_piene():
    df = pd.DataFrame([{"categoria": "Demolizioni", "codice": "1.01",
                        "descrizione": "Demolizione", "um": "m²",
                        "parti": 1.0, "lunghezza": 5.0, "larghezza": 4.0,
                        "altezza": None, "quantita_manuale": None,
                        "prezzo": 100.0}])
    voci = tabelle.voci_da_df(df)
    assert len(voci) == 1
    assert voci[0]["descrizione"] == "Demolizione"
    assert voci[0]["lunghezza"] == 5.0


def test_voci_da_df_le_celle_vuote_sono_None_non_zero():
    """Uno zero e' una quantita' decisa da qualcuno; il vuoto no."""
    df = pd.DataFrame([{"categoria": "X", "codice": "", "descrizione": "Voce",
                        "um": "m", "parti": None, "lunghezza": None,
                        "larghezza": None, "altezza": None,
                        "quantita_manuale": None, "prezzo": None}])
    voce = tabelle.voci_da_df(df)[0]
    assert voce["lunghezza"] is None
    assert voce["prezzo"] is None
    assert voce["codice"] is None          # stringa vuota = niente


def test_voci_da_df_salta_le_righe_del_tutto_vuote():
    df = tabelle.df_vuoto()
    df.loc[0] = [None] * len(tabelle.COLONNE)
    assert tabelle.voci_da_df(df) == []


# ------------------------------------------------------------------ spese

def test_cat_pulita_toglie_il_pallino():
    assert tabelle.cat_pulita("🟡 LAVORI") == "LAVORI"
    assert tabelle.cat_pulita("LAVORI") == "LAVORI"
    assert tabelle.cat_pulita(None) == ""


def test_cat_display_mette_il_pallino():
    assert tabelle.cat_display("LAVORI") == "🟡 LAVORI"
    assert tabelle.cat_display("🟡 LAVORI") == "🟡 LAVORI"   # non lo raddoppia


def test_cat_display_lascia_stare_le_categorie_sconosciute():
    assert tabelle.cat_display("PIPPO") == "PIPPO"


def test_categoria_fa_il_giro_completo_senza_sporcarsi():
    """Tabella → dati → tabella: nel JSON la categoria resta pulita."""
    righe = [{"importo": 100.0, "aliquota_iva": 22.0, "data": "01/01/2026",
              "nr_fattura": "1", "oggetto": "x", "categoria": "LAVORI",
              "note": ""}]
    df = tabelle.df_spese_da_righe(righe, tabelle.COLONNE_SPESE)
    assert df["categoria"][0] == "🟡 LAVORI"      # a video col pallino
    assert tabelle.spese_da_df(df)[0]["categoria"] == "LAVORI"   # nei dati no


def test_df_spese_colonna_di_testo_mancante_nasce_testo():
    """Una colonna di soli NaN diventa numerica e l'editor la rifiuta."""
    righe = [{"importo": 100.0, "aliquota_iva": 22.0, "oggetto": "x",
              "categoria": "LAVORI", "note": ""}]      # senza data/fattura
    df = tabelle.df_spese_da_righe(righe, tabelle.COLONNE_SPESE)
    assert df["data"].dtype == object
    assert df["data"][0] == ""


def test_df_spese_categoria_vuota_e_None_mai_stringa_vuota():
    """«» non e' tra le opzioni del menu: manda in crash l'editor."""
    df = tabelle.df_spese_da_righe([{"importo": 10.0}], tabelle.COLONNE_SPESE)
    assert df["categoria"][0] is None


def test_spese_da_df_salta_le_righe_senza_importo():
    df = tabelle.df_spese_da_righe(
        [{"importo": 100.0, "categoria": "LAVORI"}, {"oggetto": "vuota"}],
        tabelle.COLONNE_SPESE)
    assert len(tabelle.spese_da_df(df)) == 1


def test_spese_da_df_senza_categoria_finisce_in_altro():
    df = tabelle.df_spese_da_righe([{"importo": 100.0}],
                                   tabelle.COLONNE_SPESE)
    assert tabelle.spese_da_df(df)[0]["categoria"] == "ALTRO"


def test_spese_da_df_senza_iva_vale_zero_non_None():
    df = tabelle.df_spese_da_righe([{"importo": 100.0}],
                                   tabelle.COLONNE_SPESE)
    assert tabelle.spese_da_df(df)[0]["aliquota_iva"] == 0.0


def test_il_fornitore_e_una_colonna_sua():
    """Stava dentro «oggetto»: cosi' non si poteva ne' ordinare ne' leggere
    a colpo d'occhio chi ti ha mandato la fattura."""
    assert "fornitore" in tabelle.COLONNE_SPESE
    df = tabelle.df_spese_da_righe(
        [{"importo": 100.0, "fornitore": "ACME S.r.l.",
          "oggetto": "Materiale edile"}], tabelle.COLONNE_SPESE)
    riga = tabelle.spese_da_df(df)[0]
    assert riga["fornitore"] == "ACME S.r.l."
    assert riga["oggetto"] == "Materiale edile"


def test_i_progetti_vecchi_non_hanno_il_fornitore_e_va_bene():
    """La colonna nasce vuota, non fa cadere niente: i salvataggi fatti
    prima non la conoscono."""
    df = tabelle.df_spese_da_righe([{"importo": 100.0, "oggetto": "Vecchia"}],
                                   tabelle.COLONNE_SPESE)
    assert tabelle.spese_da_df(df)[0]["fornitore"] == ""


def test_l_iva_calcolata_non_e_un_dato_da_salvare():
    """Si ricava da importo e aliquota: nel JSON del progetto non ci va, e
    se torna indietro col ritorno di una tabella si toglie."""
    assert tabelle.COLONNA_IVA_EUR not in tabelle.COLONNE_SPESE
    df = pd.DataFrame([{"importo": 122.0, tabelle.COLONNA_IVA_EUR: 22.0}])
    assert tabelle.COLONNA_IVA_EUR not in tabelle.senza_iva_derivata(df).columns
    assert tabelle.COLONNA_IVA_EUR not in tabelle.spese_da_df(df)[0]
    # e togliere una colonna che non c'e' non e' un errore
    tabelle.senza_iva_derivata(tabelle.df_spese_vuoto())


def test_registro_previsioni_ha_le_sue_colonne():
    df = tabelle.df_spese_vuoto(tabelle.COLONNE_SPESE_PREV)
    assert list(df.columns) == tabelle.COLONNE_SPESE_PREV
    assert "nr_fattura" not in df.columns


# -------------------------------------------------------------- materiali

def test_materiali_vuoto_ha_le_colonne_e_i_tipi_giusti():
    df = tabelle.df_materiali_vuoto()
    assert list(df.columns) == tabelle.COLONNE_MATERIALI
    assert df["descrizione"].dtype == object
    assert df["prezzo"].dtype == "float64"
    assert len(df) == 0


def test_materiali_e_la_descrizione_a_fare_la_riga():
    """L'allegato firmato e' un elenco di NOMI: di prezzi non ne ha nemmeno
    uno, e pretenderne uno butterebbe via l'intero documento."""
    df = tabelle.df_materiali_da_righe([
        {"capitolo": "BAGNO", "descrizione": "BOX DOCCIA"},
        {"capitolo": "BAGNO", "descrizione": "", "prezzo": 100.0},
    ])
    righe = tabelle.materiali_da_df(df)
    assert len(righe) == 1
    assert righe[0]["descrizione"] == "BOX DOCCIA"


def test_materiali_prezzo_e_quantita_vuoti_restano_None():
    """Uno zero direbbe «gratis» e si sommerebbe agli altri."""
    df = tabelle.df_materiali_da_righe(
        [{"descrizione": "BOX DOCCIA", "quantita": None, "prezzo": None}])
    riga = tabelle.materiali_da_df(df)[0]
    assert riga["prezzo"] is None
    assert riga["quantita"] is None


def test_materiali_capitolo_e_stato_vuoti_non_sono_stringa_vuota():
    """Sono tendine, e "" non e' fra le opzioni: il data_editor va in
    errore nel browser. Stesso inciampo gia' preso con le spese."""
    df = tabelle.df_materiali_da_righe([{"descrizione": "PORTE"}])
    assert df["capitolo"].iloc[0] is None
    assert df["stato"].iloc[0] is None


def test_materiali_i_predefiniti_arrivano_al_salvataggio():
    df = tabelle.df_materiali_da_righe([{"descrizione": "PORTE"}])
    riga = tabelle.materiali_da_df(df)[0]
    assert riga["capitolo"] == materiali.CAPITOLO_PREDEFINITO
    assert riga["stato"] == materiali.STATO_PREDEFINITO


def test_materiali_giro_completo():
    partenza = [{"capitolo": "PAVIMENTI", "descrizione": "GRES", "um": "m²",
                 "quantita": 94.71, "prezzo": 22.0, "fornitore": "Rossi",
                 "stato": "Consegnato", "note": "posa a correre"}]
    assert tabelle.materiali_da_df(
        tabelle.df_materiali_da_righe(partenza)) == partenza


def test_senza_importo_derivato_toglie_la_colonna_calcolata():
    df = tabelle.df_materiali_da_righe([{"descrizione": "GRES",
                                         "prezzo": 22.0}])
    df[tabelle.COLONNA_IMPORTO_MAT] = [22.0]
    assert tabelle.COLONNA_IMPORTO_MAT not in tabelle.senza_importo_derivato(
        df).columns


# ------------------------------------------------------- comparabili (MCA)

def test_mca_giro_completo():
    """Un comparabile col solo coefficiente a mano — com'erano tutti prima
    che la griglia esistesse — torna indietro identico, e le voci della
    griglia che non ha restano vuote invece di inventarsi un valore."""
    righe = [{"nome": "Via Roma 5", "prezzo": 200000.0, "mq": 90.0,
              "coeff": 1.05, "note": "ristrutturato"}]
    df = pd.DataFrame(righe)
    tornate = tabelle.mca_da_df(df)
    assert len(tornate) == 1
    for chiave, valore in righe[0].items():
        assert tornate[0][chiave] == valore
    assert all(tornate[0][campo] is None for campo in merito.CAMPI)


def test_mca_giro_completo_con_la_griglia():
    righe = [{"nome": "C1", "prezzo": 300000.0, "mq": 80.0,
              "stato_edificio": "Normale", "eta_edificio": "20-40 anni",
              "stato_unita": "Finemente ristrutturato",
              "finiture": "Civili", "piano": "Primo",
              "ascensore": True, "balconi": "Sì", "giardino": "No",
              "terrazzo": "Sì", "luce_vista": "Nella media",
              "spazi_comuni": "Assenti", "parcheggio": "Posto auto per UI",
              "riscaldamento": "Autonomo",
              "coeff": None, "note": ""}]
    tornate = tabelle.mca_da_df(pd.DataFrame(righe))
    assert tornate[0]["ascensore"] is True
    assert tornate[0]["piano"] == "Primo"
    assert tornate[0]["coeff"] is None
    # e da lì esce il coefficiente, senza che nessuno lo scriva a mano
    esito = merito.coefficiente_effettivo(
        merito.scelte_da_riga(tornate[0]), tornate[0]["coeff"])
    assert esito["fonte"] == "griglia"
    assert esito["totale"] == pytest.approx(1.282701, abs=1e-6)


def test_mca_la_sola_spunta_dell_ascensore_non_fa_una_riga():
    """La casella nasce a False in ogni riga nuova: senza esclusione una
    riga mai toccata diventerebbe un comparabile vuoto ma contato."""
    df = pd.DataFrame([{**{c: None for c in tabelle.COLONNE_MCA},
                        "ascensore": False}])
    assert tabelle.mca_da_df(df) == []


def test_mca_vuoto_ha_i_tipi_giusti():
    df = tabelle.df_mca_vuoto()
    assert df["prezzo"].dtype == "float64"
    assert df["nome"].dtype == object
    assert list(df.columns) == tabelle.COLONNE_MCA


@pytest.mark.parametrize("funzione", [tabelle.voci_da_df,
                                      tabelle.spese_da_df,
                                      tabelle.materiali_da_df,
                                      tabelle.mca_da_df])
def test_una_tabella_vuota_non_da_righe(funzione):
    assert funzione(pd.DataFrame()) == []
