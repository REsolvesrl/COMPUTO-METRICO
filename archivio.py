"""Archivio dei progetti su Supabase Storage (salvataggio/apertura online).

Ogni progetto è un file JSON dentro un bucket privato di Supabase Storage.
Le credenziali stanno fuori dal codice, in uno di questi due posti.

Su Streamlit Cloud, nei «secrets»:

    [supabase]
    url = "https://xxxx.supabase.co"
    key = "…chiave segreta / service_role…"
    bucket = "progetti"

Su host tipo Render, che non hanno il file secrets.toml, nelle variabili
d'ambiente `SUPABASE_URL`, `SUPABASE_KEY` e `SUPABASE_BUCKET`.

Il modulo non solleva mai in modo silenzioso all'import: `configurato()` dice
se le credenziali ci sono, e le funzioni di rete sollevano un'eccezione con un
messaggio leggibile (gestita dalla UI) se qualcosa va storto.
"""
import os
import re
from urllib.parse import quote

import requests
import streamlit as st

TIMEOUT = 30           # secondi per ogni chiamata di rete
ESTENSIONE = ".json"


def _cfg():
    """(base_storage_url, key, bucket), oppure None se le credenziali mancano.

    Prima i secrets di Streamlit, poi le variabili d'ambiente: così le stesse
    funzioni valgono sia su Streamlit Cloud sia su Render.
    """
    url = key = bucket = ""
    try:
        s = st.secrets["supabase"]
        url = str(s["url"])
        key = str(s["key"])
        bucket = str(s["bucket"]) if "bucket" in s else ""
    except Exception:
        pass                       # nessun secrets.toml: si prova l'ambiente
    url = (url or os.environ.get("SUPABASE_URL", "")).rstrip("/")
    key = key or os.environ.get("SUPABASE_KEY", "")
    bucket = bucket or os.environ.get("SUPABASE_BUCKET", "") or "progetti"
    if not url or not key:
        return None
    return f"{url}/storage/v1", key, bucket


def configurato():
    """True se i secrets di Supabase sono presenti e completi."""
    return _cfg() is not None


def _headers(key):
    return {"Authorization": f"Bearer {key}", "apikey": key}


def _chiave(nome):
    """Nome-file sicuro per lo storage (una sola estensione .json)."""
    nome = (nome or "progetto").strip()
    if nome.lower().endswith(ESTENSIONE):
        nome = nome[:-len(ESTENSIONE)]
    # via i caratteri che romperebbero il percorso; spazi e accenti restano
    nome = re.sub(r'[\\/:*?"<>|]+', "", nome).strip()
    return (nome or "progetto") + ESTENSIONE


def _percorso(base, bucket, nome):
    return f"{base}/object/{bucket}/{quote(_chiave(nome), safe='')}"


def _errore(risposta):
    """Messaggio d'errore leggibile da una risposta HTTP non riuscita."""
    testo = (risposta.text or "").strip()
    return f"Supabase ha risposto {risposta.status_code}: {testo[:200]}"


def elenco_progetti():
    """Nomi (senza .json) dei progetti nel bucket, in ordine alfabetico."""
    cfg = _cfg()
    if cfg is None:
        return []
    base, key, bucket = cfg
    r = requests.post(
        f"{base}/object/list/{bucket}",
        headers=_headers(key),
        json={"prefix": "", "limit": 1000,
              "sortBy": {"column": "name", "order": "asc"}},
        timeout=TIMEOUT)
    if not r.ok:
        raise RuntimeError(_errore(r))
    nomi = []
    for o in r.json():
        n = o.get("name", "")
        if n.lower().endswith(ESTENSIONE):
            nomi.append(n[:-len(ESTENSIONE)])
    return sorted(nomi, key=str.lower)


def salva_progetto(nome, contenuto):
    """Crea o sovrascrive il progetto `nome` con i byte JSON `contenuto`."""
    cfg = _cfg()
    if cfg is None:
        raise RuntimeError("Archivio online non configurato.")
    base, key, bucket = cfg
    intestazioni = _headers(key)
    intestazioni["Content-Type"] = "application/json"
    intestazioni["x-upsert"] = "true"      # sovrascrive se esiste già
    r = requests.post(_percorso(base, bucket, nome),
                      headers=intestazioni, data=contenuto, timeout=TIMEOUT)
    if not r.ok:
        raise RuntimeError(_errore(r))


def carica_progetto(nome):
    """Scarica il progetto `nome` e restituisce il dizionario Python."""
    cfg = _cfg()
    if cfg is None:
        raise RuntimeError("Archivio online non configurato.")
    base, key, bucket = cfg
    r = requests.get(_percorso(base, bucket, nome),
                     headers=_headers(key), timeout=TIMEOUT)
    if not r.ok:
        raise RuntimeError(_errore(r))
    return r.json()


def elimina_progetto(nome):
    """Elimina definitivamente il progetto `nome` dall'archivio online."""
    cfg = _cfg()
    if cfg is None:
        raise RuntimeError("Archivio online non configurato.")
    base, key, bucket = cfg
    r = requests.delete(_percorso(base, bucket, nome),
                        headers=_headers(key), timeout=TIMEOUT)
    if not r.ok:
        raise RuntimeError(_errore(r))
