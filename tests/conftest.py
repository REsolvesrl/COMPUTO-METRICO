"""I test non toccano il lavoro vero.

L'app conserva tre cose fuori dai progetti — l'archivio, il listino
personale, lo storico delle operazioni — e da quando riapre da sola
l'ultimo lavoro, all'avvio le LEGGE. Senza questo isolamento un `pytest`
lanciato sul computer di chi usa il programma partirebbe caricandogli un
progetto vero, e i test sarebbero diversi su ogni macchina.

Qui tutto viene dirottato in una cartella usa e getta, per l'intera
sessione di test.
"""
import os
import shutil
import tempfile
from pathlib import Path

import pytest

# ⚠️ Il registro d'uso (uso.py) è la quarta cosa, e la più delicata: conta
# le «operazioni valutate con CME» per l'Allegato F. Ogni test che apre e
# salva un progetto ne scriveva una — circa quindici a ogni `pytest` — e al
# 24 settembre il registro vero ne aveva 212 di prova su 225.
# Va dirottato QUI, all'import del conftest, e non in una fixture: uso.py
# fissa la sua cartella (BASE) quando viene importato, e i moduli di test lo
# importano già mentre pytest li raccoglie, prima di qualunque fixture.
os.environ["USO_DIR"] = tempfile.mkdtemp(prefix="cme_uso_di_prova_")


@pytest.fixture(autouse=True, scope="session")
def _registro_d_uso_finto():
    """Se il registro puntasse ancora a quello vero, niente test."""
    import uso
    assert uso.BASE != Path.home() / ".resolve_uso", \
        "i test scriverebbero nel registro d'uso vero"
    assert str(uso.BASE) == os.environ["USO_DIR"]
    yield
    shutil.rmtree(os.environ["USO_DIR"], ignore_errors=True)


@pytest.fixture(autouse=True, scope="session")
def _archivi_finti(tmp_path_factory):
    import os
    cartella = tmp_path_factory.mktemp("cme_finto")
    variabili = {
        "CME_ARCHIVIO": cartella / "progetti",
        "CME_LISTINO": cartella / "listino_personale.json",
        "CME_STORICO": cartella / "storico_operazioni.json",
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
    giro un progetto salvato fa partire il test successivo con quello già
    aperto: le prove diventano dipendenti dall'ordine, che è il modo più
    sicuro per non fidarsi più di loro.
    """
    progetti = _archivi_finti / "progetti"
    if progetti.is_dir():
        for file in progetti.glob("*.json"):
            file.unlink(missing_ok=True)
    yield
