"""Le righe del computo, lette e scritte direttamente sul file del progetto.

Gemello di quello che `streamlit_app.py` fa con lo stato di sessione, ma
senza sessione: prende il dizionario di un progetto salvato (quello di
`archivio_locale.carica_progetto`) e ne ricava le righe, oppure ci scrive
dentro una quantità o un prezzo. Niente Streamlit, niente HTTP: lo usa il
motore nuovo (`server/`), e un giorno potrà usarlo anche la pagina vecchia.

⚠️ Il formato del file è quello di `_payload_progetto` in
`streamlit_app.py`, e qui non si inventa niente:

- le voci del listino guida tengono quantità e prezzo in `listino_stato`,
  **solo** se si discostano dalla guida (quantità > 0 o prezzo diverso);
- le voci scritte a mano stanno per intero in `voci`, con
  `quantita_manuale` e `prezzo`;
- le riscritture di testo stanno in `testi_voci` (`d` descrizione, `u` u.m.);
- l'ordine del computo è quello di `voci_scelte`;
- Tetto e Facciata contano solo se sono in `lavori_facoltativi`.

Tutto il resto del file (planimetrie, business plan, spese, materiali…)
passa di qui senza essere toccato.
"""
import calcoli
import listino


def _voci_extra(dati):
    """Le voci scritte a mano, per codice (solo quelle con una descrizione,
    come fa la pagina vecchia riaprendo un progetto)."""
    return {r["codice"]: r for r in (dati.get("voci") or [])
            if r.get("codice") and (r.get("descrizione") or "").strip()}


def categoria_accesa(dati, categoria):
    """Tetto e Facciata si accendono per progetto; il resto è sempre acceso."""
    if categoria not in listino.CATEGORIE_FACOLTATIVE:
        return True
    return categoria in (dati.get("lavori_facoltativi") or [])


def voce(dati, codice):
    """Una riga del computo, con quantità e importo calcolati. None se il
    codice non è né nel listino né fra le voci scritte a mano."""
    extra = _voci_extra(dati).get(codice)
    testi = (dati.get("testi_voci") or {}).get(codice) or {}
    if extra is not None:
        riga = {
            "codice": codice,
            "categoria": extra.get("categoria") or calcoli.SENZA_CATEGORIA,
            "descrizione": extra.get("descrizione") or "",
            "um": extra.get("um") or "",
            "quantita_manuale": float(extra.get("quantita_manuale") or 0.0),
            "prezzo": float(extra.get("prezzo") or 0.0),
            "a_mano": True,
        }
    else:
        guida = listino.voce_per_codice(codice)
        if guida is None:
            return None
        stato = (dati.get("listino_stato") or {}).get(codice) or {}
        riga = {
            "codice": codice,
            "categoria": guida["categoria"],
            "descrizione": testi.get("d") or guida["descrizione"],
            "um": testi.get("u") or guida["um"],
            "quantita_manuale": float(stato.get("q", 0.0)),
            "prezzo": float(stato.get("p", guida["prezzo"])),
            "a_mano": False,
        }
    calcolata = calcoli.calcola_voce(riga)
    calcolata.pop("quantita_manuale")
    # Una voce a zero resta a video ma fuori dai totali: «da quantificare».
    calcolata["da_quantificare"] = calcolata["quantita"] == 0
    return calcolata


def righe(dati):
    """Le righe del computo nell'ordine di `voci_scelte`, raggruppate per
    categoria nell'ordine del listino, senza i lavori spenti."""
    tutte = [r for c in (dati.get("voci_scelte") or [])
             if (r := voce(dati, c)) is not None
             and categoria_accesa(dati, r["categoria"])]
    ordine = {cat: i for i, cat in enumerate(listino.CATEGORIE)}
    return sorted(tutte, key=lambda r: ordine.get(r["categoria"], len(ordine)))


def totali(dati, le_righe=None):
    """Totale lavori, per categoria, IVA e totale IVA inclusa."""
    le_righe = righe(dati) if le_righe is None else le_righe
    per_categoria = calcoli.totali_per_categoria(le_righe)
    totale = calcoli.totale_generale(le_righe)
    aliquota = float((dati.get("progetto") or {}).get("aliquota_iva") or 0.0)
    iva, con_iva = calcoli.totale_con_iva(totale, aliquota)
    return {
        "per_categoria": per_categoria,
        "incidenze": calcoli.incidenze_percentuali(per_categoria, totale),
        "totale": totale,
        "aliquota_iva": aliquota,
        "iva": iva,
        "totale_con_iva": con_iva,
    }


def scrivi(dati, codice, quantita=None, prezzo=None):
    """Scrive quantità e/o prezzo di una voce nel dizionario del progetto.

    Rispetta la regola del file: per le voci del listino, in `listino_stato`
    resta solo quello che si discosta dalla guida. Ritorna False se il
    codice non è una voce del computo.
    """
    if codice not in (dati.get("voci_scelte") or []):
        return False
    extra = _voci_extra(dati).get(codice)
    if extra is not None:
        if quantita is not None:
            extra["quantita_manuale"] = float(quantita)
        if prezzo is not None:
            extra["prezzo"] = float(prezzo)
        return True
    guida = listino.voce_per_codice(codice)
    if guida is None:
        return False
    stato = dati.setdefault("listino_stato", {})
    elemento = stato.get(codice) or {"q": 0.0, "p": guida["prezzo"]}
    if quantita is not None:
        elemento["q"] = float(quantita)
    if prezzo is not None:
        elemento["p"] = float(prezzo)
    if elemento["q"] > 0 or elemento["p"] != guida["prezzo"]:
        stato[codice] = elemento
    else:
        stato.pop(codice, None)
    return True
