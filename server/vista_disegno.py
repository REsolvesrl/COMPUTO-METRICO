"""La vista della scheda «📐 Misura da planimetria».

Quello che `scheda_planimetria()` decideva di mostrare — le piante, la
tela, la zona o il muro selezionati, la pulizia e il rilevamento, le
superfici commerciali, i locali con le loro spunte, le detrazioni, i muri,
le voci che il disegno porta nel computo — ricavato dal banco.
"""
from __future__ import annotations

import planimetria as geo
from banco_disegno import etichetta_parete
from costanti import (CATEGORIE_INVOLUCRO, CATEGORIE_SOLO_COMPUTO,
                      TIPI_PARETE, TIPI_PARETE_SCELTA)
from formato import numero_it


def _riga_conto(voce, conto, valore, um, segno=""):
    return [voce, conto, f"{segno}{numero_it(abs(valore), 2)} {um}"]


def _conto_lati(n_porte, n_porte_esterne):
    """«5 interne × 2 lati + 1 esterna» — da dove viene il numero dei lati."""
    pezzi = []
    if n_porte:
        pezzi.append(f"{n_porte} interne × 2 lati")
    if n_porte_esterne:
        pezzi.append(f"{n_porte_esterne} esterne × 1 lato")
    return (" + ".join(pezzi) + " = ") if pezzi else ""


def conto_in_chiaro(q, altezza, f, aperture):
    """«Il conto in chiaro»: mostra_dettaglio_finiture del vecchio, in dati.

    Prima il censimento dei locali, poi ogni totale con le sue detrazioni
    una per una. I numeri vengono tutti da `quantita_finiture`: qui non si
    ricalcola niente, o il pannello del controllo e il computo potrebbero
    dire due cose diverse.
    """
    larg_porta, alt_porta, h_riv = f["porta_larg"], f["porta_alt"], f["riv_alt"]
    n_porte, n_porte_est = f["porta_n"], f["porta_n_est"]
    censimento = None
    if q.get("dettaglio"):
        censimento = [{
            "Locale": r["nome"],
            "Perimetro (m)": numero_it(r["perimetro"], 2),
            "Battiscopa (m)": numero_it(r["battiscopa"], 2),
            "Pareti (m²)": numero_it(r["pareti"], 2),
            "Soffitti (m²)": numero_it(r["soffitti"], 2),
            "Fascia rivestita (m²)": numero_it(r["fascia"], 2),
            "Perché è fuori": (
                "balcone o terrazzo: niente zoccolino né tinteggiatura"
                if r["esterno"] else
                "rivestito, e senza la spunta del battiscopa"
                if r["rivestito"] and not r["battiscopa"] else ""),
        } for r in q["dettaglio"]]
        somme = {c: numero_it(sum(r[k] for r in q["dettaglio"]), 2)
                 for c, k in (("Perimetro (m)", "perimetro"),
                              ("Battiscopa (m)", "battiscopa"),
                              ("Pareti (m²)", "pareti"),
                              ("Soffitti (m²)", "soffitti"),
                              ("Fascia rivestita (m²)", "fascia"))}
        censimento.append({"Locale": "TOTALE", "Perché è fuori": "", **somme})

    sezioni = []
    lati_b = q["lati_battiscopa"]
    lati_txt = (f"{lati_b:.0f}" if abs(lati_b - round(lati_b)) < 1e-9
                else numero_it(lati_b, 1))
    righe = [_riga_conto("Perimetri dei locali con lo zoccolino",
                         "somma della colonna «Battiscopa» qui sopra",
                         q["battiscopa_lordo"], "m")]
    if q["detr_porte_ml"]:
        conto = (f"{numero_it(larg_porta, 2)} m × "
                 f"{_conto_lati(n_porte, n_porte_est)}{lati_txt} lati")
        if abs(lati_b - q["lati_porta"]) > 1e-9:
            conto += (f" (non {q['lati_porta']}: un lato che dà in un locale "
                      "rivestito senza zoccolino non interrompe niente)")
        righe.append(_riga_conto("Vani porta", conto, q["detr_porte_ml"],
                                 "m", "−"))
    for ap in aperture:
        n, larg = int(ap.get("n") or 0), float(ap.get("larghezza") or 0.0)
        if not n:
            continue
        if ap.get("battiscopa"):
            righe.append(_riga_conto(
                ap["nome"], f"{n} × {numero_it(larg, 2)} m: arrivano a terra "
                "e interrompono lo zoccolino", n * larg, "m", "−"))
        else:
            righe.append([ap["nome"], "il davanzale sta in alto: lo "
                          "zoccolino ci passa sotto indisturbato", "—"])
    sezioni.append({"titolo": "Battiscopa", "intestazione": "Battiscopa",
                    "righe": righe,
                    "totale": f"{numero_it(q['battiscopa'], 2)} m"})

    righe = [_riga_conto(
        "Perimetri dei locali da tinteggiare × altezza",
        f"somma della colonna «Pareti»: perimetro × {numero_it(altezza, 2)} m",
        q["pareti_lorde"], "m²")]
    if q["detr_rivestimenti"]:
        righe.append(_riga_conto(
            "Fasce rivestite", f"perimetro dei locali rivestiti × "
            f"{numero_it(h_riv, 2)} m: sotto la piastrella non si rasa né si "
            "tinteggia", q["detr_rivestimenti"], "m²", "−"))
    if q["detr_porte_m2"]:
        righe.append(_riga_conto(
            "Vani porta", f"{numero_it(larg_porta, 2)} × "
            f"{numero_it(alt_porta, 2)} m × "
            f"{_conto_lati(n_porte, n_porte_est)}{q['lati_porta']} lati",
            q["detr_porte_m2"], "m²", "−"))
    for ap in aperture:
        n = int(ap.get("n") or 0)
        if not n:
            continue
        larg, alt = float(ap["larghezza"] or 0.0), float(ap["altezza"] or 0.0)
        righe.append(_riga_conto(
            ap["nome"], f"{n} × {numero_it(larg, 2)} × {numero_it(alt, 2)} m",
            n * larg * alt, "m²", "−"))
    if q["recupero_vani_riv"]:
        righe.append(_riga_conto(
            "Vani dei locali rivestiti, restituiti",
            "la fascia se li era già portati via tutti interi: toglierli una "
            "seconda volta scontava due volte la striscia bassa",
            q["recupero_vani_riv"], "m²", "+"))
    sezioni.append({"titolo": "Pareti da rasare e tinteggiare",
                    "intestazione": "Pareti", "righe": righe,
                    "totale": f"{numero_it(q['pareti'], 2)} m²"})

    sezioni.append({
        "titolo": "Soffitti e pavimenti — nessuna detrazione",
        "intestazione": "Voce", "righe": [
            _riga_conto("Soffitti", "superficie dei locali da tinteggiare: "
                        "un soffitto non ha vani da togliere",
                        q["soffitti"], "m²"),
            _riga_conto("Pavimento (interni)", "superficie dei locali "
                        "spuntati, balconi e terrazzi esclusi",
                        q["pavimento"], "m²"),
            _riga_conto("Pavimento esterno", "balconi, terrazzi e logge: "
                        "altra posa, altro prezzo, voce sua",
                        q["pavimento_esterno"], "m²")],
        "totale": f"{numero_it(q['soffitti'] + q['pavimento'] + q['pavimento_esterno'], 2)} m²"})

    if q["rivestimenti_lordi"]:
        righe = [_riga_conto(
            "Fascia dei locali rivestiti",
            f"perimetro dei locali rivestiti × {numero_it(h_riv, 2)} m",
            q["rivestimenti_lordi"], "m²")]
        if q["detr_riv_porte"]:
            righe.append(_riga_conto(
                "Vani porta, la parte dentro la fascia",
                f"una porta alta {numero_it(alt_porta, 2)} su una fascia da "
                f"{numero_it(h_riv, 2)} vale {numero_it(larg_porta, 2)} × "
                f"{numero_it(h_riv, 2)}, non il vano intero",
                q["detr_riv_porte"], "m²", "−"))
        if q["detr_riv_finestre"]:
            righe.append(_riga_conto(
                "Finestre, la parte dentro la fascia",
                "solo quello che cade sotto il bordo alto della fascia",
                q["detr_riv_finestre"], "m²", "−"))
        sezioni.append({"titolo": "Rivestimenti (la fascia piastrellata)",
                        "intestazione": "Rivestimenti", "righe": righe,
                        "totale": f"{numero_it(q['rivestimenti'], 2)} m²"})
    return {"censimento": censimento, "sezioni": sezioni}


def vista_planimetria(b):
    d = b.dati
    categorie = d["categorie"]
    colori = b.mappa_colori()
    fuori = {
        "piante": [{"indice": i, "nome": p["nome"], "scala": bool(p["mpp"]),
                    "impronta": b.impronta_immagine(i)}
                   for i, p in enumerate(d["piante"])],
        "attiva": b.pianta_idx if d["piante"] else None,
        "categorie": [{"nome": c["nome"], "percento": c["percento"],
                       "soglia": c.get("soglia"), "oltre": c.get("oltre"),
                       "colore": colori.get(c["nome"], "#9E9E9E")}
                      for c in categorie],
        "cat_attiva": (b.cat_attiva if b.cat_attiva in
                       [c["nome"] for c in categorie]
                       else (categorie[0]["nome"] if categorie else None)),
        "tipi_parete": [{"codice": c, **TIPI_PARETE[c]}
                        for c in TIPI_PARETE_SCELTA],
        "tipo_parete": b.tipo_parete,
        "storia": ({"passi": len(b.storia),
                    "ultima": b.storia[-1]["descrizione"]}
                   if b.storia else None),
        "scala_persa": b.scala_persa,
        "etichette": d["etichette"],
        "etichette_spostate": sum(1 for p in d["piante"]
                                  for el in (p["zone"], p["pareti"])
                                  for e in el if e.get("etichetta_pos")),
    }
    b.scala_persa = False
    if not d["piante"]:
        return fuori
    i = b.pianta_idx
    pianta = d["piante"][i]
    mpp = pianta["mpp"]
    fuori["tela"] = b.argomenti_tela()
    fuori["tela"]["src"] = (f"/api/piante/{i}/immagine"
                            f"?v={b.impronta_immagine(i)}")
    fuori["mpp"] = mpp
    zona = next((z for z in pianta["zone"] if z["id"] == b.sel_zona), None)
    if zona is not None:
        fuori["zona_sel"] = {
            "id": zona["id"], "nome": zona.get("nome") or "",
            "categoria": zona["categoria"],
            "involucro": zona["categoria"] in CATEGORIE_INVOLUCRO,
            "area": geo.area_reale_m2(zona["punti"], mpp) if mpp else None,
            "perimetro": (geo.perimetro_reale_m(zona["punti"], mpp)
                          if mpp else None)}
    parete = next((p for p in pianta["pareti"] if p["id"] == b.sel_parete),
                  None)
    if parete is not None:
        fuori["parete_sel"] = {
            "id": parete["id"], "tipo": parete.get("tipo", "demolire"),
            "lunghezza": (geo.distanza_pixel(parete["p1"], parete["p2"]) * mpp
                          if mpp else None),
            "etichetta": etichetta_parete(parete, mpp)}
    a = b.anteprima_pulizia
    fuori["pulizia"] = {
        "anteprima": a is not None and a["indice"] == i,
        "rimossi": a["rimossi"] if a else 0,
        "forza": a["forza"] if a else 1.0,
        "originale": i in b.originali}
    img = b.immagine(i)
    fuori["ritaglio"] = {"larghezza": img.width, "altezza": img.height,
                         "annullabili": len(b.ritagli.get(i, []))}
    r = b.ultimo_rilevamento
    fuori["rilevamento"] = len(r["ids"]) if r and r["indice"] == i else 0

    # ------------------------------------------- superfici commerciali
    piante = b.piante_calcolo()
    perc = b.percentuali()
    righe_sup, tot_sup, tot_comm, senza_scala = geo.riepilogo_superfici(
        piante, perc, escludi=CATEGORIE_SOLO_COMPUTO)
    righe_int, _, _, _ = geo.riepilogo_superfici(
        [dict(p, zone=[z for z in p["zone"]
                       if z["categoria"] in CATEGORIE_SOLO_COMPUTO])
         for p in piante], perc)
    # La superficie REALE è quella che si calpesta: le stanze interne più
    # le pertinenze calpestabili, ognuna per intero. Restano fuori il
    # perimetro commerciale (è un contorno che le racchiude già, e sommarlo
    # le conterebbe due volte) e i giardini, MAI calpestabili in questo
    # conto, qualunque sia il nome della loro categoria. (Nel vecchio era
    # perimetro più pertinenze: l'utente l'ha corretta il 23/09/2026.)
    giardini = [c["nome"] for c in categorie
                if "giardino" in c["nome"].lower()]
    _, reale, _, _ = geo.riepilogo_superfici(
        piante, perc, escludi=tuple(CATEGORIE_INVOLUCRO) + tuple(giardini))
    ha_interne = any(z["categoria"] in CATEGORIE_SOLO_COMPUTO
                     for p in piante for z in p["zone"])
    ha_perimetro = any(z["categoria"] in CATEGORIE_INVOLUCRO
                       for p in piante for z in p["zone"])
    fuori["superfici"] = {
        "senza_scala": senza_scala,
        "manca_perimetro": ha_interne and not ha_perimetro,
        "righe": [{"Pianta": r["pianta"], "Categoria": r["categoria"],
                   "Zone": r["zone"], "m² reali": numero_it(r["m2"], 2),
                   "%": numero_it(r["percento"], 0) + " %",
                   "m² commerciali": numero_it(r["m2_commerciale"], 2),
                   "Serve a": "Superficie commerciale"} for r in righe_sup]
        + [{"Pianta": r["pianta"], "Categoria": r["categoria"],
            "Zone": r["zone"], "m² reali": numero_it(r["m2"], 2),
            "%": "—", "m² commerciali": "non conta",
            "Serve a": "Computo (calpestabile)"} for r in righe_int],
        "interne": bool(righe_int),
        "totale": reale, "commerciale": tot_comm,
    }

    # ------------------------------------------------ locali e finiture
    locali, senza_scala_loc = b.locali()
    f = d["finiture"]
    fuori["altezza"] = d["altezza_locali"]
    fuori["finiture"] = f
    fuori["mostra_altezza"] = bool(locali) or any(p.get("pareti")
                                                  for p in piante)
    fuori["locali"] = {"righe": [{
        "pianta": r["uid"], "zona": r["id"], "Pianta": r["pianta"],
        "Locale": r["nome"], "m2": r["m2"], "perimetro": r["perimetro"],
        "pavimento": r["pavimento"], "battiscopa": r["battiscopa"],
        "pittura": r["pittura"], "rivestito": r["rivestito"]}
        for r in locali], "senza_scala": senza_scala_loc}
    q = b.finiture()
    if q is not None:
        fuori["quantita"] = {
            "pavimento": q["pavimento"], "battiscopa": q["battiscopa"],
            "detr_ml": q["detr_porte_ml"] + q["detr_aperture_ml"],
            "pareti": q["pareti"],
            "detr_m2": round(q["pareti_lorde"] - q["pareti"], 2),
            "soffitti": q["soffitti"],
            "pavimento_esterno": q["pavimento_esterno"],
            "rivestimenti": q["rivestimenti"],
            "detr_riv": (q["detr_riv_porte"] + q["detr_riv_finestre"]
                         if q["rivestimenti_lordi"] else 0),
            "nessun_rivestito": (not q["rivestimenti_lordi"] and not any(
                r["rivestito"] for r in locali)),
        }
        fuori["conto"] = conto_in_chiaro(q, d["altezza_locali"], f,
                                         b.aperture())

    # ----------------------------------------------------------- muri
    muri, senza_scala_muri = b.muri()
    fuori["muri"] = muri
    fuori["muri_senza_scala"] = senza_scala_muri

    # -------------------------------------------- dal disegno al computo
    grandezze = b.grandezze()
    fuori["grandezze"] = grandezze
    fuori["vicino"] = [
        {"nome": n, "valore": v, "um": um} for n, v, um in (
            ("Superficie commerciale", tot_comm, "m²"),
            ("Pavimento", grandezze.get("pavimento"), "m²"),
            ("Battiscopa", grandezze.get("battiscopa"), "m"),
            ("Tinteggiatura", grandezze.get("tinteggiatura"), "m²"),
            ("Muri da demolire", grandezze.get("muri_demolire"), "m²"),
            ("Muri da costruire", grandezze.get("muri_costruire"), "m²"))
        if v]
    voci = b.voci_dal_disegno(grandezze)
    fuori["dal_disegno"] = {
        "attivo": any(v > 0 for v in grandezze.values()),
        "agganciato": d["auto_computo"],
        "voci": voci,
        "a_mano": sorted(v["codice"] for v in voci
                         if v["spuntata"] and v["a_mano"]),
        "da_scrivere": len(b.proposte_dal_disegno(grandezze)),
        "spuntate": sum(1 for v in voci if v["spuntata"]),
    }
    return fuori
