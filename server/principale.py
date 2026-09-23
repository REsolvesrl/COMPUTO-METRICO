"""Il motore nuovo di CME: il banco di lavoro dietro una manciata di rotte.

Il modello è quello di Streamlit, senza Streamlit: il motore tiene aperto
UN progetto (il banco, come una sessione), la pagina manda un gesto e
riceve la vista intera, ricalcolata. Si salva col tasto, come prima.

⚠️ Il salvataggio passa per lo stesso identico modulo del programma
vecchio - `archivio_locale` - e il banco scrive il file nello stesso
formato (lo prova tests/test_banco_come_il_vecchio.py). Un progetto
scritto da qui si riapre col vecchio, e viceversa.

⚠️ Si ascolta **solo su 127.0.0.1**, ed è scritto nell'avvio: Streamlit,
per com'è fatto, risponde invece su tutte le schede di rete.
"""

from __future__ import annotations

import os
import threading
from datetime import datetime
from pathlib import Path

# ⚠️ **Il cantiere non tocca il lavoro vero, e non perché qualcuno si
# ricordi di dirglielo.** Finché questa versione è in costruzione lavora in
# ~/CME/prova: i progetti in `prova/progetti`, e accanto a loro — perché è
# lì che li cercano i loro moduli — il listino personale e lo storico delle
# operazioni. Anche il registro d'uso va in una cartella sua: le prove non
# sono lavorazioni. È deciso qui, non nel .bat (che si può lanciare in un
# altro modo) né in una variabile d'ambiente (che si può dimenticare): chi
# vuole l'archivio vero lo dice a voce alta impostando `CME_ARCHIVIO`.
#
# Quando il cantiere avrà finito, si toglie questo blocco.
_PROVA = Path.home() / "CME" / "prova"
os.environ.setdefault("CME_ARCHIVIO", str(_PROVA / "progetti"))
os.environ.setdefault("USO_DIR", str(_PROVA / "uso"))

import json  # noqa: E402

import plotly  # noqa: E402
from fastapi import FastAPI, HTTPException, UploadFile  # noqa: E402
from fastapi.responses import FileResponse, Response  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import archivio_locale  # noqa: E402
import esporta  # noqa: E402
from banco import Banco, ErroreBanco  # noqa: E402
from server import vista as viste  # noqa: E402

RADICE = Path(__file__).resolve().parent.parent
WEB = RADICE / "web"
PLOTLY_JS = Path(plotly.__file__).parent / "package_data" / "plotly.min.js"

app = FastAPI(title="CME", docs_url="/api/documentazione", redoc_url=None)

BANCO = Banco()
# Un gesto alla volta: le rotte girano in un gruppo di thread, e due gesti
# che si incrociano sullo stesso progetto sarebbero un disastro silenzioso.
CHIAVE = threading.Lock()


# ------------------------------------------------------------- i gesti
#
# Ogni gesto è una funzione (banco, **argomenti) → testo da dire, o None.
# Solo quelli in questo elenco si possono chiedere dalla pagina.


def _salva(b):
    nome = b.salva()
    return f"«{nome}» salvato alle {b.ultimo_salvataggio:%H:%M}"


def _archivia(b, nome, sovrascrivi=False):
    return f"Progetto «{b.archivia(nome, sovrascrivi)}» archiviato."


def _elimina(b, nome):
    b.elimina_dallarchivio(nome)
    return f"Progetto «{nome}» eliminato dall'archivio."


def _apri_versione(b, file):
    trovata = next((v for v in archivio_locale.versioni(b.nome_archivio())
                    if v.name == file), None)
    if trovata is None:
        raise ErroreBanco("Questa versione non c'è più.")
    b.apri_versione(trovata)


def _sposta(b, codice, categoria):
    nuovo = b.sposta_voce_tua(codice, categoria)
    return f"{codice} → {nuovo} · ora in {categoria} ✔" if nuovo != codice \
        else None


def _crea(b, categoria, descrizione, um, quantita, prezzo):
    codice = b.crea_voce_a_mano(categoria, descrizione, um, quantita, prezzo)
    return f"{codice} · {descrizione.strip()} → {categoria}"


def _annulla(b):
    fatto = b.annulla_computo()
    return f"Annullato: {fatto} ↩️" if fatto else None


def _salva_listino(b):
    return f"Listino personale salvato: {b.salva_listino_personale()} prezzi ✔"


def _applica_listino(b):
    return f"{b.applica_listino_personale()} prezzi aggiornati ✔"


def _elimina_listino(b):
    b.elimina_listino_personale()
    return "Listino personale cancellato"


GESTI = {
    "salva": _salva,
    "apri": lambda b, nome: b.apri(nome),
    "apri_versione": _apri_versione,
    "nuovo": lambda b: b.nuovo(),
    "archivia": _archivia,
    "elimina": _elimina,
    "imposta_progetto": lambda b, campo, valore:
        b.imposta_progetto(campo, valore),
    "quantita": lambda b, codice, valore: b.scrivi_quantita(codice, valore),
    "prezzo": lambda b, codice, valore: b.scrivi_prezzo(codice, valore),
    "descrizione": lambda b, codice, testo: b.scrivi_descrizione(codice,
                                                                 testo),
    "unita": lambda b, codice, um: b.scrivi_unita(codice, um),
    "porta": lambda b, codice: b.porta_nel_computo(codice),
    "togli": lambda b, codice: b.togli_dal_computo(codice),
    "scarta": lambda b, codice: b.scarta(codice),
    "ripristina_scarti": lambda b: b.ripristina_scarti(),
    "prendi_tutte": lambda b: b.prendi_tutte(),
    "scambia": lambda b, codice, verso: b.scambia_con_vicina(codice, verso),
    "sposta": _sposta,
    "crea_voce": _crea,
    "facoltativo": lambda b, categoria, acceso:
        b.cambia_lavoro_facoltativo(categoria, acceso),
    "riaggancia": lambda b, codice=None: b.riaggancia_al_disegno(codice),
    "annulla_computo": _annulla,
    "salva_listino": _salva_listino,
    "applica_listino": _applica_listino,
    "elimina_listino": _elimina_listino,
    "materiali": lambda b, righe: b.scrivi_materiali(righe),
    "riordina_materiali": lambda b, criterio: b.riordina_materiali(criterio),
}


class Gesto(BaseModel):
    nome: str
    argomenti: dict = {}


def _vista():
    BANCO.riapri_ultimo()
    return viste.vista(BANCO)


# ---------------------------------------------------------------- rotte


@app.get("/api/salute")
def salute() -> dict:
    """Dove sta la roba. La prima cosa da guardare quando qualcosa non
    torna: dice su quale archivio si sta lavorando davvero."""
    cartella = archivio_locale.cartella()
    return {
        "archivio_progetti": str(cartella),
        "archivio_esiste": cartella.is_dir(),
        "progetti": len(archivio_locale.elenco_progetti()),
        "registro_uso": os.environ.get("USO_DIR"),
        "progetto_aperto": BANCO.dati["progetto"]["nome"],
    }


@app.get("/api/vista")
def vista() -> dict:
    with CHIAVE:
        return _vista()


@app.post("/api/gesto")
def gesto(corpo: Gesto) -> dict:
    """Un gesto sul progetto aperto; torna la vista intera, e cosa dire."""
    funzione = GESTI.get(corpo.nome)
    if funzione is None:
        raise HTTPException(400, f"Gesto sconosciuto: {corpo.nome}")
    with CHIAVE:
        esito = None
        try:
            testo = funzione(BANCO, **corpo.argomenti)
            if testo:
                esito = {"tipo": "ok", "testo": testo}
        except ErroreBanco as errore:
            esito = {"tipo": "errore", "testo": str(errore)}
        except TypeError as errore:
            raise HTTPException(400, f"Gesto «{corpo.nome}»: {errore}")
        BANCO.giro()
        return {"vista": _vista(), "esito": esito}


@app.post("/api/apri_file")
async def apri_file(file: UploadFile) -> dict:
    """«Apri un progetto salvato (.json)»: dal file, non dall'archivio."""
    contenuto = await file.read()
    try:
        dati = json.loads(contenuto)
    except (json.JSONDecodeError, UnicodeDecodeError):
        return {"vista": None, "esito": {
            "tipo": "errore",
            "testo": "Il file non sembra un progetto salvato da questa app."}}
    with CHIAVE:
        BANCO.carica(dati)
        return {"vista": _vista(), "esito": None}


def _file(contenuto, nome, tipo):
    return Response(contenuto, media_type=tipo, headers={
        "Content-Disposition": f"attachment; filename=\"{nome}\""})


@app.get("/api/scarica/{che_cosa}")
def scarica(che_cosa: str):
    """I file da portarsi via, costruiti adesso e non prima."""
    with CHIAVE:
        b = BANCO
        if che_cosa == "json":
            return _file(b.scarica_json(), b.nome_file("json"),
                         "application/json")
        if che_cosa == "pdf":
            return _file(esporta.pdf_computo(b), b.nome_file("pdf"),
                         "application/pdf")
        if che_cosa == "pdf_senza_prezzi":
            return _file(esporta.pdf_computo(b, con_prezzi=False),
                         b.nome_file("pdf").replace(".pdf",
                                                    "_senza_prezzi.pdf"),
                         "application/pdf")
        if che_cosa == "xlsx":
            return _file(esporta.excel_computo(b), b.nome_file("xlsx"),
                         "application/vnd.openxmlformats-officedocument."
                         "spreadsheetml.sheet")
        if che_cosa == "csv":
            return _file(esporta.csv_computo(b), b.nome_file("csv"),
                         "text/csv")
        if che_cosa == "allegato_materiali":
            return _file(esporta.pdf_allegato_materiali(b),
                         b.nome_file("pdf").replace(
                             ".pdf", "_allegato_materiali.pdf"),
                         "application/pdf")
    raise HTTPException(404, f"Non so preparare «{che_cosa}»")


# ------------------------------------------------------------- la pagina

@app.get("/statico/vendor/plotly.min.js")
def plotly_js() -> FileResponse:
    """Plotly.js viene dal pacchetto Python che disegna le figure: stessa
    versione per forza, e nessuna copia da tenere allineata a mano."""
    return FileResponse(PLOTLY_JS, media_type="text/javascript")


if WEB.is_dir():
    app.mount("/statico", StaticFiles(directory=WEB), name="statico")

    @app.get("/")
    def pagina() -> FileResponse:
        return FileResponse(WEB / "index.html")
