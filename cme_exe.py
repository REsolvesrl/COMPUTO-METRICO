"""Punto di ingresso del programma impacchettato (CME.exe).

Un solo eseguibile con due mestieri, scelti dagli argomenti:

* senza argomenti — è la finestra: accende il motore (rilanciando SE STESSO
  con `--motore`) e mostra l'app dentro una finestra di Windows;
* con `--motore <porta>` — è il motore: fa girare Streamlit su quella porta.

Perché non lanciare `python -m streamlit` come fa `avvia_finestra.py`: dentro
il pacchetto Python non c'è come comando separato, e `sys.executable` è
CME.exe stesso. Rilanciarsi con un argomento diverso è il modo pulito di
avere due processi — e quindi di poter spegnere il motore chiudendo la
finestra, invece di lasciarlo acceso.
"""
import multiprocessing
import os
import socket
import subprocess
import sys
import time
from pathlib import Path

TITOLO = "CME — Computo Metrico Estimativo"
ATTESA_MASSIMA = 120        # il primo avvio del pacchetto è il più lento


def cartella_base():
    """Dove stanno i file dell'app: nel pacchetto o accanto al sorgente."""
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent


# ----------------------------------------------------------------- motore

def fai_il_motore(porta):
    """Esegue Streamlit in questo processo, senza aprire il browser."""
    base = cartella_base()
    # Streamlit legge .streamlit/config.toml (il tema) dalla cartella corrente
    os.chdir(base)
    sys.path.insert(0, str(base))
    from streamlit.web import cli as stcli
    sys.argv = [
        "streamlit", "run", str(base / "streamlit_app.py"),
        "--server.port", str(porta),
        "--server.address", "127.0.0.1",     # solo questo computer
        "--server.headless", "true",
        "--browser.gatherUsageStats", "false",
        "--global.developmentMode", "false",
    ]
    sys.exit(stcli.main())


# ---------------------------------------------------------------- finestra

def porta_libera():
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def accendi_motore(porta):
    senza_finestra = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(
        [sys.executable, "--motore", str(porta)],
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
        creationflags=senza_finestra)


def attendi_motore(porta, processo, secondi=ATTESA_MASSIMA):
    scadenza = time.monotonic() + secondi
    while time.monotonic() < scadenza:
        if processo.poll() is not None:
            return False
        with socket.socket() as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", porta)) == 0:
                return True
        time.sleep(0.3)
    return False


def ultime_parole(processo):
    try:
        uscita = processo.communicate(timeout=5)[0] or b""
    except Exception:
        return "Il motore non ha detto niente."
    righe = uscita.decode("utf-8", "replace").strip().splitlines()
    return "\n".join(righe[-20:]) or "Il motore non ha detto niente."


def fai_la_finestra():
    import webview
    porta = porta_libera()
    motore = accendi_motore(porta)
    if not attendi_motore(porta, motore):
        dettaglio = ultime_parole(motore)
        webview.create_window(
            TITOLO + " — avvio non riuscito",
            html="<h2 style='font-family:sans-serif'>CME non è riuscito ad "
                 "avviarsi</h2><p style='font-family:sans-serif'>Copia questo "
                 "messaggio e mandalo a Claude:</p><pre style='white-space:"
                 f"pre-wrap;background:#f4f4f4;padding:12px'>{dettaglio}</pre>",
            width=900, height=600)
        webview.start()
        return 1

    webview.create_window(TITOLO, f"http://127.0.0.1:{porta}",
                          width=1500, height=950, min_size=(1000, 650))
    try:
        webview.start()
    finally:
        motore.terminate()
        try:
            motore.wait(timeout=10)
        except subprocess.TimeoutExpired:
            motore.kill()
    return 0


def main():
    multiprocessing.freeze_support()
    if len(sys.argv) > 2 and sys.argv[1] == "--motore":
        fai_il_motore(int(sys.argv[2]))
        return 0
    return fai_la_finestra()


if __name__ == "__main__":
    sys.exit(main())
