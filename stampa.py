"""Il computo metrico come documento da consegnare: PDF.

Nessuna dipendenza da Streamlit: entrano dati normali, escono byte. Così la
stampa si prova con pytest senza far partire l'interfaccia.

⚠️ **Il PDF si stampa su carta bianca**, non sull'ardesia del Campionario.
Il mondo visivo governa lo schermo; qui il documento esce da una stampante,
finisce in un fascicolo e viene letto accanto ad altri preventivi. Un fondo
scuro sarebbe un francobollo di toner e un foglio illeggibile in fotocopia.
Del Campionario restano l'ottone dei filetti, il maiuscoletto delle
etichette e le cifre incolonnate.

I caratteri sono quelli incorporati in ogni lettore PDF (Helvetica): niente
file da scaricare, niente rete — il programma deve funzionare staccato.
"""

import io

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.lib.units import mm
from reportlab.platypus import (
    KeepTogether,
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)

from formato import colore_testo_su, euro, numero_it

ARDESIA = colors.HexColor("#1A2744")
OTTONE = colors.HexColor("#9A7B3F")      # ottone scurito: su bianco, leggibile
CEMENTO = colors.HexColor("#5A6068")
RIGA_ALTERNA = colors.HexColor("#F4F2ED")

MARGINE = 15 * mm
LARGHEZZA_UTILE = A4[0] - 2 * MARGINE

STILE_TITOLO = ParagraphStyle(
    "titolo", fontName="Helvetica-Bold", fontSize=17, leading=20,
    textColor=ARDESIA, spaceAfter=2)
STILE_ETICHETTA = ParagraphStyle(
    "etichetta", fontName="Helvetica-Bold", fontSize=7, leading=10,
    textColor=CEMENTO)
STILE_DATO = ParagraphStyle(
    "dato", fontName="Helvetica", fontSize=9, leading=12, textColor=ARDESIA)
STILE_CATEGORIA = ParagraphStyle(
    "categoria", fontName="Helvetica-Bold", fontSize=10, leading=13,
    textColor=ARDESIA)
STILE_VOCE = ParagraphStyle(
    "voce", fontName="Helvetica", fontSize=8, leading=10.5,
    textColor=ARDESIA)
STILE_INTESTAZIONE = ParagraphStyle(
    "intestazione", fontName="Helvetica-Bold", fontSize=7, leading=9,
    textColor=colors.white)
STILE_NOTA = ParagraphStyle(
    "nota", fontName="Helvetica-Oblique", fontSize=7.5, leading=10,
    textColor=CEMENTO)
STILE_TOTALE = ParagraphStyle(
    "totale", fontName="Helvetica-Bold", fontSize=12, leading=15,
    textColor=ARDESIA, alignment=TA_RIGHT)

COLONNE_VOCI = [17 * mm, 80 * mm, 13 * mm, 22 * mm, 22 * mm, 26 * mm]


def _pie_di_pagina(canvas, documento):
    """Numero di pagina e nome del progetto, su ogni foglio.

    Un computo si sfoglia, si fotocopia e si spilla: se un foglio si stacca
    deve sapere da solo a quale lavoro appartiene e che posto occupa.
    """
    canvas.saveState()
    canvas.setFont("Helvetica", 7.5)
    canvas.setFillColor(CEMENTO)
    canvas.drawString(MARGINE, 10 * mm, documento.titolo_corrente)
    canvas.drawRightString(A4[0] - MARGINE, 10 * mm,
                           f"pagina {canvas.getPageNumber()}")
    canvas.setStrokeColor(OTTONE)
    canvas.setLineWidth(0.5)
    canvas.line(MARGINE, 13 * mm, A4[0] - MARGINE, 13 * mm)
    canvas.restoreState()


def _testata(progetto):
    """Il cartiglio: che documento è, di che lavoro, per chi, di che giorno."""
    dati = [
        ("Committente", progetto.get("committente")),
        ("Oggetto", progetto.get("oggetto")),
        ("Data", progetto.get("data")),
    ]
    righe = [[Paragraph(etichetta.upper(), STILE_ETICHETTA),
              Paragraph(str(valore or "—"), STILE_DATO)]
             for etichetta, valore in dati]
    tabella = Table(righe, colWidths=[30 * mm, LARGHEZZA_UTILE - 30 * mm])
    tabella.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("TOPPADDING", (0, 0), (-1, -1), 1),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 1),
        ("LEFTPADDING", (0, 0), (0, -1), 0),
    ]))
    return [
        Paragraph("Computo metrico estimativo", STILE_TITOLO),
        Paragraph(str(progetto.get("nome") or "Progetto senza nome"),
                  ParagraphStyle("sottotitolo", fontName="Helvetica",
                                 fontSize=11, leading=14, textColor=OTTONE,
                                 spaceAfter=7)),
        tabella,
        Spacer(1, 7 * mm),
    ]


def _raggruppa(voci):
    """Le voci per categoria, nell'ordine in cui si presentano."""
    gruppi = {}
    for voce in voci:
        gruppi.setdefault(voce.get("categoria") or "Senza categoria",
                          []).append(voce)
    return gruppi


def _tabella_categoria(categoria, voci_categoria, tinta):
    """Un blocco: intestazione della categoria, le sue voci, il suo totale."""
    intestazioni = ["Codice", "Descrizione", "U.M.", "Quantità", "Prezzo",
                    "Importo"]
    # Le tinte delle categorie sono scelte per lo schermo scuro: sul bianco
    # alcune sono chiare (il grigio delle aree esterne) e il bianco sopra non
    # si leggerebbe. Il colore del testo lo decide la tinta, non l'abitudine.
    stile_intestazione = ParagraphStyle(
        "intestazione_cat", parent=STILE_INTESTAZIONE,
        textColor=colors.HexColor(colore_testo_su(tinta.hexval()[2:])))
    righe = [[Paragraph(t, stile_intestazione) for t in intestazioni]]
    for voce in voci_categoria:
        righe.append([
            Paragraph(str(voce.get("codice") or ""), STILE_VOCE),
            Paragraph(str(voce.get("descrizione") or ""), STILE_VOCE),
            Paragraph(str(voce.get("um") or ""), STILE_VOCE),
            Paragraph(numero_it(voce.get("quantita"), 2), STILE_VOCE),
            Paragraph(euro(voce.get("prezzo")), STILE_VOCE),
            Paragraph(euro(voce.get("importo")), STILE_VOCE),
        ])
    totale = round(sum(float(v.get("importo") or 0.0)
                       for v in voci_categoria), 2)
    righe.append([Paragraph("", STILE_VOCE),
                  Paragraph(f"Totale {categoria.lower()}", STILE_CATEGORIA),
                  "", "", "",
                  Paragraph(f"<b>{euro(totale)}</b>", STILE_VOCE)])

    tabella = Table(righe, colWidths=COLONNE_VOCI, repeatRows=1)
    stile = [
        ("BACKGROUND", (0, 0), (-1, 0), tinta),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (3, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -2), 0.25, colors.HexColor("#D6D2C8")),
        ("LINEABOVE", (0, -1), (-1, -1), 0.75, OTTONE),
        ("SPAN", (1, -1), (4, -1)),
    ]
    for i in range(1, len(righe) - 1):
        if i % 2 == 0:
            stile.append(("BACKGROUND", (0, i), (-1, i), RIGA_ALTERNA))
    tabella.setStyle(TableStyle(stile))
    return [Paragraph(categoria.upper(), STILE_ETICHETTA), Spacer(1, 1.5 * mm),
            tabella, Spacer(1, 5 * mm)]


def _tabella_totali(totali):
    """La coda dei conti: lavori, IVA, totale finale.

    Niente riserva per imprevisti: quello che si consegna all'impresa sono
    i lavori computati, non i lavori più un accantonamento che riguarda
    chi paga. La riserva vive nel business plan, dove è una scelta di
    chi fa l'operazione e si vede accanto alle altre.
    """
    def riga(etichetta, valore, forte=False):
        stile = STILE_CATEGORIA if forte else STILE_VOCE
        return [Paragraph(etichetta, stile), Paragraph(euro(valore), stile)]

    iva_pct = numero_it(totali.get("iva_pct"), 0)
    righe = [
        riga("Somma dei lavori", totali.get("somma")),
        riga("Totale lavori (IVA esclusa)", totali.get("totale_lavori"),
             forte=True),
        riga(f"IVA {iva_pct}%", totali.get("iva")),
        riga("TOTALE (IVA inclusa)", totali.get("totale"), forte=True),
    ]
    # 75 mm mandavano «Totale lavori (IVA esclusa)» a capo: una riga di conti
    # spezzata in due si legge male e allunga la coda del documento.
    larghezza = 95 * mm
    tabella = Table(righe, colWidths=[larghezza * 0.62, larghezza * 0.38],
                    hAlign="RIGHT")
    tabella.setStyle(TableStyle([
        ("ALIGN", (1, 0), (1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEABOVE", (0, 1), (-1, 1), 0.5, colors.HexColor("#D6D2C8")),
        ("LINEABOVE", (0, 3), (-1, 3), 1, OTTONE),
        ("BACKGROUND", (0, 3), (-1, 3), colors.HexColor("#F0E9DA")),
    ]))
    return [tabella]


def pdf_computo(progetto, voci, totali, tinte=None):
    """Il computo come PDF pronto da consegnare. Ritorna i byte del file.

    progetto: {"nome", "committente", "oggetto", "data"}.
    voci: [{"categoria", "codice", "descrizione", "um", "quantita",
        "prezzo", "importo"}] già calcolate.
    totali: {"somma", "totale_lavori", "iva_pct", "iva", "totale"}.
    tinte: {categoria: "#RRGGBB"} per la fascia d'intestazione; le categorie
        senza tinta prendono l'ardesia.
    """
    buffer = io.BytesIO()
    documento = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=MARGINE, rightMargin=MARGINE,
        topMargin=MARGINE, bottomMargin=20 * mm,
        title=f"Computo — {progetto.get('nome') or 'senza nome'}",
        author="CME — Computo Metrico Estimativo",
    )
    documento.titolo_corrente = str(progetto.get("nome")
                                    or "Progetto senza nome")

    tinte = tinte or {}
    elementi = _testata(progetto)
    gruppi = _raggruppa(voci)
    if not gruppi:
        elementi.append(Paragraph(
            "Nessuna voce compilata: il computo è vuoto.", STILE_NOTA))
    for categoria, voci_categoria in gruppi.items():
        tinta = tinte.get(categoria)
        elementi.extend(_tabella_categoria(
            categoria, voci_categoria,
            colors.HexColor(tinta) if tinta else ARDESIA))
    elementi.append(Spacer(1, 3 * mm))
    elementi.extend(_tabella_totali(totali))

    documento.build(elementi, onFirstPage=_pie_di_pagina,
                    onLaterPages=_pie_di_pagina)
    return buffer.getvalue()
