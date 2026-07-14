from fattura import (
    _aliquota,
    _norma_data,
    _num_it,
    dati_da_pdf_testo,
    dati_da_xml,
)


# ---------------------------------------------------------------- utilità

def test_num_it():
    assert _num_it("-1.234,56") == -1234.56
    assert _num_it("23,72") == 23.72
    assert _num_it("1.000,00") == 1000.0
    assert _num_it("-23,72 €") == -23.72
    assert _num_it("") is None
    assert _num_it(None) is None


def test_norma_data():
    assert _norma_data("2026-07-08") == "08/07/2026"
    assert _norma_data("8/7/2026") == "08/07/2026"
    assert _norma_data("") == ""


def test_aliquota_singola_pulita():
    # 100 imponibile, 22 imposta -> 22% esatti
    assert _aliquota(100.0, 22.0) == 22.0
    assert _aliquota(100.0, 10.0) == 10.0


def test_aliquota_mista_effettiva():
    # nota di credito: imponibile -22,04, imposta -1,68 -> 7,6%
    assert _aliquota(-22.04, -1.68) == 7.6


# ---------------------------------------------------------------- XML

XML_FATTURA = """<?xml version="1.0" encoding="UTF-8"?>
<p:FatturaElettronica xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2">
  <FatturaElettronicaHeader>
    <CedentePrestatore><DatiAnagrafici><Anagrafica>
      <Denominazione>ACME Edilizia S.r.l.</Denominazione>
    </Anagrafica></DatiAnagrafici></CedentePrestatore>
  </FatturaElettronicaHeader>
  <FatturaElettronicaBody>
    <DatiGenerali><DatiGeneraliDocumento>
      <TipoDocumento>TD01</TipoDocumento>
      <Data>2026-01-15</Data>
      <Numero>123/2026</Numero>
      <ImportoTotaleDocumento>122.00</ImportoTotaleDocumento>
    </DatiGeneraliDocumento></DatiGenerali>
    <DatiBeniServizi>
      <DettaglioLinee><Descrizione>Materiale edile</Descrizione></DettaglioLinee>
      <DatiRiepilogo>
        <AliquotaIVA>22.00</AliquotaIVA>
        <ImponibileImporto>100.00</ImponibileImporto>
        <Imposta>22.00</Imposta>
      </DatiRiepilogo>
    </DatiBeniServizi>
  </FatturaElettronicaBody>
</p:FatturaElettronica>"""


def test_dati_da_xml_fattura():
    d = dati_da_xml(XML_FATTURA)
    assert d["importo"] == 122.0
    assert d["aliquota_iva"] == 22.0
    assert d["data"] == "15/01/2026"
    assert d["nr_fattura"] == "123/2026"
    assert d["oggetto"] == "ACME Edilizia S.r.l. — Materiale edile"
    assert d["note"] == ""


def test_dati_da_xml_nota_credito():
    xml = XML_FATTURA.replace("TD01", "TD04").replace(
        "<ImportoTotaleDocumento>122.00", "<ImportoTotaleDocumento>-122.00")
    d = dati_da_xml(xml)
    assert d["importo"] == -122.0
    assert d["note"] == "Nota di credito"


def test_dati_da_xml_non_valido():
    assert dati_da_xml(b"non sono xml") is None


# ---------------------------------------------------------------- PDF (testo)

# testo stile foglio SdI, aliquota unica
PDF_FATTURA = """FATTURA
nr. 55/2026 del 03/02/2026
FORNITORE
Leroy Merlin Italia
CLIENTE
RESOLVE SRL
Totale imponibile
100,00 €
Totale IVA
22,00 €
Totale documento
122,00 €
"""

# testo della nota di credito reale (aliquote miste)
PDF_NOTA = """NOTA DI CREDITO
nr. 412616027839 del 08/07/2026
FORNITORE
HERA COMM S.p.A.
Totale imponibile
-22,04 €
Totale IVA
-1,68 €
Totale documento
-23,72 €
"""


def test_dati_da_pdf_fattura_semplice():
    d = dati_da_pdf_testo(PDF_FATTURA)
    assert d["nr_fattura"] == "55/2026"
    assert d["data"] == "03/02/2026"
    assert d["importo"] == 122.0
    assert d["aliquota_iva"] == 22.0
    assert "Leroy Merlin Italia" in d["oggetto"]


def test_dati_da_pdf_nota_credito():
    d = dati_da_pdf_testo(PDF_NOTA)
    assert d["nr_fattura"] == "412616027839"
    assert d["data"] == "08/07/2026"
    assert d["importo"] == -23.72
    assert d["aliquota_iva"] == 7.6


def test_dati_da_pdf_non_riconosciuto():
    assert dati_da_pdf_testo("testo qualunque senza campi") is None
    assert dati_da_pdf_testo("") is None


def test_dati_da_pdf_bonifico_non_e_fattura():
    # un bonifico ha "del" ma NESSUN importo totale riconoscibile: niente dati
    # (prima si estraeva spazzatura tipo nr_fattura="eficiario")
    testo = ("Disposizione di bonifico\n"
             "Beneficiario del pagamento: Deal srls\n"
             "IBAN IT60X...\nImporto 18.040,00 EUR\n")
    assert dati_da_pdf_testo(testo) is None


def test_dati_da_pdf_numero_deve_iniziare_con_cifra():
    # "beneficiario del" non deve diventare un numero fattura
    testo = ("FATTURA\nProforma numero del cliente\n"
             "Totale documento\n100,00 €\n")
    d = dati_da_pdf_testo(testo)
    assert d is not None            # c'è il totale
    assert d["nr_fattura"] == ""    # ma nessun numero-spazzatura
