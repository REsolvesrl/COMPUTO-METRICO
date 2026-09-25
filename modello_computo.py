"""Il punto di partenza di ogni computo nuovo: le voci dei nostri cantieri.

«Nuovo progetto» non apre un foglio bianco: apre nel computo tutte le voci
del listino che vengono da un cantiere vero (ENI e La Spezia Migliarina,
quelle con `cantieri` in listino.py), con i loro testi e i loro prezzi. Si
toglie quello che non serve invece di riscrivere ogni volta quello che
serve, come per l'elenco dei materiali. Le voci generiche del listino
restano nel pool.

Tetto e Facciata ci sono, ma spenti: accendendoli si trovano già pronti.

Le quantità partono tutte da zero: sono del cantiere, non del modello.
Una voce a zero resta a video («da quantificare») ma fuori da totali e
stampa, quindi il modello non mette mai un euro nel computo da solo.

Fino al 25/09/2026 il modello era il solo computo di Migliarina, con le sue
voci scritte a mano accanto al listino; da quando quelle voci sono entrate
nel listino (vedi rinumerazione.py) basta l'elenco dei codici.
"""
import copy

import listino

# Le voci nel computo di un progetto nuovo, nell'ordine del listino.
VOCI_SCELTE = [v["codice"] for v in listino.VOCI if v.get("cantieri")]


def progetto_nuovo():
    """Il modello nel formato di un progetto salvato, pronto da caricare."""
    return copy.deepcopy({
        "listino": listino.VERSIONE,
        "voci_scelte": VOCI_SCELTE,
        "listino_stato": {},
        "testi_voci": {},
        "voci": [],
    })
