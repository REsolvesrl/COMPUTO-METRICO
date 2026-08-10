"""Le operazioni chiuse, fuori dai progetti: la memoria fra un affare e l'altro.

Ogni progetto è un'isola: quando il cantiere finisce, quello che hai imparato
resta dentro quel file e non serve alla valutazione successiva. Qui invece
sopravvive una riga per operazione chiusa — contratto, extra, sforamento,
costo al metro — e da tre righe in poi comincia a dire cose che nessun
prezzario sa: quanto sfori **tu**, con le **tue** imprese.

Dove: `~/CME/storico_operazioni.json`, accanto ai progetti e al listino
personale, oppure il percorso scritto in `CME_STORICO`.
"""
import json
import os
from datetime import date
from pathlib import Path

import archivio_locale

CAMPI = ("nome", "chiusa_il", "contratto", "extra", "scostamento",
         "mq_calpestabili", "eur_mq")


def percorso():
    """Il file dello storico, senza crearlo."""
    scelta = os.environ.get("CME_STORICO")
    if scelta:
        return Path(scelta).expanduser()
    return archivio_locale.cartella().parent / "storico_operazioni.json"


def carica():
    """Le operazioni chiuse, dalla più recente. [] se non ce ne sono.

    Uno storico rovinato non deve impedire di lavorare: si riparte da
    vuoto, che è la condizione di chi non ha ancora chiuso niente.
    """
    file = percorso()
    if not file.is_file():
        return []
    try:
        dati = json.loads(file.read_text(encoding="utf-8"))
        righe = [r for r in (dati.get("operazioni") or [])
                 if isinstance(r, dict)]
        return sorted(righe, key=lambda r: r.get("chiusa_il") or "",
                      reverse=True)
    except Exception:  # noqa: BLE001 — file rovinato: si riparte da vuoto
        return []


def registra(operazione, quando=None):
    """Aggiunge (o sostituisce) l'operazione chiusa. Ritorna tutte le righe.

    La chiave è il nome: richiudere la stessa operazione la corregge invece
    di contarla due volte — capita di sbagliare l'importo degli extra e di
    volerlo rimettere a posto il giorno dopo.
    """
    riga = {campo: operazione.get(campo) for campo in CAMPI}
    riga["nome"] = (riga.get("nome") or "").strip() or "Operazione senza nome"
    riga["chiusa_il"] = riga.get("chiusa_il") or (quando
                                                  or date.today()).isoformat()
    righe = [r for r in carica() if r.get("nome") != riga["nome"]]
    righe.append(riga)
    _scrivi(righe)
    return sorted(righe, key=lambda r: r.get("chiusa_il") or "", reverse=True)


def elimina(nome):
    """Toglie un'operazione dallo storico. True se c'era."""
    righe = carica()
    restanti = [r for r in righe if r.get("nome") != nome]
    if len(restanti) == len(righe):
        return False
    _scrivi(restanti)
    return True


def _scrivi(righe):
    """Come per i progetti: prima il temporaneo, poi il rinomino."""
    file = percorso()
    file.parent.mkdir(parents=True, exist_ok=True)
    temporaneo = file.with_suffix(".json.parziale")
    temporaneo.write_text(
        json.dumps({"operazioni": righe}, ensure_ascii=False, indent=1),
        encoding="utf-8")
    temporaneo.replace(file)


def scostamenti(righe=None):
    """Gli sforamenti delle operazioni chiuse, per tararci gli imprevisti."""
    return [r.get("scostamento") for r in (carica() if righe is None else righe)
            if r.get("scostamento") is not None]


def costi_al_mq(righe=None):
    """I costi di ristrutturazione al metro già realizzati."""
    return [r.get("eur_mq") for r in (carica() if righe is None else righe)
            if r.get("eur_mq")]


def media(valori):
    """Media semplice, None se non c'è niente da mediare."""
    valori = [float(v) for v in (valori or []) if v is not None]
    if not valori:
        return None
    return round(sum(valori) / len(valori), 2)
