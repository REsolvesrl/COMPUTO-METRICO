"""Logica di calcolo del computo metrico estimativo (CME).

Solo funzioni pure: niente Streamlit, niente pandas. Tutta la logica
testabile vive qui; la UI in streamlit_app.py importa da questo modulo.

Convenzioni:
- le dimensioni non compilate valgono None (non 0);
- una "detrazione" (es. il vano di una porta da scomputare da una parete)
  si ottiene con un numero di parti negativo;
- le quantità sono arrotondate a 3 decimali, gli importi in euro a 2.
"""

SENZA_CATEGORIA = "Senza categoria"


def quantita_voce(parti=None, lunghezza=None, larghezza=None, altezza=None,
                  quantita_manuale=None):
    """Quantità di una voce di computo.

    Se almeno una tra parti/lunghezza/larghezza/altezza è compilata, la
    quantità è il prodotto dei soli campi compilati (i vuoti non contano).
    Se sono tutte vuote vale la quantità inserita a mano (0 se manca
    anche quella).
    """
    dimensioni = [d for d in (parti, lunghezza, larghezza, altezza) if d is not None]
    if dimensioni:
        quantita = 1.0
        for dimensione in dimensioni:
            quantita *= dimensione
        return round(quantita, 3)
    if quantita_manuale is not None:
        return round(float(quantita_manuale), 3)
    return 0.0


def quantita_da_misure(misure):
    """Somma delle quantità di un elenco di misurazioni (libretto delle misure).

    Ogni misura è un dizionario con parti/lunghezza/larghezza/altezza: valgono
    le stesse regole di quantita_voce (campi vuoti ignorati, parti negative =
    detrazione). È il classico "libretto delle misure" dei computi: una voce
    (es. la demolizione di un pavimento) viene scomposta in più righe — una per
    stanza — che si sommano nella quantità totale. Restituisce la somma
    arrotondata a 3 decimali (0 se l'elenco è vuoto).
    """
    totale = 0.0
    for misura in misure:
        totale += quantita_voce(
            misura.get("parti"),
            misura.get("lunghezza"),
            misura.get("larghezza"),
            misura.get("altezza"),
        )
    return round(totale, 3)


def calcola_voce(voce):
    """Restituisce una copia della voce con "quantita" e "importo" calcolati.

    La voce è un dizionario; le chiavi assenti sono trattate come vuote.
    """
    quantita = quantita_voce(
        voce.get("parti"),
        voce.get("lunghezza"),
        voce.get("larghezza"),
        voce.get("altezza"),
        voce.get("quantita_manuale"),
    )
    prezzo = voce.get("prezzo") or 0.0
    risultato = dict(voce)
    risultato["quantita"] = quantita
    risultato["importo"] = round(quantita * prezzo, 2)
    return risultato


def calcola_computo(voci):
    """Calcola quantità e importo di ogni voce dell'elenco."""
    return [calcola_voce(voce) for voce in voci]


def totali_per_categoria(voci_calcolate):
    """Somma gli importi per categoria: {categoria: totale}.

    Le voci senza categoria finiscono sotto SENZA_CATEGORIA.
    """
    totali = {}
    for voce in voci_calcolate:
        categoria = (voce.get("categoria") or "").strip() or SENZA_CATEGORIA
        totali[categoria] = round(totali.get(categoria, 0.0) + voce["importo"], 2)
    return totali


def totale_generale(voci_calcolate):
    """Totale lavori (somma di tutti gli importi), arrotondato a 2 decimali."""
    return round(sum(voce["importo"] for voce in voci_calcolate), 2)


def incidenze_percentuali(totali_categorie, totale):
    """Peso percentuale di ogni categoria sul totale: {categoria: %}."""
    if not totale:
        return {categoria: 0.0 for categoria in totali_categorie}
    return {
        categoria: round(importo / totale * 100, 2)
        for categoria, importo in totali_categorie.items()
    }


def totale_con_iva(totale, aliquota_iva):
    """Restituisce (importo IVA, totale IVA inclusa)."""
    iva = round(totale * aliquota_iva / 100, 2)
    return iva, round(totale + iva, 2)


def totale_con_imprevisti(totale, percento_imprevisti):
    """Restituisce (importo imprevisti, totale con imprevisti).

    Gli imprevisti sono un accantonamento percentuale sul totale lavori
    (tipicamente il 5%) che copre le sorprese di cantiere; si applicano
    prima dell'IVA.
    """
    imprevisti = round(totale * percento_imprevisti / 100, 2)
    return imprevisti, round(totale + imprevisti, 2)
