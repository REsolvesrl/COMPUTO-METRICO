"""Le fatture caricate, tenute accanto al progetto che le ha ricevute.

Fino al 2/10/2026 una fattura trascinata nel Business plan veniva letta e
poi buttata: restavano i numeri nella tabella delle spese, del documento non
restava niente. Chi a distanza di mesi voleva rivedere la fattura di una
riga doveva andarsela a ripescare nella posta o nel cassetto fiscale.

Adesso il file viene messo da parte, **una cartella per cantiere**: due
operazioni diverse non devono mai mescolare le loro fatture, e aprire la
cartella di un cantiere deve dare quel cantiere e basta.

    <archivio>/fatture/<nome del progetto>/<nome del file>

Dentro l'archivio, come le `versioni`: così una sola variabile d'ambiente
(CME_ARCHIVIO) sposta tutto quanto, e chi fa copia dell'archivio si porta
dietro anche i documenti. La cartella nasce quando arriva la prima fattura,
non prima.

La riga di spesa tiene solo il NOME del file, non il percorso: il cantiere
lo dice la cartella. Così l'archivio si può spostare di posto — altro
computer, altro disco — senza che i collegamenti si rompano.

⚠️ La cartella porta il nome del progetto, esattamente come il suo .json. Se
il progetto si rinomina, il salvataggio scrive un file nuovo e lascia stare
il vecchio: le fatture si comportano allo stesso modo e restano col nome di
prima. È una conseguenza, non una scelta: cambiare nome qui vuol dire fare
un altro progetto.
"""
import re
import unicodedata
from pathlib import Path

import archivio_locale

CARTELLA_FATTURE = "fatture"


def _pulito(nome, ripiego):
    """Un nome che un filesystem accetta: senza separatori né caratteri
    proibiti, senza punti davanti, mai vuoto."""
    nome = unicodedata.normalize("NFC", str(nome or "")).strip()
    nome = re.sub(r'[\\/:*?"<>|\x00-\x1f]+', "", nome).strip(" .")
    return nome[:120] or ripiego


def cartella(progetto):
    """La cartella delle fatture di un cantiere, senza crearla."""
    return (archivio_locale.cartella() / CARTELLA_FATTURE
            / _pulito(progetto, "progetto"))


def _col_numero(nome, n):
    """«fattura.pdf» + 2 → «fattura (2).pdf»: il numero PRIMA dell'estensione.

    Dopo l'estensione («fattura.pdf (2)») il file smette di essere un PDF
    per il computer di chi lo apre, e non si apre più con niente.
    """
    gambo, punto, coda = nome.rpartition(".")
    if punto and gambo:
        return f"{gambo} ({n}).{coda}"
    return f"{nome} ({n})"


def nome_distinto(nome, presi):
    """Lo stesso nome se non è fra i `presi`, altrimenti col suo numero.

    Due fatture possono chiamarsi tutte e due «fattura.pdf» — i fornitori
    non si mettono d'accordo — e la seconda non deve cancellare la prima.
    """
    nome = _pulito(nome, "fattura.pdf")
    if nome not in presi:
        return nome
    for n in range(2, 1000):
        tentativo = _col_numero(nome, n)
        if tentativo not in presi:
            return tentativo
    raise OSError(f"Troppi file che si chiamano «{nome}».")


def salva(progetto, nome_file, contenuto):
    """Mette via una fattura e restituisce il nome con cui l'ha messa.

    Il nome che torna va scritto nella riga di spesa: può non essere quello
    di partenza (un doppione prende un numero in coda).
    """
    cart = cartella(progetto)
    cart.mkdir(parents=True, exist_ok=True)
    nome = nome_distinto(nome_file, {f.name for f in cart.iterdir()})
    (cart / nome).write_bytes(contenuto)
    return nome


def percorso(progetto, nome):
    """Il file di una fattura, o None se non c'è.

    ⚠️ Il nome arriva da una riga di tabella, che si scrive a mano: un nome
    con dentro un percorso («..\\..\\qualcosa») non deve far leggere file
    fuori dalla cartella del cantiere. Si confronta il percorso risolto con
    la cartella, e quello che casca fuori non esiste.
    """
    if not nome:
        return None
    cart = cartella(progetto)
    file = (cart / str(nome)).resolve()
    try:
        file.relative_to(cart.resolve())
    except (ValueError, OSError):
        return None
    return file if file.is_file() else None


def elenco(progetto):
    """I nomi delle fatture messe da parte per questo cantiere."""
    cart = cartella(progetto)
    if not cart.is_dir():
        return []
    return sorted((f.name for f in cart.iterdir() if f.is_file()),
                  key=str.lower)
