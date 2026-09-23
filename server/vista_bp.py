"""La vista del «📊 Business plan»: studio di fattibilità, spese a
consuntivo, cantiere (contratto e SAL), MCA.

Stessi conti e stesse parole della scheda del vecchio. ⚠️ Le etichette
inglesi dello studio di fattibilità (ESTIMATED, Buy cost, Net Return…)
sono il vocabolario del foglio Excel da cui viene: non si traducono.
"""
from __future__ import annotations

import json

import fattibilita
import grafici
import merito
import storico
import cantiere as cantiere_mod
from banco_bp import DERIVATI
from costanti import (COLORE_CATEGORIA_SPESA, OTTONE, TENDINE_MERITO,
                      VOCI_CON_IVA)
from formato import colore_testo_su, euro, numero_it
from tabelle import EMOJI_CATEGORIA


def _figura(fig):
    return json.loads(fig.to_json())


def _quota_cantiere(righe):
    return round(sum(r["importo"] for r in righe
                     if r["categoria"] in fattibilita.CATEGORIE_CANTIERE), 2)


def _spese(b):
    d = b.dati
    sostenute, prev = d["spese"], d["spese_prev"]
    tot_sost = fattibilita.totale_spese(sostenute)
    tot_prev = fattibilita.totale_spese(prev)
    riepilogo = fattibilita.riepilogo_per_categoria(sostenute)
    iva_totale = round(sum(v["iva"] for v in riepilogo.values()), 2)
    ristr_computo = b.totali()["totale"]
    sost_c, prev_c = _quota_cantiere(sostenute), _quota_cantiere(prev)
    consuntivo = round(sost_c + prev_c, 2)
    confronto = None
    if any(r["categoria"] in fattibilita.CATEGORIE_CANTIERE
           for r in sostenute + prev):
        scost = round(consuntivo - ristr_computo, 2)
        confronto = {
            "preventivo": ristr_computo, "speso": sost_c, "previsto": prev_c,
            "scostamento": scost,
            "scostamento_pct": (round(scost / ristr_computo * 100, 2)
                                if ristr_computo else None)}
    return {
        "sostenute": [dict(r, iva_eur=fattibilita.iva_scorporata(
            r["importo"], r["aliquota_iva"])) for r in sostenute],
        "prev": prev,
        "totale_sostenute": tot_sost, "totale_prev": tot_prev,
        "totale": round(tot_sost + tot_prev, 2),
        "quota_cantiere": _quota_cantiere(sostenute + prev),
        "riepilogo": [{"categoria": c, "importo": v["importo"],
                       "iva": v["iva"],
                       "colore": COLORE_CATEGORIA_SPESA.get(c, OTTONE),
                       "su_colore": colore_testo_su(
                           COLORE_CATEGORIA_SPESA.get(c, OTTONE))}
                      for c, v in riepilogo.items()],
        "iva_totale": iva_totale,
        "torta": _figura(grafici.grafico_torta_spese(riepilogo))
        if riepilogo else None,
        "categorie": [{"valore": c, "testo": f"{EMOJI_CATEGORIA.get(c, '')} {c}".strip()}
                      for c in fattibilita.CATEGORIE_SPESE],
        "fatture_lette": b.fatture_lette,
        "confronto": confronto,
    }


def _riga_costo(etichetta, bp, derivati, centro=None, destra=None, iva=None,
                imponibile=None, aiuto_centro=None, aiuto_destra=None,
                arancio=False):
    """Una riga del dettaglio costi: etichetta | % | netto | IVA % | IVA €."""
    def valore(chiave):
        return derivati[chiave] if chiave in derivati else bp.get(chiave)
    riga = {"etichetta": etichetta, "arancio": arancio,
            "centro": ({"chiave": centro, "valore": bp[centro],
                        "aiuto": aiuto_centro} if centro else None),
            "destra": ({"chiave": destra, "valore": valore(destra),
                        "aiuto": aiuto_destra} if destra else None)}
    if iva:
        base = imponibile if imponibile is not None else (valore(destra)
                                                          or 0.0)
        riga["iva"] = {"chiave": iva, "valore": bp[iva],
                       "euro": fattibilita.iva_su(base, bp[iva])}
    return riga


def _fattibilita(b, spese):
    d = b.dati
    bp = d["business_plan"]
    derivati = b.euro_derivati()
    mq_plan = b.mq_da_planimetria()
    mq_calp = b.mq_calpestabili()
    mq_a_mano = bool(bp["bp_mq"] and bp["bp_mq"] != b._mq_automatici)
    mq_eff = bp["bp_mq"] or mq_plan
    ristr_eff, usa = b.ristrutturazione()
    consuntivo = b.cantiere_consuntivo()
    parametri = {
        "prezzo_acquisto": bp["bp_acquisto"],
        "prezzo_vendita": bp["bp_vendita"],
        "imposta_pct": bp["bp_imposta"],
        "imposte_fisse": bp["bp_imposte_fisse"],
        "notaio": bp["bp_notaio"],
        "agenzia_in_pct": bp["bp_ag_in"],
        "agenzia_out_pct": bp["bp_ag_out"],
        "iva_agenzia_pct": bp["bp_iva_ag"],
        "imprevisti": bp["bp_imprevisti"],
        "spese_mutuo": bp["bp_mutuo"],
        "ristrutturazione": ristr_eff,
        "mq": mq_eff,
        "mq_calpestabile": mq_calp,
        "durata_mesi": bp["bp_durata"],
    }
    valori = {**bp, **derivati}
    iva_voci = [fattibilita.iva_su(valori.get(campo, 0.0),
                                   bp.get(aliquota, 0.0))
                for campo, aliquota in VOCI_CON_IVA]
    iva_voci.append(fattibilita.iva_su(ristr_eff, bp.get("bp_iva_ristr", 0.0)))
    parametri["iva_costi"] = round(sum(iva_voci), 2)
    parametri["iva_costi_vendita"] = fattibilita.iva_su(
        derivati["bp_ag_out_eur"], bp.get("bp_iva_ag_out", 0.0))
    parametri["iva_agenzia_pct"] = 0.0
    esito = fattibilita.studio_fattibilita(parametri)
    acq, ven = esito["costi_acquisto"], esito["costi_vendita"]

    matrici = None
    if bp["bp_acquisto"] > 0 and bp["bp_vendita"] > 0:
        matrici = {}
        for metrica in ("multiplo", "guadagno"):
            pa, pv, mat = fattibilita.matrice_sensitivita(
                parametri, bp["bp_passo"], metrica=metrica)
            matrici[metrica] = _figura(grafici.grafico_sensitivita(
                pa, pv, mat, metrica, base_acquisto=bp["bp_acquisto"],
                base_vendita=bp["bp_vendita"]))

    senza_base = []
    if not bp["bp_acquisto"]:
        senza_base.append("il prezzo di acquisto (imposte e agenzia IN)")
    if not bp["bp_vendita"]:
        senza_base.append("il prezzo di vendita (agenzia OUT)")
    if not ristr_eff:
        senza_base.append("l'importo dei lavori (imprevisti)")

    durata = bp["bp_durata"]
    etichetta_annuo = ("Rendimento annuo (12 mesi: coincide col ROE)"
                       if durata == 12 else f"Rendimento annuo ({durata} mesi)")
    costi = [
        _riga_costo("Imposte d'acquisto", bp, derivati, centro="bp_imposta",
                    destra="bp_imposta_eur", iva="bp_iva_imposta"),
        _riga_costo("Imposte fisse", bp, derivati, destra="bp_imposte_fisse",
                    iva="bp_iva_imposte_fisse"),
        _riga_costo("Notaio", bp, derivati, destra="bp_notaio",
                    iva="bp_iva_notaio",
                    aiuto_destra="Compreso IVA, visure, archivio notarile…"),
        _riga_costo("Spese e interessi mutuo", bp, derivati,
                    destra="bp_mutuo", iva="bp_iva_mutuo"),
        _riga_costo("Imprevisti e condominio", bp, derivati,
                    centro="bp_imprevisti_pct", destra="bp_imprevisti",
                    iva="bp_iva_imprevisti",
                    aiuto_centro="Percentuale sull'importo dei lavori "
                    "considerato qui sotto. Il 10% e' la quota del contratto "
                    "d'appalto: cambiala quando serve, oppure scrivi "
                    "l'importo a destra e la percentuale si adegua."),
        _riga_costo("Agenzia IN", bp, derivati, centro="bp_ag_in",
                    destra="bp_ag_in_eur", iva="bp_iva_ag_in",
                    aiuto_centro="Commissione % sul prezzo di acquisto; "
                    "l'importo a destra è imponibile, l'IVA sta nella sua "
                    "colonna"),
        _riga_costo("Ristrutturazione stimata", bp, derivati,
                    destra="bp_ristr", iva="bp_iva_ristr",
                    imponibile=ristr_eff, arancio=True,
                    aiuto_destra="I lavori NUDI, senza riserva: gli "
                    "imprevisti sono la riga qui sopra e si contano una "
                    "volta sola. Lasciando 0 arriva il totale del computo — "
                    "che NON comprende i materiali a cura tua: quelli si "
                    "mettono fra le spese."),
    ]
    agenzia_out = _riga_costo(
        "Agenzia OUT", bp, derivati, centro="bp_ag_out",
        destra="bp_ag_out_eur", iva="bp_iva_ag_out",
        aiuto_centro="Commissione % sul prezzo di vendita; l'importo a "
        "destra è imponibile, l'IVA sta nella sua colonna")
    iva_credito = round(acq["iva"] + ven["iva"], 2)

    return {
        "bp": {**bp, **derivati},
        "mq": {"valore": bp["bp_mq"], "planimetria": mq_plan,
               "a_mano": mq_a_mano, "calpestabili": mq_calp,
               "piante": bool(d["piante"])},
        "esito": {
            "acquisto": [("€/mq acquisto",
                          numero_it(esito["eur_mq_acquisto"], 0) + " €"
                          if esito["eur_mq_acquisto"] else "—", None),
                         ("Buy cost", euro(acq["totale"]), None),
                         ("Prezzo netto — entry", euro(esito["entry"]),
                          "bold")],
            "vendita": [("€/mq vendita",
                         numero_it(esito["eur_mq_vendita"], 0) + " €"
                         if esito["eur_mq_vendita"] else "—", None),
                        ("Sell cost", euro(ven["totale"]), None),
                        ("Prezzo netto — exit", euro(esito["exit"]), "bold")],
            "risultati": [
                ("Net Return (ROI)", numero_it(esito["multiplo"], 2) + "x",
                 "bold"),
                ("Return on Equity (ROE)",
                 numero_it(esito["roe"] * 100, 1) + " %", None),
                (etichetta_annuo,
                 numero_it((esito["roi_annuo"] or 0) * 100, 1) + " %", None),
                ("Total cost", euro(acq["totale"] + ven["totale"]),
                 "cattivo"),
                ("EBIT", euro(esito["ebit"]),
                 "buono" if esito["ebit"] >= 0 else "cattivo")],
            "acquisto_totali": [("di cui IVA", euro(acq["iva"]), None),
                                ("TOTALE SPESE ACQUISTO",
                                 euro(acq["totale"]), "bold")],
            "vendita_totali": [
                ("di cui IVA (vendita)",
                 euro(ven["iva"]) if ven.get("iva") else None, None),
                ("TOTALE SPESE (acquisto + vendita)",
                 euro(acq["totale"] + ven["totale"]), "bold")],
            "iva_credito": ([("TOTALE IVA A CREDITO", euro(iva_credito),
                              "buono")] if iva_credito else []),
            "eur_mq_ristrutturazione": esito["eur_mq_ristrutturazione"],
        },
        "matrici": matrici,
        "senza_base": senza_base,
        "costi": costi,
        "agenzia_out": agenzia_out,
        "ristr_eff": ristr_eff,
        "usa_consuntivo": usa,
        "consuntivo": consuntivo,
    }


def _cantiere(b):
    d = b.dati
    c = d["cantiere"]
    stato = b.stato_cantiere()
    percentuali = [q["percento"] for q in c["sal"]]
    somma = cantiere_mod.somma_percentuali(percentuali)
    chiuse = storico.carica()
    fuori = {
        "contratto": c["contratto"], "extra": c["extra"], "sal": c["sal"],
        "totale_computo": b.totali()["totale"],
        "somma": somma,
        "stato": stato,
        "nome_operazione": d["progetto"]["nome"] or "Progetto senza nome",
        "storico": [{
            "Operazione": r.get("nome"), "Chiusa il": r.get("chiusa_il"),
            "Contratto": euro(r.get("contratto")),
            "Extra": euro(r.get("extra")),
            "Scostamento": (numero_it(r.get("scostamento"), 2) + " %"
                            if r.get("scostamento") is not None else "—"),
            "€/mq lavori": (numero_it(r.get("eur_mq"), 0) + " €"
                            if r.get("eur_mq") else "—"),
        } for r in chiuse],
        "chiuse": len(chiuse),
        "saldate_pct": cantiere_mod.somma_percentuali(
            [q["percento"] for q in c["sal"] if q["pagato"]]),
    }
    if chiuse:
        consigliati = cantiere_mod.imprevisti_consigliati(
            storico.scostamenti(chiuse))
        fuori["consigliati"] = consigliati
        fuori["media_mq"] = storico.media(storico.costi_al_mq(chiuse))
        fuori["riserva"] = float(d["business_plan"]["bp_imprevisti_pct"]
                                 or 0.0)
        fuori["proposta"] = (max(0.0, consigliati)
                             if consigliati is not None else None)
    return fuori


def _mca(b):
    d = b.dati
    bp = d["business_plan"]
    righe = d["mca_comparabili"]
    lordi = [r["prezzo"] / r["mq"] for r in righe
             if (r.get("prezzo") or 0) > 0 and (r.get("mq") or 0) > 0]
    valore_zona = sum(lordi) / len(lordi) if lordi else None
    scala = merito.scala_stato_unita(valore_zona, bp["bp_costo_ristr_mq"],
                                     bp["bp_quota_mercato"] / 100)
    scelte_sog = {c: v for c, v in d["mca_soggetto"].items()}
    merito_sog = merito.coefficiente_effettivo(scelte_sog,
                                               bp["bp_coeff_sogg"], scala)
    coeff_sog = merito_sog["totale"] or 1.0
    mq_eff = bp["bp_mq"] or b.mq_da_planimetria()
    comparabili = []
    for riga in righe:
        eff = merito.coefficiente_effettivo(merito.scelte_da_riga(riga),
                                            riga.get("coeff"), scala)
        comparabili.append({**riga, "coeff": eff["totale"]})
    esito = fattibilita.stima_mca(
        comparabili, coeff_sog, mq_eff, bp["bp_sconto"],
        statistica=d["mca_statistica"], elasticita_taglio=bp["bp_taglio"])
    taglio_sog = merito.coefficiente_taglio(mq_eff, bp["bp_taglio"])
    fuori = {
        "righe": righe,
        "tendine": {c: {"etichetta": e, "voci": list(v)}
                    for c, (e, v) in TENDINE_MERITO.items()},
        "campi": list(merito.CAMPI),
        "soggetto": d["mca_soggetto"],
        "coeff_sog": coeff_sog,
        "fonte": merito_sog["fonte"],
        "calcolato": merito_sog.get("calcolato"),
        "dettaglio_griglia": bool(merito_sog.get("dettaglio")),
        "mancanti": merito_sog.get("mancanti") or [],
        "mq_eff": mq_eff,
        "taglio_sog": taglio_sog if bp["bp_taglio"] else None,
        "bp": bp,
        "valore_zona": valore_zona,
        "statistica": d["mca_statistica"],
    }
    if valore_zona:
        finito = scala["Finemente ristrutturato"]
        grezzo = scala["Da ristrutturare integralmente"]
        fuori["salto"] = {"finito": finito, "grezzo": grezzo,
                          "eur": (finito - grezzo) / finito * valore_zona}
    if esito is not None:
        fuori["esito"] = {
            "dettaglio": [{
                "Comparabile": x["nome"], "m²": numero_it(x["mq"], 0),
                "€/mq": numero_it(x["eur_mq"], 0),
                "Coeff. merito": numero_it(x["coeff"], 3),
                "Coeff. taglio": (numero_it(x["coeff_taglio"], 3)
                                  if x["coeff_taglio"] else "—"),
                "€/mq normalizzato": numero_it(x["eur_mq_normalizzato"], 0),
                "Scarto dalla mediana": f"{numero_it(x['scarto_pct'], 1)}%",
            } for x in esito["dettaglio"]],
            **{k: esito[k] for k in ("usati", "scartati", "cv", "outlier",
                                     "statistica", "eur_mq_media",
                                     "eur_mq_mediana", "eur_mq_soggetto",
                                     "eur_mq_probabile", "valore")},
        }
    return fuori


def vista_bp(b):
    spese = _spese(b)
    return {
        "spese": spese,
        "fattibilita": _fattibilita(b, spese),
        "cantiere": _cantiere(b),
        "mca": _mca(b),
    }
