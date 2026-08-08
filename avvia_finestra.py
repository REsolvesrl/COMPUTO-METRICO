"""Apre CME in una finestra sua, senza browser e senza finestra nera.

Come funziona: Streamlit ha bisogno di un piccolo server, ma non c'è motivo
che l'utente lo veda. Qui il server parte in silenzio su una porta libera del
computer (non è raggiungibile da fuori: ascolta solo su 127.0.0.1, cioè la
macchina stessa) e il suo schermo viene mostrato dentro una finestra normale
di Windows, con tanto di icona nella barra delle applicazioni.

Chiudendo la finestra si chiude anche il server: nessun processo che resta
acceso a insaputa di chi lavora.
"""
import socket
import subprocess
import sys
import time
from pathlib import Path

import webview

CARTELLA = Path(__file__).resolve().parent
APP = CARTELLA / "streamlit_app.py"
TITOLO = "CME — Computo Metrico Estimativo"
ATTESA_MASSIMA = 90          # secondi concessi al primo avvio, che è il lento


def porta_libera():
    """Una porta di sicuro libera, scelta dal sistema operativo.

    Fissarne una (es. 8501) darebbe errore se fosse già occupata da un'altra
    app — o da una copia di CME rimasta aperta.
    """
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def avvia_server(porta):
    """Lancia Streamlit in silenzio e restituisce il processo."""
    comando = [
        sys.executable, "-m", "streamlit", "run", str(APP),
        "--server.port", str(porta),
        "--server.address", "127.0.0.1",   # solo questo computer
        "--server.headless", "true",       # non aprire il browser
        "--browser.gatherUsageStats", "false",
    ]
    # CREATE_NO_WINDOW: senza questo comparirebbe la finestra nera del terminale
    senza_finestra = getattr(subprocess, "CREATE_NO_WINDOW", 0)
    return subprocess.Popen(comando, cwd=str(CARTELLA),
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                            creationflags=senza_finestra)


def attendi_server(porta, processo, secondi=ATTESA_MASSIMA):
    """Aspetta che il server risponda. False se muore o non parte in tempo."""
    scadenza = time.monotonic() + secondi
    while time.monotonic() < scadenza:
        if processo.poll() is not None:      # il server è morto durante l'avvio
            return False
        with socket.socket() as s:
            s.settimeout(0.5)
            if s.connect_ex(("127.0.0.1", porta)) == 0:
                return True
        time.sleep(0.3)
    return False


def messaggio_errore(processo):
    """Le ultime righe scritte dal server, per capire cosa è andato storto."""
    try:
        uscita = processo.communicate(timeout=5)[0] or b""
    except Exception:
        return "Il server non ha detto niente."
    righe = uscita.decode("utf-8", "replace").strip().splitlines()
    return "\n".join(righe[-15:]) or "Il server non ha detto niente."


def main():
    porta = porta_libera()
    server = avvia_server(porta)

    if not attendi_server(porta, server):
        # Niente finestra vuota che lascia l'utente a indovinare: si mostra
        # l'errore vero del server dentro una finestra leggibile.
        dettaglio = messaggio_errore(server)
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
        webview.start()          # si blocca finché l'utente chiude la finestra
    finally:
        server.terminate()       # chiusa la finestra, si spegne anche il motore
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
