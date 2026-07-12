"""Logica del business plan immobiliare (studio di fattibilità, MCA).

Replica il modello Excel dell'utente ("Studio fattibilità" + "MCA sell"),
in funzioni pure e testate coi numeri esatti di quel file:

- costi di acquisto: imposta % sul prezzo + imposte fisse + notaio +
  agenzia IN (% + IVA) + imprevisti/condominio + spese mutuo +
  ristrutturazione;
- costi di vendita: agenzia OUT (% + IVA);
- risultati: prezzo netto entry/exit, EBIT, money multiple, ROE e
  rendimento annualizzato (novità rispetto all'Excel: il tempo conta);
- matrici di sensitività su prezzo di acquisto × prezzo di vendita
  (ricalcolate SEMPRE dal vivo: le Data Table dell'Excel restavano
  facilmente "vecchie" rispetto agli input);
- MCA (market comparison approach): €/mq dei comparabili normalizzato
  per il coefficiente di merito, media, riproporzionata sul soggetto e
  scontata della trattativa → valore stimato di vendita.
"""

CATEGORIE_SPESE = ["ACQUISTO", "LAVORI", "MATERIALE", "ARCHITETTO",
                   "COSTI INDIRETTI", "AGENZIA", "ALTRO"]
STATI_SPESA = ["Sostenuta", "Da sostenere"]
# categorie del consuntivo che formano il "costo cantiere" da confrontare
# col preventivo (computo metrico)
CATEGORIE_CANTIERE = ["LAVORI", "MATERIALE", "ARCHITETTO"]


def costi_acquisto(prezzo, imposta_pct=9.0, imposte_fisse=0.0,
                   notaio=3500.0, agenzia_pct=3.0, iva_agenzia_pct=22.0,
                   imprevisti=0.0, spese_mutuo=0.0, ristrutturazione=0.0):
    """Dettaglio dei costi di acquisto; "totale" è la somma."""
    dettaglio = {
        "imposte": round(prezzo * imposta_pct / 100 + imposte_fisse, 2),
        "notaio": round(notaio, 2),
        "agenzia": round(prezzo * agenzia_pct / 100
                         * (1 + iva_agenzia_pct / 100), 2),
        "imprevisti": round(imprevisti, 2),
        "spese_mutuo": round(spese_mutuo, 2),
        "ristrutturazione": round(ristrutturazione, 2),
    }
    dettaglio["totale"] = round(sum(dettaglio.values()), 2)
    return dettaglio


def costi_vendita(prezzo, agenzia_pct=2.5, iva_agenzia_pct=22.0):
    """Dettaglio dei costi di vendita; "totale" è la somma."""
    agenzia = round(prezzo * agenzia_pct / 100
                    * (1 + iva_agenzia_pct / 100), 2)
    return {"agenzia": agenzia, "totale": agenzia}


def studio_fattibilita(parametri):
    """Il quadro completo dell'operazione a partire dai parametri.

    parametri: dizionario con prezzo_acquisto, prezzo_vendita e (opzionali)
    imposta_pct, imposte_fisse, notaio, agenzia_in_pct, agenzia_out_pct,
    iva_agenzia_pct, imprevisti, spese_mutuo, ristrutturazione, mq,
    durata_mesi.
    """
    acquisto = float(parametri.get("prezzo_acquisto") or 0.0)
    vendita = float(parametri.get("prezzo_vendita") or 0.0)
    acq = costi_acquisto(
        acquisto,
        imposta_pct=parametri.get("imposta_pct", 9.0),
        imposte_fisse=parametri.get("imposte_fisse", 0.0),
        notaio=parametri.get("notaio", 3500.0),
        agenzia_pct=parametri.get("agenzia_in_pct", 3.0),
        iva_agenzia_pct=parametri.get("iva_agenzia_pct", 22.0),
        imprevisti=parametri.get("imprevisti", 0.0),
        spese_mutuo=parametri.get("spese_mutuo", 0.0),
        ristrutturazione=parametri.get("ristrutturazione", 0.0),
    )
    ven = costi_vendita(
        vendita,
        agenzia_pct=parametri.get("agenzia_out_pct", 2.5),
        iva_agenzia_pct=parametri.get("iva_agenzia_pct", 22.0),
    )
    entry = round(acquisto + acq["totale"], 2)
    uscita = round(vendita - ven["totale"], 2)
    ebit = round(uscita - entry, 2)
    multiplo = round(uscita / entry, 6) if entry else 0.0
    roe = round(ebit / entry, 6) if entry else 0.0
    durata = float(parametri.get("durata_mesi") or 0.0)
    roi_annuo = None
    if durata > 0 and multiplo > 0:
        roi_annuo = round(multiplo ** (12.0 / durata) - 1.0, 6)
    mq = float(parametri.get("mq") or 0.0)
    return {
        "costi_acquisto": acq,
        "costi_vendita": ven,
        "entry": entry,
        "exit": uscita,
        "ebit": ebit,
        "multiplo": multiplo,
        "roe": roe,
        "roi_annuo": roi_annuo,
        "eur_mq_acquisto": round(acquisto / mq, 2) if mq else None,
        "eur_mq_vendita": round(vendita / mq, 2) if mq else None,
    }


def matrice_sensitivita(parametri, passo, metrica="multiplo",
                        n_acquisto=11, n_vendita=9):
    """Sensitività su prezzo di acquisto (righe) × vendita (colonne).

    metrica: "multiplo" (money multiple) o "guadagno" (EBIT assoluto, €).
    Ritorna (prezzi_acquisto, prezzi_vendita, matrice) con la combinazione
    base al centro della griglia.
    """
    base_a = float(parametri.get("prezzo_acquisto") or 0.0)
    base_v = float(parametri.get("prezzo_vendita") or 0.0)
    meta_a = n_acquisto // 2
    meta_v = n_vendita // 2
    prezzi_a = [base_a + (i - meta_a) * passo for i in range(n_acquisto)]
    prezzi_v = [base_v + (j - meta_v) * passo for j in range(n_vendita)]
    prezzi_a = [p for p in prezzi_a if p > 0]
    prezzi_v = [p for p in prezzi_v if p > 0]
    matrice = []
    for pa in prezzi_a:
        riga = []
        for pv in prezzi_v:
            p = dict(parametri)
            p["prezzo_acquisto"] = pa
            p["prezzo_vendita"] = pv
            esito = studio_fattibilita(p)
            riga.append(esito["multiplo"] if metrica == "multiplo"
                        else esito["ebit"])
        matrice.append(riga)
    return prezzi_a, prezzi_v, matrice


def stima_mca(comparabili, coeff_soggetto, mq_soggetto, sconto_pct=13.0):
    """Valore di vendita col metodo comparativo (MCA).

    comparabili: [{"nome", "prezzo", "mq", "coeff"}] — coeff è il
    coefficiente di merito complessivo dell'immobile comparabile (prodotto
    dei fattori: vetustà, finiture, piano, luminosità…). Il €/mq di ognuno
    viene NORMALIZZATO dividendolo per il suo coeff; la media dei
    normalizzati, moltiplicata per il coeff del soggetto, dà il €/mq del
    soggetto; lo sconto di trattativa porta al probabile venduto.

    Ritorna None se non c'è nessun comparabile valido.
    """
    dettaglio = []
    for c in comparabili:
        prezzo = float(c.get("prezzo") or 0.0)
        mq = float(c.get("mq") or 0.0)
        coeff = float(c.get("coeff") or 0.0)
        if prezzo <= 0 or mq <= 0 or coeff <= 0:
            continue
        eur_mq = prezzo / mq
        dettaglio.append({
            "nome": c.get("nome") or f"C{len(dettaglio) + 1}",
            "eur_mq": round(eur_mq, 2),
            "coeff": coeff,
            "eur_mq_normalizzato": round(eur_mq / coeff, 2),
        })
    if not dettaglio:
        return None
    media = (sum(d["eur_mq_normalizzato"] for d in dettaglio)
             / len(dettaglio))
    eur_mq_soggetto = media * float(coeff_soggetto or 1.0)
    eur_mq_probabile = eur_mq_soggetto * (1 - float(sconto_pct) / 100)
    mq_sog = float(mq_soggetto or 0.0)
    return {
        "dettaglio": dettaglio,
        "eur_mq_media": round(media, 2),
        "eur_mq_soggetto": round(eur_mq_soggetto, 2),
        "eur_mq_probabile": round(eur_mq_probabile, 2),
        "valore": round(eur_mq_probabile * mq_sog, 2) if mq_sog else None,
    }
