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

import base64  # noqa: E402
import io  # noqa: E402
import json  # noqa: E402

import plotly  # noqa: E402
from fastapi import FastAPI, HTTPException, UploadFile  # noqa: E402
from fastapi.responses import FileResponse, Response  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from pydantic import BaseModel  # noqa: E402

import archivio_locale  # noqa: E402
import esporta  # noqa: E402
from banco import Banco, ErroreBanco  # noqa: E402
from banco_disegno import ErroreDisegno  # noqa: E402
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


def _annulla_disegno(b):
    fatto = b.annulla_disegno()
    return f"Annullato: {fatto} ↩️" if fatto else None


def _zona_al_computo(b):
    b.zona_al_computo()
    return "Aggiunta al computo ✔"


def _usa_pulizia(b):
    b.usa_pulizia()
    return "Planimetria pulita ✔"


def _rileva(b):
    return f"Trovate {b.rileva_stanze()} stanze ✔"


def _superficie_al_computo(b):
    b.superficie_commerciale_al_computo()
    return "Superficie commerciale aggiunta al computo ✔"


def _scrivi_dal_disegno(b):
    n = b.scrivi_quantita_dal_disegno()
    return f"{n} voci aggiornate nel computo ✔" if n else None


GESTI_DISEGNO = {
    "scegli_pianta": lambda b, indice: b.scegli_pianta(indice),
    "togli_pianta": lambda b, indice: b.togli_pianta(indice),
    "rinomina_pianta": lambda b, nome: b.rinomina_pianta(nome),
    "categoria_nuove": lambda b, nome: b.scegli_categoria_nuove(nome),
    "tipo_parete": lambda b, codice: b.scegli_tipo_parete(codice),
    "evento_tela": lambda b, evento: b.evento_tela(evento),
    "annulla_disegno": _annulla_disegno,
    "imposta_scala": lambda b, metri: b.imposta_scala(metri),
    "annulla_scala": lambda b: b.annulla_scala(),
    "nome_zona": lambda b, nome: b.nome_zona(nome),
    "categoria_zona": lambda b, categoria: b.categoria_zona(categoria),
    "zona_al_computo": _zona_al_computo,
    "elimina_zona": lambda b: b.elimina_zona(),
    "tipo_parete_sel": lambda b, codice: b.tipo_parete_sel(codice),
    "lunghezza_parete": lambda b, metri: b.lunghezza_parete(metri),
    "elimina_parete": lambda b: b.elimina_parete(),
    "prova_pulizia": lambda b, forza: b.prova_pulizia(forza),
    "usa_pulizia": _usa_pulizia,
    "scarta_pulizia": lambda b: b.scarta_pulizia(),
    "ripristina_originale": lambda b: b.ripristina_originale(),
    "rileva_stanze": _rileva,
    "annulla_rilevamento": lambda b: b.annulla_rilevamento(),
    "etichette": lambda b, campo, valore: b.imposta_etichette(campo, valore),
    "riporta_etichette": lambda b: b.riporta_etichette(),
    "superficie_al_computo": _superficie_al_computo,
    "altezza": lambda b, metri: b.imposta_altezza(metri),
    "spunta_locale": lambda b, pianta, zona, campo, valore:
        b.spunta_locale(pianta, zona, campo, valore),
    "finitura": lambda b, campo, valore: b.imposta_finitura(campo, valore),
    "aggancia": lambda b, acceso: b.aggancia_al_disegno(acceso),
    "voce_dal_disegno": lambda b, codice, acceso:
        b.spunta_voce_dal_disegno(codice, acceso),
    "scrivi_dal_disegno": _scrivi_dal_disegno,
}


def _chiudi(b):
    return f"«{b.chiudi_operazione()}» è nello storico ✔"


GESTI_BP = {
    "bp": lambda b, chiave, valore: b.imposta_bp(chiave, valore),
    "riprendi_mq": lambda b: b.riprendi_mq_planimetria(),
    "usa_come_vendita": lambda b, valore: b.usa_come_vendita(valore),
    "applica_imprevisti": lambda b, percentuale:
        b.applica_imprevisti(percentuale),
    "spese": lambda b, registro, righe: b.scrivi_spese(registro, righe),
    "aggiungi_fatture": lambda b, righe: b.aggiungi_fatture(righe),
    "scarta_fatture": lambda b: b.scarta_fatture(),
    "cantiere": lambda b, campo, valore: b.imposta_cantiere(campo, valore),
    "sal": lambda b, righe: b.scrivi_sal(righe),
    "contratto_dal_computo": lambda b: b.contratto_dal_computo(),
    "chiudi_operazione": _chiudi,
    "comparabili": lambda b, righe: b.scrivi_comparabili(righe),
    "soggetto": lambda b, campo, valore: b.scegli_soggetto(campo, valore),
    "statistica": lambda b, valore: b.scegli_statistica(valore),
}


GESTI = {
    **GESTI_DISEGNO,
    **GESTI_BP,
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
        except ErroreDisegno as errore:
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


@app.post("/api/planimetrie")
async def carica_planimetria(file: UploadFile) -> dict:
    """Una planimetria nuova: PNG, JPG o PDF (una per pagina)."""
    contenuto = await file.read()
    with CHIAVE:
        esito = None
        try:
            BANCO.aggiungi_planimetrie(contenuto, file.filename or "pianta")
        except ErroreDisegno as errore:
            esito = {"tipo": "errore", "testo": str(errore)}
        BANCO.giro()
        return {"vista": _vista(), "esito": esito}


@app.post("/api/fatture")
async def leggi_fatture(file: list[UploadFile]) -> dict:
    """Le fatture trascinate: si leggono qui, sul computer, e nessun dato
    esce. Le righe lette tornano da controllare prima di aggiungerle."""
    contenuti = [(f.filename or "", await f.read()) for f in file]
    with CHIAVE:
        n = BANCO.leggi_fatture(contenuti)
        esito = None
        if BANCO.fatture_lette["non_letti"]:
            esito = {"tipo": "errore", "testo": "Non sono riuscito a leggere: "
                     + ", ".join(BANCO.fatture_lette["non_letti"])
                     + ". Aggiungile a mano nella tabella sotto."}
        elif n:
            esito = {"tipo": "ok", "testo": f"{n} fattura/e lette."}
        return {"vista": _vista(), "esito": esito}


def _jpeg(img, qualita=85):
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=qualita)
    return buffer.getvalue()


@app.get("/api/piante/{indice}/immagine")
def immagine_pianta(indice: int):
    """L'immagine della pianta. L'indirizzo porta l'impronta dell'immagine,
    quindi il browser la può tenere: se cambia (pulizia), cambia indirizzo."""
    with CHIAVE:
        try:
            b64 = BANCO.dati["piante"][indice]["immagine"]
        except IndexError:
            raise HTTPException(404, "Planimetria inesistente")
    return Response(base64.b64decode(b64), media_type="image/jpeg",
                    headers={"Cache-Control": "max-age=31536000, immutable"})


@app.get("/api/piante/{indice}/miniatura")
def miniatura_pianta(indice: int):
    with CHIAVE:
        try:
            img = BANCO.immagine(indice).copy()
        except IndexError:
            raise HTTPException(404, "Planimetria inesistente")
    img.thumbnail((240, 240))
    return Response(_jpeg(img), media_type="image/jpeg",
                    headers={"Cache-Control": "max-age=31536000, immutable"})


@app.get("/api/anteprima_pulizia")
def anteprima_pulizia():
    with CHIAVE:
        a = BANCO.anteprima_pulizia
        if not a:
            raise HTTPException(404, "Nessuna anteprima")
        return Response(_jpeg(a["img"]), media_type="image/jpeg",
                        headers={"Cache-Control": "no-store"})


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
        if che_cosa in ("pdf_planimetrie", "pdf_planimetrie_orizzontale"):
            return _file(b.pdf_planimetrie(
                orizzontale=che_cosa.endswith("orizzontale")),
                b.nome_file("pdf").replace(".pdf", "_planimetrie.pdf"),
                "application/pdf")
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


# Il visualizzatore delle planimetrie è quello del programma vecchio, così
# com'è: cme_viewer/frontend parla il protocollo dei componenti Streamlit
# (postMessage), e la pagina nuova lo parla uguale. Nessuna copia da tenere
# allineata: ogni correzione fatta là vale anche qui.
TELA = RADICE / "cme_viewer" / "frontend"
if TELA.is_dir():
    app.mount("/tela", StaticFiles(directory=TELA, html=True), name="tela")

if WEB.is_dir():
    app.mount("/statico", StaticFiles(directory=WEB), name="statico")

    @app.get("/")
    def pagina() -> FileResponse:
        return FileResponse(WEB / "index.html")
