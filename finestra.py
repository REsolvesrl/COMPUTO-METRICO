"""La finestra dell'applicazione, condivisa fra l'avvio normale e il .exe.

Storia di questa scelta (2026-08-09). La prima versione incastonava la pagina
con pywebview, cioè WebView2. Con lo stesso identico codice Python, il
componente della planimetria si inceppava al secondo «annulla» — e nel
browser vero, no: stessi log, nessun errore, tutto regolare. Invece di
combattere contro un motore di rendering che non possiamo ispezionare, si usa
quello che funziona: Edge (o Chrome) in **modalità applicazione**, che dà
esattamente ciò che serviva — una finestra pulita, senza schede né barra
degli indirizzi, con la sua voce nella barra delle applicazioni.
"""
import os
import socket
import subprocess
import tempfile
from pathlib import Path


def porta_libera():
    """Una porta di sicuro libera, scelta dal sistema operativo.

    Fissarne una darebbe «porta occupata» il giorno in cui restano aperte due
    copie del programma, o un'altra app usa lo stesso numero.
    """
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def trova_browser():
    """Edge o Chrome, il primo che si trova. None se non c'è nessuno dei due."""
    basi = [
        os.environ.get("ProgramFiles(x86)", r"C:\Program Files (x86)"),
        os.environ.get("ProgramFiles", r"C:\Program Files"),
        os.environ.get("LOCALAPPDATA", ""),
    ]
    candidati = []
    for base in basi:
        if not base:
            continue
        candidati += [
            Path(base) / "Microsoft" / "Edge" / "Application" / "msedge.exe",
            Path(base) / "Google" / "Chrome" / "Application" / "chrome.exe",
        ]
    return next((c for c in candidati if c.is_file()), None)


def apri_finestra(indirizzo, profilo="cme-finestra"):
    """Apre `indirizzo` in una finestra pulita. Processo, o None se non può.

    `--user-data-dir` non è un dettaglio: senza, Edge passa l'indirizzo a una
    finestra già aperta ed esce subito, e il programma crederebbe che l'utente
    abbia chiuso l'app appena avviata.
    """
    browser = trova_browser()
    if browser is None:
        return None
    cartella_profilo = Path(tempfile.gettempdir()) / profilo
    return subprocess.Popen([
        str(browser),
        f"--app={indirizzo}",
        f"--user-data-dir={cartella_profilo}",
        "--no-first-run", "--no-default-browser-check",
        "--window-size=1500,950",
    ])


def mostra_errore(testo, titolo="CME non è riuscito ad avviarsi"):
    """Scrive l'errore in una pagina e la apre: meglio di una finestra vuota."""
    pagina = Path(tempfile.gettempdir()) / "cme_avvio_fallito.html"
    pagina.write_text(
        "<meta charset='utf-8'><body style=\"font-family:system-ui;"
        "background:#1A2744;color:#ECE7DA;padding:2rem\">"
        f"<h2>{titolo}</h2><p>Copia questo messaggio e mandalo a Claude:</p>"
        "<pre style=\"white-space:pre-wrap;background:#243352;padding:1rem;"
        f"border:1px solid #C9A96A\">{testo}</pre></body>",
        encoding="utf-8")
    indirizzo = pagina.as_uri()
    if apri_finestra(indirizzo, profilo="cme-errore") is None:
        import webbrowser
        webbrowser.open(indirizzo)
