"""Le rotte del computo.

⚠️ Il salvataggio passa per lo stesso identico modulo del programma
vecchio - `archivio_locale` - che non è stato toccato. Stessa cartella
(`~/CME/progetti`, o quella di `CME_ARCHIVIO`), stesso formato JSON, stessa
cartella `versioni/`. Un progetto scritto da qui si riapre col programma
vecchio, e viceversa: è la condizione per poter lavorare col vecchio mentre
questo è in cantiere.

⚠️ Si ascolta **solo su 127.0.0.1**, ed è scritto nell'avvio: Streamlit, per
com'è fatto, risponde invece su tutte le schede di rete.
"""

from __future__ import annotations

import json
import os
from datetime import datetime
from pathlib import Path

# ⚠️ **Il cantiere non tocca i progetti veri, e non perché qualcuno si
# ricordi di dirglielo.** Finché questa versione è in costruzione lavora su
# una copia, e il posto della copia è deciso qui - non nel .bat, che si può
# lanciare in un altro modo, né in una variabile d'ambiente, che si può
# dimenticare. Chi vuole l'archivio vero lo dice a voce alta impostando
# `CME_ARCHIVIO`: `setdefault` non lo sovrascrive.
#
# Quando il cantiere avrà finito, si toglie questo blocco - ed è una riga
# sola da togliere, di proposito.
os.environ.setdefault(
    "CME_ARCHIVIO", str(Path.home() / "CME" / "progetti-prova")
)

from fastapi import FastAPI, HTTPException  # noqa: E402
from fastapi.responses import FileResponse  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import archivio_locale  # noqa: E402
import computo  # noqa: E402

RADICE = Path(__file__).resolve().parent.parent
WEB = RADICE / "web"

app = FastAPI(title="CME", docs_url="/api/documentazione", redoc_url=None)


# ----------------------------------------------------------------- dati


class Modifica(BaseModel):
    """Cosa è cambiato su una voce. I campi assenti non si toccano."""

    codice: str
    quantita: float | None = None
    prezzo: float | None = None


class Modifiche(BaseModel):
    modifiche: list[Modifica]


def _carica(nome: str) -> dict:
    try:
        return archivio_locale.carica_progetto(nome)
    except RuntimeError:
        raise HTTPException(404, f"Non trovo il progetto «{nome}»")


def _applica(dati: dict, corpo: Modifiche) -> list[str]:
    """Scrive le modifiche nel dizionario; ritorna i codici ignorati."""
    return [m.codice for m in corpo.modifiche
            if not computo.scrivi(dati, m.codice, m.quantita, m.prezzo)]


def _vista(nome: str, dati: dict) -> dict:
    righe = computo.righe(dati)
    return {
        "nome": nome,
        "progetto": dati.get("progetto") or {},
        "righe": righe,
        "totali": computo.totali(dati, righe),
    }


# ---------------------------------------------------------------- rotte


@app.get("/api/salute")
def salute() -> dict:
    """Dove sta la roba, e quanta ce n'è. La prima cosa da guardare quando
    qualcosa non torna: dice su quale archivio si sta lavorando davvero."""
    cartella = archivio_locale.cartella()
    return {
        "archivio_progetti": str(cartella),
        "archivio_esiste": cartella.is_dir(),
        "progetti": len(archivio_locale.elenco_progetti()),
    }


@app.get("/api/progetti")
def elenco_progetti() -> list[dict]:
    """I progetti salvati, dal più recente."""
    ultimo, _ = archivio_locale.ultimo_progetto()
    elenco = []
    for nome in archivio_locale.elenco_progetti():
        file = archivio_locale.percorso(nome)
        elenco.append({
            "nome": nome,
            "quando": datetime.fromtimestamp(file.stat().st_mtime).isoformat(),
            "ultimo": nome == ultimo,
        })
    return sorted(elenco, key=lambda p: p["quando"], reverse=True)


@app.get("/api/progetti/{nome}")
def apri_progetto(nome: str) -> dict:
    """Le righe del computo e i totali."""
    return _vista(nome, _carica(nome))


@app.post("/api/progetti/{nome}/prova")
def prova_modifiche(nome: str, corpo: Modifiche) -> dict:
    """Come verrebbe il computo con queste modifiche, **senza salvare**.

    ⚠️ Qui non si salva a ogni tasto, al contrario di CATASTO: ogni
    salvataggio di CME mette da parte una versione, e se ne tengono tre.
    Salvare a ogni cifra le brucerebbe in tre battute - e sono il rimedio
    a «ho sovrascritto il computo buono». Si salva col tasto, come prima.
    """
    dati = _carica(nome)
    if _applica(dati, corpo):
        raise HTTPException(400, "Una delle voci non è nel computo")
    return _vista(nome, dati)


@app.patch("/api/progetti/{nome}")
def salva_modifiche(nome: str, corpo: Modifiche) -> dict:
    """Scrive le modifiche e salva, con `archivio_locale.salva_progetto`."""
    dati = _carica(nome)
    ignorate = _applica(dati, corpo)
    file = archivio_locale.salva_progetto(
        nome, json.dumps(dati, ensure_ascii=False, separators=(",", ":")))
    return {
        **_vista(nome, dati),
        "salvato": datetime.fromtimestamp(file.stat().st_mtime).isoformat(),
        "ignorate": ignorate,
    }


# ------------------------------------------------------------- la pagina

if WEB.is_dir():
    app.mount("/statico", StaticFiles(directory=WEB), name="statico")

    @app.get("/")
    def pagina() -> FileResponse:
        return FileResponse(WEB / "index.html")
