"""Estrazione dei dati di una fattura per auto-compilare le spese sostenute.

Due strade, entrambe senza servizi esterni (tutto in locale):

- **XML** della fattura elettronica (FatturaPA): i campi sono strutturati, si
  leggono con precisione (numero, data, imponibile, IVA, totale, fornitore).
- **PDF di cortesia** generato dal foglio di stile SdI: si lavora sul testo
  estratto (da PyMuPDF, a monte) con alcune regole; funziona bene sui PDF
  "stile SdI", best-effort sugli altri (i campi non trovati restano vuoti).

Le funzioni qui sono pure e testabili: ricevono già i byte dell'XML o il testo
del PDF; l'apertura del PDF (fitz) e l'upload vivono nella UI.

Ogni estrazione restituisce un dizionario con le chiavi della tabella spese
(importo, aliquota_iva, data, nr_fattura, oggetto, note) oppure None se non è
riconosciuta nulla. L'aliquota IVA restituita è quella che RIPRODUCE l'IVA
totale sull'imponibile (per una fattura a aliquota unica è l'aliquota esatta;
per una mista è quella "media" che rende comunque corretto lo scorporo).
"""
import re
import xml.etree.ElementTree as ET


def _local(tag):
    """Nome del tag senza namespace (FatturaPA usa prefissi vari)."""
    return tag.split("}")[-1]


def _num_it(testo):
    """Converte un numero all'italiana ('-1.234,56') in float. None se vuoto."""
    if testo is None:
        return None
    s = str(testo).strip().replace("€", "").replace("\xa0", "").strip()
    if not s:
        return None
    # formato italiano: punto = migliaia, virgola = decimali
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    try:
        return float(s)
    except ValueError:
        return None


def _norma_data(testo):
    """Data in gg/mm/aaaa. Accetta ISO (2026-07-08) o già gg/mm/aaaa."""
    if not testo:
        return ""
    testo = str(testo).strip()
    m = re.match(r"(\d{4})-(\d{2})-(\d{2})", testo)
    if m:
        return f"{m.group(3)}/{m.group(2)}/{m.group(1)}"
    m = re.match(r"(\d{1,2})/(\d{1,2})/(\d{4})", testo)
    if m:
        return f"{int(m.group(1)):02d}/{int(m.group(2)):02d}/{m.group(3)}"
    return testo


def _aliquota(imponibile, imposta):
    """Aliquota % che riproduce l'imposta sull'imponibile.

    Arrotondata all'intero quando ci va molto vicino (le aliquote singole
    tornano 22/10/4 esatti); altrimenti a un decimale.
    """
    if not imponibile:
        return 0.0
    grezza = abs(imposta) / abs(imponibile) * 100
    intero = round(grezza)
    if abs(grezza - intero) < 0.15:
        return float(intero)
    return round(grezza, 1)


def _oggetto(fornitore, descrizione):
    fornitore = (fornitore or "").strip()
    descrizione = (descrizione or "").strip()
    if fornitore and descrizione:
        return f"{fornitore} — {descrizione}"[:120]
    return (fornitore or descrizione)[:120]


# ---------------------------------------------------------------- XML

def _primo(root, nome):
    for e in root.iter():
        if _local(e.tag) == nome:
            return e
    return None


def _tutti(root, nome):
    return [e for e in root.iter() if _local(e.tag) == nome]


TIPI_NOTA_CREDITO = {"TD04", "TD08"}


def dati_da_xml(contenuto):
    """Estrae i dati dalla fattura elettronica XML (bytes o str). None se KO.

    Robusta: qualunque problema di parsing (XML firmato .p7m, codifica
    inattesa, struttura non prevista) restituisce None invece di sollevare.
    """
    try:
        return _dati_da_xml(contenuto)
    except Exception:
        return None


def _dati_da_xml(contenuto):
    try:
        root = ET.fromstring(contenuto)
    except ET.ParseError:
        return None
    if _local(root.tag) != "FatturaElettronica":
        # potrebbe essere annidato o firmato: cerca comunque il corpo
        if _primo(root, "FatturaElettronicaBody") is None:
            return None

    numero = _primo(root, "Numero")
    data = _primo(root, "Data")
    tipo = _primo(root, "TipoDocumento")
    totale = _primo(root, "ImportoTotaleDocumento")

    imponibile_tot = sum(_num_it(e.text) or 0.0
                         for e in _tutti(root, "ImponibileImporto"))
    imposta_tot = sum(_num_it(e.text) or 0.0
                      for e in _tutti(root, "Imposta"))

    lordo = _num_it(totale.text) if totale is not None else None
    if lordo is None:
        lordo = round(imponibile_tot + imposta_tot, 2)

    # fornitore: denominazione, oppure nome + cognome
    cedente = _primo(root, "CedentePrestatore")
    fornitore = ""
    if cedente is not None:
        den = _primo(cedente, "Denominazione")
        if den is not None and den.text:
            fornitore = den.text.strip()
        else:
            nome = _primo(cedente, "Nome")
            cognome = _primo(cedente, "Cognome")
            fornitore = " ".join(p.text.strip() for p in (nome, cognome)
                                 if p is not None and p.text).strip()

    descr = _primo(root, "Descrizione")
    descrizione = descr.text.strip() if descr is not None and descr.text else ""

    tipo_txt = tipo.text.strip() if tipo is not None and tipo.text else ""
    note = "Nota di credito" if tipo_txt in TIPI_NOTA_CREDITO else ""

    return {
        "importo": lordo,
        "aliquota_iva": _aliquota(imponibile_tot, imposta_tot),
        "data": _norma_data(data.text if data is not None else ""),
        "nr_fattura": (numero.text.strip()
                       if numero is not None and numero.text else ""),
        "oggetto": _oggetto(fornitore, descrizione),
        "note": note,
    }


# ---------------------------------------------------------------- PDF (testo)

# importo all'italiana, eventualmente negativo, seguito o meno da €
_IMPORTO = r"(-?\s?[\d.]+,\d{2})"


def _cerca(testo, pattern, flags=re.IGNORECASE):
    m = re.search(pattern, testo, flags)
    return m.group(1).strip() if m else None


def dati_da_pdf_testo(testo):
    """Estrae i dati dal testo di un PDF di cortesia (best-effort).

    Restituisce None solo se non riconosce proprio nulla (né numero, né
    totale): in quel caso la UI lascia la riga da compilare a mano.
    """
    if not testo:
        return None
    # numero e data: "nr. 412616027839 del 08/07/2026"
    numero = _cerca(testo, r"n[r°\.]{0,2}\.?\s*([0-9A-Za-z/_.\-]+)\s+del\s")
    data = _cerca(testo, r"del\s+(\d{1,2}/\d{1,2}/\d{4})")

    # totale documento (lordo) — vari sinonimi del foglio di stile SdI
    lordo_txt = (_cerca(testo, r"Totale\s+documento\s*\n?\s*" + _IMPORTO)
                 or _cerca(testo, r"Netto\s+a\s+pagare\s*\n?\s*" + _IMPORTO)
                 or _cerca(testo, r"Importo\s+totale\s+documento\s*\n?\s*"
                           + _IMPORTO))
    imponibile_txt = _cerca(testo, r"Totale\s+imponibile\s*\n?\s*" + _IMPORTO)
    iva_txt = _cerca(testo, r"Totale\s+IVA\s*\n?\s*" + _IMPORTO)

    lordo = _num_it(lordo_txt)
    imponibile = _num_it(imponibile_txt)
    imposta = _num_it(iva_txt)
    if lordo is None and imponibile is not None:
        lordo = round((imponibile or 0.0) + (imposta or 0.0), 2)

    # aliquota: se imponibile+IVA noti la si ricava; se compare una sola
    # percentuale nel riepilogo, si usa quella
    aliquota = 0.0
    if imponibile:
        aliquota = _aliquota(imponibile, imposta or 0.0)
    else:
        percentuali = set(re.findall(r"(\d{1,2})\s?%", testo))
        if len(percentuali) == 1:
            aliquota = float(percentuali.pop())

    # fornitore: la riga subito dopo "FORNITORE"
    fornitore = _cerca(testo, r"FORNITORE\s*\n\s*(.+)")
    # descrizione: prima riga significativa dopo l'intestazione tabella o la
    # "Descrizione causale"
    descrizione = (_cerca(testo, r"Descrizione\s+causale\s+(.+)")
                   or "")

    if numero is None and lordo is None:
        return None

    return {
        "importo": lordo,
        "aliquota_iva": aliquota,
        "data": _norma_data(data or ""),
        "nr_fattura": numero or "",
        "oggetto": _oggetto(fornitore, descrizione),
        "note": "",
    }
