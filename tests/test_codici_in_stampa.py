"""Sui documenti i codici vanno di fila: 9.1, 9.2, 9.3…

A video il codice è quello del listino (la 9.12 accanto alla 9.4, perché
nel computo le voci si prendono e si spostano come servono); su un foglio
che va all'impresa sembrerebbe un elenco a cui mancano dei pezzi. PDF, PDF
senza prezzi, Excel e CSV rinumerano da sé, nell'ordine della pagina.
"""
import io

import fitz
import pandas as pd

import banco
import esporta


def _banco():
    b = banco.Banco()
    b.dati["progetto"]["nome"] = "Codici"
    b.cambia_lavoro_facoltativo("Facciata", True)
    for codice, q in (("9.2", 60), ("9.12", 220), ("9.4", 500), ("2.2", 10)):
        b.scrivi_quantita(codice, q)
    # a video: 9.2, 9.12, 9.4 nella Facciata, un 2.2 preso dopo, e una
    # voce da quantificare (9.3) che non si prende un numero
    b.dati["voci_scelte"] = ["9.2", "9.12", "9.4", "2.2", "9.3"]
    return b


def test_le_voci_si_rinumerano_di_fila_nell_ordine_della_pagina():
    voci = _banco().voci_da_stampare()
    assert [(v["codice"], v["descrizione"][:20]) for v in voci] == [
        ("2.1", "Demolizione tramezze"),
        ("9.1", "Smontaggio di pluvia"),
        ("9.2", "Rimozione del rivest"),
        ("9.3", "Scarificazione della"),
    ]


def test_a_video_e_nel_file_restano_i_codici_del_listino():
    b = _banco()
    b.voci_da_stampare()
    assert "9.12" in b.dati["voci_scelte"]
    assert {v["codice"] for v in b.voci_calcolate()} == {"9.2", "9.12",
                                                        "9.4", "2.2"}


def test_i_totali_non_cambiano():
    b = _banco()
    assert sum(v["importo"] for v in b.voci_da_stampare()) == \
        b.totali()["totale"]


def _testo(byte):
    return "\n".join(p.get_text() for p in fitz.open(stream=byte,
                                                      filetype="pdf"))


def test_i_due_pdf_portano_i_codici_di_fila():
    b = _banco()
    for con_prezzi in (True, False):
        testo = _testo(esporta.pdf_computo(b, con_prezzi=con_prezzi))
        assert "9.3" in testo and "9.12" not in testo


def test_excel_e_csv_portano_i_codici_di_fila():
    b = _banco()
    foglio = pd.read_excel(io.BytesIO(esporta.excel_computo(b)),
                           sheet_name="Computo", dtype={"codice": str})
    assert list(foglio["codice"]) == ["2.1", "9.1", "9.2", "9.3"]
    csv = pd.read_csv(io.BytesIO(esporta.csv_computo(b)), sep=";",
                      encoding="utf-8-sig", dtype={"codice": str})
    assert list(csv["codice"]) == ["2.1", "9.1", "9.2", "9.3"]
