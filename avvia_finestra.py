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

from finestra import apri_finestra, mostra_errore, porta_libera

CARTELLA = Path(__file__).resolve().parent
APP = CARTELLA / "streamlit_app.py"
TITOLO = "CME — Computo Metrico Estimativo"
ATTESA_MASSIMA = 90          # secondi concessi al primo avvio, che è il lento


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
        # l'errore vero del server, in una pagina leggibile e copiabile.
        mostra_errore(messaggio_errore(server))
        return 1

    try:
        finestra = apri_finestra(f"http://127.0.0.1:{porta}")
        if finestra is not None:
            finestra.wait()      # si blocca finché l'utente chiude la finestra
        else:
            # Nessun Edge né Chrome: si apre nel browser predefinito. Meno
            # elegante di una finestra dedicata, ma funziona sempre.
            import webbrowser
            webbrowser.open(f"http://127.0.0.1:{porta}")
            input()              # tiene vivo il motore finché non si chiude
    finally:
        server.terminate()       # chiusa la finestra, si spegne anche il motore
        try:
            server.wait(timeout=10)
        except subprocess.TimeoutExpired:
            server.kill()
    return 0


if __name__ == "__main__":
    sys.exit(main())
