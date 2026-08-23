"""Il PDF del computo: che esca, e che dentro ci sia quello che deve.

Il testo si rilegge con PyMuPDF (fitz), che il progetto ha già: così i test
controllano il contenuto del documento, non solo che il file esista.
"""
import fitz
import pytest

import materiali
from stampa import pdf_computo, pdf_materiali

PROGETTO = {"nome": "Via Roma 12", "committente": "Resolve S.r.l.",
            "oggetto": "Ristrutturazione appartamento", "data": "09/08/2026"}

VOCI = [
    {"categoria": "Demolizioni", "codice": "2.1",
     "descrizione": "Demolizione pavimenti", "um": "m²",
     "quantita": 84.3, "prezzo": 100.0, "importo": 8430.0},
    {"categoria": "Demolizioni", "codice": "2.2",
     "descrizione": "Demolizione murature", "um": "m²",
     "quantita": 11.82, "prezzo": 100.0, "importo": 1182.0},
    {"categoria": "Ricostruzioni e ripristini", "codice": "3.10",
     "descrizione": "Posa pavimenti in gres", "um": "m²",
     "quantita": 88.52, "prezzo": 45.0, "importo": 3983.4},
]

TOTALI = {"somma": 13595.4, "totale_lavori": 13595.4, "iva_pct": 10.0,
          "iva": 1359.54, "totale": 14954.94}


def _testo_del_pdf(byte):    # nome «privato»: pytest raccoglie
    # come test qualunque funzione che cominci per «test»
    documento = fitz.open(stream=byte, filetype="pdf")
    return "\n".join(pagina.get_text() for pagina in documento)


def test_produce_un_pdf_vero():
    byte = pdf_computo(PROGETTO, VOCI, TOTALI)
    assert byte[:5] == b"%PDF-"
    assert len(byte) > 1000


def test_riporta_i_dati_del_progetto():
    testo = _testo_del_pdf(pdf_computo(PROGETTO, VOCI, TOTALI))
    assert "Via Roma 12" in testo
    assert "Resolve S.r.l." in testo
    assert "Ristrutturazione appartamento" in testo
    assert "09/08/2026" in testo


def test_riporta_le_voci_con_codice_e_importo():
    testo = _testo_del_pdf(pdf_computo(PROGETTO, VOCI, TOTALI))
    assert "2.1" in testo
    assert "Demolizione pavimenti" in testo
    assert "8.430,00" in testo


def test_raggruppa_per_categoria():
    testo = _testo_del_pdf(pdf_computo(PROGETTO, VOCI, TOTALI))
    assert "DEMOLIZIONI" in testo
    assert "RICOSTRUZIONI E RIPRISTINI" in testo


def test_il_totale_finale_e_quello_che_si_paga():
    testo = _testo_del_pdf(pdf_computo(PROGETTO, VOCI, TOTALI))
    assert "14.954,94" in testo
    assert "IVA 10%" in testo


def test_il_computo_consegnato_non_porta_riserve():
    """Il PDF va all'impresa: sono i lavori computati, non i lavori più un
    accantonamento che riguarda chi paga. La riserva sta nel business plan."""
    testo = _testo_del_pdf(pdf_computo(PROGETTO, VOCI, TOTALI))
    assert "mprevisti" not in testo


def test_il_computo_vuoto_lo_dice():
    testo = _testo_del_pdf(pdf_computo(PROGETTO, [], TOTALI))
    assert "vuoto" in testo.lower()


def test_progetto_senza_nome_non_lascia_il_titolo_in_bianco():
    testo = _testo_del_pdf(pdf_computo({}, VOCI, TOTALI))
    assert "senza nome" in testo.lower()


def test_le_tinte_delle_categorie_non_fanno_saltare_la_stampa():
    """Anche una tinta chiarissima: il testo si adatta, non si rompe."""
    byte = pdf_computo(PROGETTO, VOCI, TOTALI,
                       tinte={"Demolizioni": "#E57373",
                              "Ricostruzioni e ripristini": "#FFFFFF"})
    assert byte[:5] == b"%PDF-"


def test_ogni_pagina_e_numerata():
    testo = _testo_del_pdf(pdf_computo(PROGETTO, VOCI * 40, TOTALI))
    assert "pagina 1" in testo
    assert "pagina 2" in testo


@pytest.mark.parametrize("simbolo", ["€", "à", "²"])
def test_i_caratteri_italiani_arrivano_nel_pdf(simbolo):
    """Euro, accenti e metri quadri: senza font scaricati dalla rete."""
    voci = [{"categoria": "Prova", "codice": "9.99",
             "descrizione": f"Voce con {simbolo} dentro", "um": "m²",
             "quantita": 1.0, "prezzo": 1.0, "importo": 1.0}]
    testo = _testo_del_pdf(pdf_computo(PROGETTO, voci, TOTALI))
    assert simbolo in testo


# ------------------- il foglio per le imprese: le stesse opere, nessun prezzo

def test_senza_prezzi_restano_lavorazioni_e_quantita():
    """E' il foglio su cui l'impresa scrive la SUA offerta."""
    testo = _testo_del_pdf(pdf_computo(PROGETTO, VOCI, TOTALI,
                                       con_prezzi=False))
    assert "Demolizione murature" in testo
    assert "11,82" in testo          # la quantita' c'e'
    assert "Codice" in testo and "U.M." in testo


def test_senza_prezzi_le_caselle_da_riempire_ci_sono():
    """Le colonne del prezzo e dell'importo restano, e con loro la coda dei
    conti: l'impresa deve poter mettere i suoi prezzi e fare la somma."""
    testo = _testo_del_pdf(pdf_computo(PROGETTO, VOCI, TOTALI,
                                       con_prezzi=False))
    assert "Prezzo" in testo and "Importo" in testo
    assert "Totale demolizioni" in testo
    assert "TOTALE (IVA inclusa)" in testo


def test_senza_prezzi_non_esce_nessuna_cifra_in_euro():
    """Un prezzo gia' stampato sopra non e' una richiesta di preventivo, e'
    una proposta — e quello che torna indietro non e' piu' un confronto.
    Le caselle ci sono, i numeri dentro no."""
    testo = _testo_del_pdf(pdf_computo(PROGETTO, VOCI, TOTALI,
                                       con_prezzi=False))
    assert "€" not in testo
    for cifra in ("13.595,40", "1.359,54", "14.954,94", "100,00"):
        assert cifra not in testo, cifra


def test_col_prezzi_i_totali_ci_sono_ancora():
    testo = _testo_del_pdf(pdf_computo(PROGETTO, VOCI, TOTALI))
    assert "Prezzo" in testo and "Importo" in testo
    assert "TOTALE (IVA inclusa)" in testo


# ------------------------------- la coda: la clausola e le due firme

def test_la_nota_della_tolleranza_chiude_il_computo():
    """E' la clausola che regge il totale: chi firma la sta accettando
    insieme alla cifra."""
    testo = _testo_del_pdf(pdf_computo(PROGETTO, VOCI, TOTALI))
    assert "tolleranza massima del 10%" in testo
    assert "riquadratura spallette" in testo


def test_senza_importi_niente_clausola_sull_importo():
    """Dove il totale e' una casella da riempire, la tolleranza sarebbe una
    condizione su una cifra che ancora non esiste — e la scrive l'impresa,
    non noi."""
    testo = _testo_del_pdf(pdf_computo(PROGETTO, VOCI, TOTALI,
                                       con_prezzi=False))
    assert "tolleranza" not in testo


def test_il_gruppo_firma_c_e_in_tutt_e_due():
    for con_prezzi in (True, False):
        testo = _testo_del_pdf(pdf_computo(PROGETTO, VOCI, TOTALI,
                                           con_prezzi=con_prezzi))
        assert "PER ACCETTAZIONE:" in testo, con_prezzi
        assert "Resolve S.r.l." in testo, con_prezzi
        # due righe di penna: una per parte
        assert testo.count("_" * 20) >= 2, con_prezzi


def test_il_posto_dell_impresa_resta_vuoto():
    """Il nome se lo scrive lei: finche' non firma non sappiamo quale sia."""
    testo = _testo_del_pdf(pdf_computo(PROGETTO, VOCI, TOTALI))
    # l'unico nome stampato e' quello del committente
    assert testo.count("Resolve S.r.l.") == 2   # cartiglio + firma


# ------------------------------------------- allegato 1: i materiali

MATERIALI = [
    {"capitolo": "BAGNO", "descrizione": "PIATTO DOCCIA",
     "quantita": 1.0, "fornitore": "Ceramiche Rossi",
     "link": "https://esempio.it/piatto-doccia", "stato": "Ordinato",
     "note": ""},
    {"capitolo": "BAGNO", "descrizione": "BOX DOCCIA",
     "quantita": None, "fornitore": "", "link": "", "stato": "Da ordinare",
     "note": ""},
    {"capitolo": "IMPIANTO RISCALDAMENTO",
     "descrizione": "UNITA INTERNA + ESTERNA CLIMA CANALIZZATO",
     "quantita": 1.0, "fornitore": "", "link": "", "stato": "Da ordinare",
     "note": "Si fornisce inoltre: plenum coibentato, collarini."},
]

PROGETTO_FIRMA = {**PROGETTO, "luogo": "La Spezia"}


def test_allegato_materiali_e_un_pdf_vero():
    byte = pdf_materiali(PROGETTO_FIRMA, MATERIALI)
    assert byte[:5] == b"%PDF-"


def test_allegato_dice_che_documento_e():
    testo = _testo_del_pdf(pdf_materiali(PROGETTO_FIRMA, MATERIALI))
    assert "ALLEGATO 1 AL COMPUTO METRICO" in testo
    assert "Elenco materiali acquistati cura Committente" in testo


def test_allegato_raggruppa_per_capitolo():
    testo = _testo_del_pdf(pdf_materiali(PROGETTO_FIRMA, MATERIALI))
    assert "BAGNO" in testo
    assert "IMPIANTO RISCALDAMENTO" in testo
    assert "PIATTO DOCCIA" in testo


def test_l_allegato_non_porta_nessuna_cifra():
    """Elenca le forniture che restano fuori dall'appalto, non quanto
    costano: e' cosi' che e' fatto il foglio vero."""
    testo = _testo_del_pdf(pdf_materiali(PROGETTO_FIRMA, MATERIALI))
    assert "€" not in testo
    assert "TOTALE" not in testo.upper().replace("COMPUTO METRICO", "")


def test_l_allegato_non_ha_la_colonna_um():
    """Sul foglio firmato non compilava mai: e' spazio chiesto a vuoto."""
    testo = _testo_del_pdf(pdf_materiali(PROGETTO_FIRMA, MATERIALI))
    assert "U.M." not in testo


def test_gli_appunti_di_chi_compra_restano_fuori():
    """Fornitore, link e stato dell'ordine sono roba tua: questo foglio lo
    firma l'impresa, e da chi compri non la riguarda."""
    testo = _testo_del_pdf(pdf_materiali(PROGETTO_FIRMA, MATERIALI))
    assert "Ceramiche Rossi" not in testo
    assert "esempio.it" not in testo
    assert "Ordinato" not in testo


def test_la_quantita_che_manca_non_diventa_uno_stampato():
    """Sul foglio una quantita' non scritta resta non scritta."""
    testo = _testo_del_pdf(pdf_materiali(
        PROGETTO_FIRMA, [{"capitolo": "BAGNO", "descrizione": "BOX DOCCIA",
                          "quantita": None}]))
    assert "1,00" not in testo


def test_la_nota_diventa_un_asterisco_e_una_riga_in_fondo():
    testo = _testo_del_pdf(pdf_materiali(PROGETTO_FIRMA, MATERIALI))
    assert "UNITA INTERNA + ESTERNA CLIMA CANALIZZATO *" in testo
    assert "* Si fornisce inoltre: plenum coibentato" in testo


def test_allegato_porta_la_clausola_e_le_firme():
    testo = _testo_del_pdf(pdf_materiali(PROGETTO_FIRMA, MATERIALI))
    assert "a cura e spese del Committente" in testo
    assert "PER ACCETTAZIONE:" in testo
    assert "Resolve S.r.l." in testo


def test_allegato_porta_luogo_e_data():
    testo = _testo_del_pdf(pdf_materiali(PROGETTO_FIRMA, MATERIALI))
    assert "La Spezia, lì 09/08/2026" in testo


def test_senza_luogo_resta_la_data():
    """I progetti salvati prima non hanno il luogo: il foglio si firma lo
    stesso, e la data e' il minimo che deve portare."""
    testo = _testo_del_pdf(pdf_materiali(PROGETTO, MATERIALI))
    assert "lì 09/08/2026" in testo


def test_l_elenco_standard_si_stampa_tutto():
    """Il giro che fa un progetto nuovo: le voci di partenza, sul foglio."""
    testo = _testo_del_pdf(
        pdf_materiali(PROGETTO_FIRMA, materiali.elenco_standard()))
    for attesa in ("PIATTO DOCCIA", "MANIGLIE", "LANA DI ROCCIA",
                   "CLIMATIZZATORE MOD. UNICO TWIN"):
        assert attesa in testo, attesa


def test_allegato_vuoto_lo_dice():
    testo = _testo_del_pdf(pdf_materiali(PROGETTO_FIRMA, []))
    assert "Nessun materiale elencato" in testo


def test_il_computo_normale_non_e_cambiato():
    """L'occhiello e' nuovo, ma il computo non ne ha nessuno: la sua
    testata deve restare quella di prima."""
    testo = _testo_del_pdf(pdf_computo(PROGETTO, VOCI, TOTALI))
    assert "Computo metrico estimativo" in testo
    assert "ALLEGATO" not in testo
