"""I materiali che compra il committente, non l'impresa.

In cantiere questo foglio esiste già, ed è un documento firmato: «ALLEGATO 1
COMPUTO METRICO — Elenco materiali acquistati cura Committente», sottoscritto
per accettazione dalle due parti. Serve a segnare il confine dell'appalto:
quello che c'è scritto lì l'impresa non lo fornisce e non lo mette a
preventivo. Da lì viene tutto quello che c'è in questo modulo.

**Qui dentro non ci sono soldi, ed è una scelta.** L'allegato firmato di
prezzi non ne porta nemmeno uno: è un elenco di cose da comprare, e il
confine che traccia è di forniture, non di importi. I soldi dei materiali
vivono già altrove e con più verità — nel registro delle spese a consuntivo,
dove arrivano dalle fatture vere, e fra le «spese da sostenere» quando sono
ancora un budget. Tenerne una seconda contabilità qui vorrebbe dire due
numeri per la stessa cosa, e prima o poi due numeri diversi.

Quello che invece serve mentre si compra: **da chi** (il fornitore), **dove**
(il link del negozio, per ritrovare quel modello esatto sei mesi dopo) e **a
che punto è** l'ordine.

I **capitoli** sono quelli del foglio, nel suo ordine: bagno, porte e infissi,
impianto elettrico, muratura, pavimenti, riscaldamento. **Non** sono i sette
mestieri del computo, e non devono diventarlo: «BAGNO» è una stanza, non un
mestiere. Questo elenco lo legge chi va a comprare — che ragiona per stanze e
per fornitori — non chi posa.

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

# Dove sta l'acquisto, non com'è fatta la cosa. Tre stati e basta: il quarto
# («pagato») sarebbe la fattura, e la fattura ha già il suo registro nelle
# spese a consuntivo — due posti dove segnare lo stesso pagamento sono un
# posto di troppo.
STATI = ["Da ordinare", "Ordinato", "Consegnato"]
STATO_PREDEFINITO = STATI[0]

# La nota dell'allegato vero, attaccata alla riga del clima canalizzato.
NOTA_CLIMA = ("Si fornisce inoltre: plenum coibentato, collarini, bocchette "
              "mandata, griglia di ripresa, fascette stringitubo, eventuale "
              "termostato.")

# ---------------------------------------------------------------------------
# L'elenco standard: le voci dell'allegato del cantiere di Migliarina, che si
# comprano su ogni ristrutturazione di questo tipo. Un progetto nuovo nasce
# con queste già in tabella — «tanto quelle vanno sicuramente acquistate» —
# e si toglie quel che su questo cantiere non serve, invece di riscrivere
# trenta righe ogni volta.
#
# ⚠️ Non è un listino di prezzi e non deve diventarlo: sono NOMI di cose. Il
# modello preciso, il fornitore e il link li mette chi compra, cantiere per
# cantiere, perché cambiano tutti e tre a ogni giro.
# ---------------------------------------------------------------------------
ELENCO_STANDARD = [
    ("BAGNO", "PIATTO DOCCIA", ""),
    ("BAGNO", "BOX DOCCIA", ""),
    ("BAGNO", "MOBILE BAGNO + SPECCHIO + APPLIQUE", ""),
    ("BAGNO", "LAVABO D'APPOGGIO", ""),
    ("BAGNO", "PILETTA LAVABO E BIDET", ""),
    ("BAGNO", "SIFONE LAVABO", ""),
    ("BAGNO", "TERMOARREDO ELETTRICO", ""),
    ("BAGNO", "MISCELATORE LAVABO E BIDET", ""),
    ("BAGNO", "SET MISCELATORE DOCCIA", ""),
    ("BAGNO", "BOILER ELETTRICO", ""),
    ("BAGNO", "COPPIA DI SANITARI FILOMURO (CON SEDILE)", ""),
    ("BAGNO", "PLACCA WC", ""),
    ("BAGNO", "CASSETTA DI SCARICO", ""),
    ("PORTE E INFISSI", "PORTE A BATTENTE / SCRIGNO", ""),
    ("PORTE E INFISSI", "MANIGLIE", ""),
    ("PORTE E INFISSI", "CONTROTELAI PORTE INTERNE", ""),
    ("PORTE E INFISSI", "PORTE BLINDATE E CONTROTELAIO", ""),
    ("PORTE E INFISSI", "FINESTRE", ""),
    ("PORTE E INFISSI", "TAPPARELLE COMPRESO KIT DOVE NECESSARIO", ""),
    ("IMPIANTO ELETTRICO", "CITOFONO", ""),
    ("IMPIANTO ELETTRICO", "FRUTTI", ""),
    ("IMPIANTO ELETTRICO", "PLACCHE", ""),
    ("IMPIANTO ELETTRICO", "SUPPORTI", ""),
    ("IMPIANTO ELETTRICO", "STRISCE LED / FARETTI CARTONGESSO", ""),
    ("MURATURA", "LANA DI ROCCIA", ""),
    ("MURATURA", "PANNELLI FONOASSORBENTI (ES. GOMMAPIOMBO)", ""),
    ("PAVIMENTI", "PAVIMENTO/RIVESTIMENTO GRES", ""),
    ("IMPIANTO RISCALDAMENTO", "UNITÀ INTERNA + ESTERNA CLIMA CANALIZZATO",
     NOTA_CLIMA),
    ("IMPIANTO RISCALDAMENTO", "CLIMATIZZATORE MOD. UNICO TWIN", ""),
]


def riga_vuota(capitolo=CAPITOLO_PREDEFINITO, descrizione="", note=""):
    """Una riga completa di tutti i suoi campi, con i valori di partenza."""
    return {
        "capitolo": capitolo,
        "descrizione": descrizione,
        "um": "",
        "quantita": None,
        "fornitore": "",
        "link": "",
        "stato": STATO_PREDEFINITO,
        "note": note,
    }


def elenco_standard():
    """L'elenco di partenza, come righe nuove e indipendenti.

    Copie fresche a ogni chiamata: se restituisse i dizionari del modulo,
    modificarne uno in un progetto lo cambierebbe per tutti i successivi.
    """
    return [riga_vuota(capitolo, descrizione, note)
            for capitolo, descrizione, note in ELENCO_STANDARD]


def _conta_per(righe, chiave, ordine, predefinito):
    """Quante voci per capitolo (o per stato), nell'ordine di riferimento.

    Quello che non sta nell'elenco di riferimento — un capitolo scritto a
    mano, o arrivato da un progetto vecchio — va in coda invece che sparire.
    """
    conti = {}
    for riga in righe or []:
        valore = (riga.get(chiave) or "").strip() or predefinito
        conti[valore] = conti.get(valore, 0) + 1
    posizione = {v: i for i, v in enumerate(ordine)}
    return {v: conti[v]
            for v in sorted(conti, key=lambda v: posizione.get(v,
                                                              len(posizione)))}


def conteggi_per_capitolo(righe):
    """{capitolo: quante voci}, nell'ordine dei capitoli."""
    return _conta_per(righe, "capitolo", CAPITOLI, CAPITOLO_PREDEFINITO)


def conteggi_per_stato(righe):
    """{stato: quante voci} — a che punto è la spesa.

    È il numero per cui esiste la colonna: quante cose devi ancora ordinare.
    """
    return _conta_per(righe, "stato", STATI, STATO_PREDEFINITO)


def quante_da_ordinare(righe):
    """Le voci ancora da ordinare: il numero che dice se sei in ritardo."""
    return conteggi_per_stato(righe).get(STATO_PREDEFINITO, 0)


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
