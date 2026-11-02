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
    # fornitore e descrizione stanno in due colonne, non incollati in una
    assert d["fornitore"] == "ACME Edilizia S.r.l."
    assert d["oggetto"] == "Materiale edile"
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
    assert "Leroy Merlin Italia" in d["fornitore"]


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
    # nessun numero-spazzatura: si dichiara di non averlo trovato
    assert d["nr_fattura"] == "//"


# ------------------------------------------------- il numero della fattura

TOTALE = "Totale documento\n1.220,00 €\n"


def _numero_letto(intestazione):
    return dati_da_pdf_testo(intestazione + "\n" + TOTALE)["nr_fattura"]


def test_numero_dalle_diciture_del_foglio_sdi():
    """Il «nr. X del …» non è l'unica forma in cui i PDF scrivono il numero:
    prima ne veniva riconosciuta una sola, e su tutto il resto la colonna
    restava vuota senza spiegare perché."""
    assert _numero_letto("Numero documento\n412616027839") == "412616027839"
    assert _numero_letto("Numero documento: 55/2026") == "55/2026"
    assert _numero_letto("Numero del documento 2026-A/17") == "2026-A/17"
    assert _numero_letto("Numero fattura  88/B") == "88/B"
    assert _numero_letto("Fattura n. 55/2026") == "55/2026"
    assert _numero_letto("FATTURA nr 7 del 03/02/2026") == "7"


def test_numero_non_trovato_si_dichiara():
    """Una casella vuota non distingue «non ce l'ha» da «non l'ho letto»."""
    assert _numero_letto("Ricevuta di pagamento") == "//"


def test_niente_numeri_inventati():
    """Un «n. 3» qualunque in mezzo al testo non è un numero di fattura:
    meglio il ripiego che un dato pescato a caso."""
    assert _numero_letto("Pagamento in n. 3 rate mensili") == "//"
    assert _numero_letto("Beneficiario del pagamento: Deal srls") == "//"


def test_il_fornitore_non_sta_piu_dentro_l_oggetto():
    """Stavano incollati («studiokennedy snc — PAGAMENTO MEDIAZIONE…») e il
    nome restava prigioniero di una cella di testo lunga: niente ordinamento
    per fornitore, e la descrizione troncata dove inizia a dire qualcosa."""
    d = dati_da_pdf_testo(PDF_FATTURA)
    assert "—" not in d["oggetto"]
    assert d["fornitore"] and d["fornitore"] not in d["oggetto"]


def test_il_numero_xml_batte_ogni_regola_sul_testo():
    """Nell'XML il campo è strutturato: si legge, non si indovina."""
    assert dati_da_xml(XML_FATTURA)["nr_fattura"] == "123/2026"


# ------------------------------------------------- la ritenuta d'acconto

# La parcella di un notaio, sul modello di quella vera della Migliarina:
# imposte anticipate fuori campo IVA (art. 15), competenze al 22% con la
# cassa, e un «Totale documento» che e' gia' il NETTO della ritenuta.
PDF_NOTAIO = """PARCELLA
nr. 1407 del 15/10/2026
FORNITORE
Notaio Mario Rossi
RITENUTA
Ritenuta d'acconto (persone fisiche), Aliquota ritenuta 20%, Causale pagamento
A
RIEPILOGO IVA
Totale imponibile \ Importo
1.619,61 €
Totale escluso IVA (N1)
12.748,00 €
Totale IVA
356,31 €
Totale documento
14.400,00 €
Ritenuta d'acconto (persone fisiche)
-323,92 €
"""


def test_la_ritenuta_del_notaio_rientra_nel_costo():
    d = dati_da_pdf_testo(PDF_NOTAIO)
    # 14.400 al notaio + 323,92 all'Erario con l'F24
    assert d["importo"] == 14723.92
    assert "323,92" in d["note"] and "F24" in d["note"]


def test_le_imposte_anticipate_entrano_nell_aliquota_media():
    # prima l'imponibile «\ Importo» non si leggeva e l'IVA usciva a zero;
    # contando solo i 1.619,61 imponibili sarebbe uscita al 22% su tutto
    d = dati_da_pdf_testo(PDF_NOTAIO)
    assert d["aliquota_iva"] == 2.5


def test_un_totale_gia_lordo_non_prende_la_ritenuta_due_volte():
    lordo = PDF_NOTAIO.replace("14.400,00", "14.723,92")
    assert dati_da_pdf_testo(lordo)["importo"] == 14723.92


def test_netto_a_pagare_senza_riepilogo_si_rifa_lordo():
    testo = """FATTURA
nr. 8/2026 del 02/03/2026
Netto a pagare
800,00 €
Ritenuta d'acconto
-200,00 €
"""
    assert dati_da_pdf_testo(testo)["importo"] == 1000.0


def test_senza_ritenuta_niente_nota():
    assert dati_da_pdf_testo(PDF_FATTURA)["note"] == ""


def _xml_professionista(totale):
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<p:FatturaElettronica xmlns:p="http://x">
  <FatturaElettronicaBody>
    <DatiGenerali><DatiGeneraliDocumento>
      <TipoDocumento>TD06</TipoDocumento><Data>2026-10-15</Data>
      <Numero>1407</Numero>
      <DatiRitenuta><TipoRitenuta>RT01</TipoRitenuta>
        <ImportoRitenuta>323.92</ImportoRitenuta>
        <AliquotaRitenuta>20.00</AliquotaRitenuta></DatiRitenuta>
      <ImportoTotaleDocumento>{totale}</ImportoTotaleDocumento>
    </DatiGeneraliDocumento></DatiGenerali>
    <DatiBeniServizi>
      <DatiRiepilogo><AliquotaIVA>22.00</AliquotaIVA>
        <ImponibileImporto>1619.61</ImponibileImporto>
        <Imposta>356.31</Imposta></DatiRiepilogo>
      <DatiRiepilogo><AliquotaIVA>0.00</AliquotaIVA><Natura>N1</Natura>
        <ImponibileImporto>12748.00</ImponibileImporto>
        <Imposta>0.00</Imposta></DatiRiepilogo>
    </DatiBeniServizi>
  </FatturaElettronicaBody>
</p:FatturaElettronica>"""


def test_xml_col_totale_netto_rimette_la_ritenuta():
    d = dati_da_xml(_xml_professionista("14400.00"))
    assert d["importo"] == 14723.92
    assert "F24" in d["note"]


def test_xml_col_totale_lordo_resta_com_e():
    assert dati_da_xml(_xml_professionista("14723.92"))["importo"] == 14723.92


# ------------------------------------------------------- le autofatture

# Sul modello dell'autofattura vera della Migliarina: dieci finestre da un
# fornitore polacco, acquisto intra-UE. L'IVA si integra: si versa e si
# detrae insieme, e al fornitore va solo l'imponibile.
PDF_AUTOFATTURA = """AUTOFATTURA
nr. AF01 66/26 del 02/11/2026
Emessa da: Cessionario / committente
FORNITORE
Fornitore Estero Sp. z o.o.
RIEPILOGO IVA
Totale imponibile
1.626,22 €
Totale IVA
357,77 €
Totale documento
1.983,99 €
Netto a pagare
1.983,99 €
"""


def test_l_autofattura_entra_per_il_solo_imponibile():
    d = dati_da_pdf_testo(PDF_AUTOFATTURA)
    assert d["importo"] == 1626.22
    assert d["aliquota_iva"] == 0.0
    assert "357,77" in d["note"]


def test_il_numero_dell_autofattura_comincia_con_le_lettere():
    assert dati_da_pdf_testo(PDF_AUTOFATTURA)["nr_fattura"] == "AF01 66/26"


def test_una_fattura_normale_tiene_la_sua_iva():
    d = dati_da_pdf_testo(PDF_FATTURA)
    assert d["importo"] == 122.0 and d["aliquota_iva"] == 22.0


def _xml_tipo(tipo):
    return XML_FATTURA.replace("<TipoDocumento>TD01</TipoDocumento>",
                               f"<TipoDocumento>{tipo}</TipoDocumento>")


def test_xml_delle_integrazioni_a_iva_zero():
    for tipo in ("TD16", "TD17", "TD18", "TD19"):
        d = dati_da_xml(_xml_tipo(tipo))
        assert (d["importo"], d["aliquota_iva"]) == (100.0, 0.0), tipo


def test_xml_della_regolarizzazione_tiene_l_iva():
    # TD20: l'IVA chi compra la versa davvero all'Erario
    d = dati_da_xml(_xml_tipo("TD20"))
    assert (d["importo"], d["aliquota_iva"]) == (122.0, 22.0)
