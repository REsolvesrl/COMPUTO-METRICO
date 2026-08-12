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

# Quante versioni di uno stesso progetto restano a disposizione, CONTANDO
# quella attuale: il file del progetto più le due precedenti. Al salvataggio
# successivo la più vecchia delle tre esce di scena.
#
# Tre e non dieci perché il valore di una versione precedente cade in fretta:
# serve a rimediare all'ultimo errore («ho sovrascritto il computo buono»),
# non a fare la storia dell'operazione. E ogni versione pesa quanto il
# progetto — con le planimetrie dentro, qualche megabyte l'una.
VERSIONI_TENUTE = 3
CARTELLA_VERSIONI = "versioni"


def cartella():
    """La cartella dell'archivio, senza crearla."""
    scelta = os.environ.get("CME_ARCHIVIO")
    if scelta:
        return Path(scelta).expanduser()
    return Path.home() / "CME" / "progetti"


def cartella_versioni():
    """Dove finiscono le versioni precedenti, senza crearla.

    Sottocartella dell'archivio: così `elenco_progetti` e `ultimo_progetto`,
    che guardano solo i file in cima, non la vedono nemmeno — le versioni
    non sono progetti da aprire, sono il passato di un progetto.
    """
    return cartella() / CARTELLA_VERSIONI


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


def _radice(nome):
    """Il nome-file senza estensione, con cui si nominano le sue versioni."""
    return _chiave(nome)[:-len(ESTENSIONE)]


def versioni(nome):
    """Le versioni PRECEDENTI del progetto, dalla più recente. [] se non ce ne sono.

    Non comprende il progetto attuale: quello è il suo file, e si apre da lì.
    """
    cart = cartella_versioni()
    if not cart.is_dir():
        return []
    trovate = [f for f in cart.glob(_radice(nome) + "__*" + ESTENSIONE)
               if f.is_file()]
    # il nome porta la data in formato ordinabile, quindi ordinare per nome
    # ordina per tempo — e non dipende dalle date dei file, che una copia o
    # un backup possono cambiare senza che il contenuto cambi
    return sorted(trovate, key=lambda f: f.name, reverse=True)


def quando_versione(file):
    """La data di una versione, letta dal suo nome."""
    marca = Path(file).name.rsplit("__", 1)[-1][:-len(ESTENSIONE)]
    try:
        return datetime.strptime(marca, "%Y%m%d-%H%M%S")
    except ValueError:
        return datetime.fromtimestamp(Path(file).stat().st_mtime)


def carica_versione(file):
    """Legge una versione precedente e restituisce il dizionario Python."""
    with open(file, encoding="utf-8") as fh:
        return json.load(fh)


def _metti_da_parte(finale, quando=None):
    """Archivia il progetto attuale prima che venga sovrascritto.

    Poi pota: restano le VERSIONI_TENUTE − 1 più recenti, perché la terza
    è il file del progetto che sta per essere riscritto.
    """
    if not finale.is_file():
        return                      # primo salvataggio: non c'è un prima
    cart = cartella_versioni()
    cart.mkdir(parents=True, exist_ok=True)
    radice = finale.name[:-len(ESTENSIONE)]
    marca = (quando or datetime.now()).strftime("%Y%m%d-%H%M%S")
    # due salvataggi nello stesso secondo finiscono sullo stesso nome: il
    # secondo sovrascrive il primo, che è la cosa giusta (sono lo stesso
    # istante di lavoro) e soprattutto non fa fallire il salvataggio
    (cart / f"{radice}__{marca}{ESTENSIONE}").write_bytes(finale.read_bytes())
    for vecchia in sorted(cart.glob(radice + "__*" + ESTENSIONE),
                          key=lambda f: f.name,
                          reverse=True)[VERSIONI_TENUTE - 1:]:
        vecchia.unlink(missing_ok=True)


def salva_progetto(nome, contenuto):
    """Scrive (o sovrascrive) il progetto `nome` con i byte JSON `contenuto`.

    Scrive prima un file temporaneo e poi lo rinomina: se manca la corrente a
    metà salvataggio, il progetto di prima resta intatto invece di rimanere
    troncato a metà.

    Prima di sovrascrivere, la versione attuale viene messa da parte: di ogni
    progetto restano le ultime VERSIONI_TENUTE, e la più vecchia esce di
    scena da sola. È il rimedio all'errore che il salvataggio manuale non
    poteva coprire — salvare sopra il lavoro buono — e a differenza di un
    salvataggio automatico ogni versione è uno stato che una persona ha
    deciso di salvare, non un'istantanea presa da un timer.

    ⚠️ La messa da parte non deve MAI impedire il salvataggio: se la copia
    non riesce (disco pieno, cartella in sola lettura) si salva lo stesso.
    Perdere la cronologia è un dispiacere, perdere il lavoro no.
    """
    cart = cartella()
    cart.mkdir(parents=True, exist_ok=True)
    finale = cart / _chiave(nome)
    try:
        _metti_da_parte(finale)
    except OSError:
        pass
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
    """Elimina il progetto `nome`, con tutte le sue versioni precedenti.

    Le versioni se ne vanno con lui: sono il passato di quel progetto, e
    lasciarle in giro vorrebbe dire che «elimina» non elimina davvero.
    """
    file = cartella() / _chiave(nome)
    if not file.is_file():
        raise RuntimeError(f"Il progetto «{nome}» non è in archivio.")
    file.unlink()
    for vecchia in versioni(nome):
        vecchia.unlink(missing_ok=True)
