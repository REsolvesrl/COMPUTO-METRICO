"""I test non toccano il lavoro vero.

L'app conserva tre cose fuori dai progetti — l'archivio, il listino
personale, lo storico delle operazioni — e da quando riapre da sola
l'ultimo lavoro, all'avvio le LEGGE. Senza questo isolamento un `pytest`
lanciato sul computer di chi usa il programma partirebbe caricandogli un
progetto vero, e i test sarebbero diversi su ogni macchina.

Qui tutto viene dirottato in una cartella usa e getta, per l'intera
sessione di test.
"""
import pytest


@pytest.fixture(autouse=True, scope="session")
def _archivi_finti(tmp_path_factory):
    import os
    cartella = tmp_path_factory.mktemp("cme_finto")
    variabili = {
        "CME_ARCHIVIO": cartella / "progetti",
        "CME_LISTINO": cartella / "listino_personale.json",
        "CME_STORICO": cartella / "storico_operazioni.json",
        "CME_AUTOSALVA": cartella / "ripristino.json",
    }
    precedenti = {n: os.environ.get(n) for n in variabili}
    for nome, percorso in variabili.items():
        os.environ[nome] = str(percorso)
    yield cartella
    for nome, valore in precedenti.items():
        if valore is None:
            os.environ.pop(nome, None)
        else:
            os.environ[nome] = valore


@pytest.fixture(autouse=True)
def _riparti_pulito(_archivi_finti):
    """Ogni test comincia senza lavoro da riprendere.

    Da quando l'app riapre da sola l'ultimo lavoro, un test che lascia in
    giro un salvataggio automatico fa partire il test successivo con un
    progetto già aperto: le prove diventano dipendenti dall'ordine, che è
    il modo più sicuro per non fidarsi più di loro.
    """
    autosalva = _archivi_finti / "ripristino.json"
    progetti = _archivi_finti / "progetti"
    autosalva.unlink(missing_ok=True)
    if progetti.is_dir():
        for file in progetti.glob("*.json"):
            file.unlink(missing_ok=True)
    yield
