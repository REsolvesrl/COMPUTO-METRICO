"""
uso.py — registro d'uso per MORA, CME e CATASTO.

Scopo: contare automaticamente le lavorazioni svolte con ciascun applicativo,
per alimentare la relazione di congruita' e per documentare l'utilizzo effettivo.

Caratteristiche
---------------
- File unico, nessuna dipendenza esterna (solo libreria standard).
- Log append-only in JSONL, un file per anno.
- Catena di hash: ogni riga incorpora l'hash della precedente, quindi una
  modifica retroattiva rompe la catena ed e' rilevabile con `verifica`.
- Nessun dato personale viene registrato: si scrivono solo contatori e
  riferimenti non identificativi.

Uso nel codice degli applicativi
--------------------------------
    from uso import registra
    registra("MORA", "posizione_analizzata")
    registra("CME",  "operazione_valutata")
    registra("CATASTO", "verifica_catastale")

Da riga di comando
------------------
    python uso.py report 2026        # tabella dei conteggi
    python uso.py allegato 2026      # righe pronte per l'Allegato F
    python uso.py verifica 2026      # controllo integrita' della catena
    python uso.py consolida 2026 CARTELLA   # somma i registri di piu' postazioni

Piu' postazioni
---------------
Ogni postazione tiene il proprio registro: il nome del file include quello
della macchina, cosi' i file di postazioni diverse possono essere copiati in
un'unica cartella senza sovrascriversi. A fine anno si raccolgono i file e si
esegue `consolida`, che verifica separatamente la catena di ciascuno e somma
i conteggi.
"""

from __future__ import annotations

import glob
import hashlib
import json
import os
import socket
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path

# Cartella del registro. Sovrascrivibile con la variabile d'ambiente USO_DIR.
BASE = Path(os.environ.get("USO_DIR", Path.home() / ".resolve_uso"))

# Eventi previsti per ciascun applicativo. Serve solo a evitare refusi.
EVENTI = {
    "MORA": ["posizione_analizzata", "report_esportato"],
    "CME": ["operazione_valutata", "computo_prodotto", "cantiere_aggiornato"],
    "CATASTO": ["verifica_catastale", "note_lavorate", "export_prodotto"],
}


def _postazione() -> str:
    """Nome della postazione, ripulito. Sovrascrivibile con USO_POSTAZIONE."""
    nome = os.environ.get("USO_POSTAZIONE") or socket.gethostname() or "postazione"
    return "".join(c if c.isalnum() or c in "-_" else "-" for c in nome)[:32]


def _percorso(anno: int) -> Path:
    BASE.mkdir(parents=True, exist_ok=True)
    return BASE / f"uso_{anno}_{_postazione()}.jsonl"


def _ultimo_hash(path: Path) -> str:
    if not path.exists():
        return "0" * 64
    ultima = None
    with path.open("r", encoding="utf-8") as f:
        for riga in f:
            if riga.strip():
                ultima = riga
    if ultima is None:
        return "0" * 64
    return json.loads(ultima).get("h", "0" * 64)


def _hash_riga(prec: str, corpo: dict) -> str:
    grezzo = prec + json.dumps(corpo, sort_keys=True, ensure_ascii=False)
    return hashlib.sha256(grezzo.encode("utf-8")).hexdigest()


def registra(app: str, evento: str, riferimento: str | None = None) -> None:
    """Registra una lavorazione.

    `riferimento` e' facoltativo e deve essere un codice non identificativo
    (es. numero di pratica interno). Non passare mai nomi, codici fiscali o
    altri dati personali: vengono comunque troncati e resi in forma di hash.
    """
    if app in EVENTI and evento not in EVENTI[app]:
        raise ValueError(f"evento '{evento}' non previsto per {app}: {EVENTI[app]}")

    ora = datetime.now(timezone.utc)
    corpo = {
        "t": ora.isoformat(timespec="seconds"),
        "app": app,
        "ev": evento,
        "p": _postazione(),
    }
    if riferimento:
        corpo["rif"] = hashlib.sha256(str(riferimento).encode("utf-8")).hexdigest()[:12]

    path = _percorso(ora.year)
    prec = _ultimo_hash(path)
    corpo["h"] = _hash_riga(prec, corpo)

    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(corpo, ensure_ascii=False) + "\n")


def _leggi_file(path: Path) -> list[dict]:
    if not path.exists():
        return []
    with path.open("r", encoding="utf-8") as f:
        return [json.loads(r) for r in f if r.strip()]


def _file_anno(anno: int, cartella: Path | None = None) -> list[Path]:
    base = cartella or BASE
    return sorted(Path(p) for p in glob.glob(str(base / f"uso_{anno}*.jsonl")))


def _leggi(anno: int, cartella: Path | None = None) -> list[dict]:
    righe: list[dict] = []
    for f in _file_anno(anno, cartella):
        righe.extend(_leggi_file(f))
    return righe


def report(anno: int, cartella: Path | None = None) -> str:
    righe = _leggi(anno, cartella)
    if not righe:
        return f"Nessuna registrazione per il {anno}."

    conteggi = Counter((r["app"], r["ev"]) for r in righe)
    per_mese = Counter((r["app"], r["t"][:7]) for r in righe)

    postazioni = sorted({r.get("p", "?") for r in righe})
    out = [
        f"REGISTRO D'USO {anno}",
        "=" * 46,
        f"Postazioni: {', '.join(postazioni)}",
        "",
    ]
    for app in sorted({a for a, _ in conteggi}):
        out.append(app)
        for (a, ev), n in sorted(conteggi.items()):
            if a == app:
                out.append(f"   {ev:<24} {n:>6}")
        mesi = sorted(m for (a, m) in per_mese if a == app)
        if mesi:
            out.append(f"   {'attivo da':<24} {mesi[0]} a {mesi[-1]}")
        out.append("")
    out.append(f"Totale registrazioni: {len(righe)}")
    return "\n".join(out)


def allegato(anno: int, cartella: Path | None = None) -> str:
    """Righe pronte da incollare nella Parte 1 dell'Allegato F."""
    righe = _leggi(anno, cartella)
    c = Counter((r["app"], r["ev"]) for r in righe)
    mappa = [
        ("Posizioni creditizie analizzate con MORA", ("MORA", "posizione_analizzata")),
        ("Operazioni immobiliari valutate con CME", ("CME", "operazione_valutata")),
        ("Verifiche catastali effettuate con CATASTO", ("CATASTO", "verifica_catastale")),
    ]
    out = [f"| # | Dato (anno {anno}) | Valore |", "|---|---|---|"]
    for i, (etichetta, chiave) in enumerate(mappa, start=1):
        out.append(f"| {i} | {etichetta} | {c.get(chiave, 0)} |")
    out.append("| 4 | Tempo medio per lavorazione senza applicativo (ore) | _da stimare_ |")
    out.append("| 5 | Costo orario di chi la svolgerebbe (€/ora) | _da stimare_ |")
    out.append("| 6 | Costo annuo di distribuzione e archiviazione (€) | _da rilevare_ |")
    return "\n".join(out)


def verifica(anno: int, cartella: Path | None = None) -> str:
    files = _file_anno(anno, cartella)
    if not files:
        return f"Nessuna registrazione per il {anno}."
    esiti = []
    for path in files:
        righe = _leggi_file(path)
        prec = "0" * 64
        rotto = None
        for i, r in enumerate(righe, start=1):
            atteso = _hash_riga(prec, {k: v for k, v in r.items() if k != "h"})
            if atteso != r.get("h"):
                rotto = (i, r.get("t"))
                break
            prec = r["h"]
        if rotto:
            esiti.append(f"{path.name}: CATENA INTERROTTA alla riga {rotto[0]} ({rotto[1]}).")
        else:
            esiti.append(f"{path.name}: integra, {len(righe)} registrazioni. Hash finale {prec}")
    esiti.append("")
    esiti.append("Apporre marca temporale sugli hash finali a fine anno.")
    return "\n".join(esiti)


def consolida(anno: int, cartella: Path) -> str:
    """Verifica e somma i registri di piu' postazioni raccolti in una cartella."""
    return verifica(anno, cartella) + "\n\n" + report(anno, cartella) + "\n\n" + allegato(anno, cartella)


if __name__ == "__main__":
    comando = sys.argv[1] if len(sys.argv) > 1 else "report"
    anno = int(sys.argv[2]) if len(sys.argv) > 2 else datetime.now().year
    cartella = Path(sys.argv[3]) if len(sys.argv) > 3 else None
    if comando == "consolida":
        if cartella is None:
            sys.exit("uso: python uso.py consolida ANNO CARTELLA")
        print(consolida(anno, cartella))
    else:
        print({"report": report, "allegato": allegato, "verifica": verifica}[comando](anno, cartella))
