"""Il contratto d'appalto: SAL concordati in anticipo ed extra alla chiusura.

Come si paga davvero un'impresa, in queste operazioni: **non** a fattura per
voce di computo, ma a **stati di avanzamento** fissati nel contratto prima
che il cantiere apra — tipicamente 20-30-30-20, ma ogni cantiere fa storia a
sé. Gli **extra** non si vedono lungo la strada: si calcolano a cantiere
chiuso, quando ci si siede con le parti e si fa il SAL finale.

Da qui discende tutto il modulo:

- durante i lavori il software non ha niente da dire sullo scostamento, e
  non finge di averlo: i SAL sono percentuali decise a tavolino, seguirle
  misura il calendario dei pagamenti, non l'andamento del cantiere;
- l'unico numero che conta davvero è **quanto si è sforato alla fine** —
  contratto contro totale pagato. È quello che dice se la percentuale di
  imprevisti del business plan è tarata bene, e quindi se il prossimo
  acquisto sta in piedi.

Solo funzioni pure: niente Streamlit, niente pandas.
"""

# Ripartizione tipica dei SAL, da cambiare cantiere per cantiere.
SAL_PREDEFINITI = (20.0, 30.0, 30.0, 20.0)


def piano_sal(importo_contratto, percentuali):
    """Gli stati di avanzamento con il loro importo.

    percentuali: [20, 30, 30, 20] — le quote concordate nel contratto.
    Ritorna [{"n", "percento", "importo"}], nell'ordine dato.

    Le percentuali NON vengono normalizzate a 100: se il contratto ne
    somma 90 o 110 è un errore da vedere, non da correggere di nascosto.
    Ci pensa `somma_percentuali` a dirlo.
    """
    importo = float(importo_contratto or 0.0)
    piano = []
    for n, percento in enumerate(percentuali or [], start=1):
        percento = float(percento or 0.0)
        piano.append({
            "n": n,
            "percento": percento,
            "importo": round(importo * percento / 100.0, 2),
        })
    return piano


def somma_percentuali(percentuali):
    """Quanto fanno in tutto le quote dei SAL: deve dare 100."""
    return round(sum(float(p or 0.0) for p in (percentuali or [])), 2)


def stato_cantiere(importo_contratto, percentuali, pagati=(), extra=0.0):
    """Dove sta il cantiere: pagato, residuo, e il conto finale con gli extra.

    pagati: gli indici (a partire da 1) dei SAL già saldati.
    extra: i lavori in più, che si conoscono solo a cantiere chiuso.

    «maturato» è ciò che il contratto prevede di pagare fino al SAL più
    avanzato già saldato; «residuo» è quel che manca al contratto. Gli extra
    stanno fuori dal residuo perché non sono un pagamento in ritardo: sono
    lavoro in più che il contratto non conosceva.

    ⚠️ Il residuo può essere NEGATIVO, e deve poterlo essere: se le quote
    sommano più di 100 e i SAL sono saldati, hai pagato più di quanto hai
    firmato. Prima qui c'era un `max(0.0, ...)` che quel caso lo azzerava —
    la stessa correzione di nascosto che `piano_sal` rifiuta di fare sulle
    percentuali, fatta un passo più in là. Un contratto sforato in
    pagamento è esattamente il genere di cosa per cui si guarda questa
    schermata.
    """
    piano = piano_sal(importo_contratto, percentuali)
    pagati = {int(n) for n in (pagati or [])}
    pagato = round(sum(s["importo"] for s in piano if s["n"] in pagati), 2)
    contratto = round(float(importo_contratto or 0.0), 2)
    extra = round(float(extra or 0.0), 2)
    residuo = round(contratto - pagato, 2)
    return {
        "piano": piano,
        "contratto": contratto,
        "pagato": pagato,
        "residuo": residuo,
        "extra": extra,
        "totale_finale": round(contratto + extra, 2),
        "da_pagare": round(residuo + extra, 2),
        "scostamento": scostamento_percentuale(contratto, contratto + extra),
    }


def scostamento_percentuale(contratto, totale_finale):
    """Di quanto si è sforato, in percentuale sul contratto.

    È il numero che vale per l'operazione DOPO: dice se il 10% di imprevisti
    previsto dal contratto d'appalto regge alla prova dei fatti, o se sui
    tuoi cantieri va alzato. None quando non c'è un contratto da confrontare
    — meglio niente che uno zero che sembra «nessuno sforamento».
    """
    contratto = float(contratto or 0.0)
    if contratto <= 0:
        return None
    return round((float(totale_finale or 0.0) - contratto) / contratto * 100,
                 2)


def imprevisti_consigliati(scostamenti):
    """La percentuale di imprevisti suggerita dai cantieri già chiusi.

    È la media degli sforamenti passati: dopo tre operazioni non è più una
    convenzione, è la tua storia. None finché non c'è niente su cui basarsi
    — un consiglio senza dati è peggio del valore predefinito.

    Gli sforamenti negativi (hai speso meno del contratto) contano: sono
    altrettanto veri, e tenerli fuori gonfierebbe la media.

    ⚠️ E il risultato resta negativo se la media lo è. C'era un
    `max(minimo, …)` che lo riportava a zero, e diceva una cosa falsa
    proprio dopo la riga di documentazione che spiega perché i negativi
    contano: chi chiude sotto contratto si sentiva rispondere «i tuoi
    cantieri dicono 0,00%» invece di «−3%». Chi legge il numero decide poi
    cosa farne — una riserva non può essere negativa, ma sapere che non
    serve è un'informazione, non un errore da nascondere.
    """
    valori = [float(s) for s in (scostamenti or []) if s is not None]
    if not valori:
        return None
    return round(sum(valori) / len(valori), 2)
