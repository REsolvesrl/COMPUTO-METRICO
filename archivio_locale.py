"""Archivio dei progetti in una cartella del computer.

Gemello di `archivio.py` (che invece parla con Supabase), con le stesse quattro
funzioni: elenco, salva, carica, elimina. Qui però non servono account, chiavi
né connessione: ogni progetto è un file `.json` dentro una cartella.

Dove: `~/CME/progetti` (per Fredrik: `C:\\Users\\fredr\\CME\\progetti`), oppure
il percorso scritto nella variabile d'ambiente `CME_ARCHIVIO`. La cartella
viene creata al primo salvataggio, non all'avvio: un'app che si mette a creare
cartelle solo perché è partita è invadente.
"""
import json
import os
import re
from datetime import datetime
from pathlib import Path

ESTENSIONE = ".json"


def cartella():
    """La cartella dell'archivio, senza crearla."""
    scelta = os.environ.get("CME_ARCHIVIO")
    if scelta:
        return Path(scelta).expanduser()
    return Path.home() / "CME" / "progetti"


def configurato():
    """Sempre vero: l'archivio locale non ha niente da configurare.

    Esiste per simmetria con archivio.configurato(), così la UI può trattare i
    due archivi allo stesso modo.
    """
    return True


def _chiave(nome):
    """Nome-file sicuro (stessa regola dell'archivio online)."""
    nome = (nome or "progetto").strip()
    if nome.lower().endswith(ESTENSIONE):
        nome = nome[:-len(ESTENSIONE)]
    nome = re.sub(r'[\\/:*?"<>|]+', "", nome).strip()
    return (nome or "progetto") + ESTENSIONE


def percorso(nome):
    """Percorso completo del file di un progetto."""
    return cartella() / _chiave(nome)


def elenco_progetti():
    """Nomi dei progetti archiviati, in ordine alfabetico."""
    cart = cartella()
    if not cart.is_dir():
        return []
    nomi = [f.name[:-len(ESTENSIONE)] for f in cart.glob("*" + ESTENSIONE)
            if f.is_file()]
    return sorted(nomi, key=str.lower)


def ultimo_progetto():
    """(nome, quando) del progetto archiviato più di recente, o (None, None).

    Serve a riaprire l'app dov'era rimasta: si guarda la data di modifica
    del file, non il nome, perché è l'unica che dice davvero quale è stato
    l'ultimo lavoro.
    """
    cart = cartella()
    if not cart.is_dir():
        return None, None
    file = [f for f in cart.glob("*" + ESTENSIONE) if f.is_file()]
    if not file:
        return None, None
    piu_recente = max(file, key=lambda f: f.stat().st_mtime)
    return (piu_recente.name[:-len(ESTENSIONE)],
            datetime.fromtimestamp(piu_recente.stat().st_mtime))


def salva_progetto(nome, contenuto):
    """Scrive (o sovrascrive) il progetto `nome` con i byte JSON `contenuto`.

    Scrive prima un file temporaneo e poi lo rinomina: se manca la corrente a
    metà salvataggio, il progetto di prima resta intatto invece di rimanere
    troncato a metà.
    """
    cart = cartella()
    cart.mkdir(parents=True, exist_ok=True)
    finale = cart / _chiave(nome)
    temporaneo = finale.with_suffix(".json.parziale")
    if isinstance(contenuto, str):
        contenuto = contenuto.encode("utf-8")
    temporaneo.write_bytes(contenuto)
    temporaneo.replace(finale)
    return finale


def carica_progetto(nome):
    """Legge il progetto `nome` e restituisce il dizionario Python."""
    file = cartella() / _chiave(nome)
    if not file.is_file():
        raise RuntimeError(f"Il progetto «{nome}» non è in archivio.")
    with open(file, encoding="utf-8") as fh:
        return json.load(fh)


def elimina_progetto(nome):
    """Elimina il file del progetto `nome`."""
    file = cartella() / _chiave(nome)
    if not file.is_file():
        raise RuntimeError(f"Il progetto «{nome}» non è in archivio.")
    file.unlink()
