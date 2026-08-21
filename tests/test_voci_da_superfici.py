"""Il ponte fra le misure sulla planimetria e le voci del listino.

`VOCI_DA_SUPERFICI` (in streamlit_app.py) dice quale voce di listino riceve
quale quantità misurata sul disegno: i muri tracciati «da demolire» vanno
nella 1.02, quelli «da costruire» nella 2.01, e così per pavimenti,
battiscopa e tinteggiature.

Il collegamento è fragile in un modo silenzioso: se un codice sparisce o
cambia numero nel listino, l'app non protesta — la riga `if voce is None:
continue` la salta e basta. L'utente preme «Scrivi le quantità nel listino»
e quella voce semplicemente non compare, senza un errore da leggere.

Qui il sorgente si legge, non si importa: importare streamlit_app farebbe
partire l'intera interfaccia.
"""
import ast
from pathlib import Path

import listino

SORGENTE = Path(__file__).resolve().parent.parent / "streamlit_app.py"

# Unità di misura che ogni grandezza misurata sulla planimetria deve avere.
# I muri si computano a superficie (lunghezza × altezza), il battiscopa a
# metri lineari: un'unità sbagliata farebbe entrare nel computo un numero
# plausibile e sbagliato.
UM_ATTESA = {
    "pavimento": "m²",
    "pavimento_esterno": "m²",
    "rivestimenti": "m²",
    "battiscopa": "m",
    "tinteggiatura": "m²",
    "muri_demolire": "m²",
    "muri_costruire": "m²",
}


def _voci_da_superfici():
    """La costante letta dal sorgente, come lista di tuple."""
    # utf-8-sig: il sorgente comincia con un BOM (lo lascia Windows) e ast
    # non lo digerisce.
    albero = ast.parse(SORGENTE.read_text(encoding="utf-8-sig"))
    for nodo in albero.body:
        if (isinstance(nodo, ast.Assign)
                and any(getattr(b, "id", None) == "VOCI_DA_SUPERFICI"
                        for b in nodo.targets)):
            return ast.literal_eval(nodo.value)
    raise AssertionError("VOCI_DA_SUPERFICI non trovata in streamlit_app.py")


def test_ogni_codice_esiste_nel_listino():
    mancanti = [codice for codice, _, _ in _voci_da_superfici()
                if listino.voce_per_codice(codice) is None]
    assert not mancanti, (
        "Codici che non esistono più nel listino: le quantità misurate sulla "
        "planimetria non arriverebbero mai nel computo — " + ", ".join(mancanti))


def test_unita_di_misura_coerenti():
    sbagliate = []
    for codice, grandezza, _ in _voci_da_superfici():
        voce = listino.voce_per_codice(codice)
        if voce is None:
            continue
        attesa = UM_ATTESA.get(grandezza)
        assert attesa, f"Grandezza {grandezza!r} senza unità attesa nel test"
        if voce["um"] != attesa:
            sbagliate.append(f"{codice} ({grandezza}): {voce['um']} "
                             f"invece di {attesa}")
    assert not sbagliate, "Unità di misura incoerenti — " + "; ".join(sbagliate)


def test_i_muri_tracciati_hanno_la_loro_voce():
    """Demolire e costruire devono restare collegati, ciascuno alla sua voce."""
    per_grandezza = {grandezza: codice
                     for codice, grandezza, _ in _voci_da_superfici()}
    assert per_grandezza.get("muri_demolire") == "1.02"
    assert per_grandezza.get("muri_costruire") == "2.01"
