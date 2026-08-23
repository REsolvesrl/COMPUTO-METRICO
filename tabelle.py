"""Le tabelle dell'app: com'è fatta ognuna e come si passa da e verso i dati.

Fra l'editor a griglia e il JSON del progetto c'è sempre una conversione: la
tabella parla di celle, il progetto parla di dizionari. Quella conversione è
logica, non interfaccia — e ha regole che si pagano care se si sbagliano:

- una cella vuota deve diventare `None`, non `""` né `0`, altrimenti una
  quantità mancante finisce nel computo come uno zero deciso da nessuno;
- le colonne di testo lasciate vuote devono nascere **come testo**: una
  colonna di soli NaN diventa numerica e l'editor la rifiuta;
- la categoria di spesa, nella tabella, porta davanti un pallino colorato:
  va tolto prima di calcolare o salvare, o si ritroverebbe nel JSON.

Qui c'è pandas ma non Streamlit: si prova con pytest, senza far partire
l'interfaccia.
"""
import pandas as pd

import fattibilita
import materiali
import merito

# ------------------------------------------------------------- il computo

COLONNE_TESTO = ["categoria", "codice", "descrizione", "um"]
COLONNE_NUMERI = ["parti", "lunghezza", "larghezza", "altezza",
                  "quantita_manuale", "prezzo"]
COLONNE = COLONNE_TESTO + COLONNE_NUMERI

# Spese a consuntivo: due registri distinti (come il foglio «Spese» Excel).
# Sostenute = fatture reali (con data e numero); da sostenere = previsioni.
# «fornitore» sta per conto suo: stava dentro «oggetto», appiccicato alla
# descrizione con un trattino, e cosi' non lo si poteva ne' ordinare ne'
# leggere a colpo d'occhio — su un registro di fatture il nome di chi te le
# manda e' meta' dell'informazione. I progetti salvati prima non ce l'hanno:
# la colonna nasce vuota, e la descrizione resta dov'era.
COLONNE_SPESE = ["importo", "aliquota_iva", "data", "nr_fattura",
                 "fornitore", "oggetto", "categoria", "note"]

# L'IVA in euro NON e' qui dentro: si ricava da importo e aliquota, e un
# valore derivato non si salva — si ricalcola. La colonna esiste solo nella
# tabella a schermo, dove la mette la scheda.
COLONNA_IVA_EUR = "iva_eur"


def senza_iva_derivata(df):
    """Il DataFrame ripulito dalla colonna derivata dell'IVA in euro.

    Serve ogni volta che il RITORNO di una tabella a schermo torna a essere
    dato: il data_editor restituisce anche le colonne calcolate, e se una di
    quelle rientrasse nei dati salvati, al giro dopo ci si ritroverebbe a
    inserire una colonna che c'e' gia'.
    """
    return df.drop(columns=[COLONNA_IVA_EUR], errors="ignore")
COLONNE_SPESE_PREV = ["oggetto", "importo", "aliquota_iva", "categoria",
                      "note"]
COLONNE_SPESE_NUM = ["importo", "aliquota_iva"]

# I materiali a cura del committente. Si legge da sinistra a destra
# nell'ordine in cui si sanno le cose: che roba è, quanta, da chi la compri,
# dove, a che punto è. **Nessuna colonna di soldi**, ed è una scelta
# spiegata in materiali.py: i prezzi dei materiali vivono nel registro
# spese, dove arrivano dalle fatture vere. Niente unità di misura: sul
# foglio firmato non compilava mai, ed è una colonna che chiedeva spazio a
# vuoto.
COLONNE_MATERIALI = ["capitolo", "descrizione", "quantita",
                     "fornitore", "link", "stato", "note"]
COLONNE_MATERIALI_NUM = ["quantita"]

# Tessere colorate per i capitoli dell'allegato: nove tinte per nove
# capitoli, sul modello dei sette mestieri del computo. Quadrate e non
# pallini: il data_editor non permette uno sfondo di cella vero (è tela
# grafica, vedi il vincolo in DESIGN.md), e fra i glifi disponibili il
# quadrato pieno è quello che più si avvicina a un riempimento — un
# pallino, di fianco a un testo, legge come un'etichetta di stato, non
# come una tinta. «ALTRO» resta senza — è il ripiego di chi non trova la
# sua stanza in elenco, non una stanza vera — così come «Pratiche e
# oneri» resta senza tinta piena nel computo.
EMOJI_CAPITOLO = {
    "BAGNO": "🟦", "PORTE E INFISSI": "🟫", "IMPIANTO ELETTRICO": "🟨",
    "MURATURA": "🟧", "PAVIMENTI": "🟩", "IMPIANTO RISCALDAMENTO": "🟥",
    "CUCINA": "🟪", "ARREDO ED ELETTRODOMESTICI": "⬛", "ESTERNI": "⬜",
}
CAPITOLI_EMOJI = [f"{EMOJI_CAPITOLO.get(c, '')} {c}".strip()
                 for c in materiali.CAPITOLI]

# Un semaforo, non una tavolozza: rosso quello che manca ancora, giallo
# quello mosso, verde quello arrivato — è la stessa lettura a colpo
# d'occhio con cui si guarda un cantiere.
EMOJI_STATO = {
    "Da ordinare": "🟥", "Ordinato": "🟨", "Consegnato": "🟩",
}
STATI_EMOJI = [f"{EMOJI_STATO.get(s, '')} {s}".strip()
              for s in materiali.STATI]
# ⚠️ Le voci della griglia di merito stanno IN MEZZO, fra i mq e il
# coefficiente: e' l'ordine in cui si compila una riga (che immobile e',
# poi quanto vale). Il coefficiente viene dopo perche' ormai e' l'ECCEZIONE
# — il numero battuto a mano da chi non si fida della griglia — e non piu'
# il dato da inserire.
COLONNE_MCA = (["nome", "prezzo", "mq"] + list(merito.CAMPI)
               + ["coeff", "note"])
COLONNE_MCA_NUM = ("prezzo", "mq", "coeff")
# L'ascensore e' l'unica spunta della griglia. Senza questa riga finirebbe
# fra le colonne di testo e tornerebbe dal salvataggio come la stringa
# "False", che e' vera.
COLONNE_MCA_BOOL = ("ascensore",)

# Pallino colorato mostrato davanti alla categoria nella tabella modificabile
# (il data_editor non colora lo sfondo delle celle: l'emoji è il ripiego).
EMOJI_CATEGORIA = {
    "ACQUISTO": "🔴", "LAVORI": "🟡", "MATERIALE": "🟢",
    "ARCHITETTO": "🟠", "COSTI INDIRETTI": "⚪",
    "AGENZIA": "🟣", "ALTRO": "🟤",
}
CATEGORIE_SPESE_EMOJI = [f"{EMOJI_CATEGORIA.get(c, '')} {c}".strip()
                         for c in fattibilita.CATEGORIE_SPESE]


def _mancante(valore):
    """True per una cella vuota, comunque l'editor l'abbia lasciata."""
    return valore is None or pd.isna(valore)


# ------------------------------------------------------- voci del computo

def df_vuoto():
    colonne = {}
    for col in COLONNE:
        tipo = "object" if col in COLONNE_TESTO else "float64"
        colonne[col] = pd.Series(dtype=tipo)
    return pd.DataFrame(colonne)


def voci_da_df(df):
    """Trasforma la tabella dell'editor in una lista di voci (dizionari)."""
    voci = []
    for _, riga in df.iterrows():
        voce = {}
        for col in COLONNE:
            valore = riga.get(col)
            if _mancante(valore) or valore == "":
                voce[col] = None
            elif col in COLONNE_NUMERI:
                voce[col] = float(valore)
            else:
                voce[col] = str(valore)
        if any(v is not None for v in voce.values()):
            voci.append(voce)
    return voci


# ------------------------------------------------------------------ spese

def _pallino_pulito(valore, mappa_emoji):
    """Il valore senza l'eventuale pallino emoji iniziale, qualunque mappa."""
    testo = (str(valore) if valore is not None else "").strip()
    for emoji in mappa_emoji.values():
        if testo.startswith(emoji):
            return testo[len(emoji):].strip()
    return testo


def _pallino_display(valore, mappa_emoji):
    """Il valore col pallino emoji davanti, se la mappa gliene assegna uno."""
    base = _pallino_pulito(valore, mappa_emoji)
    emoji = mappa_emoji.get(base)
    return f"{emoji} {base}" if emoji else base


def cat_pulita(valore):
    """Categoria senza l'eventuale pallino emoji iniziale (per calcoli/JSON)."""
    return _pallino_pulito(valore, EMOJI_CATEGORIA)


def cat_display(valore):
    """Categoria col pallino emoji davanti (per la tabella modificabile)."""
    return _pallino_display(valore, EMOJI_CATEGORIA)


def capitolo_pulito(valore):
    """Capitolo senza l'eventuale tessera colorata iniziale."""
    return _pallino_pulito(valore, EMOJI_CAPITOLO)


def capitolo_display(valore):
    """Capitolo con la tessera colorata davanti (per la tabella modificabile)."""
    return _pallino_display(valore, EMOJI_CAPITOLO)


def stato_pulito(valore):
    """Stato dell'ordine senza l'eventuale tessera colorata iniziale."""
    return _pallino_pulito(valore, EMOJI_STATO)


def stato_display(valore):
    """Stato dell'ordine con la tessera colorata davanti (semaforo)."""
    return _pallino_display(valore, EMOJI_STATO)


def df_spese_vuoto(colonne=None):
    """Tabella spese vuota (sostenute per default, o l'elenco colonne dato)."""
    colonne = colonne or COLONNE_SPESE
    dati = {}
    for col in colonne:
        tipo = "float64" if col in COLONNE_SPESE_NUM else "object"
        dati[col] = pd.Series(dtype=tipo)
    return pd.DataFrame(dati)


def df_spese_da_righe(righe, colonne):
    """Tabella spese tipizzata da una lista di dizionari.

    Le colonne mancanti nei dati (es. una spesa da sostenere senza numero
    fattura) vengono create vuote ma col tipo GIUSTO: testo → stringa
    (mai una colonna float di soli NaN, che l'editor rifiuterebbe come
    colonna di testo), numeri → float.
    """
    dati = {}
    for col in colonne:
        valori = [r.get(col) for r in righe]
        if col in COLONNE_SPESE_NUM:
            dati[col] = pd.to_numeric(pd.Series(valori, dtype="object"),
                                      errors="coerce")
        elif col == "categoria":
            # nella tabella modificabile la categoria porta il pallino emoji;
            # vuota = None (NON stringa vuota: "" non è tra le opzioni del menu
            # a tendina e fa crashare il data_editor nel browser)
            dati[col] = pd.Series(
                [None if _mancante(v) else (cat_display(v) or None)
                 for v in valori], dtype="object")
        else:
            dati[col] = pd.Series(
                ["" if _mancante(v) else str(v) for v in valori],
                dtype="object")
    return pd.DataFrame(dati)


def spese_da_df(df):
    """Le spese come lista di dizionari (solo le righe con un importo).

    Vale per entrambi i registri: i campi assenti in una tabella (una non ha
    data né numero fattura) diventano stringa vuota.
    """
    righe = []
    for _, riga in df.iterrows():
        importo = riga.get("importo")
        if _mancante(importo):
            continue

        def testo(campo, predefinito=""):
            valore = riga.get(campo)
            return predefinito if _mancante(valore) else str(valore)

        aliquota = riga.get("aliquota_iva")
        righe.append({
            "importo": float(importo),
            "aliquota_iva": (0.0 if _mancante(aliquota) else float(aliquota)),
            "data": testo("data"),
            "nr_fattura": testo("nr_fattura"),
            "fornitore": testo("fornitore"),
            "oggetto": testo("oggetto"),
            "categoria": cat_pulita(testo("categoria")) or "ALTRO",
            "note": testo("note"),
        })
    return righe


# ------------------------------------------------------------- materiali

def df_materiali_vuoto():
    """Tabella dei materiali vuota, con i tipi giusti."""
    dati = {}
    for col in COLONNE_MATERIALI:
        # «Float64» (nullable, non il numpy «float64»): è il tipo che
        # pandas riserva apposta per un numero che può mancare, con un
        # NA suo — dove il numpy semplice ha solo NaN, buono per i conti
        # ma nato per dire «non un numero», non «non c'è ancora».
        tipo = "Float64" if col in COLONNE_MATERIALI_NUM else "object"
        dati[col] = pd.Series(dtype=tipo)
    return pd.DataFrame(dati)


def df_materiali_da_righe(righe):
    """Tabella dei materiali da una lista di dizionari.

    ⚠️ Capitolo e stato vuoti diventano **None**, mai stringa vuota: sono
    tendine, e `""` non è fra le opzioni — il data_editor va in errore nel
    browser. È lo stesso inciampo già preso con la categoria delle spese, e
    porta la stessa tessera colorata davanti al testo.
    """
    dati = {}
    for col in COLONNE_MATERIALI:
        valori = [r.get(col) for r in righe]
        if col in COLONNE_MATERIALI_NUM:
            # Il tipo nullable qui non è un capriccio: la quantità mancante
            # è la NORMA su questo elenco (l'allegato firmato non la porta
            # quasi mai), e un tipo numerico pensato per il caso raro
            # rischia di trattarla come un'eccezione invece che come lo
            # stato più comune della colonna.
            dati[col] = pd.to_numeric(
                pd.Series(valori, dtype="object"),
                errors="coerce").astype("Float64")
        elif col == "capitolo":
            dati[col] = pd.Series(
                [None if _mancante(v) else (capitolo_display(v) or None)
                 for v in valori], dtype="object")
        elif col == "stato":
            dati[col] = pd.Series(
                [None if _mancante(v) else (stato_display(v) or None)
                 for v in valori], dtype="object")
        else:
            dati[col] = pd.Series(
                ["" if _mancante(v) else str(v) for v in valori],
                dtype="object")
    return pd.DataFrame(dati)


def materiali_da_df(df):
    """I materiali come lista di dizionari (solo le righe con una descrizione).

    ⚠️ È la DESCRIZIONE a fare la riga. Nelle spese basta un importo, perché
    una spesa senza cifra non è una spesa; qui è il contrario: l'allegato è
    un elenco di NOMI, e di cifre non ne ha nemmeno una.

    ⚠️⚠️ La quantità mancante resta **None**, non zero. Uno zero direbbe
    «nessuno», e su un elenco di cose da comprare vuol dire il contrario di
    «quante non l'ho ancora deciso».
    """
    righe = []
    for _, riga in df.iterrows():
        descrizione = riga.get("descrizione")
        descrizione = "" if _mancante(descrizione) else str(descrizione).strip()
        if not descrizione:
            continue

        def numero(campo):
            valore = riga.get(campo)
            return None if _mancante(valore) else float(valore)

        def testo(campo, predefinito=""):
            valore = riga.get(campo)
            if _mancante(valore):
                return predefinito
            return str(valore).strip() or predefinito

        righe.append({
            "capitolo": (capitolo_pulito(testo("capitolo"))
                        or materiali.CAPITOLO_PREDEFINITO),
            "descrizione": descrizione,
            "quantita": numero("quantita"),
            "fornitore": testo("fornitore"),
            "link": testo("link"),
            "stato": stato_pulito(testo("stato")) or materiali.STATO_PREDEFINITO,
            "note": testo("note"),
        })
    return righe


# ------------------------------------------------------- comparabili (MCA)

def df_mca_vuoto():
    colonne = {}
    for col in COLONNE_MCA:
        tipo = "float64" if col in COLONNE_MCA_NUM else "object"
        colonne[col] = pd.Series(dtype=tipo)
    return pd.DataFrame(colonne)


def mca_da_df(df):
    """La tabella dei comparabili come lista di dizionari."""
    righe = []
    for _, riga in df.iterrows():
        valori = {}
        for col in COLONNE_MCA:
            valore = riga.get(col)
            if _mancante(valore):
                valori[col] = None
            elif col in COLONNE_MCA_NUM:
                valori[col] = float(valore)
            elif col in COLONNE_MCA_BOOL:
                valori[col] = bool(valore)
            else:
                valori[col] = str(valore)
        # ⚠️ Una spunta NON messa non e' un dato: la casella dell'ascensore
        # nasce a False in ogni riga nuova, e senza questa esclusione una
        # riga mai toccata si salverebbe come comparabile vero — vuoto, ma
        # contato fra gli scartati a ogni stima.
        if any(v is not None and v is not False for v in valori.values()):
            righe.append(valori)
    return righe
