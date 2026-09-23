"""Quello che la pagina mostra, scheda per scheda, ricavato dal banco.

È la parte di `streamlit_app.py` che decideva COSA c'è a video — quali
categorie, quali righe, quali totali, quali avvisi — separata da COME si
vede, che adesso è della pagina (web/). Si ricalcola tutta dopo ogni gesto,
come Streamlit rifaceva la pagina: costa millesimi di secondo, e una vista
sempre intera non può dire due cose diverse in due posti.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import archivio_locale
import grafici
import listino
import materiali
from banco import Banco, serie_della_categoria, unita_della_voce, \
    unita_per_categoria
from costanti import COLORI_CATEGORIE, OTTONE, UM_A_CORPO, UM_A_PASSI
from formato import colore_testo_su
from server.vista_disegno import vista_planimetria
from tabelle import EMOJI_CAPITOLO, EMOJI_STATO

RADICE = Path(__file__).resolve().parent.parent


def _figura(fig):
    """Una figura Plotly come la vuole Plotly.js nel browser."""
    return json.loads(fig.to_json())


def versione_codice():
    """«codice del 23/09 alle 17:40»: quando è stato scritto quello che gira.

    Nel vecchio era la data di streamlit_app.py; qui è la più recente fra
    il motore e la pagina, che sono i due pezzi che si aggiornano.
    """
    file = [*RADICE.glob("*.py"), *(RADICE / "server").glob("*.py"),
            *(RADICE / "web").glob("*.*")]
    try:
        quando = datetime.fromtimestamp(max(f.stat().st_mtime for f in file))
    except (OSError, ValueError):
        return ""
    return quando.strftime("codice del %d/%m alle %H:%M")


def _colore(categoria):
    return COLORI_CATEGORIE.get(categoria, (OTTONE, "orange"))


# ------------------------------------------------------------- testata


def testata(b: Banco):
    ultimo = b.ultimo_salvataggio
    return {
        "nome": (b.dati["progetto"]["nome"] or "").strip(),
        "vuoto": b.vuoto(),
        "stato": b.stato_salvataggio(),
        "salvato_alle": ultimo.strftime("%H:%M") if ultimo else None,
        "versione": versione_codice(),
        "nome_archivio": b.nome_archivio(),
        "cartella": str(archivio_locale.cartella()),
    }


def archivio(b: Banco):
    try:
        elenco = archivio_locale.elenco_progetti()
        errore = None
    except OSError as e:
        elenco, errore = [], str(e)
    versioni = [{
        "file": v.name,
        "quando": archivio_locale.quando_versione(v).isoformat(),
        "kb": round(v.stat().st_size / 1024),
    } for v in archivio_locale.versioni(b.nome_archivio())]
    return {"progetti": elenco, "errore": errore, "versioni": versioni,
            "tenute": archivio_locale.VERSIONI_TENUTE,
            "cartella": str(archivio_locale.cartella())}


# ------------------------------------------------------------- computo


def _riga(b: Banco, codice):
    voce = b.voce(codice)
    descrizione, um = b.testi(codice)
    q, p = b.quantita(codice), b.prezzo(codice)
    aiuto = voce.get("nota")
    if voce.get("analisi"):
        aiuto = (aiuto + "\n\n" if aiuto else "") + voce["analisi"]
    return {
        "codice": codice, "categoria": voce["categoria"],
        "descrizione": descrizione, "um": um,
        "unita": unita_della_voce(voce["categoria"], um),
        "a_passi": um in UM_A_PASSI,
        "quantita": q, "prezzo": p,
        "parziale": round(q * p, 2) if q > 0 else None,
        "a_mano": codice in b.dati["voci_a_mano"],
        "tua": b.e_tua(codice), "aiuto": aiuto,
    }


def computo(b: Banco):
    d = b.dati
    totali = b.totali()
    categorie = []
    for indice, cat in enumerate(b.categorie_del_computo(), start=1):
        tinta, md = _colore(cat)
        categorie.append({
            "indice": indice, "nome": cat, "serie": serie_della_categoria(cat),
            "colore": tinta, "md": md, "su_tinta": colore_testo_su(tinta),
            "totale": b.totale_categoria(cat),
            "voci": [_riga(b, c) for c in b.scelte_della_categoria(cat)],
        })

    pool = []
    for indice, cat in enumerate(b.categorie_del_computo(), start=1):
        candidate = list(listino.voci_della_categoria(cat)) + [
            v for v in d["voci"] if v["categoria"] == cat]
        disponibili = []
        for voce in candidate:
            c = voce["codice"]
            if c in d["voci_scelte"] or c in d["voci_scartate"]:
                continue
            descrizione, um = b.testi(c)
            disponibili.append({
                "codice": c, "descrizione": descrizione, "um": um,
                "prezzo": b.prezzo(c) if b.e_tua(c) else voce["prezzo"],
                "nota": voce.get("nota") or "",
                "tua": listino.voce_per_codice(c) is None})
        tinta, md = _colore(cat)
        pool.append({"indice": indice, "nome": cat, "colore": tinta,
                     "md": md, "voci": disponibili})

    per_cat = totali["per_categoria"]
    riepilogo = {
        "righe": [{"nome": f"{serie_della_categoria(c)}. {c}",
                   "colore": _colore(c)[0], "importo": b.totale_categoria(c)}
                  for c in b.categorie_del_computo()],
        "totale": totali["totale"], "aliquota_iva": totali["aliquota_iva"],
        "iva": totali["iva"], "totale_con_iva": totali["totale_con_iva"],
        "grafico": (_figura(grafici.grafico_totali(per_cat))
                    if len(per_cat) >= 2 else None),
    }
    accese = b.categorie_accese()
    return {
        "categorie": categorie,
        "facoltative": [{"nome": c, "acceso": c in d["lavori_facoltativi"]}
                        for c in listino.CATEGORIE_FACOLTATIVE],
        "storia": ({"passi": len(b.storia_computo),
                    "ultima": b.storia_computo[-1]["descrizione"]}
                   if b.storia_computo else None),
        "listino_personale": b.listino_personale(),
        "pool": pool,
        "scartate": len(d["voci_scartate"]),
        "categorie_accese": accese,
        "unita_per_categoria": {c: unita_per_categoria(c) for c in accese},
        "um_a_corpo": UM_A_CORPO,
        "riepilogo": riepilogo,
        "tabella": [{"categoria": v["categoria"], "codice": v["codice"],
                     "descrizione": v["descrizione"], "um": v["um"],
                     "quantita": v["quantita"], "prezzo": v["prezzo"],
                     "importo": v["importo"]} for v in totali["voci"]],
    }


# ----------------------------------------------------------- materiali


def vista_materiali(b: Banco):
    righe = b.dati["materiali"]
    per_stato = materiali.conteggi_per_stato(righe) if righe else {}
    per_capitolo = materiali.conteggi_per_capitolo(righe) if righe else {}
    return {
        "righe": righe,
        "capitoli": [{"nome": c, "tessera": EMOJI_CAPITOLO.get(c, "")}
                     for c in materiali.CAPITOLI],
        "stati": [{"nome": s, "tessera": EMOJI_STATO.get(s, "")}
                  for s in materiali.STATI],
        "capitolo_predefinito": materiali.CAPITOLO_PREDEFINITO,
        "stato_predefinito": materiali.STATO_PREDEFINITO,
        "per_stato": per_stato,
        "per_capitolo": per_capitolo,
    }


# -------------------------------------------------------------- intera


def vista(b: Banco):
    ripreso, b.ripreso = b.ripreso, None
    scartate, b.piante_scartate = b.piante_scartate, []
    return {
        "testata": testata(b),
        "ripreso": ripreso,
        "piante_scartate": scartate,
        "progetto": b.dati["progetto"],
        "archivio": archivio(b),
        "computo": computo(b),
        "materiali": vista_materiali(b),
        "planimetria": vista_planimetria(b),
    }
