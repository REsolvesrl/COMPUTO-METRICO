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
from materiali import note_numerate, raggruppa_per_capitolo

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
# «un carattere più piccolo» della nota di voce: 6,5 contro 7,5. Non è
# corsivo come le altre note — è una clausola, non un commento.
STILE_NOTA_FINALE = ParagraphStyle(
    "nota_finale", fontName="Helvetica", fontSize=7.5, leading=10.5,
    textColor=ARDESIA)
# Il nome di chi firma non è una didascalia: sta sopra la riga della penna
# e si legge da lontano, come su un contratto.
STILE_FIRMA = ParagraphStyle(
    "firma", fontName="Helvetica-Bold", fontSize=10.5, leading=14,
    textColor=ARDESIA)
STILE_FIRMA_ETICHETTA = ParagraphStyle(
    "firma_etichetta", fontName="Helvetica-Bold", fontSize=8.5, leading=12,
    textColor=ARDESIA)
STILE_TOTALE = ParagraphStyle(
    "totale", fontName="Helvetica-Bold", fontSize=12, leading=15,
    textColor=ARDESIA, alignment=TA_RIGHT)

COLONNE_VOCI = [17 * mm, 80 * mm, 13 * mm, 22 * mm, 22 * mm, 26 * mm]

# La riserva del 10% e l'elenco delle opere comprese: sta in fondo, in
# piccolo, ed è la clausola che regge il totale — chi firma la sta
# accettando insieme alla cifra.
NOTA_FINALE = (
    "<b>N.B:</b> L'importo totale indicato considera una tolleranza massima "
    "del 10% tra le opere elencate nel computo metrico e le opere "
    "effettivamente realizzate. L'importo totale comprende le seguenti "
    "opere: smontaggio e smaltimento finestre, porte interne, battiscopa, "
    "impianti e riquadratura spallette")

COMMITTENTE_FIRMATARIO = "Resolve S.r.l."


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


def _testata(progetto, titolo="Computo metrico estimativo", occhiello=None):
    """Il cartiglio: che documento è, di che lavoro, per chi, di che giorno.

    `occhiello` è l'etichetta piccola sopra il titolo — «ALLEGATO 1 AL
    COMPUTO METRICO». Sta lì e non dentro il titolo perché è la voce del
    sistema, quella che nomina le cose: un allegato dice prima di che cosa
    è allegato, poi come si chiama.
    """
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
    elementi = []
    if occhiello:
        elementi.append(Paragraph(occhiello.upper(), STILE_ETICHETTA))
    elementi += [
        Paragraph(titolo, STILE_TITOLO),
        Paragraph(str(progetto.get("nome") or "Progetto senza nome"),
                  ParagraphStyle("sottotitolo", fontName="Helvetica",
                                 fontSize=11, leading=14, textColor=OTTONE,
                                 spaceAfter=7)),
        tabella,
        Spacer(1, 7 * mm),
    ]
    return elementi


def _raggruppa(voci):
    """Le voci per categoria, nell'ordine in cui si presentano."""
    gruppi = {}
    for voce in voci:
        gruppi.setdefault(voce.get("categoria") or "Senza categoria",
                          []).append(voce)
    return gruppi


def _tabella_categoria(categoria, voci_categoria, tinta, con_prezzi=True):
    """Un blocco: intestazione della categoria, le sue voci, il suo totale.

    Senza prezzi le colonne del prezzo e dell'importo restano, VUOTE: è il
    foglio che si dà all'impresa perché ci scriva la sua offerta, e le
    caselle da riempire devono esserci — un prezzo già stampato sopra non
    è una richiesta di preventivo, è una proposta.
    """
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
        riga = [
            Paragraph(str(voce.get("codice") or ""), STILE_VOCE),
            Paragraph(str(voce.get("descrizione") or ""), STILE_VOCE),
            Paragraph(str(voce.get("um") or ""), STILE_VOCE),
            Paragraph(numero_it(voce.get("quantita"), 2), STILE_VOCE),
        ]
        if con_prezzi:
            riga += [Paragraph(euro(voce.get("prezzo")), STILE_VOCE),
                     Paragraph(euro(voce.get("importo")), STILE_VOCE)]
        else:
            riga += ["", ""]          # da riempire a penna, o al computer
        righe.append(riga)
    totale = round(sum(float(v.get("importo") or 0.0)
                       for v in voci_categoria), 2)
    righe.append([Paragraph("", STILE_VOCE),
                  Paragraph(f"Totale {categoria.lower()}",
                            STILE_CATEGORIA),
                  "", "", "",
                  Paragraph(f"<b>{euro(totale)}</b>", STILE_VOCE)
                  if con_prezzi else ""])

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
    if not con_prezzi:
        # le caselle da compilare si vedono: un riquadro leggero attorno
        # alle due colonne vuote, righe dei totali comprese
        stile += [
            ("BOX", (4, 1), (5, -1), 0.5, colors.HexColor("#B9B4A8")),
            ("INNERGRID", (4, 1), (5, -1), 0.25,
             colors.HexColor("#D6D2C8")),
        ]
    for i in range(1, len(righe) - 1):
        if i % 2 == 0:
            stile.append(("BACKGROUND", (0, i), (-1, i), RIGA_ALTERNA))
    tabella.setStyle(TableStyle(stile))
    return [Paragraph(categoria.upper(), STILE_ETICHETTA), Spacer(1, 1.5 * mm),
            tabella, Spacer(1, 5 * mm)]


def _tabella_totali(totali, con_prezzi=True):
    """La coda dei conti: lavori, IVA, totale finale.

    Niente riserva per imprevisti: quello che si consegna all'impresa sono
    i lavori computati, non i lavori più un accantonamento che riguarda
    chi paga. La riserva vive nel business plan, dove è una scelta di
    chi fa l'operazione e si vede accanto alle altre.
    """
    def riga(etichetta, valore, forte=False):
        stile = STILE_CATEGORIA if forte else STILE_VOCE
        return [Paragraph(etichetta, stile),
                Paragraph(euro(valore), stile) if con_prezzi else ""]

    # ⚠️ Con l'aliquota a ZERO la riga dell'IVA non si scrive: «IVA 0% —
    # 0,00 €» non è un'informazione, è una riga di conto che dichiara di
    # non contare niente. E con lei se ne va anche il «(IVA inclusa)» del
    # totale: senza una riga d'imposta sopra, quella precisazione parla di
    # una cosa che sul foglio non compare, e due righe identiche con
    # etichette diverse — «esclusa» ed «inclusa» sullo stesso numero —
    # fanno solo dubitare del conto.
    aliquota = float(totali.get("iva_pct") or 0.0)
    righe = [
        riga("Somma dei lavori", totali.get("somma")),
        riga("Totale lavori (IVA esclusa)", totali.get("totale_lavori"),
             forte=True),
    ]
    if aliquota > 0:
        righe.append(
            riga(f"IVA {numero_it(aliquota, 0)}%", totali.get("iva")))
        righe.append(
            riga("TOTALE (IVA inclusa)", totali.get("totale"), forte=True))
    else:
        righe.append(riga("TOTALE", totali.get("totale"), forte=True))
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
        # ⚠️ L'ULTIMA riga, non la quarta: senza IVA le righe sono tre, e
        # un indice fisso avrebbe messo il filetto d'ottone e il fondo
        # chiaro su una riga che non c'è — o peggio, sulla riga sbagliata.
        ("LINEABOVE", (0, -1), (-1, -1), 1, OTTONE),
        ("BACKGROUND", (0, -1), (-1, -1), colors.HexColor("#F0E9DA")),
    ] + ([] if con_prezzi else [
        ("BOX", (1, 0), (1, -1), 0.5, colors.HexColor("#B9B4A8")),
        ("INNERGRID", (1, 0), (1, -1), 0.25, colors.HexColor("#D6D2C8")),
    ])))
    return [tabella]


def _gruppo_firma():
    """Le due firme in fondo: chi commissiona e chi esegue.

    A sinistra il committente, che è sempre lo stesso; a destra il posto
    per l'impresa, VUOTO — il nome se lo scrive lei, perché finché non
    firma non sappiamo quale sia. Due righe di penna, alla stessa altezza:
    un foglio che si firma in due deve mostrarlo a colpo d'occhio.
    """
    meta = LARGHEZZA_UTILE / 2
    riga_penna = "_" * 34
    righe = [
        [Paragraph("PER ACCETTAZIONE:", STILE_FIRMA_ETICHETTA), ""],
        [Spacer(1, 6 * mm), Spacer(1, 6 * mm)],
        [Paragraph(COMMITTENTE_FIRMATARIO, STILE_FIRMA),
         Paragraph("", STILE_FIRMA)],
        [Spacer(1, 12 * mm), Spacer(1, 12 * mm)],
        [Paragraph(riga_penna, STILE_FIRMA),
         Paragraph(riga_penna, STILE_FIRMA)],
    ]
    tabella = Table(righe, colWidths=[meta, meta])
    tabella.setStyle(TableStyle([
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("LEFTPADDING", (0, 0), (0, -1), 8 * mm),
        ("LEFTPADDING", (1, 0), (1, -1), 8 * mm),
        ("TOPPADDING", (0, 0), (-1, -1), 0),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 0),
    ]))
    # KeepTogether: un blocco firma spezzato fra due pagine — il nome di qua
    # e la riga di là — è un documento che nessuno firma volentieri.
    return [Spacer(1, 10 * mm), KeepTogether([tabella])]


def pdf_computo(progetto, voci, totali, tinte=None, con_prezzi=True):
    """Il computo come PDF pronto da consegnare. Ritorna i byte del file.

    progetto: {"nome", "committente", "oggetto", "data"}.
    voci: [{"categoria", "codice", "descrizione", "um", "quantita",
        "prezzo", "importo"}] già calcolate.
    totali: {"somma", "totale_lavori", "iva_pct", "iva", "totale"}.
    tinte: {categoria: "#RRGGBB"} per la fascia d'intestazione; le categorie
        senza tinta prendono l'ardesia.
    con_prezzi: falso per il foglio da dare alle imprese perché ci facciano
        il preventivo. Le colonne del prezzo e dell'importo restano, e
        anche la coda dei conti: sono VUOTE, riquadrate, da riempire —
        l'impresa deve poter mettere i suoi prezzi e fare la somma. La
        nota della tolleranza e il gruppo firma ci sono in tutt'e due: sono
        le condizioni con cui si fa il prezzo, e vanno lette prima di
        scriverlo.
    """
    buffer = io.BytesIO()
    documento = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=MARGINE, rightMargin=MARGINE,
        topMargin=MARGINE, bottomMargin=20 * mm,
        title=("Computo" + ("" if con_prezzi else " (senza prezzi)")
               + f" — {progetto.get('nome') or 'senza nome'}"),
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
            colors.HexColor(tinta) if tinta else ARDESIA,
            con_prezzi=con_prezzi))
    elementi.append(Spacer(1, 3 * mm))
    elementi.extend(_tabella_totali(totali, con_prezzi=con_prezzi))
    # La clausola sta su ENTRAMBI i fogli, con prezzi e senza.
    # ⚠️ Prima era solo su quello coi prezzi, per una ragione che sembrava
    # buona: parla dell'importo totale, e sul foglio da preventivare il
    # totale è una casella vuota — sarebbe una condizione su una cifra che
    # non c'è ancora. Il ragionamento è stato ribaltato di proposito, ed è
    # più forte: la tolleranza del 10% e l'elenco delle opere comprese
    # sono le REGOLE con cui l'impresa deve fare il prezzo, non un commento
    # al numero già fatto. Chi prepara l'offerta deve leggerle PRIMA di
    # scrivere la cifra, non trovarsele addosso dopo aver firmato.
    elementi.append(Spacer(1, 5 * mm))
    elementi.append(Paragraph(NOTA_FINALE, STILE_NOTA_FINALE))
    elementi.extend(_gruppo_firma())

    documento.build(elementi, onFirstPage=_pie_di_pagina,
                    onLaterPages=_pie_di_pagina)
    return buffer.getvalue()


# ------------------------------------------------ allegato 1: i materiali

# La clausola che è tutta la ragione del foglio. Dice il confine e basta:
# che cosa sia a carico dell'impresa lo dice il computo, voce per voce, e
# ripeterlo qui in una riga sola vorrebbe dire riscrivere un contratto in
# un sottotitolo.
NOTA_MATERIALI = (
    "<b>N.B:</b> I materiali elencati sono acquistati a cura e spese del "
    "Committente. Non rientrano nell'appalto e il loro costo non è "
    "compreso nell'importo del computo metrico.")

# La descrizione si prende quasi tutto: è un elenco di cose, e la colonna
# di destra è lì solo per le voci che una misura ce l'hanno. Niente U.M. —
# sul foglio firmato non compilava mai — e niente fornitore, link o stato
# dell'ordine: sono roba di chi compra, e questo foglio lo legge l'impresa.
COLONNE_MAT = [150 * mm, 30 * mm]


def _riga_luogo_data(progetto):
    """«La Spezia, lì 29/11/2025» — la riga che precede le firme.

    Il luogo può mancare (i progetti di prima non ce l'hanno): allora resta
    la data da sola, che è il minimo che un foglio da firmare deve portare.
    """
    luogo = str(progetto.get("luogo") or "").strip()
    data = str(progetto.get("data") or "").strip()
    if not data:
        return []
    testo = f"{luogo}, lì {data}" if luogo else f"lì {data}"
    return [Spacer(1, 6 * mm), Paragraph(testo, STILE_DATO)]


def _tabella_capitolo(capitolo, righe, marcatori):
    """Un capitolo dell'allegato: il titolo e sotto le sue cose.

    `marcatori` è {id(riga): "*"} — l'asterisco che rimanda alla nota in
    fondo, attaccato alla descrizione com'è sul foglio vero.

    Nessun totale, in nessuna forma: questo elenco di soldi non ne porta.
    """
    intestazione_bianca = ParagraphStyle(
        "intestazione_cap", parent=STILE_INTESTAZIONE, textColor=colors.white)
    tabella_righe = [[Paragraph(t, intestazione_bianca)
                      for t in ("Descrizione", "Quantità")]]
    for riga in righe:
        descrizione = str(riga.get("descrizione") or "")
        marcatore = marcatori.get(id(riga))
        if marcatore:
            descrizione = f"{descrizione} {marcatore}"
        quantita = riga.get("quantita")
        tabella_righe.append([
            Paragraph(descrizione, STILE_VOCE),
            # La quantità che manca resta VUOTA, non «1,00»: sul foglio è
            # sottinteso che il box doccia sia uno, e stamparlo darebbe a
            # un'omissione l'aria di una misura presa.
            Paragraph("" if quantita is None else numero_it(quantita, 2),
                      STILE_VOCE),
        ])

    stile = [
        ("BACKGROUND", (0, 0), (-1, 0), ARDESIA),
        ("VALIGN", (0, 0), (-1, -1), "TOP"),
        ("ALIGN", (1, 0), (-1, -1), "RIGHT"),
        ("TOPPADDING", (0, 0), (-1, -1), 3),
        ("BOTTOMPADDING", (0, 0), (-1, -1), 3),
        ("LINEBELOW", (0, 0), (-1, -1), 0.25, colors.HexColor("#D6D2C8")),
    ]
    for i in range(1, len(tabella_righe)):
        if i % 2 == 0:
            stile.append(("BACKGROUND", (0, i), (-1, i), RIGA_ALTERNA))
    tabella = Table(tabella_righe, colWidths=COLONNE_MAT, repeatRows=1)
    tabella.setStyle(TableStyle(stile))
    return [Paragraph(capitolo.upper(), STILE_ETICHETTA), Spacer(1, 1.5 * mm),
            tabella, Spacer(1, 5 * mm)]


def pdf_materiali(progetto, righe):
    """L'allegato dei materiali a cura del committente. Ritorna i byte.

    progetto: {"nome", "committente", "oggetto", "data", "luogo"}.
    righe: [{"capitolo", "descrizione", "um", "quantita", "note"}].
        Fornitore, link e stato dell'ordine ci sono nei dati ma **non nel
        documento**: sono appunti di chi compra, e questo foglio lo firma
        l'impresa.

    Un documento solo, senza prezzi, perché così è il foglio vero: elenca le
    forniture che restano fuori dall'appalto, non quanto costano.
    """
    buffer = io.BytesIO()
    documento = SimpleDocTemplate(
        buffer, pagesize=A4,
        leftMargin=MARGINE, rightMargin=MARGINE,
        topMargin=MARGINE, bottomMargin=20 * mm,
        title=f"Allegato materiali — {progetto.get('nome') or 'senza nome'}",
        author="CME — Computo Metrico Estimativo",
    )
    documento.titolo_corrente = str(progetto.get("nome")
                                    or "Progetto senza nome")

    elementi = _testata(
        progetto, titolo="Elenco materiali acquistati cura Committente",
        occhiello="Allegato 1 al computo metrico")

    note = note_numerate(righe)
    marcatori = {id(n["riga"]): n["marcatore"] for n in note}
    gruppi = raggruppa_per_capitolo(righe)
    if not gruppi:
        elementi.append(Paragraph("Nessun materiale elencato.", STILE_NOTA))
    for capitolo, righe_capitolo in gruppi.items():
        elementi.extend(_tabella_capitolo(capitolo, righe_capitolo,
                                          marcatori))

    if note:
        elementi.append(Spacer(1, 4 * mm))
        for nota in note:
            elementi.append(Paragraph(
                f"{nota['marcatore']} {nota['testo']}", STILE_NOTA_FINALE))

    elementi.append(Spacer(1, 5 * mm))
    elementi.append(Paragraph(NOTA_MATERIALI, STILE_NOTA_FINALE))
    elementi.extend(_riga_luogo_data(progetto))
    elementi.extend(_gruppo_firma())

    documento.build(elementi, onFirstPage=_pie_di_pagina,
                    onLaterPages=_pie_di_pagina)
    return buffer.getvalue()
