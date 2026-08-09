"""Il PDF del computo: che esca, e che dentro ci sia quello che deve.

Il testo si rilegge con PyMuPDF (fitz), che il progetto ha già: così i test
controllano il contenuto del documento, non solo che il file esista.
"""
import fitz
import pytest

from stampa import pdf_computo

PROGETTO = {"nome": "Via Roma 12", "committente": "Resolve S.r.l.",
            "oggetto": "Ristrutturazione appartamento", "data": "09/08/2026"}

VOCI = [
    {"categoria": "Demolizioni", "codice": "1.01",
     "descrizione": "Demolizione pavimenti", "um": "m²",
     "quantita": 84.3, "prezzo": 100.0, "importo": 8430.0},
    {"categoria": "Demolizioni", "codice": "1.02",
     "descrizione": "Demolizione murature", "um": "m²",
     "quantita": 11.82, "prezzo": 100.0, "importo": 1182.0},
    {"categoria": "Ricostruzioni e ripristini", "codice": "2.10",
     "descrizione": "Posa pavimenti in gres", "um": "m²",
     "quantita": 88.52, "prezzo": 45.0, "importo": 3983.4},
]

TOTALI = {"somma": 13595.4, "imprevisti_pct": 5.0, "imprevisti": 679.77,
          "totale_lavori": 14275.17, "iva_pct": 10.0, "iva": 1427.52,
          "totale": 15702.69}


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
    assert "1.01" in testo
    assert "Demolizione pavimenti" in testo
    assert "8.430,00" in testo


def test_raggruppa_per_categoria():
    testo = _testo_del_pdf(pdf_computo(PROGETTO, VOCI, TOTALI))
    assert "DEMOLIZIONI" in testo
    assert "RICOSTRUZIONI E RIPRISTINI" in testo


def test_il_totale_finale_e_quello_che_si_paga():
    testo = _testo_del_pdf(pdf_computo(PROGETTO, VOCI, TOTALI))
    assert "15.702,69" in testo
    assert "IVA 10%" in testo


def test_il_computo_vuoto_lo_dice():
    testo = _testo_del_pdf(pdf_computo(PROGETTO, [], TOTALI))
    assert "vuoto" in testo.lower()


def test_progetto_senza_nome_non_lascia_il_titolo_in_bianco():
    testo = _testo_del_pdf(pdf_computo({}, VOCI, TOTALI))
    assert "senza nome" in testo.lower()


def test_appendice_del_libretto_misure():
    libretto = {"1.01": ([
        {"descrizione": "Soggiorno", "parti": 1, "lunghezza": 5.0,
         "larghezza": 4.0, "altezza": None, "quantita": 20.0},
        {"descrizione": "vano porta", "parti": -1, "lunghezza": 0.8,
         "larghezza": 2.1, "altezza": None, "quantita": -1.68},
    ], 18.32)}
    testo = _testo_del_pdf(pdf_computo(
        PROGETTO, VOCI, TOTALI, libretto=libretto,
        descrizioni={"1.01": "Demolizione pavimenti"}))
    assert "Libretto delle misure" in testo
    assert "Soggiorno" in testo
    assert "vano porta" in testo
    assert "18,320" in testo


def test_senza_libretto_niente_appendice():
    testo = _testo_del_pdf(pdf_computo(PROGETTO, VOCI, TOTALI))
    assert "Libretto delle misure" not in testo


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
