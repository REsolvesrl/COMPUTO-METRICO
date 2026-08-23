"""I prezzi veri dell'utente, quelli che sopravvivono al singolo progetto.

Il listino guida (`listino.py`) ha prezzi indicativi: alla prima operazione
si correggono, alla seconda si ricorreggono da capo, perché vivono dentro il
progetto e con quello se ne vanno. Qui invece stanno in un file solo, fuori
dai progetti, e si riapplicano quando serve.

Dove: `~/CME/listino_personale.json`, accanto alla cartella dei progetti,
oppure il percorso scritto in `CME_LISTINO`. Il file nasce al primo
salvataggio, non all'avvio.

Si salvano **solo i prezzi diversi dalla guida**: un file di scostamenti
resta leggibile a occhio e, soprattutto, le voci che non hai mai toccato
continuano a seguire gli aggiornamenti del listino guida invece di restare
congelate a un valore che non hai scelto.
"""
import json
import os
from datetime import date
from pathlib import Path

import archivio_locale
import listino

# ⚠️ La numerazione del listino è cambiata una volta (la serie di una voce
# ora è il numero della sua categoria). I file salvati PRIMA vanno convertiti
# leggendoli; quelli salvati DOPO no — e non c'è modo di distinguerli dal
# solo codice, perché «3.10» è insieme un codice di ieri e uno di oggi.
# Quindi ogni file dice quale numerazione parla. Senza il numero è di ieri:
# è vero per definizione, il marcatore non esisteva.
VERSIONE_CODICI = 2


def percorso():
    """Il file del listino personale, senza crearlo."""
    scelta = os.environ.get("CME_LISTINO")
    if scelta:
        return Path(scelta).expanduser()
    return archivio_locale.cartella().parent / "listino_personale.json"


def esiste():
    return percorso().is_file()


def scostamenti(voci, prezzi, tolleranza=0.005):
    """{codice: prezzo} dei soli prezzi che si discostano dalla guida.

    voci: le voci del listino guida ({"codice", "prezzo"}).
    prezzi: {codice: prezzo attualmente in uso nel progetto}.

    Un prezzo uguale alla guida non è una tua scelta: è il valore che c'era.
    Salvarlo lo congelerebbe, e domani non seguirebbe più un aggiornamento
    del listino. I prezzi a zero o negativi non si salvano: sono un campo
    svuotato per sbaglio, non un prezzo.
    """
    personali = {}
    for voce in voci:
        codice = voce["codice"]
        if codice not in prezzi:
            continue
        prezzo = float(prezzi[codice] or 0.0)
        if prezzo <= 0:
            continue
        if abs(prezzo - float(voce["prezzo"])) > tolleranza:
            personali[codice] = round(prezzo, 2)
    return personali


def da_applicare(salvati, voci, prezzi_correnti=None, tolleranza=0.005):
    """{codice: prezzo} da riscrivere nel progetto.

    Si scartano i codici che nel listino guida non esistono più (rinumerato,
    voce tolta): scriverli creerebbe quantità appese a una voce fantasma.
    Se si passano i prezzi correnti, si scartano anche quelli già a posto —
    così chi chiama sa se c'è davvero qualcosa da cambiare.
    """
    codici = {voce["codice"] for voce in voci}
    risultato = {}
    for codice, prezzo in (salvati or {}).items():
        if codice not in codici:
            continue
        prezzo = round(float(prezzo or 0.0), 2)
        if prezzo <= 0:
            continue
        if prezzi_correnti is not None:
            attuale = float(prezzi_correnti.get(codice) or 0.0)
            if abs(attuale - prezzo) <= tolleranza:
                continue
        risultato[codice] = prezzo
    return risultato


def salva(prezzi, quando=None):
    """Scrive il listino personale. Ritorna il percorso del file.

    Come per i progetti: prima un file temporaneo, poi il rinomino. Se manca
    la corrente a metà scrittura, il listino di prima resta intatto.
    """
    file = percorso()
    file.parent.mkdir(parents=True, exist_ok=True)
    contenuto = {
        "versione_codici": VERSIONE_CODICI,
        "prezzi": {c: round(float(p), 2) for c, p in (prezzi or {}).items()},
        "aggiornato": (quando or date.today()).isoformat(),
    }
    temporaneo = file.with_suffix(".json.parziale")
    temporaneo.write_text(
        json.dumps(contenuto, ensure_ascii=False, indent=1), encoding="utf-8")
    temporaneo.replace(file)
    return file


def carica():
    """(prezzi, quando) dal file. ({}, None) se non c'è o è illeggibile.

    Un listino rovinato non deve impedire di aprire l'app: si riparte dai
    prezzi della guida, che è esattamente la situazione di chi non l'ha mai
    salvato.
    """
    file = percorso()
    if not file.is_file():
        return {}, None
    try:
        dati = json.loads(file.read_text(encoding="utf-8"))
        # I codici di ieri diventano quelli di oggi, ma SOLO se il file è di
        # ieri: senza il controllo, un listino salvato oggi verrebbe
        # riconvertito domani — «3.10» finirebbe su «4.10» — e i prezzi
        # sparirebbero senza dire niente, che è il modo peggiore di perdere
        # un lavoro.
        vecchio = int(dati.get("versione_codici") or 1) < VERSIONE_CODICI
        prezzi = {(listino.codice_aggiornato(str(c)) if vecchio else str(c)):
                  float(p)
                  for c, p in (dati.get("prezzi") or {}).items()}
        return prezzi, dati.get("aggiornato")
    except Exception:  # noqa: BLE001 — file rovinato: si riparte dalla guida
        return {}, None


def elimina():
    """Toglie il listino personale. True se c'era davvero."""
    file = percorso()
    if not file.is_file():
        return False
    file.unlink()
    return True
