"""I materiali che compra il committente, non l'impresa.

In cantiere questo foglio esiste già, ed è un documento firmato: «ALLEGATO 1
COMPUTO METRICO — Elenco materiali acquistati cura Committente», sottoscritto
per accettazione dalle due parti. Serve a segnare il confine dell'appalto:
quello che c'è scritto qui l'impresa non lo fornisce e non lo mette a
preventivo. Da lì viene tutto quello che c'è in questo modulo.

- **Il prezzo non è obbligatorio.** Sull'allegato firmato non c'era nessun
  prezzo: è un elenco di cose, e il conto viene dopo, quando si va a
  comprare. Una riga senza prezzo è una riga buona — e il totale che la
  ignora deve DIRLO. Un totale che tace le voci ancora da quotare è un
  totale che mente, e qui si mentirebbe verso il basso: la cifra sembra
  buona proprio finché mancano i pezzi più cari.
- **La quantità che manca vale 1.** Il box doccia è uno, e chi scrive «BOX
  DOCCIA — 450 €» ha già detto tutto. È la stessa convenzione delle
  dimensioni non compilate nel computo (`calcoli.quantita_voce`): quel che
  non si scrive non conta, non azzera.
- **I capitoli sono quelli del foglio**, nell'ordine in cui li scrive: bagno,
  porte e infissi, impianto elettrico, muratura, pavimenti, riscaldamento.
  **Non** sono i sette mestieri del computo, e non devono diventarlo: «BAGNO»
  è una stanza, non un mestiere. Questo elenco lo legge chi va a comprare —
  che ragiona per stanze e per fornitori — non chi posa.

Questi importi **non entrano nel totale dei lavori**: sono soldi che escono
dalla tua tasca, non dalla fattura dell'impresa, e il computo che va in gara
non deve vederli. Entrano invece nel costo dell'operazione, ed è nel business
plan che si ritrovano.

Solo funzioni pure: niente Streamlit, niente pandas.
"""

# I sei dell'allegato firmato, nel loro ordine. Gli ultimi quattro sono le
# vie d'uscita: la cucina, l'arredo e gli esterni su quel cantiere non
# c'erano, ma su un altro ci sono, e senza un posto dove metterli
# finirebbero tutti in «ALTRO», che è come non avere capitoli.
CAPITOLI = [
    "BAGNO",
    "PORTE E INFISSI",
    "IMPIANTO ELETTRICO",
    "MURATURA",
    "PAVIMENTI",
    "IMPIANTO RISCALDAMENTO",
    "CUCINA",
    "ARREDO ED ELETTRODOMESTICI",
    "ESTERNI",
    "ALTRO",
]

CAPITOLO_PREDEFINITO = CAPITOLI[-1]

# Dove sta la spesa, non com'è fatta la cosa. Tre stati e basta: il quarto
# («pagato») sarebbe la fattura, e la fattura ha già il suo registro nelle
# spese a consuntivo — due posti dove segnare lo stesso pagamento sono un
# posto di troppo.
STATI = ["Da ordinare", "Ordinato", "Consegnato"]
STATO_PREDEFINITO = STATI[0]


def calcola_riga(riga):
    """Copia della riga con «importo» calcolato.

    L'importo è `quantità × prezzo`, con la quantità mancante che vale 1.
    Se il prezzo manca l'importo è **None**, non zero: quella riga un
    importo non ce l'ha ancora, e uno zero la conterebbe come gratis.
    """
    esito = dict(riga)
    quantita = riga.get("quantita")
    prezzo = riga.get("prezzo")
    esito["quantita"] = (None if quantita is None
                         else round(float(quantita), 3))
    if prezzo is None:
        esito["importo"] = None
    else:
        pezzi = 1.0 if quantita is None else float(quantita)
        esito["importo"] = round(pezzi * float(prezzo), 2)
    return esito


def calcola_elenco(righe):
    """Ogni riga con il suo importo."""
    return [calcola_riga(riga) for riga in righe or []]


def totale(righe_calcolate):
    """Quanto costa quello che un prezzo ce l'ha già.

    Le righe ancora da quotare non entrano — vanno contate a parte con
    `da_quotare`, e chi mostra questo numero deve mostrare anche quello.
    """
    return round(sum(float(r["importo"]) for r in righe_calcolate or []
                     if r.get("importo") is not None), 2)


def da_quotare(righe_calcolate):
    """Quante righe non hanno ancora un prezzo."""
    return sum(1 for r in righe_calcolate or [] if r.get("importo") is None)


def _somma_per(righe_calcolate, chiave, ordine, predefinito):
    """Aggrega gli importi per uno dei due campi di classificazione.

    L'ordine è quello dell'elenco di riferimento; quello che non ci sta —
    un capitolo scritto a mano in un progetto vecchio — va in coda, nel
    suo ordine di comparsa. Le righe senza prezzo contano come voce ma
    non come importo: un capitolo con tre cose e nessun prezzo esiste, e
    deve comparire col suo zero e il suo «3 da quotare».
    """
    agg = {}
    for riga in righe_calcolate or []:
        valore = (riga.get(chiave) or "").strip() or predefinito
        voce = agg.setdefault(valore, {"importo": 0.0, "voci": 0,
                                       "da_quotare": 0})
        voce["voci"] += 1
        if riga.get("importo") is None:
            voce["da_quotare"] += 1
        else:
            voce["importo"] += float(riga["importo"])
    posizione = {v: i for i, v in enumerate(ordine)}
    chiavi = sorted(agg, key=lambda v: posizione.get(v, len(posizione)))
    return {v: {**agg[v], "importo": round(agg[v]["importo"], 2)}
            for v in chiavi}


def totali_per_capitolo(righe_calcolate):
    """{capitolo: {'importo', 'voci', 'da_quotare'}}, nell'ordine dei capitoli."""
    return _somma_per(righe_calcolate, "capitolo", CAPITOLI,
                      CAPITOLO_PREDEFINITO)


def totali_per_stato(righe_calcolate):
    """{stato: {'importo', 'voci', 'da_quotare'}} — a che punto è la spesa.

    È il numero per cui esiste la colonna: quanto hai già impegnato e
    quanto ti resta da ordinare.
    """
    return _somma_per(righe_calcolate, "stato", STATI, STATO_PREDEFINITO)


def raggruppa_per_capitolo(righe):
    """Le righe raggruppate per capitolo, nell'ordine dei capitoli.

    Serve all'allegato in PDF, che è fatto di blocchi: un titolo di
    capitolo e sotto le sue cose, come il foglio da cui viene.
    """
    gruppi = {}
    for riga in righe or []:
        capitolo = (riga.get("capitolo") or "").strip() or CAPITOLO_PREDEFINITO
        gruppi.setdefault(capitolo, []).append(riga)
    posizione = {c: i for i, c in enumerate(CAPITOLI)}
    return {c: gruppi[c]
            for c in sorted(gruppi, key=lambda c: posizione.get(
                c, len(posizione)))}


def note_numerate(righe):
    """Le note delle righe, con l'asterisco che le richiama.

    Sull'allegato vero la nota sta in fondo al foglio e la riga che la
    riguarda porta un asterisco: «UNITÀ INTERNA + ESTERNA CLIMA CANALIZZATO
    *» e sotto «* Si fornisce inoltre: plenum coibentato, collarini…». Uno,
    due, tre asterischi nell'ordine in cui compaiono.

    Ritorna [{"riga", "marcatore", "testo"}]: `riga` è la riga stessa, così
    chi stampa sa a quale descrizione attaccare il marcatore.
    """
    note = []
    for riga in righe or []:
        testo = (riga.get("note") or "").strip()
        if testo:
            note.append({"riga": riga,
                         "marcatore": "*" * (len(note) + 1),
                         "testo": testo})
    return note
