"""Il disegno sulla tela è JavaScript: qui si controlla quel poco che si può.

I test Python non vedono il canvas. Possono però accorgersi di due cose che
sono già costate un giro a vuoto:

1. che il codice del disegno non abbia errori di sintassi (un `main.js`
   rotto non dà errori in Python: la tela resta semplicemente vuota);
2. che il riferimento al file porti un numero di versione — è statico e il
   browser se lo tiene, quindi una modifica al disegno può restare
   invisibile anche dopo aver riavviato l'app.
"""
import re
import shutil
import subprocess
from pathlib import Path

import pytest

FRONTEND = Path(__file__).resolve().parent.parent / "cme_viewer" / "frontend"
MAIN_JS = FRONTEND / "main.js"
INDEX = FRONTEND / "index.html"


def test_il_disegno_e_al_suo_posto():
    assert MAIN_JS.is_file() and INDEX.is_file()


@pytest.mark.skipif(shutil.which("node") is None,
                    reason="node non installato su questa macchina")
def test_il_codice_del_disegno_non_ha_errori_di_sintassi():
    """Un main.js rotto non fa rumore in Python: la tela resta vuota."""
    esito = subprocess.run(["node", "--check", str(MAIN_JS)],
                           capture_output=True, text=True)
    assert esito.returncode == 0, esito.stderr


def test_il_disegno_si_carica_con_un_numero_di_versione():
    """Senza, il browser continua a usare la copia vecchia.

    È successo: il perimetro commerciale doveva restare visibile a locali
    nascosti, il codice era giusto e il server lo serviva, ma nel browser
    non cambiava niente.
    """
    testo = INDEX.read_text(encoding="utf-8")
    assert re.search(r'src="\./main\.js\?v=[^"]+"', testo), (
        "index.html deve caricare main.js con un ?v=… da cambiare a ogni "
        "modifica del disegno, o il browser terrà la versione vecchia")


def test_il_perimetro_commerciale_resta_visibile_a_locali_nascosti():
    """La regola vive in una funzione sola: che ci sia, e che sia usata."""
    testo = MAIN_JS.read_text(encoding="utf-8")
    assert "function zoneVisibili" in testo
    assert "senza_sfondo" in testo.split("function zoneVisibili")[1][:300]
    # e nessun disegno delle zone deve più passare da `mostraAree` a mano
    assert "mostraAree ? zone : []" not in testo
    assert "mostraAree ? zoneOrdinate() : []" not in testo
