"""I file che escono dal computo: PDF, PDF senza prezzi, Excel, CSV, Allegato 1.

Gli stessi documenti del programma vecchio, costruiti dalle stesse funzioni
(`stampa.py` per i PDF) e con le stesse tabelle per l'Excel: qui cambia solo
da dove arrivano i dati — dal banco, invece che dallo stato di sessione.
Si costruiscono al clic, mai prima: è la lezione del vecchio, dove tre PDF
rifatti a ogni gesto erano la parte più lenta della pagina.
"""
import io
from datetime import date

import pandas as pd

import planimetria
import stampa
from costanti import CATEGORIE_SOLO_COMPUTO, COLORI_CATEGORIE
from formato import numero_it
from tabelle import COLONNE


def _tinte():
    return {cat: COLORI_CATEGORIE[cat][0] for cat in COLORI_CATEGORIE}


def _totali_pdf(totali):
    return {"somma": totali["totale"], "totale_lavori": totali["totale"],
            "iva_pct": totali["aliquota_iva"], "iva": totali["iva"],
            "totale": totali["totale_con_iva"]}


def pdf_computo(banco, con_prezzi=True):
    """Il computo da consegnare; senza prezzi, quello da mandare alle
    imprese — con la data di OGGI, perché è il giorno in cui si chiede il
    preventivo, non quello in cui è nato il progetto."""
    totali = banco.totali()
    progetto = dict(banco.dati["progetto"])
    if not con_prezzi:
        progetto["data"] = date.today().strftime("%d/%m/%Y")
    return stampa.pdf_computo(progetto, banco.voci_da_stampare(),
                              _totali_pdf(totali),
                              tinte=_tinte(), con_prezzi=con_prezzi)


def pdf_allegato_materiali(banco):
    """L'Allegato 1, con la data all'italiana: è un foglio che si firma."""
    prg = banco.dati["progetto"]
    progetto = {
        "nome": prg["nome"], "committente": prg["committente"],
        "oggetto": prg["oggetto"], "luogo": prg["luogo"],
        "data": date.fromisoformat(prg["data"]).strftime("%d/%m/%Y"),
    }
    return stampa.pdf_materiali(progetto, banco.dati["materiali"])


def _df_calcolato(voci):
    """Le voci come escono sui documenti: codici di fila (voci_da_stampare)."""
    if voci:
        return pd.DataFrame(voci).reindex(
            columns=COLONNE + ["quantita", "importo"])
    return pd.DataFrame(columns=COLONNE + ["quantita", "importo"])


def csv_computo(banco):
    df = _df_calcolato(banco.voci_da_stampare())
    return df.to_csv(index=False, sep=";", decimal=",").encode("utf-8-sig")


def excel_computo(banco):
    """Fogli: Computo, Riepilogo, Materiali, Superfici e Dati progetto."""
    totali = banco.totali()
    prg = banco.dati["progetto"]
    per_cat, incidenze = totali["per_categoria"], totali["incidenze"]
    df_riepilogo = pd.DataFrame({
        "Categoria": list(per_cat),
        "Importo": [per_cat[c] for c in per_cat],
        "Incidenza %": [incidenze[c] for c in per_cat],
    }).sort_values("Importo", ascending=False, ignore_index=True)
    df_riepilogo = pd.concat([df_riepilogo, pd.DataFrame({
        "Categoria": ["Totale lavori (IVA esclusa)",
                      f"IVA {numero_it(prg['aliquota_iva'], 0)}%",
                      "Totale finale (IVA inclusa)"],
        "Importo": [totali["totale"], totali["iva"],
                    totali["totale_con_iva"]],
        "Incidenza %": [100.0, None, None],
    })], ignore_index=True)
    df_progetto = pd.DataFrame({
        "Campo": ["Nome", "Committente", "Oggetto", "Luogo", "Data",
                  "Aliquota IVA %"],
        "Valore": [prg["nome"], prg["committente"], prg["oggetto"],
                   prg["luogo"], prg["data"], prg["aliquota_iva"]],
    })
    righe = banco.dati["materiali"]
    df_materiali = pd.DataFrame([{
        "Capitolo": r.get("capitolo") or "",
        "Descrizione": r.get("descrizione") or "",
        "Quantità": r.get("quantita"),
        "Fornitore": r.get("fornitore") or "",
        "Link": r.get("link") or "",
        "Stato": r.get("stato") or "",
        "Note": r.get("note") or "",
    } for r in righe]) if righe else None

    righe_sup, tot_sup, tot_comm, _ = planimetria.riepilogo_superfici(
        banco.piante_calcolo(), banco.percentuali(),
        escludi=CATEGORIE_SOLO_COMPUTO)
    df_superfici = None
    if righe_sup:
        df_superfici = pd.concat([pd.DataFrame([{
            "Pianta": r["pianta"], "Categoria": r["categoria"],
            "N. zone": r["zone"], "m² reali": r["m2"],
            "%": r["percento"], "m² commerciali": r["m2_commerciale"],
        } for r in righe_sup]), pd.DataFrame([{
            "Pianta": "TOTALE", "Categoria": "", "N. zone": None,
            "m² reali": tot_sup, "%": None, "m² commerciali": tot_comm}])],
            ignore_index=True)

    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        _df_calcolato(banco.voci_da_stampare()).to_excel(
            writer, sheet_name="Computo", index=False)
        df_riepilogo.to_excel(writer, sheet_name="Riepilogo", index=False)
        if df_materiali is not None and len(df_materiali):
            df_materiali.to_excel(writer, sheet_name="Materiali", index=False)
        if df_superfici is not None and len(df_superfici):
            df_superfici.to_excel(writer, sheet_name="Superfici", index=False)
        df_progetto.to_excel(writer, sheet_name="Dati progetto", index=False)
    return buffer.getvalue()
