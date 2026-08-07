"""CME — Computo Metrico Estimativo.

Interfaccia Streamlit a due schede:
1. Computo metrico — tabella voci, quantità calcolate, totali, export.
2. Misura da planimetria — più planimetrie per progetto, zone colorate per
   categoria con percentuale commerciale, scala a vettore, misura pareti e
   riepilogo delle superfici commerciali del fabbricato.

La logica di calcolo vive in calcoli.py; la geometria in planimetria.py;
il visualizzatore interattivo in cme_viewer/.
"""

import base64
import copy
import hashlib
import hmac
import io
import json
import os
import tempfile
import time
from datetime import date, datetime
from pathlib import Path

import fitz  # PyMuPDF, per leggere i PDF
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from PIL import Image

import archivio
import calcoli
import fattibilita
import fattura
import listino
import planimetria
import rilevamento
from cme_viewer import image_viewer, pil_a_src

st.set_page_config(
    page_title="CME — Computo Metrico",
    page_icon="🏗️",
    layout="wide",
)

# Ritocchi al tema di Streamlit che il file .streamlit/config.toml non copre.
st.markdown("""
<style>
/* Il testo dei riquadri «info» usciva a 2,7:1 sul fondo navy: sotto qualsiasi
   soglia, proprio dove l'app spiega cosa fare. */
[data-testid="stAlertContentInfo"], [data-testid="stAlertContentInfo"] p {
    color: #D7DEEA;
}
/* Le didascalie occupavano tutta la larghezza della pagina: righe da 200
   caratteri, ben oltre la misura in cui l'occhio ritrova l'inizio della riga
   dopo. Il limite non allarga nulla, taglia solo le righe troppo lunghe. */
[data-testid="stCaptionContainer"] { max-width: 82ch; }
</style>
""", unsafe_allow_html=True)

# ==========================================================
# 🔒 ACCESSO RISERVATO
# Il cancello si attiva SOLO se la password è configurata (secrets di
# Streamlit oppure variabile d'ambiente APP_PASSWORD). Se non c'è, l'app
# resta ad accesso libero: così i deploy esistenti non cambiano comportamento.
# ==========================================================

LOGO_PATH = Path(__file__).parent / "assets" / "logo_resolve.png"


def _password_attesa():
    """Password di accesso, da st.secrets o da variabile d'ambiente."""
    try:
        if "APP_PASSWORD" in st.secrets:
            return str(st.secrets["APP_PASSWORD"])
    except Exception:
        pass
    return os.environ.get("APP_PASSWORD")


def _accesso_consentito():
    attesa = _password_attesa()
    if not attesa:
        return True                       # nessuna password impostata
    if st.session_state.get("auth_ok"):
        return True

    _, centro, _ = st.columns([1, 2, 1])
    with centro:
        if LOGO_PATH.exists():
            st.image(str(LOGO_PATH), width=200)
        st.subheader("Accesso riservato")
        st.caption(
            "Strumento interno di Resolve S.r.l. "
            "Inserisci la password per continuare."
        )
        pwd = st.text_input("Password", type="password", key="auth_pwd")
        if st.button("Entra", type="primary"):
            # confronto a tempo costante: non rivela la password carattere
            # per carattere misurando i tempi di risposta
            if hmac.compare_digest(pwd, attesa):
                st.session_state["auth_ok"] = True
                st.session_state.pop("auth_pwd", None)
                st.rerun()
            else:
                st.error("⛔ Password errata.")
    return False


if not _accesso_consentito():
    st.stop()


COLONNE_TESTO = ["categoria", "codice", "descrizione", "um"]
COLONNE_NUMERI = ["parti", "lunghezza", "larghezza", "altezza",
                  "quantita_manuale", "prezzo"]
COLONNE = COLONNE_TESTO + COLONNE_NUMERI

# Colonne del "libretto delle misure": ogni voce del listino può essere
# scomposta in più righe (una per stanza/parete) che si sommano nella quantità.
COLONNE_MISURE = ["descrizione", "parti", "lunghezza", "larghezza", "altezza"]
COLONNE_MISURE_NUM = ["parti", "lunghezza", "larghezza", "altezza"]

UM_OPZIONI = ["m", "m²", "m³", "kg", "t", "cad", "h", "a corpo",
              "punto", "utenza"]

# Colori delle categorie del listino: (pallino/hex, colore markdown titolo).
COLORI_CATEGORIE = {
    "Demolizioni": ("#E57373", "red"),
    "Ricostruzioni e ripristini": ("#66BB6A", "green"),
    "Idraulico": ("#64B5F6", "blue"),
    "Elettricista": ("#F0A840", "orange"),
    "Serramenti": ("#9575CD", "violet"),
    "Aree esterne": ("#B0BEC5", "gray"),
}
ALTRE_VOCI = "Voci aggiuntive"

# Voci del listino ricavabili dalle superfici misurate sulla planimetria:
# (codice, grandezza da cui prendere la quantità, accesa di default).
# Accese solo quelle che valgono in ogni ristrutturazione; demolizioni e
# rasatura dipendono da cosa si trova in cantiere, quindi si spuntano a mano.
VOCI_DA_SUPERFICI = [
    ("1.01", "pavimento", False),         # demolizione pavimenti
    ("1.10", "battiscopa", False),        # rimozione zoccolini
    ("2.03", "pavimento", False),         # rifacimento massetto
    ("2.10", "pavimento_sfrido", True),   # posa gres (+5% di sfrido)
    ("2.14", "battiscopa", True),         # posa battiscopa
    ("2.17", "tinteggiatura", False),     # rasatura muri e soffitti
    ("2.18", "tinteggiatura", True),      # tinteggiatura muri e soffitti
    # dai muri tracciati sulla planimetria (lunghezza × altezza)
    ("1.02", "muri_demolire", True),      # demolizione murature
    ("2.01", "muri_costruire", True),     # ricostruzione muri in forati
]

# Business plan: colonne delle tabelle e impostazioni predefinite
# (chiave di sessione → valore iniziale; il tipo del default comanda).
# Spese a consuntivo: due registri distinti (come il foglio «Spese» Excel).
# Sostenute = fatture reali (con data e numero); da sostenere = previsioni.
COLONNE_SPESE = ["importo", "aliquota_iva", "data", "nr_fattura",
                 "oggetto", "categoria", "note"]
COLONNE_SPESE_PREV = ["oggetto", "importo", "aliquota_iva", "categoria",
                      "note"]
COLONNE_SPESE_NUM = ["importo", "aliquota_iva"]
COLONNE_MCA = ["nome", "prezzo", "mq", "coeff", "note"]

# Colori categorie di spesa: allineati ai pallini-emoji della colonna
# Categoria, così pallino + fetta di torta + cella del riepilogo combaciano.
# Toni chiari (reggono un testo scuro sopra) e nessun blu (si confondeva col
# fondo navy).
COLORE_CATEGORIA_SPESA = {
    "ACQUISTO": "#FF8A70",         # 🔴 corallo
    "LAVORI": "#F4C143",           # 🟡 giallo
    "MATERIALE": "#78C46E",        # 🟢 verde
    "ARCHITETTO": "#F0982E",       # 🟠 arancio
    "COSTI INDIRETTI": "#D9DCE0",  # ⚪ grigio chiaro
    "AGENZIA": "#B49BE0",          # 🟣 viola
    "ALTRO": "#C0392B",            # 🟤 rosso scuro
}
# Pallino colorato mostrato davanti alla categoria nella tabella modificabile
# (il data_editor non colora lo sfondo delle celle: l'emoji è il ripiego).
EMOJI_CATEGORIA = {
    "ACQUISTO": "🔴", "LAVORI": "🟡", "MATERIALE": "🟢",
    "ARCHITETTO": "🟠", "COSTI INDIRETTI": "⚪",
    "AGENZIA": "🟣", "ALTRO": "🟤",
}
CATEGORIE_SPESE_EMOJI = [f"{EMOJI_CATEGORIA.get(c, '')} {c}".strip()
                         for c in fattibilita.CATEGORIE_SPESE]
IMPOSTAZIONI_BP = {
    "bp_acquisto": 0.0, "bp_vendita": 0.0, "bp_mq": 0.0,
    "bp_imposta": 9.0, "bp_imposte_fisse": 0.0, "bp_notaio": 3500.0,
    "bp_ag_in": 3.0, "bp_ag_out": 2.5, "bp_iva_ag": 22.0,
    "bp_imprevisti": 15000.0, "bp_mutuo": 0.0, "bp_durata": 12,
    "bp_ristr": 0.0, "bp_passo": 10000.0,
    "bp_coeff_sogg": 1.0, "bp_sconto": 13.0,
}

# Palette del brand Resolve (dark navy + oro), come MORA.
ORO = "#C9A96A"           # oro champagne — barre del grafico
CREMA = "#ECE7DA"         # testo
GRIGLIA = "#3C4C6E"       # linee griglia su fondo navy
ETICHETTE = "#A9B4C9"     # etichette assi

# Planimetria. Le immagini sono tenute a una risoluzione "canonica" (CANON_MAX):
# è lo spazio in cui vivono scala, zone e pareti. Zoom e spostamento avvengono
# solo nel browser (componente cme_viewer) e non toccano queste coordinate.
CANON_MAX = 2000

# Colori delle categorie di superficie (assegnati in ordine).
PALETTE_ZONE = ["#E57373", "#F0A840", "#E8D44D", "#66BB6A", "#4DB6AC",
                "#64B5F6", "#9575CD", "#F06292"]

# Categorie di superficie con le incidenze delle «superfici di ornamento».
# Solo i GIARDINI hanno lo scaglione: l'incidenza piena vale fino a `soglia`
# m², l'eccedenza pesa `oltre` %. La soglia si applica al totale della
# categoria in quella planimetria (è l'unità immobiliare ad avere diritto ai
# primi 25 m² pieni, non il singolo giardino).
CATEGORIE_DEFAULT = [
    {"nome": "Superficie commerciale", "percento": 100.0},
    {"nome": "Superficie interna", "percento": 100.0},
    {"nome": "Balcone", "percento": 30.0},
    {"nome": "Terrazzo", "percento": 35.0},
    {"nome": "Loggia", "percento": 40.0},
    {"nome": "Giardino", "percento": 15.0, "soglia": 25.0, "oltre": 5.0},
    {"nome": "Garage / Box", "percento": 50.0},
    {"nome": "Cantina", "percento": 30.0},
    {"nome": "Vano scale", "percento": 50.0},
]

# Colore di ogni categoria. È esplicito e non più legato alla posizione in
# elenco: così due categorie possono condividerlo (vano scale e garage) e
# riordinare la lista non rimescola i colori del disegno.
COLORE_CATEGORIA_SUP = {
    "Superficie commerciale": "#7E57C2",   # viola — solo contorno
    "Superficie interna": "#E57373",       # rosso
    "Balcone": "#F0A840",                  # arancio
    "Terrazzo": "#E8D44D",                 # giallo
    "Loggia": "#4DB6AC",                   # verde acqua
    "Giardino": "#4CAF50",                 # verde: è il giardino
    "Garage / Box": "#64B5F6",             # azzurro
    "Cantina": "#9575CD",                  # lilla
    "Vano scale": "#64B5F6",               # azzurro, come il garage
    # categorie di lavori precedenti: stesso colore dell'equivalente
    # attuale, così un disegno vecchio non cambia aspetto
    "Balcone scoperto": "#F0A840",
    "Balcone coperto": "#F0A840",
    "Balcone / Lastrico solare": "#F0A840",
    "Terrazzo di attico (a tasca)": "#E8D44D",
    "Portico / Patio": "#E8D44D",
    "Corte / Cortile": "#BCAAA4",
    "Giardino di appartamento": "#4CAF50",
    "Giardino di villa o villino": "#558B2F",
    "Cantina / Soffitta": "#9575CD",
}

# Categorie di lavori precedenti che non sono più nell'elenco: restano
# valide dove sono state usate, con la loro regola. I giardini portano lo
# scaglione come quelli attuali, altrimenti una zona disegnata prima del
# cambio conterebbe l'intera superficie all'incidenza piena.
PERCENTUALI_STORICHE = {
    "Cantina / Soffitta": 25.0,
    "Balcone scoperto": 30.0,
    "Balcone coperto": 35.0,
    "Balcone / Lastrico solare": 25.0,
    "Terrazzo di attico (a tasca)": 40.0,
    "Portico / Patio": 35.0,
    "Corte / Cortile": 10.0,
    "Giardino di appartamento": {"percento": 15.0, "soglia": 25.0,
                                 "oltre": 5.0},
    "Giardino di villa o villino": {"percento": 10.0, "soglia": 25.0,
                                    "oltre": 2.0},
}

# Categorie «involucro»: perimetri che servono SOLO a misurare la superficie
# commerciale. Si disegnano senza sfondo e restano sotto le altre aree, così
# ci si può disegnare sopra; non sono locali da lavorare, quindi non entrano
# in pavimenti, battiscopa e tinteggiature, non ostacolano il rilevamento
# automatico delle stanze e non occupano spazio per le etichette.
CATEGORIE_INVOLUCRO = ("Superficie commerciale",)

# Categorie che servono SOLO al computo metrico: le stanze interne si
# misurano per pavimenti, battiscopa e tinteggiature, ma la parte vendibile
# si prende col perimetro «Superficie commerciale», che le racchiude già.
# Contarle in entrambi i posti significherebbe contare due volte lo stesso
# spazio, gonfiando la superficie commerciale.
CATEGORIE_SOLO_COMPUTO = ("Superficie interna",)

# Categoria delle stanze riconosciute dal rilevamento automatico: sono
# locali, quindi superficie interna al 100%.
CATEGORIA_STANZE = "Superficie interna"

# Tipi di parete: colore sul disegno a seconda dell'intervento.
# "esistente" resta solo per compatibilità con progetti già salvati; le nuove
# pareti si scelgono tra demolire e costruire (TIPI_PARETE_SCELTA).
TIPI_PARETE = {
    "esistente": {"nome": "Esistente", "colore": "#C9A96A"},
    "demolire": {"nome": "Da demolire", "colore": "#E53935"},
    "costruire": {"nome": "Da costruire", "colore": "#FFD400"},
}
TIPI_PARETE_SCELTA = ["demolire", "costruire"]


# ------------------------------------------------------------------ utilità

def euro(valore):
    """Formato italiano: 1.234,56 €"""
    if valore is None or pd.isna(valore):
        return ""
    testo = f"{valore:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    return f"{testo} €"


def testo_su(colore_hex):
    """Colore di testo leggibile su uno sfondo dato: navy scuro sui colori
    chiari, crema su quelli scuri (in base alla luminosità percepita)."""
    h = colore_hex.lstrip("#")
    r, g, b = int(h[0:2], 16), int(h[2:4], 16), int(h[4:6], 16)
    luminanza = 0.299 * r + 0.587 * g + 0.114 * b
    return "#1A2744" if luminanza > 140 else "#ECE7DA"


def numero_it(valore, decimali=3):
    if valore is None or pd.isna(valore):
        return ""
    testo = f"{valore:,.{decimali}f}"
    return testo.replace(",", "X").replace(".", ",").replace("X", ".")


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
            if valore is None or pd.isna(valore) or valore == "":
                voce[col] = None
            elif col in COLONNE_NUMERI:
                voce[col] = float(valore)
            else:
                voce[col] = str(valore)
        if any(v is not None for v in voce.values()):
            voci.append(voce)
    return voci


def df_misure_vuoto():
    """Tabella vuota per il libretto delle misure di una voce."""
    colonne = {"descrizione": pd.Series(dtype="object")}
    for col in COLONNE_MISURE_NUM:
        colonne[col] = pd.Series(dtype="float64")
    return pd.DataFrame(colonne)


def df_misure(righe):
    """Costruisce la tabella del libretto misure da un elenco di dizionari."""
    if not righe:
        return df_misure_vuoto()
    df = pd.DataFrame(righe).reindex(columns=COLONNE_MISURE)
    for col in COLONNE_MISURE_NUM:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def misure_da_df(df):
    """La tabella del libretto misure come elenco di dizionari (righe piene)."""
    righe = []
    for _, riga in df.iterrows():
        misura = {}
        for col in COLONNE_MISURE:
            valore = riga.get(col)
            if valore is None or pd.isna(valore) or valore == "":
                misura[col] = None
            elif col in COLONNE_MISURE_NUM:
                misura[col] = float(valore)
            else:
                misura[col] = str(valore)
        if any(v is not None for v in misura.values()):
            righe.append(misura)
    return righe


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
            def _cat(v):
                if v is None or (isinstance(v, float) and pd.isna(v)):
                    return None
                return cat_display(v) or None
            dati[col] = pd.Series([_cat(v) for v in valori], dtype="object")
        else:
            dati[col] = pd.Series(
                ["" if v is None or (isinstance(v, float) and pd.isna(v))
                 else str(v) for v in valori], dtype="object")
    return pd.DataFrame(dati)


def spese_da_df(df):
    """Le spese come lista di dizionari (solo le righe con un importo).

    Vale per entrambi i registri: i campi assenti in una tabella (una non ha
    data né numero fattura) diventano stringa vuota.
    """
    righe = []
    for _, riga in df.iterrows():
        importo = riga.get("importo")
        if importo is None or pd.isna(importo):
            continue

        def testo(campo, predefinito=""):
            valore = riga.get(campo)
            return predefinito if valore is None or pd.isna(valore) \
                else str(valore)

        aliquota = riga.get("aliquota_iva")
        righe.append({
            "importo": float(importo),
            "aliquota_iva": (0.0 if aliquota is None or pd.isna(aliquota)
                             else float(aliquota)),
            "data": testo("data"),
            "nr_fattura": testo("nr_fattura"),
            "oggetto": testo("oggetto"),
            "categoria": cat_pulita(testo("categoria")) or "ALTRO",
            "note": testo("note"),
        })
    return righe


def cat_pulita(valore):
    """Categoria senza l'eventuale pallino emoji iniziale (per calcoli/JSON)."""
    testo = (str(valore) if valore is not None else "").strip()
    for emoji in EMOJI_CATEGORIA.values():
        if testo.startswith(emoji):
            return testo[len(emoji):].strip()
    return testo


def cat_display(valore):
    """Categoria col pallino emoji davanti (per la tabella modificabile)."""
    base = cat_pulita(valore)
    emoji = EMOJI_CATEGORIA.get(base)
    return f"{emoji} {base}" if emoji else base


def config_colonne_spese():
    """Configurazione colonne condivisa tra editor spese e anteprima fatture."""
    return {
        "importo": st.column_config.NumberColumn(
            "Importo (€)", format="%.2f"),
        "aliquota_iva": st.column_config.NumberColumn(
            "IVA %", min_value=0.0, max_value=22.0, step=1.0,
            help="Aliquota della fattura, per lo scorporo (22, 10 o 0)"),
        "data": st.column_config.TextColumn("Data", help="Es. 22/10/2025"),
        "nr_fattura": st.column_config.TextColumn(
            "Nr. fattura", help="Numero/riferimento della fattura"),
        "oggetto": st.column_config.TextColumn("Oggetto", width="large"),
        "categoria": st.column_config.SelectboxColumn(
            "Categoria", options=CATEGORIE_SPESE_EMOJI),
        "note": st.column_config.TextColumn("Note"),
    }


def dati_fattura_da_file(file):
    """Estrae i dati di una spesa da un file fattura (PDF o XML).

    Non solleva MAI: qualunque file illeggibile (XML firmato .p7m, codifica
    inattesa, PDF protetto, ecc.) restituisce None e finisce tra i «non
    letti», senza far cadere l'app.
    """
    try:
        nome = (file.name or "").lower()
        contenuto = file.getvalue()
        if nome.endswith((".xml", ".p7m")):
            dati = fattura.dati_da_xml(contenuto)
            if dati:
                return dati
        if nome.endswith(".pdf") or contenuto[:4] == b"%PDF":
            with fitz.open(stream=contenuto, filetype="pdf") as doc:
                testo = "\n".join(doc[i].get_text()
                                  for i in range(doc.page_count))
            return fattura.dati_da_pdf_testo(testo)
    except Exception:
        return None
    return None


def df_mca_vuoto():
    colonne = {}
    for col in COLONNE_MCA:
        tipo = "float64" if col in ("prezzo", "mq", "coeff") else "object"
        colonne[col] = pd.Series(dtype=tipo)
    return pd.DataFrame(colonne)


def mca_da_df(df):
    """La tabella dei comparabili come lista di dizionari."""
    righe = []
    for _, riga in df.iterrows():
        valori = {}
        for col in COLONNE_MCA:
            valore = riga.get(col)
            if valore is None or pd.isna(valore):
                valori[col] = None
            elif col in ("prezzo", "mq", "coeff"):
                valori[col] = float(valore)
            else:
                valori[col] = str(valore)
        if any(v is not None for v in valori.values()):
            righe.append(valori)
    return righe


def aggiungi_voce_computo(categoria, descrizione, um, quantita, prezzo,
                          codice=None):
    """Appende una voce alla tabella del computo (planimetria e listino)."""
    riga = {col: None for col in COLONNE}
    riga["categoria"] = categoria or None
    riga["codice"] = codice or None
    riga["descrizione"] = descrizione or None
    riga["um"] = um
    riga["quantita_manuale"] = quantita
    riga["prezzo"] = prezzo if prezzo else None
    st.session_state.df_voci = pd.concat(
        [st.session_state.df_voci, pd.DataFrame([riga])], ignore_index=True)
    st.session_state.versione_editor += 1


def nome_file(estensione):
    base = (st.session_state.prg_nome or "computo").strip().replace(" ", "_")
    base = "".join(c for c in base if c.isalnum() or c in "_-") or "computo"
    return f"{base}.{estensione}"


# ------------------------------------------------------- checklist listino

def quantita_prezzo_listino(voce):
    """Quantità e prezzo correnti (dai widget) di una voce del listino."""
    quantita = float(st.session_state.get(f"lq_{voce['codice']}") or 0.0)
    prezzo = float(st.session_state.get(f"lp_{voce['codice']}")
                   or voce["prezzo"])
    return quantita, prezzo


def totale_categoria_listino(categoria):
    """Somma quantità × prezzo delle voci compilate della categoria."""
    totale = 0.0
    for voce in listino.voci_della_categoria(categoria):
        quantita, prezzo = quantita_prezzo_listino(voce)
        totale += quantita * prezzo
    return round(totale, 2)


def voci_dal_listino():
    """Le voci del listino con quantità > 0, nel formato del computo."""
    voci = []
    for voce in listino.VOCI:
        quantita, prezzo = quantita_prezzo_listino(voce)
        if quantita > 0:
            voci.append({"categoria": voce["categoria"],
                         "codice": voce["codice"],
                         "descrizione": voce["descrizione"],
                         "um": voce["um"], "parti": None, "lunghezza": None,
                         "larghezza": None, "altezza": None,
                         "quantita_manuale": quantita, "prezzo": prezzo})
    return voci


def css_schede_computo():
    """CSS delle schede colorate del computo (stile «card» per categoria).

    Ogni scheda è avvolta in un st.container(key="card_…"): Streamlit le
    assegna la classe .st-key-card_… e da lì coloriamo sfondo e bordo.

    IMPORTANTE: il «Totale» a destra è disegnato dal CSS (::after), NON
    scritto nell'etichetta dell'expander. Se il totale stesse nel titolo,
    a ogni modifica il titolo cambierebbe e Streamlit tratterebbe la
    tendina come un widget nuovo, richiudendola: con il CSS il titolo
    resta identico e la tendina rimane aperta mentre si lavora.
    """
    regole = ["""
[class*="st-key-card_"] [data-testid="stExpander"] details {
    border-radius: 12px;
}
[class*="st-key-card_"] summary [data-testid="stMarkdownContainer"] {
    width: 100%;
}
[class*="st-key-card_"] summary [data-testid="stMarkdownContainer"] p {
    display: flex;
    align-items: baseline;
    width: 100%;
    font-size: 1.25rem;
}
[class*="st-key-card_"] summary [data-testid="stMarkdownContainer"] p::after {
    margin-left: auto;
    font-weight: 700;
    padding-left: 0.5rem;
    white-space: nowrap;
}
"""]
    carte = [(f"card_{i}", COLORI_CATEGORIE[cat][0],
              totale_categoria_listino(cat))
             for i, cat in enumerate(listino.CATEGORIE, start=1)]
    tot_extra = calcoli.totale_generale(
        calcoli.calcola_computo(voci_da_df(st.session_state.df_voci)))
    carte.append(("card_extra", ORO, tot_extra))
    for chiave, colore, totale in carte:
        regole.append(f"""
.st-key-{chiave} [data-testid="stExpander"] details {{
    background: {colore}26;
    border: 1px solid {colore}99;
}}
.st-key-{chiave} [data-testid="stExpander"] summary:hover {{
    background: {colore}33;
    border-radius: 12px;
}}
.st-key-{chiave} summary [data-testid="stMarkdownContainer"] p::after {{
    content: "Totale: {euro(totale)}";
}}
.st-key-{chiave} hr {{
    height: 2px;
    background-color: {colore}77;
    border: none;
    margin: 0.35rem 0 0.6rem;
}}
""")
    return "<style>" + "".join(regole) + "</style>"


def riga_voce_listino(voce):
    """Una riga della checklist: descrizione, quantità, prezzo, parziale.

    La quantità si inserisce a mano oppure, spuntando "📐 Libretto misure",
    scomponendola in più righe (parti × lung × larg × alt) che si sommano —
    con le detrazioni scritte come parti negative. Quando il libretto è
    attivo la quantità è la somma delle misure (non digitabile a mano) e
    viene comunque scritta in lq_<codice>, così riepilogo, export e
    salvataggio la leggono senza modifiche.
    """
    codice = voce["codice"]
    c_voce, c_qta, c_prezzo, c_parz = st.columns(
        [3.4, 1, 1, 1], vertical_alignment="center")
    aiuto = voce.get("nota")
    if voce.get("analisi"):
        aiuto = (aiuto + "\n\n" if aiuto else "") + voce["analisi"]
    c_voce.markdown(f"**{codice}** {voce['descrizione']} · "
                    f":gray[{voce['um']}]", help=aiuto)
    usa_misure = c_voce.checkbox(
        "📐 Libretto misure", key=f"usamis_{codice}",
        help="Scomponi la quantità in più misure (parti × lung × larg × alt) "
             "che si sommano. Le detrazioni si scrivono con parti negative.")

    prezzo = c_prezzo.number_input(
        "Prezzo €", min_value=0.0, step=1.0, format="%.2f",
        key=f"lp_{codice}", label_visibility="collapsed")

    if usa_misure:
        # Tabella "di partenza" costante tra i run (finché non si carica/azzera
        # un progetto): il data_editor ci scrive sopra gli edit dell'utente e
        # noi leggiamo il ritorno. Ripassare il ritorno come dato di partenza
        # rischierebbe il doppio conteggio delle righe aggiunte.
        base = st.session_state.misure_base.get(codice)
        if base is None:
            base = df_misure(st.session_state.misure_correnti.get(codice, []))
            st.session_state.misure_base[codice] = base
        editato = st.data_editor(
            base, num_rows="dynamic", hide_index=True,
            key=f"med_{codice}_{st.session_state.versione_misure}",
            column_config={
                "descrizione": st.column_config.TextColumn(
                    "Descrizione", width="large",
                    help="Es. Soggiorno, Camera 1, vano porta…"),
                "parti": st.column_config.NumberColumn(
                    "Parti", help="Numero di parti uguali. "
                                  "Negativo = detrazione (es. -1)."),
                "lunghezza": st.column_config.NumberColumn("Lungh. (m)"),
                "larghezza": st.column_config.NumberColumn("Largh. (m)"),
                "altezza": st.column_config.NumberColumn("Alt. (m)"),
            })
        righe = misure_da_df(editato)
        st.session_state.misure_correnti[codice] = righe
        quantita = calcoli.quantita_da_misure(righe)
        # NON creo il number_input lq_ in questo ramo: scrivo la key come
        # semplice valore di sessione (letto da riepilogo, export e JSON).
        st.session_state[f"lq_{codice}"] = quantita
        c_qta.markdown(f"**{numero_it(quantita, 2)}** :gray[{voce['um']}]")
    else:
        st.session_state.misure_base.pop(codice, None)
        st.session_state.misure_correnti.pop(codice, None)
        quantita = c_qta.number_input(
            "Quantità", min_value=0.0, step=1.0, format="%.2f",
            key=f"lq_{codice}", label_visibility="collapsed")

    if quantita > 0:
        c_parz.markdown(f"**{euro(quantita * prezzo)}**")
    else:
        c_parz.markdown(":gray[0,00 €]")


def grafico_totali(totali):
    """Barre orizzontali: una serie, un solo colore, etichette dirette."""
    categorie = sorted(totali, key=totali.get)
    valori = [totali[c] for c in categorie]
    fig = go.Figure(go.Bar(
        x=valori,
        y=categorie,
        orientation="h",
        marker_color=ORO,
        text=[euro(v) for v in valori],
        textposition="outside",
        textfont=dict(color=CREMA),
        cliponaxis=False,
        hovertemplate="%{y}: %{text}<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=80, t=10, b=10),
        height=max(200, 60 + 40 * len(categorie)),
        showlegend=False,
        font=dict(family='system-ui, -apple-system, "Segoe UI", sans-serif',
                  color=CREMA),
        xaxis=dict(showgrid=True, gridcolor=GRIGLIA, zeroline=False,
                   tickfont=dict(color=ETICHETTE)),
        yaxis=dict(showgrid=False, tickfont=dict(color=CREMA)),
    )
    return fig


def grafico_torta_spese(riepilogo):
    """Torta delle spese sostenute per categoria (importi lordi)."""
    categorie = list(riepilogo)
    valori = [riepilogo[c]["importo"] for c in categorie]
    colori = [COLORE_CATEGORIA_SPESA.get(c, ORO) for c in categorie]
    fig = go.Figure(go.Pie(
        labels=categorie,
        values=valori,
        marker=dict(colors=colori, line=dict(color="#1A2744", width=1)),
        textinfo="percent",
        # testo della % leggibile su ogni fetta (scuro sui chiari, crema sugli scuri)
        textfont=dict(color=[testo_su(c) for c in colori], size=11),
        hovertemplate="%{label}: %{value:.2f} € (%{percent})<extra></extra>",
        sort=False,
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=10, b=10),
        height=320,
        showlegend=True,
        legend=dict(font=dict(color=CREMA, size=10), orientation="v",
                    yanchor="middle", y=0.5, xanchor="left", x=1.0),
        font=dict(family='system-ui, -apple-system, "Segoe UI", sans-serif',
                  color=CREMA),
    )
    return fig


def tabella_riepilogo_spese_html(riepilogo, totale, iva_totale):
    """Riepilogo per categoria come tabella HTML.

    Ogni categoria è evidenziata col suo colore della torta (bordo + sfondo
    tenue); la riga TOTALE ha sfondo diverso, bordo oro e grassetto per
    risaltare rispetto al resto.
    """
    righe = []
    for cat, v in riepilogo.items():
        colore = COLORE_CATEGORIA_SPESA.get(cat, ORO)
        # sfondo pieno del colore (uguale alla fetta di torta) + testo che
        # si adatta alla luminosità (scuro sui chiari, crema sugli scuri)
        righe.append(
            '<tr>'
            f'<td style="padding:5px 8px;background:{colore};'
            f'color:{testo_su(colore)};'
            f'font-weight:700;white-space:nowrap;">{cat}</td>'
            '<td style="padding:5px 8px;text-align:right;color:#ECE7DA;'
            f'white-space:nowrap;">{euro(v["importo"])}</td>'
            '<td style="padding:5px 8px;text-align:right;color:#A9B4C9;'
            f'white-space:nowrap;">{euro(v["iva"])}</td></tr>')
    righe.append(
        '<tr style="background:#2C3E63;font-weight:700;">'
        '<td style="padding:8px;color:#C9A96A;letter-spacing:.03em;'
        'border-top:2px solid #C9A96A;white-space:nowrap;">TOTALE</td>'
        '<td style="padding:8px;text-align:right;color:#ECE7DA;'
        f'border-top:2px solid #C9A96A;white-space:nowrap;">{euro(totale)}</td>'
        '<td style="padding:8px;text-align:right;color:#ECE7DA;'
        f'border-top:2px solid #C9A96A;white-space:nowrap;">'
        f'{euro(iva_totale)}</td></tr>')
    return (
        '<table style="width:100%;border-collapse:collapse;'
        'font-size:0.9rem;margin-bottom:10px;">'
        '<thead><tr style="color:#A9B4C9;font-size:0.78rem;'
        'text-align:left;">'
        '<th style="padding:4px 8px;">Categoria</th>'
        '<th style="padding:4px 8px;text-align:right;">€</th>'
        '<th style="padding:4px 8px;text-align:right;">IVA</th>'
        '</tr></thead><tbody>' + "".join(righe) + '</tbody></table>')


def grafico_sensitivita(prezzi_acquisto, prezzi_vendita, matrice, metrica,
                        base_acquisto=None, base_vendita=None, altezza=330):
    """Matrice di sensitività come mappa di calore stile Excel.

    Colori come la formattazione condizionale del foglio — minimo → rosso,
    massimo → verde — ma con il BIANCO sul PAREGGIO, non sulla mediana.
    L'Excel ancora il bianco al 50° percentile: è un rango relativo, e su
    una matrice tutta in utile finisce per dipingere di rosso salmone uno
    scenario da +25.900 € solo perché è il peggiore dei buoni. Su una
    schermata compra/non-compra il colore dev'essere un verdetto: sotto il
    pareggio si perde, sopra si guadagna. Il prezzo base di
    acquisto/vendita è evidenziato in
    **grassetto sull'etichetta nativa** dell'asse (non su una copia
    posizionata a mano): così l'allineamento con le altre etichette è
    garantito dal disegno stesso del grafico — uno spostamento in pixel
    stimato a occhio si è rivelato inaffidabile da un browser all'altro.
    Lo sfondo colorato del chip è un rettangolo agganciato alle coordinate
    dei DATI (colonna/riga esatta), non a coordinate di pagina che
    dipendono dalla larghezza della finestra.
    """
    if metrica == "multiplo":
        testo = [[numero_it(v, 2) + "x" for v in riga] for riga in matrice]
    else:
        testo = [[numero_it(v / 1000, 1) + "k" for v in riga]
                 for riga in matrice]
    piatti = sorted(v for riga in matrice for v in riga)
    minimo, massimo = piatti[0], piatti[-1]
    if minimo == massimo:
        minimo, massimo = minimo - 1, massimo + 1
    # il pareggio: un money multiple di 1,00x, o un guadagno di 0 €
    pareggio = 1.0 if metrica == "multiplo" else 0.0
    if pareggio <= minimo:
        # ogni scenario della matrice è in utile: dal pareggio in su
        scala = [[0.0, "#FFFFFF"], [1.0, "#63BE7B"]]
    elif pareggio >= massimo:
        # ogni scenario è in perdita: nessun verde da mostrare
        scala = [[0.0, "#F8696B"], [1.0, "#FFFFFF"]]
    else:
        frazione_bianco = (pareggio - minimo) / (massimo - minimo)
        scala = [[0.0, "#F8696B"], [frazione_bianco, "#FFFFFF"],
                 [1.0, "#63BE7B"]]

    etichette_v = [numero_it(p / 1000, 0) + "k" for p in prezzi_vendita]
    etichette_a = [numero_it(p / 1000, 0) + "k" for p in prezzi_acquisto]

    def indice_base(prezzi, base):
        if base is None or not prezzi:
            return None
        return min(range(len(prezzi)), key=lambda i: abs(prezzi[i] - base))

    idx_a = indice_base(prezzi_acquisto, base_acquisto)
    idx_v = indice_base(prezzi_vendita, base_vendita)
    # grassetto sull'etichetta VERA (pseudo-html nativo di Plotly): stessa
    # posizione delle altre etichette per costruzione, zero rischio.
    if idx_v is not None:
        etichette_v[idx_v] = f"<b>{etichette_v[idx_v]}</b>"
    if idx_a is not None:
        etichette_a[idx_a] = f"<b>{etichette_a[idx_a]}</b>"

    fig = go.Figure(go.Heatmap(
        z=matrice, x=etichette_v, y=etichette_a,
        text=testo, texttemplate="%{text}",
        textfont=dict(size=11, color="#1A2744"),
        colorscale=scala, zmin=minimo, zmax=massimo, showscale=False,
        xgap=1, ygap=1,
        hovertemplate=("Acquisto %{y} · Vendita %{x}: %{text}"
                       "<extra></extra>"),
    ))
    # Margini in pixel (uguali a quelli di update_layout più sotto). In
    # coordinate "paper" y=1.0 è il bordo ALTO dell'area dati e x=0 il bordo
    # SINISTRO: le etichette vivono appena FUORI da lì, nei margini
    # (y>1.0 in alto, x<0 a sinistra). Il margine superiore va da y=1.0 a
    # y=1.0 + margine/area_dati; restarci dentro (2 px di sicurezza) evita
    # che il riquadro ad altezza fissa di Streamlit lo ritagli.
    margine_alto_px, margine_sx_px = 26, 48
    area_alto = altezza - margine_alto_px
    frazione_alto = (margine_alto_px - 2) / area_alto
    # sfondo azzurro DIETRO l'etichetta della colonna base (nel margine
    # superiore): xref="x" segue il dato (giusto a qualunque larghezza).
    if idx_v is not None:
        fig.add_shape(type="rect", xref="x", x0=idx_v - 0.5, x1=idx_v + 0.5,
                      yref="paper", y0=1.0, y1=1.0 + frazione_alto,
                      fillcolor="#DDEBF7", line=dict(width=0),
                      layer="below")
    # sfondo giallo dietro l'etichetta della riga base (margine sinistro):
    # yref="y" segue il dato; xref="paper" x<0 sta nel margine. Confermato
    # visivamente dall'utente che funziona.
    if idx_a is not None:
        fig.add_shape(type="rect", yref="y", y0=idx_a - 0.5, y1=idx_a + 0.5,
                      xref="paper", x0=-0.075, x1=0.005,
                      fillcolor="#FFF2CC", line=dict(width=0),
                      layer="below")
    # riquadro spesso sulla cella base (punto di riferimento della matrice):
    # solo coordinate dati, già robusto.
    if idx_a is not None and idx_v is not None:
        fig.add_shape(type="rect",
                      x0=idx_v - 0.5, x1=idx_v + 0.5,
                      y0=idx_a - 0.5, y1=idx_a + 0.5,
                      line=dict(color="#111111", width=3))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=margine_sx_px, r=0, t=margine_alto_px, b=0),
        height=altezza,
        font=dict(family='system-ui, -apple-system, "Segoe UI", sans-serif',
                  color=CREMA),
        xaxis=dict(title=None, side="top", ticks="",
                   tickfont=dict(color=ETICHETTE)),
        yaxis=dict(title=None, autorange="reversed", ticks="",
                   tickfont=dict(color=ETICHETTE)),
    )
    return fig


def legenda_heatmap(metrica):
    """Dichiara cosa significano i colori della matrice.

    Senza legenda il rosso si legge «perdita» anche quando è solo «meno
    buono degli altri»: dirlo evita di dover ricordare com'è tarata la scala.
    """
    pareggio = "1,00x" if metrica == "multiplo" else "0 €"
    chip = ("display:inline-block;width:11px;height:11px;border-radius:2px;"
            "margin-right:5px;vertical-align:-1px;border:1px solid #3C4C6E;")
    return (
        '<div style="font-size:0.72rem;color:#A9B4C9;margin:-6px 0 10px;">'
        f'<span style="{chip}background:#F8696B;"></span>in perdita'
        '&nbsp;&nbsp;·&nbsp;&nbsp;'
        f'<span style="{chip}background:#FFFFFF;"></span>pareggio '
        f'({pareggio})&nbsp;&nbsp;·&nbsp;&nbsp;'
        f'<span style="{chip}background:#63BE7B;"></span>in utile</div>')


def righe_bp(righe):
    """Blocchetto riepilogo stile Excel: righe etichetta/valore compatte.

    righe: [(etichetta, valore, stile)] con stile None | "bold" |
    "buono" (verde) | "cattivo" (rosso).
    """
    pezzi = []
    for etichetta, valore, stile in righe:
        colore = {"buono": "#7DDC7D", "cattivo": "#FF8A8A"}.get(stile, CREMA)
        peso = "700" if stile else "500"
        pezzi.append(
            f'<div style="display:flex;justify-content:space-between;'
            f'align-items:baseline;padding:3px 2px;font-size:0.93rem;'
            f'border-bottom:1px solid rgba(255,255,255,0.08);">'
            f'<span style="color:#A9B4C9;">{etichetta}</span>'
            f'<span style="font-weight:{peso};color:{colore};'
            f'white-space:nowrap;">{valore}</span></div>')
    return "".join(pezzi)


def nota_base_calcolo(acquisto, vendita):
    """Ripete i due prezzi su cui i risultati sono DAVVERO calcolati.

    Streamlit applica un number_input solo alla conferma: fino a quel
    momento il campo mostra la cifra digitata mentre tutto il blocco qui
    sotto resta calcolato sulla precedente. Il server non può accorgersene
    (il valore non confermato non gli arriva), quindi la difesa è ripetere
    qui i valori effettivamente usati: se non coincidono con quelli nei
    campi, il prezzo non è stato applicato.
    """
    def cifra(valore):
        return (euro(valore) if valore
                else '<span style="color:#F0A840;">non inserito</span>')

    return (
        '<div style="font-size:0.72rem;color:#A9B4C9;margin:10px 0 2px;'
        'padding:5px 8px;border-left:2px solid #3C4C6E;line-height:1.5;">'
        'Risultati calcolati su<br>acquisto <b style="color:#ECE7DA;">'
        f'{cifra(acquisto)}</b> · vendita <b style="color:#ECE7DA;">'
        f'{cifra(vendita)}</b></div>')


def guardia_prezzi_bp(acquisto, vendita):
    """Segnala i prezzi digitati ma non ancora applicati.

    Streamlit applica un number_input solo alla conferma, e in questa
    versione non mostra alcun avviso: si digita 295.000, il campo lo fa
    vedere, e sotto resta un ROE calcolato sullo zero. Qui i due valori che
    il server sta davvero usando finiscono in un marcatore, e uno script nel
    documento padre confronta con ciò che c'è nel campo: se differiscono,
    compare un badge sotto la cella. Nessun aggancio agli interni di
    Streamlit, a parte le classi `.st-key-…` dei contenitori (che sono
    l'API pubblica di `st.container(key=…)`).
    """
    st.markdown(
        f'<div id="cme-prezzi-applicati" style="display:none"'
        f' data-acq="{float(acquisto or 0):.2f}"'
        f' data-ven="{float(vendita or 0):.2f}"></div>',
        unsafe_allow_html=True)
    st.iframe("""<!doctype html><html><body><script>
(function () {
  var doc;
  try { doc = window.parent.document; } catch (errore) { return; }
  if (doc.__cmeGuardiaPrezzi) return;
  doc.__cmeGuardiaPrezzi = true;
  var CAMPI = [["bp_in_acq", "acq"], ["bp_in_ven", "ven"]];
  function controlla() {
    var marcatore = doc.getElementById("cme-prezzi-applicati");
    if (!marcatore) return;
    CAMPI.forEach(function (campo) {
      var cella = doc.querySelector(".st-key-" + campo[0]);
      if (!cella) return;
      var input = cella.querySelector("input");
      if (!input) return;
      var applicato = parseFloat(marcatore.dataset[campo[1]] || "0");
      var digitato = parseFloat(input.value);
      var diverso = input.value !== "" && !isNaN(digitato)
                    && Math.abs(digitato - applicato) > 0.005;
      var badge = cella.querySelector(".cme-nonapplicato");
      if (diverso && !badge) {
        badge = doc.createElement("span");
        badge.className = "cme-nonapplicato";
        badge.textContent = "\\u21B5 premi Invio: i numeri sotto usano ancora "
                          + "il valore precedente";
        cella.appendChild(badge);
      } else if (!diverso && badge) {
        badge.remove();
      }
    });
  }
  doc.addEventListener("input", controlla, true);
  // il rerun di Streamlit ricostruisce il DOM: un controllo periodico si
  // riaggancia da solo senza dover osservare l'intero albero
  setInterval(controlla, 400);
  controlla();
})();
</script></body></html>""", height=1)


def riga_costo_bp(etichetta, centro=None, destra=None):
    """Riga del dettaglio costi stile Excel: etichetta | %/€ | netto.

    centro e destra possono essere: None (mostra «/»), una stringa (testo
    di sola lettura) oppure un dizionario {"chiave": …, **kwargs} che
    diventa un number_input modificabile.
    """
    # la colonna «Netto» ospita cifre a 7 numeri con i loro stepper: stretta
    # com'era, i valori uscivano troncati a metà ("16200,0(")
    c_eti, c_inp, c_val = st.columns([1.7, 0.95, 1.35],
                                     vertical_alignment="center")
    c_eti.markdown(f":gray[{etichetta}]")

    def cella(colonna, contenuto, a_destra=False):
        if contenuto is None:
            colonna.markdown('<div style="text-align:center;'
                             'color:#8FA0BE;">/</div>',
                             unsafe_allow_html=True)
        elif isinstance(contenuto, str):
            allinea = "right" if a_destra else "center"
            colonna.markdown(f'<div style="text-align:{allinea};'
                             f'font-weight:600;">{contenuto}</div>',
                             unsafe_allow_html=True)
        else:
            impostazioni = dict(contenuto)
            chiave = impostazioni.pop("chiave")
            colonna.number_input(f"{etichetta} {chiave}", key=chiave,
                                 label_visibility="collapsed",
                                 **impostazioni)

    cella(c_inp, centro)
    cella(c_val, destra, a_destra=True)


def bp_ricalcola_euro():
    """Aggiorna i campi € derivati dalle percentuali del business plan.

    Da chiamare quando cambiano i prezzi o le percentuali: tiene i campi
    € (modificabili) allineati alle % — la sincronizzazione inversa la
    fanno bp_pct_da_euro_*.
    """
    prezzo_a = st.session_state.get("bp_acquisto") or 0.0
    prezzo_v = st.session_state.get("bp_vendita") or 0.0
    iva = 1 + (st.session_state.get("bp_iva_ag") or 0.0) / 100
    st.session_state.bp_imposta_eur = round(
        prezzo_a * st.session_state.bp_imposta / 100, 2)
    st.session_state.bp_ag_in_eur = round(
        prezzo_a * st.session_state.bp_ag_in / 100 * iva, 2)
    st.session_state.bp_ag_out_eur = round(
        prezzo_v * st.session_state.bp_ag_out / 100 * iva, 2)


def bp_pct_da_euro_imposta():
    prezzo = st.session_state.get("bp_acquisto") or 0.0
    if prezzo > 0:
        st.session_state.bp_imposta = round(
            st.session_state.bp_imposta_eur / prezzo * 100, 3)


def bp_pct_da_euro_ag_in():
    prezzo = st.session_state.get("bp_acquisto") or 0.0
    iva = 1 + (st.session_state.get("bp_iva_ag") or 0.0) / 100
    if prezzo > 0:
        st.session_state.bp_ag_in = round(
            st.session_state.bp_ag_in_eur / (prezzo * iva) * 100, 3)


def bp_pct_da_euro_ag_out():
    prezzo = st.session_state.get("bp_vendita") or 0.0
    iva = 1 + (st.session_state.get("bp_iva_ag") or 0.0) / 100
    if prezzo > 0:
        st.session_state.bp_ag_out = round(
            st.session_state.bp_ag_out_eur / (prezzo * iva) * 100, 3)


def excel_bytes(df_computo, df_riepilogo, df_progetto, df_superfici=None):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_computo.to_excel(writer, sheet_name="Computo", index=False)
        df_riepilogo.to_excel(writer, sheet_name="Riepilogo", index=False)
        if df_superfici is not None and len(df_superfici):
            df_superfici.to_excel(writer, sheet_name="Superfici", index=False)
        df_progetto.to_excel(writer, sheet_name="Dati progetto", index=False)
    return buffer.getvalue()


# -------------------------------------------------------------- planimetria

def carica_immagini(file):
    """Legge il file caricato: elenco di immagini RGB (una per pagina se PDF).

    Le immagini sono ridimensionate alla risoluzione canonica CANON_MAX.
    """
    dati = file.getvalue()
    immagini = []
    if file.name.lower().endswith(".pdf") or file.type == "application/pdf":
        documento = fitz.open(stream=dati, filetype="pdf")
        for pagina in list(documento)[:10]:
            pix = pagina.get_pixmap(dpi=200)
            immagini.append(
                Image.frombytes("RGB", (pix.width, pix.height), pix.samples))
    else:
        immagini.append(Image.open(io.BytesIO(dati)).convert("RGB"))
    pronte = []
    for img in immagini:
        if img.width > CANON_MAX:
            altezza = round(img.height * CANON_MAX / img.width)
            img = img.resize((CANON_MAX, altezza))
        pronte.append(img)
    return pronte


def nuova_pianta(img, nome):
    """Crea la struttura-dati di una planimetria del progetto."""
    st.session_state.uid_piante += 1
    thumb = img.copy()
    thumb.thumbnail((240, 240))
    return {"uid": st.session_state.uid_piante, "nome": nome, "img": img,
            "thumb": thumb, "src": pil_a_src(img), "mpp": None,
            "zone": [], "pareti": [], "prossimo_id": 1}


def sostituisci_immagine_pianta(pianta, nuova_img):
    """Cambia l'immagine di una pianta tenendo allineate miniatura e sorgente.

    Le dimensioni in pixel restano quelle di prima, quindi scala, zone e
    pareti — che vivono in coordinate immagine — continuano a valere.
    """
    thumb = nuova_img.copy()
    thumb.thumbnail((240, 240))
    pianta["img"] = nuova_img
    pianta["thumb"] = thumb
    pianta["src"] = pil_a_src(nuova_img)


def aggiungi_planimetrie(file):
    """Aggiunge al progetto le pagine del file caricato e le seleziona."""
    immagini = carica_immagini(file)
    base = file.name.rsplit(".", 1)[0]
    for i, img in enumerate(immagini):
        nome = base if len(immagini) == 1 else f"{base} · pag. {i + 1}"
        st.session_state.piante.append(nuova_pianta(img, nome))
    st.session_state.pianta_idx = len(st.session_state.piante) - len(immagini)
    st.session_state.sel_zona = None
    st.session_state.scala_temp = None
    st.session_state.upl_count += 1


def nuovo_id(pianta):
    pianta["prossimo_id"] += 1
    return pianta["prossimo_id"] - 1


def percento_di(regole, categoria):
    """L'incidenza piena di una categoria, sia che la regola sia un semplice
    numero sia che preveda uno scaglione."""
    valore = regole.get(categoria, 100.0)
    if isinstance(valore, dict):
        return float(valore.get("percento", 100.0))
    return float(valore)


def mappa_percentuali():
    """Regole di incidenza per categoria: percentuale piena e, dove previsto,
    soglia oltre la quale l'eccedenza pesa meno."""
    regole = {}
    for c in st.session_state.categorie:
        if c.get("soglia") and c.get("oltre") is not None:
            regole[c["nome"]] = {"percento": float(c["percento"]),
                                 "soglia": float(c["soglia"]),
                                 "oltre": float(c["oltre"])}
        else:
            regole[c["nome"]] = float(c["percento"])
    return regole


def categorie_per_progetto(piante):
    """Elenco delle categorie: quelle predefinite, più quelle di un progetto
    salvato che nel frattempo sono state tolte o rinominate.

    Le percentuali predefinite sono quelle correnti (se cambiano, i progetti
    aperti si aggiornano); le categorie non più previste restano in coda con
    la loro percentuale storica, così le zone già disegnate non perdono il
    loro peso commerciale.
    """
    categorie = [dict(c) for c in CATEGORIE_DEFAULT]
    noti = {c["nome"] for c in categorie}
    usate = {z.get("categoria") for p in piante for z in (p.get("zone") or [])}
    for nome in sorted(n for n in usate if n and n not in noti):
        regola = PERCENTUALI_STORICHE.get(nome, 100.0)
        if isinstance(regola, dict):
            categorie.append({"nome": nome, **regola})
        else:
            categorie.append({"nome": nome, "percento": float(regola)})
    return categorie


def mappa_colori():
    """Colore di ogni categoria: quello assegnato, o uno dalla tavolozza per
    le categorie di vecchi progetti che non sono più nell'elenco."""
    return {c["nome"]: COLORE_CATEGORIA_SUP.get(
        c["nome"], PALETTE_ZONE[i % len(PALETTE_ZONE)])
        for i, c in enumerate(st.session_state.categorie)}


def etichetta_zona(zona, mpp, perc_map, impostazioni):
    righe = []
    if impostazioni["nome"]:
        righe.append(zona.get("nome") or zona["categoria"])
    if impostazioni["m2"] and mpp:
        area = planimetria.area_reale_m2(zona["punti"], mpp)
        righe.append(f"{numero_it(area, 2)} m²")
    if impostazioni.get("perimetro") and mpp:
        perim = planimetria.perimetro_reale_m(zona["punti"], mpp)
        righe.append(f"per. {numero_it(perim, 2)} m")
    if impostazioni["percento"]:
        perc = percento_di(perc_map, zona["categoria"])
        righe.append(f"{numero_it(perc, 0)} %")
    return "\n".join(righe)


def etichetta_parete(parete, mpp):
    if not mpp:
        return "— m"
    metri = planimetria.distanza_pixel(parete["p1"], parete["p2"]) * mpp
    return f"{numero_it(metri, 2)} m"


def evento_viewer(valore):
    """Restituisce l'evento del componente solo se è nuovo (dedup su seq)."""
    if not valore:
        return None
    seq = valore.get("seq")
    if seq is None or seq == st.session_state.ultimo_seq:
        return None
    st.session_state.ultimo_seq = seq
    return valore


# ------------------------------------------- annulla (planimetria)
# Della planimetria si conserva solo quello che l'utente disegna — zone,
# muri e scala — non le immagini: sono la parte pesante e non cambiano mai
# per un tratto di matita. Bastano pochi kB per passo, così si possono
# tenere gli ultimi PASSI_STORIA gesti senza appesantire la sessione.
PASSI_STORIA = 25


def istantanea_piante():
    """Fotografia di ciò che si può annullare: zone, muri e scala."""
    return [{"uid": p["uid"],
             "mpp": p["mpp"],
             "prossimo_id": p["prossimo_id"],
             "zone": copy.deepcopy(p["zone"]),
             "pareti": copy.deepcopy(p["pareti"])}
            for p in st.session_state.piante]


def registra_storia(descrizione):
    """Da chiamare PRIMA di modificare zone, muri o scala."""
    storia = st.session_state.setdefault("storia", [])
    storia.append({"descrizione": descrizione, "piante": istantanea_piante()})
    del storia[:-PASSI_STORIA]


def annulla_ultima():
    """Riporta zone, muri e scala com'erano prima dell'ultima operazione."""
    storia = st.session_state.get("storia") or []
    if not storia:
        return None
    passo = storia.pop()
    per_uid = {s["uid"]: s for s in passo["piante"]}
    for pianta in st.session_state.piante:
        salvata = per_uid.get(pianta["uid"])
        if salvata is None:
            continue
        pianta["mpp"] = salvata["mpp"]
        pianta["prossimo_id"] = salvata["prossimo_id"]
        pianta["zone"] = copy.deepcopy(salvata["zone"])
        pianta["pareti"] = copy.deepcopy(salvata["pareti"])
    # le selezioni potrebbero puntare a roba che non esiste più
    st.session_state.sel_zona = None
    st.session_state.sel_parete = None
    st.session_state.scala_temp = None
    st.session_state.pop("ultimo_rilevamento", None)
    return passo["descrizione"]


# eventi del visualizzatore che modificano il disegno (gli altri — selezione,
# spostamento di un'etichetta — non vale la pena annullarli)
DA_ANNULLARE = {
    "zona_chiusa": "disegno dell'area",
    "zona_modificata": "modifica dell'area",
    "zona_eliminata": "eliminazione dell'area",
    "parete": "tracciamento del muro",
    "parete_eliminata": "eliminazione del muro",
    "rinomina": "rinomina del locale",
}


def gestisci_evento(ev, pianta):
    """Applica l'evento del visualizzatore allo stato e riesegue la pagina."""
    tipo = ev.get("tipo")
    if tipo in DA_ANNULLARE:
        registra_storia(DA_ANNULLARE[tipo])
    if tipo == "zona_chiusa":
        punti = [[float(x), float(y)] for x, y in ev.get("punti", [])]
        if len(punti) >= 3:
            nomi = [c["nome"] for c in st.session_state.categorie]
            categoria = st.session_state.get("cat_attiva_nome") or (
                nomi[0] if nomi else "Superficie interna")
            pianta["zone"].append({"id": nuovo_id(pianta),
                                   "categoria": categoria,
                                   "nome": None, "punti": punti})
    elif tipo == "zona_modificata":
        for zona in pianta["zone"]:
            if zona["id"] == ev.get("id"):
                zona["punti"] = [[float(x), float(y)]
                                 for x, y in ev.get("punti", [])]
    elif tipo == "zona_eliminata":
        pianta["zone"] = [z for z in pianta["zone"] if z["id"] != ev.get("id")]
        if st.session_state.sel_zona == ev.get("id"):
            st.session_state.sel_zona = None
    elif tipo == "selezione":
        st.session_state.sel_zona = ev.get("zona")
        st.session_state.sel_parete = ev.get("parete")
    elif tipo == "etichetta_spostata":
        elenco = pianta["zone"] if ev.get("elemento") == "zona" \
            else pianta["pareti"]
        for elemento in elenco:
            if elemento["id"] == ev.get("id"):
                elemento["etichetta_pos"] = [float(ev["pos"][0]),
                                             float(ev["pos"][1])]
    elif tipo == "parete":
        pianta["pareti"].append({"id": nuovo_id(pianta),
                                 "p1": list(ev["p1"]), "p2": list(ev["p2"]),
                                 "tipo": st.session_state.get(
                                     "tipo_parete_codice", "demolire")})
    elif tipo == "parete_eliminata":
        pianta["pareti"] = [p for p in pianta["pareti"]
                            if p["id"] != ev.get("id")]
        if st.session_state.sel_parete == ev.get("id"):
            st.session_state.sel_parete = None
    elif tipo == "scala":
        st.session_state.scala_temp = {"p1": list(ev["p1"]),
                                       "p2": list(ev["p2"])}
    elif tipo == "rinomina":
        # doppio clic sull'etichetta: cambia SOLO il nome del locale, la
        # categoria (e quindi colore e percentuale commerciale) resta
        for zona in pianta["zone"]:
            if zona["id"] == ev.get("id"):
                zona["nome"] = (ev.get("nome") or "").strip() or None
    st.rerun()


def pianta_a_json(pianta):
    """Versione serializzabile della pianta (immagine inclusa, base64 JPEG)."""
    return {"nome": pianta["nome"], "mpp": pianta["mpp"],
            "zone": pianta["zone"], "pareti": pianta["pareti"],
            "immagine": pianta["src"].split(",", 1)[1]}


def pianta_da_json(dati):
    img = Image.open(io.BytesIO(base64.b64decode(dati["immagine"])))
    pianta = nuova_pianta(img.convert("RGB"), dati.get("nome") or "Planimetria")
    pianta["mpp"] = dati.get("mpp")
    pianta["zone"] = dati.get("zone") or []
    pianta["pareti"] = dati.get("pareti") or []
    ids = ([z.get("id", 0) for z in pianta["zone"]]
           + [p.get("id", 0) for p in pianta["pareti"]])
    pianta["prossimo_id"] = (max(ids) + 1) if ids else 1
    return pianta


def progetto_json_bytes():
    """L'intero progetto (computo + planimetrie) come JSON scaricabile."""
    payload = {
        "progetto": {
            "nome": st.session_state.prg_nome,
            "committente": st.session_state.prg_committente,
            "oggetto": st.session_state.prg_oggetto,
            "data": st.session_state.prg_data.isoformat(),
            "aliquota_iva": st.session_state.iva,
            "imprevisti": st.session_state.imprevisti,
        },
        "voci": voci_da_df(st.session_state.df_voci),
        "listino_stato": {
            v["codice"]: {
                "q": float(st.session_state.get(f"lq_{v['codice']}") or 0.0),
                "p": float(st.session_state.get(f"lp_{v['codice']}")
                           or v["prezzo"]),
            }
            for v in listino.VOCI
            if (st.session_state.get(f"lq_{v['codice']}") or 0.0) > 0
            or float(st.session_state.get(f"lp_{v['codice']}")
                     or v["prezzo"]) != v["prezzo"]
        },
        "misure_listino": {
            v["codice"]: st.session_state.misure_correnti[v["codice"]]
            for v in listino.VOCI
            if st.session_state.get(f"usamis_{v['codice']}")
            and st.session_state.misure_correnti.get(v["codice"])
        },
        "business_plan": {
            **{chiave: st.session_state.get(chiave, valore)
               for chiave, valore in IMPOSTAZIONI_BP.items()},
            "bp_usa_consuntivo": bool(
                st.session_state.get("bp_usa_consuntivo", False)),
        },
        "spese": spese_da_df(st.session_state.get(
            "df_spese_live", st.session_state.df_spese)),
        "spese_prev": spese_da_df(st.session_state.get(
            "df_spese_prev_live", st.session_state.df_spese_prev)),
        "mca_comparabili": mca_da_df(st.session_state.df_mca),
        "categorie": st.session_state.categorie,
        "etichette": {"font": st.session_state.et_font,
                      "nome": st.session_state.et_nome,
                      "m2": st.session_state.et_m2,
                      "percento": st.session_state.et_pct,
                      "perimetro": st.session_state.et_perim},
        "altezza_locali": st.session_state.alt_locali,
        "finiture": {"porta_larg": st.session_state.porta_larg,
                     "porta_alt": st.session_state.porta_alt,
                     "porta_n": st.session_state.porta_n,
                     "porta_n_est": st.session_state.porta_n_est,
                     "riv_alt": st.session_state.riv_alt},
        "piante": [pianta_a_json(p) for p in st.session_state.piante],
    }
    return json.dumps(payload, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


# ------------------------------------------------------ rete di sicurezza
# Streamlit tiene il lavoro nella memoria della sessione: un F5, un tab
# chiuso per sbaglio o il server che si riavvia azzeravano ore di computo e
# planimetrie calibrate, senza preavviso. Il progetto finisce quindi anche in
# un file di appoggio, riscritto al massimo ogni AUTOSALVA_SECONDI, che alla
# partenza viene offerto come ripristino. Un solo slot: l'app ha un utente
# solo, e due slot sarebbero solo una scelta in più da fare nel momento
# peggiore.
AUTOSALVA_FILE = Path(tempfile.gettempdir()) / "cme_ripristino.json"
AUTOSALVA_SECONDI = 15


def impronta(dati):
    """Firma breve del progetto, per capire se è cambiato dall'ultimo salvataggio."""
    return hashlib.md5(dati or b"").hexdigest()


def autosalva(dati):
    """Aggiorna il file di ripristino, non più spesso del necessario.

    La scrittura passa da un file temporaneo e poi rinomina: un'interruzione
    a metà lascia intatto il ripristino precedente invece di troncarlo.
    """
    # Una sessione ancora vuota non ha niente da proteggere, e sovrascrivere
    # il file la cancellerebbe proprio sotto il naso di chi ha appena perso il
    # lavoro e non ha ancora risposto alla proposta di ripristino.
    if progetto_e_vuoto():
        return
    adesso = time.time()
    if adesso - st.session_state.get("_autosalva_ora", 0.0) < AUTOSALVA_SECONDI:
        return
    firma = impronta(dati)
    if firma == st.session_state.get("_autosalva_firma"):
        return
    try:
        provvisorio = AUTOSALVA_FILE.with_suffix(".tmp")
        provvisorio.write_bytes(dati)
        provvisorio.replace(AUTOSALVA_FILE)
    except OSError:
        return          # disco pieno o cartella in sola lettura: si prosegue
    st.session_state._autosalva_ora = adesso
    st.session_state._autosalva_firma = firma


def progetto_e_vuoto():
    """True se in sessione non c'è ancora nulla da perdere.

    Serve a proporre il ripristino solo all'apertura di una sessione pulita:
    chiederlo mentre si lavora sarebbe un invito a sovrascriversi da soli.
    """
    if st.session_state.piante:
        return False
    if len(voci_da_df(st.session_state.df_voci)):
        return False
    if any((st.session_state.get(f"lq_{v['codice']}") or 0.0) > 0
           for v in listino.VOCI):
        return False
    if st.session_state.get("bp_acquisto") or st.session_state.get("bp_vendita"):
        return False
    if len(spese_da_df(st.session_state.df_spese)):
        return False
    return True


def segna_salvato():
    """Registra che il progetto attuale è stato messo al sicuro."""
    st.session_state.ultimo_salvataggio = datetime.now()
    st.session_state.firma_salvata = impronta(
        st.session_state.get("_json_progetto"))


def stato_salvataggio(dati):
    """Riga di stato: quando si è salvato e se ci sono modifiche successive."""
    ultimo = st.session_state.get("ultimo_salvataggio")
    modificato = impronta(dati) != st.session_state.get("firma_salvata")
    if ultimo is None:
        return (":orange[**Mai salvato in questa sessione.**] Il file .json "
                "è l'unico salvataggio completo: senza, un aggiornamento "
                "della pagina perde tutto.")
    quando = ultimo.strftime("%H:%M")
    if modificato:
        return (f":orange[**Modifiche non salvate.**] Ultimo salvataggio "
                f"alle {quando}.")
    return f":green[**Salvato**] alle {quando}: sei in pari."


# ------------------------------------------------- stato iniziale e caricamento

st.session_state.setdefault("df_voci", df_vuoto())
st.session_state.setdefault("versione_editor", 0)
st.session_state.setdefault("prg_nome", "")
st.session_state.setdefault("prg_committente", "")
st.session_state.setdefault("prg_oggetto", "")
st.session_state.setdefault("prg_data", date.today())
st.session_state.setdefault("iva", 10.0)   # 10%: aliquota tipica in edilizia
st.session_state.setdefault("imprevisti", 5.0)
for _voce in listino.VOCI:
    st.session_state.setdefault(f"lq_{_voce['codice']}", 0.0)
    st.session_state.setdefault(f"lp_{_voce['codice']}", float(_voce["prezzo"]))
    st.session_state.setdefault(f"usamis_{_voce['codice']}", False)
# libretto delle misure: tabella di partenza per voce e ultimo risultato letto
st.session_state.setdefault("versione_misure", 0)
st.session_state.setdefault("misure_base", {})       # {codice: DataFrame}
st.session_state.setdefault("misure_correnti", {})   # {codice: [righe]}
# business plan
st.session_state.setdefault("df_spese", df_spese_vuoto())
st.session_state.setdefault("df_spese_prev",
                            df_spese_vuoto(COLONNE_SPESE_PREV))
st.session_state.setdefault("df_mca", df_mca_vuoto())
st.session_state.setdefault("versione_bp", 0)
# tenuto fuori da IMPOSTAZIONI_BP: lì i valori sono numerici e il
# caricamento li converte in int/float, che per una checkbox non va bene
st.session_state.setdefault("bp_usa_consuntivo", False)
st.session_state.setdefault("fatt_count", 0)  # svuota l'uploader fatture
for _chiave, _valore in IMPOSTAZIONI_BP.items():
    st.session_state.setdefault(_chiave, _valore)
# campi € derivati dalle percentuali (modificabili in due direzioni)
if "bp_imposta_eur" not in st.session_state:
    st.session_state.bp_imposta_eur = 0.0
    st.session_state.bp_ag_in_eur = 0.0
    st.session_state.bp_ag_out_eur = 0.0
    bp_ricalcola_euro()
# planimetria
st.session_state.setdefault("piante", [])
st.session_state.setdefault("pianta_idx", 0)
st.session_state.setdefault("uid_piante", 0)
st.session_state.setdefault("categorie", [dict(c) for c in CATEGORIE_DEFAULT])
st.session_state.setdefault("ultimo_seq", None)
st.session_state.setdefault("scala_temp", None)
st.session_state.setdefault("sel_zona", None)
st.session_state.setdefault("sel_parete", None)
st.session_state.setdefault("upl_count", 0)
st.session_state.setdefault("ultimo_rilevamento", None)
st.session_state.setdefault("storia", [])   # annulla (aree, muri, scala)
st.session_state.setdefault("et_font", 14)
st.session_state.setdefault("et_nome", True)
st.session_state.setdefault("et_m2", True)
st.session_state.setdefault("et_pct", True)
st.session_state.setdefault("et_perim", True)
st.session_state.setdefault("alt_locali", 2.70)
# detrazioni delle finiture: vani porta e fasce rivestite
st.session_state.setdefault("porta_larg", 0.80)
st.session_state.setdefault("porta_alt", 2.10)
st.session_state.setdefault("porta_n", 0)
st.session_state.setdefault("porta_n_est", 0)
st.session_state.setdefault("riv_alt", 1.20)

# Un caricamento (o azzeramento) va applicato PRIMA di creare i widget.
if "da_caricare" in st.session_state:
    dati = st.session_state.pop("da_caricare")
    progetto = dati.get("progetto", {})
    st.session_state.prg_nome = progetto.get("nome", "")
    st.session_state.prg_committente = progetto.get("committente", "")
    st.session_state.prg_oggetto = progetto.get("oggetto", "")
    st.session_state.iva = float(progetto.get("aliquota_iva", 10.0))
    st.session_state.imprevisti = float(progetto.get("imprevisti", 5.0))
    stato_listino = dati.get("listino_stato") or {}
    misure_salvate = dati.get("misure_listino") or {}
    st.session_state.misure_base = {}
    st.session_state.misure_correnti = {}
    for _voce in listino.VOCI:
        _cod = _voce["codice"]
        elemento = stato_listino.get(_cod) or {}
        st.session_state[f"lq_{_cod}"] = float(elemento.get("q", 0.0))
        st.session_state[f"lp_{_cod}"] = float(
            elemento.get("p", _voce["prezzo"]))
        righe_mis = misure_salvate.get(_cod) or []
        st.session_state[f"usamis_{_cod}"] = bool(righe_mis)
        if righe_mis:
            st.session_state.misure_correnti[_cod] = righe_mis
            st.session_state.misure_base[_cod] = df_misure(righe_mis)
    # la key dei data_editor include versione_misure: cambiandola si azzera
    # lo stato interno dei vecchi editor e si riparte dalle tabelle caricate
    st.session_state.versione_misure += 1
    try:
        st.session_state.prg_data = date.fromisoformat(progetto.get("data", ""))
    except (TypeError, ValueError):
        st.session_state.prg_data = date.today()
    df = pd.DataFrame(dati.get("voci", [])).reindex(columns=COLONNE)
    for col in COLONNE_NUMERI:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    st.session_state.df_voci = df if len(df) else df_vuoto()
    st.session_state.versione_editor += 1
    # planimetrie e impostazioni. Le categorie NON si riprendono dal file:
    # si riparte sempre da quelle correnti (pesi aggiornati) tenendo in coda
    # quelle usate dalle zone del progetto e non più in elenco.
    st.session_state.categorie = categorie_per_progetto(
        dati.get("piante") or [])
    etichette = dati.get("etichette") or {}
    st.session_state.et_font = int(etichette.get("font", 14))
    st.session_state.et_nome = bool(etichette.get("nome", True))
    st.session_state.et_m2 = bool(etichette.get("m2", True))
    st.session_state.et_pct = bool(etichette.get("percento", True))
    st.session_state.et_perim = bool(etichette.get("perimetro", True))
    st.session_state.alt_locali = float(dati.get("altezza_locali", 2.70))
    finiture = dati.get("finiture") or {}
    st.session_state.porta_larg = float(finiture.get("porta_larg", 0.80))
    st.session_state.porta_alt = float(finiture.get("porta_alt", 2.10))
    st.session_state.porta_n = int(finiture.get("porta_n", 0))
    st.session_state.porta_n_est = int(finiture.get("porta_n_est", 0))
    st.session_state.riv_alt = float(finiture.get("riv_alt", 1.20))
    for _k in ("porta_larg_w", "porta_alt_w", "porta_n_w", "porta_n_est_w",
               "riv_alt_w"):
        st.session_state.pop(_k, None)
    try:
        st.session_state.piante = [pianta_da_json(p)
                                   for p in dati.get("piante") or []]
    except Exception:  # noqa: BLE001 — file rovinato: meglio senza piante
        st.session_state.piante = []
    st.session_state.pianta_idx = 0
    st.session_state.sel_zona = None
    st.session_state.sel_parete = None
    st.session_state.scala_temp = None
    st.session_state.ultimo_seq = None
    st.session_state.ultimo_rilevamento = None
    # le istantanee dell'annulla riguardano il progetto precedente
    st.session_state.storia = []
    st.session_state.pop("cat_attiva", None)
    st.session_state.pop("tipo_parete", None)
    st.session_state.pop("scala_metri", None)
    # i comandi delle etichette devono ripartire dai valori del progetto
    # appena aperto, non da quelli rimasti nei widget della sessione
    for _k in ("et_font_w", "et_nome_w", "et_m2_w", "et_perim_w", "et_pct_w"):
        st.session_state.pop(_k, None)
    # business plan
    bp_salvato = dati.get("business_plan") or {}
    for _chiave, _valore in IMPOSTAZIONI_BP.items():
        nuovo = bp_salvato.get(_chiave, _valore)
        st.session_state[_chiave] = (int(nuovo) if isinstance(_valore, int)
                                     else float(nuovo))
    st.session_state.bp_usa_consuntivo = bool(
        bp_salvato.get("bp_usa_consuntivo", False))
    spese_caricate = dati.get("spese") or []
    spese_prev_caricate = dati.get("spese_prev")
    if spese_prev_caricate is None:
        # vecchio formato: un unico registro con campo "stato" → si separa
        # in sostenute e da sostenere in base allo stato salvato
        spese_prev_caricate = [s for s in spese_caricate
                               if s.get("stato") == "Da sostenere"]
        spese_caricate = [s for s in spese_caricate
                          if s.get("stato", "Sostenuta") != "Da sostenere"]
    df_sp = df_spese_da_righe(spese_caricate, COLONNE_SPESE)
    st.session_state.df_spese = df_sp if len(df_sp) else df_spese_vuoto()
    df_prev = df_spese_da_righe(spese_prev_caricate, COLONNE_SPESE_PREV)
    st.session_state.df_spese_prev = (
        df_prev if len(df_prev) else df_spese_vuoto(COLONNE_SPESE_PREV))
    # i "live" verranno rigenerati dal ritorno degli editor (con versione_bp
    # incrementato, gli editor ripartono dai dati appena caricati)
    st.session_state.pop("df_spese_live", None)
    st.session_state.pop("df_spese_prev_live", None)
    df_mc = pd.DataFrame(dati.get("mca_comparabili") or []).reindex(
        columns=COLONNE_MCA)
    for col in ("prezzo", "mq", "coeff"):
        df_mc[col] = pd.to_numeric(df_mc[col], errors="coerce")
    st.session_state.df_mca = df_mc if len(df_mc) else df_mca_vuoto()
    st.session_state.versione_bp += 1
    bp_ricalcola_euro()

# Il bottone «usa come prezzo di vendita» (MCA) scrive qui: va applicato
# PRIMA che il widget bp_vendita venga creato.
if "bp_vendita_pending" in st.session_state:
    st.session_state.bp_vendita = st.session_state.pop("bp_vendita_pending")
    bp_ricalcola_euro()

# Le quantità che la planimetria porta nel listino passano di qui. Quando si
# preme il bottone, la scheda Computo è già stata disegnata e i widget lq_…
# esistono: Streamlit vieta di riscriverli a quel punto. Come sopra, si
# applicano al giro successivo, prima che i widget nascano.
if "listino_pending" in st.session_state:
    for _cod, _quantita in st.session_state.pop("listino_pending").items():
        st.session_state[f"lq_{_cod}"] = _quantita

# I comandi delle etichette stanno SOTTO il disegno, ma il disegno legge i
# loro valori PRIMA: senza questo riallineamento userebbe quelli del giro
# precedente (portando il cursore da 10 a 11 le etichette rimpicciolivano,
# perché mostravano ancora il 10 di prima). Qui le chiavi «di verità» si
# aggiornano al valore corrente dei widget, che Streamlit ha già applicato a
# inizio giro; se un widget non esiste — perché lo script era ripartito a
# metà — resta l'ultimo valore buono.
for _et in ("et_font", "et_nome", "et_m2", "et_pct", "et_perim",
            "porta_larg", "porta_alt", "porta_n", "porta_n_est", "riv_alt"):
    if _et + "_w" in st.session_state:
        st.session_state[_et] = st.session_state[_et + "_w"]

# Le categorie si ricostruiscono a ogni giro dalle zone effettivamente
# disegnate: così i pesi aggiornati valgono subito e una zona marcata con una
# categoria di ieri (es. «Giardino di appartamento») porta con sé la sua
# regola completa — scaglione compreso — invece di finire al 100%.
st.session_state.categorie = categorie_per_progetto(st.session_state.piante)


# ------------------------------------------------------------------ pagina

st.title("🏗️ Computo Metrico Estimativo")
if st.session_state.prg_nome:
    st.caption(st.session_state.prg_nome)

tab_computo, tab_plan, tab_bp = st.tabs(
    ["📝 Computo metrico", "📐 Misura da planimetria", "📊 Business plan"])


# ============================================================ SCHEDA COMPUTO

with tab_computo:
    # Offerta di ripristino: solo a sessione pulita e solo finché non si è
    # risposto, così non si trasforma in un banner che chiede sempre la stessa
    # cosa mentre si lavora.
    if (not st.session_state.get("_ripristino_valutato")
            and progetto_e_vuoto() and AUTOSALVA_FILE.exists()):
        try:
            salvato_il = datetime.fromtimestamp(AUTOSALVA_FILE.stat().st_mtime)
        except OSError:
            salvato_il = None
        if salvato_il is not None:
            st.warning(
                "C'è del lavoro della sessione precedente, salvato "
                f"automaticamente il **{salvato_il.strftime('%d/%m')}** alle "
                f"**{salvato_il.strftime('%H:%M')}**. Lo riprendo?")
            r_si, r_no, _ = st.columns([1, 1, 3])
            if r_si.button("↩️ Riprendi il lavoro", type="primary",
                           use_container_width=True):
                try:
                    st.session_state.da_caricare = json.loads(
                        AUTOSALVA_FILE.read_bytes())
                    st.session_state._ripristino_valutato = True
                    st.rerun()
                except (OSError, json.JSONDecodeError, UnicodeDecodeError):
                    st.session_state._ripristino_valutato = True
                    st.error("Il ripristino automatico non è leggibile: "
                             "riparto da un progetto vuoto.")
            if r_no.button("Ricomincia da capo", use_container_width=True):
                st.session_state._ripristino_valutato = True
                st.rerun()

    # Dati del progetto e archivio (una volta erano nella barra laterale;
    # tolta per dare tutta la larghezza alla planimetria).
    with st.expander("📋 Dati del progetto · Apri / Nuovo"):
        d1, d2 = st.columns(2)
        d1.text_input("Nome del computo", key="prg_nome",
                      placeholder="Es. Ristrutturazione app.to Via Roma 1")
        d2.text_input("Committente", key="prg_committente")
        d3, d4, d5, d6 = st.columns([2, 1, 1, 1])
        d3.text_input("Oggetto dei lavori", key="prg_oggetto")
        d4.date_input("Data", key="prg_data", format="DD/MM/YYYY")
        d5.number_input("Aliquota IVA (%)", min_value=0.0, max_value=100.0,
                        step=1.0, key="iva",
                        help="10% ristrutturazioni (predefinita), "
                             "22% ordinaria, 4% prima casa")
        d6.number_input("Imprevisti (%)", min_value=0.0, max_value=50.0,
                        step=1.0, key="imprevisti",
                        help="Accantonamento sul totale lavori per le "
                             "sorprese di cantiere (tipicamente 5%), "
                             "applicato prima dell'IVA.")

        st.divider()
        if not progetto_e_vuoto():
            st.caption("⚠️ Aprire un progetto **sostituisce** il lavoro in "
                       "corso: se ti serve ancora, salvalo prima.")
        file_json = st.file_uploader(
            "📂 Apri un progetto salvato (.json)", type=["json"])
        if file_json is not None and st.button("Carica nel programma"):
            try:
                st.session_state.da_caricare = json.load(file_json)
                st.rerun()
            except (json.JSONDecodeError, UnicodeDecodeError):
                st.error("Il file non sembra un progetto salvato da "
                         "questa app.")

        # -------------------------------------------- archivio online
        st.divider()
        st.markdown("**☁️ Progetti online**")
        if not archivio.configurato():
            st.info("L'archivio online non è collegato: per ora usa il "
                    "salvataggio in file qui sopra. Per attivarlo servono "
                    "un progetto su supabase.com, un bucket **privato** per "
                    "i file e le sue credenziali nei «secrets» di Streamlit "
                    "sotto la voce `[supabase]` (url, key, bucket) — le "
                    "istruzioni per esteso sono in `archivio.py`.")
        else:
            try:
                progetti_online = archivio.elenco_progetti()
            except Exception as errore:
                progetti_online = []
                st.error(f"Non riesco a leggere l'archivio online: {errore}")

            o_sel, o_apri, o_del = st.columns([3, 1, 1],
                                              vertical_alignment="bottom")
            if progetti_online:
                scelto = o_sel.selectbox("Apri un progetto salvato online",
                                         progetti_online, key="prog_online_sel")
                if o_apri.button("📂 Apri", key="apri_online",
                                 use_container_width=True):
                    try:
                        st.session_state.da_caricare = \
                            archivio.carica_progetto(scelto)
                        st.rerun()
                    except Exception as errore:
                        st.error(f"Errore nell'apertura: {errore}")
                conferma_del = o_del.checkbox("elimina", key="conf_del_online",
                                              help="Spunta e premi Elimina per "
                                                   "rimuovere definitivamente "
                                                   "il progetto selezionato")
                if conferma_del and o_del.button("🗑️", key="del_online",
                                                 use_container_width=True):
                    try:
                        archivio.elimina_progetto(scelto)
                        st.session_state.conf_del_online = False
                        st.rerun()
                    except Exception as errore:
                        st.error(f"Errore nell'eliminazione: {errore}")
            else:
                o_sel.caption("Nessun progetto online ancora salvato.")

            s_nome, s_btn = st.columns([3, 1], vertical_alignment="bottom")
            nome_online = s_nome.text_input(
                "Nome con cui salvare online",
                value=st.session_state.prg_nome or "",
                key="nome_salva_online",
                placeholder="Es. Ristrutturazione Via Roma 1")
            nome_pulito = (nome_online or "").strip()
            # salvare su un nome già in archivio sostituiva la versione online
            # senza dire niente (l'upload è in upsert): ora lo si conferma
            esiste_gia = nome_pulito in progetti_online
            if esiste_gia:
                conferma_sovra = st.checkbox(
                    f"Sovrascrivi «{nome_pulito}», già presente in archivio",
                    key="conf_sovrascrivi_online",
                    help="Senza la spunta il salvataggio non parte: la "
                         "versione online resta quella di prima.")
            else:
                conferma_sovra = True
            if s_btn.button("☁️ Salva online", key="salva_online",
                            use_container_width=True):
                if not nome_pulito:
                    st.warning("Dai un nome al progetto prima di salvarlo.")
                elif not conferma_sovra:
                    st.warning(f"«{nome_pulito}» esiste già online: spunta la "
                               "conferma qui sopra, oppure cambia nome.")
                else:
                    try:
                        archivio.salva_progetto(nome_pulito,
                                                progetto_json_bytes())
                        segna_salvato()
                        st.success(f"Progetto «{nome_pulito}» salvato online.")
                    except Exception as errore:
                        st.error(f"Errore nel salvataggio: {errore}")

        # ------------------------------------------------- zona pericolosa
        # Stava accanto al riquadro «apri un progetto», a un solo click e
        # senza conferma: cancellava computo, planimetrie calibrate, business
        # plan e spese, cioè molto più di quanto cancelli l'eliminazione di un
        # singolo file in archivio — che invece la conferma ce l'aveva.
        st.divider()
        st.markdown("**🗑️ Nuovo progetto**")
        n_conf, n_btn = st.columns([3, 1], vertical_alignment="bottom")
        conferma_nuovo = n_conf.checkbox(
            "Ho capito: svuota computo, planimetrie, business plan e spese",
            key="conf_nuovo_progetto")
        if n_btn.button("🗑️ Svuota tutto", key="nuovo_progetto",
                        use_container_width=True,
                        disabled=not conferma_nuovo):
            st.session_state.da_caricare = {}
            st.session_state.conf_nuovo_progetto = False
            st.rerun()

    # ------------------------------------------------------ listino guida
    # -------------------------------------- categorie (sx) e riepilogo (dx)
    st.markdown(css_schede_computo(), unsafe_allow_html=True)
    col_sx, col_dx = st.columns([3.3, 0.7], gap="medium")

    with col_sx:
        for indice, cat in enumerate(listino.CATEGORIE, start=1):
            colore_md = COLORI_CATEGORIE[cat][1]
            # niente totale nel titolo: lo disegna il CSS (vedi
            # css_schede_computo), così la tendina non si richiude
            with st.container(key=f"card_{indice}"):
                with st.expander(f":{colore_md}[**{indice} · {cat}**]"):
                    h_voce, h_qta, h_prezzo, h_parz = st.columns(
                        [3.4, 1, 1, 1])
                    h_voce.caption("Voce · unità")
                    h_qta.caption("Quantità")
                    h_prezzo.caption("Prezzo €")
                    h_parz.caption("Parziale")
                    for voce in listino.voci_della_categoria(cat):
                        st.divider()
                        riga_voce_listino(voce)

        # tabella libera: personalizzate e voci arrivate dalla planimetria
        contenitore_extra = st.container(key="card_extra")
        with contenitore_extra, st.expander(
                f"**➕ {ALTRE_VOCI}** (personalizzate e dalla planimetria)"):
            st.caption("Tabella libera: qui arrivano anche superfici, "
                       "battiscopa e tinteggiature dalla scheda planimetria. "
                       "Doppio clic per scrivere; la riga vuota in fondo "
                       "aggiunge una voce; Canc elimina la riga selezionata. "
                       "Compila le dimensioni oppure la quantità manuale.")
            df_editato = st.data_editor(
                st.session_state.df_voci,
                num_rows="dynamic",
                hide_index=True,
                key=f"editor_voci_{st.session_state.versione_editor}",
                column_config={
                    "categoria": st.column_config.TextColumn(
                        "Categoria",
                        help="Es. Demolizioni, Murature, Impianti…"),
                    "codice": st.column_config.TextColumn(
                        "Codice",
                        help="Codice voce, facoltativo (es. 01.A01.001)"),
                    "descrizione": st.column_config.TextColumn(
                        "Descrizione", width="large"),
                    "um": st.column_config.SelectboxColumn(
                        "U.M.", options=UM_OPZIONI, help="Unità di misura"),
                    "parti": st.column_config.NumberColumn(
                        "Parti", help="Numero di parti uguali. "
                                      "Negativo = detrazione (es. -1)."),
                    "lunghezza": st.column_config.NumberColumn("Lungh. (m)"),
                    "larghezza": st.column_config.NumberColumn("Largh. (m)"),
                    "altezza": st.column_config.NumberColumn(
                        "Alt. / Peso",
                        help="Altezza in m, oppure peso unitario"),
                    "quantita_manuale": st.column_config.NumberColumn(
                        "Quantità (manuale)",
                        help="Compilala solo se lasci vuote le dimensioni"),
                    "prezzo": st.column_config.NumberColumn(
                        "Prezzo unit. (€)", format="%.2f"),
                },
            )
            st.session_state.df_voci = df_editato

    # --------------------------------------------------- riepilogo costi
    with col_dx:
        st.markdown("#### 💰 Riepilogo costi")
        voci_tutte = voci_dal_listino() + voci_da_df(st.session_state.df_voci)
        voci_calcolate = calcoli.calcola_computo(voci_tutte)
        totale = calcoli.totale_generale(voci_calcolate)

        if totale == 0:
            st.caption("Inserisci le quantità nelle categorie per vedere "
                       "la distribuzione dei costi.")
        righe_dot = [(f"{i}. {cat}", COLORI_CATEGORIE[cat][0],
                      totale_categoria_listino(cat))
                     for i, cat in enumerate(listino.CATEGORIE, start=1)]
        tot_extra_dot = calcoli.totale_generale(
            calcoli.calcola_computo(voci_da_df(st.session_state.df_voci)))
        righe_dot.append((ALTRE_VOCI, "#C9A96A", tot_extra_dot))
        html_dot = "".join(
            f'<div style="display:flex;justify-content:space-between;'
            f'align-items:center;margin:4px 0;font-size:0.9rem;">'
            f'<span><span style="display:inline-block;width:10px;'
            f'height:10px;border-radius:50%;background:{colore};'
            f'margin-right:8px;"></span>{nome}</span>'
            f'<b>{euro(importo)}</b></div>'
            for nome, colore, importo in righe_dot)
        st.markdown(html_dot, unsafe_allow_html=True)
        st.divider()

        imp_importo, totale_imprevisti = calcoli.totale_con_imprevisti(
            totale, st.session_state.imprevisti)
        iva_importo, totale_ivato = calcoli.totale_con_iva(
            totale_imprevisti, st.session_state.iva)

        st.metric("Somma parziali", euro(totale))
        st.metric(
            f"Imprevisti {numero_it(st.session_state.imprevisti, 0)}%",
            euro(imp_importo))
        st.metric("Totale lavori (IVA esclusa)", euro(totale_imprevisti))
        st.metric(f"IVA {numero_it(st.session_state.iva, 0)}%",
                  euro(iva_importo))
        # La card d'oro incoronava il totale PRIMA dell'IVA, mentre l'export
        # Excel chiama «Totale finale (IVA inclusa)» quello DOPO: lo stesso
        # nome su due cifre diverse, sullo strumento in cui il numero giusto
        # è tutto. Il finale è uno solo, ed è quello che si paga.
        st.markdown(
            '<div style="background:linear-gradient(135deg,#243459,#1A2744);'
            'border:1px solid #C9A96A;border-radius:12px;'
            'padding:12px 14px;margin:6px 0 10px;">'
            '<div style="font-size:0.72rem;color:#C9A96A;'
            'letter-spacing:.05em;">💎 TOTALE FINALE (IVA INCLUSA)</div>'
            '<div style="font-size:1.45rem;font-weight:700;color:#ECE7DA;">'
            f'{euro(totale_ivato)}</div></div>',
            unsafe_allow_html=True)

        totali = calcoli.totali_per_categoria(voci_calcolate)
        if len(totali) >= 2:
            st.plotly_chart(grafico_totali(totali),
                            config={"displayModeBar": False})

    # ------------------------------------------------- tabella ed export
    if voci_calcolate:
        df_calcolato = pd.DataFrame(voci_calcolate).reindex(
            columns=COLONNE + ["quantita", "importo"])
        with st.expander("📄 Computo calcolato (tabella completa)"):
            df_vista = pd.DataFrame({
                "Categoria": df_calcolato["categoria"].fillna(""),
                "Codice": df_calcolato["codice"].fillna(""),
                "Descrizione": df_calcolato["descrizione"].fillna(""),
                "U.M.": df_calcolato["um"].fillna(""),
                "Quantità": df_calcolato["quantita"].map(numero_it),
                "Prezzo unit.": df_calcolato["prezzo"].map(euro),
                "Importo": df_calcolato["importo"].map(euro),
            })
            st.dataframe(df_vista, hide_index=True)
    else:
        df_calcolato = pd.DataFrame(
            columns=COLONNE + ["quantita", "importo"])

    st.subheader("💾 Salva ed esporta")
    st.caption("Il file **.json** è il salvataggio del lavoro (comprese le "
               "planimetrie): conservalo e ricaricalo dal pannello "
               "**📋 Dati del progetto · Apri / Nuovo** in cima alla "
               "pagina. Excel e CSV servono per consegnare o rielaborare "
               "il computo.")

    progetto = {
        "nome": st.session_state.prg_nome,
        "committente": st.session_state.prg_committente,
        "oggetto": st.session_state.prg_oggetto,
        "data": st.session_state.prg_data.isoformat(),
        "aliquota_iva": st.session_state.iva,
        "imprevisti": st.session_state.imprevisti,
    }
    incidenze = calcoli.incidenze_percentuali(totali, totale)
    df_riepilogo = pd.DataFrame({
        "Categoria": list(totali),
        "Importo": [totali[c] for c in totali],
        "Incidenza %": [incidenze[c] for c in totali],
    }).sort_values("Importo", ascending=False, ignore_index=True)
    df_riepilogo_excel = pd.concat([
        df_riepilogo,
        pd.DataFrame({
            "Categoria": [
                "Somma lavori",
                f"Imprevisti {numero_it(st.session_state.imprevisti, 0)}%",
                "Totale con imprevisti",
                f"IVA {numero_it(st.session_state.iva, 0)}%",
                "Totale finale (IVA inclusa)"],
            "Importo": [totale, imp_importo, totale_imprevisti,
                        iva_importo, totale_ivato],
            "Incidenza %": [100.0, None, None, None, None],
        }),
    ], ignore_index=True)
    df_progetto_excel = pd.DataFrame({
        "Campo": ["Nome", "Committente", "Oggetto", "Data",
                  "Aliquota IVA %", "Imprevisti %"],
        "Valore": [progetto["nome"], progetto["committente"],
                   progetto["oggetto"], progetto["data"],
                   progetto["aliquota_iva"], progetto["imprevisti"]],
    })

    righe_sup, tot_sup, tot_comm, _ = planimetria.riepilogo_superfici(
        st.session_state.piante, mappa_percentuali(),
        escludi=CATEGORIE_SOLO_COMPUTO)
    df_superfici_excel = None
    if righe_sup:
        df_superfici_excel = pd.DataFrame([{
            "Pianta": r["pianta"], "Categoria": r["categoria"],
            "N. zone": r["zone"], "m² reali": r["m2"],
            "%": r["percento"], "m² commerciali": r["m2_commerciale"],
        } for r in righe_sup])
        df_superfici_excel = pd.concat([
            df_superfici_excel,
            pd.DataFrame([{"Pianta": "TOTALE", "Categoria": "",
                           "N. zone": None, "m² reali": tot_sup,
                           "%": None, "m² commerciali": tot_comm}]),
        ], ignore_index=True)

    # generato una sola volta per run e riusato anche nella scheda
    # planimetria (evita di serializzare due volte l'intero progetto,
    # immagini incluse, a ogni interazione)
    st.session_state._json_progetto = progetto_json_bytes()
    autosalva(st.session_state._json_progetto)
    # Tre bottoni grigi identici non dicevano che solo il primo mette al
    # sicuro il lavoro: quello resta in evidenza, con accanto il suo stato.
    st.markdown(stato_salvataggio(st.session_state._json_progetto))
    col_json, col_xlsx, col_csv = st.columns(3)
    col_json.download_button(
        "💾 Salva progetto (.json)",
        data=st.session_state._json_progetto,
        file_name=nome_file("json"),
        mime="application/json",
        type="primary",
        on_click=segna_salvato,
    )
    col_xlsx.download_button(
        "📊 Esporta Excel (.xlsx)",
        data=excel_bytes(df_calcolato, df_riepilogo_excel,
                         df_progetto_excel, df_superfici_excel),
        file_name=nome_file("xlsx"),
        mime="application/vnd.openxmlformats-officedocument."
             "spreadsheetml.sheet",
    )
    col_csv.download_button(
        "📄 Esporta CSV",
        data=df_calcolato.to_csv(index=False, sep=";", decimal=",")
                         .encode("utf-8-sig"),
        file_name=nome_file("csv"),
        mime="text/csv",
    )


# ========================================================= SCHEDA PLANIMETRIA

with tab_plan:
    piante = st.session_state.piante

    if not piante:
        st.info("Carica la prima planimetria per iniziare (puoi aggiungerne "
                "altre in seguito, per esempio un piano per pagina).")
        file_plan = st.file_uploader(
            "Carica una planimetria (PNG, JPG o PDF)",
            type=["png", "jpg", "jpeg", "pdf"],
            key=f"upl_{st.session_state.upl_count}")
        if file_plan is not None:
            try:
                aggiungi_planimetrie(file_plan)
                st.rerun()
            except Exception as errore:  # noqa: BLE001
                st.error(f"Non riesco a leggere questo file: {errore}")
    else:
        col_pagine, col_area = st.columns([1, 4], gap="medium")

        # ------------------------------------------------ elenco planimetrie
        with col_pagine:
            st.markdown("**Planimetrie**")
            for i, p in enumerate(piante):
                attiva = (i == st.session_state.pianta_idx)
                c_nome, c_x = st.columns([5, 1])
                if c_nome.button(("✅ " if attiva else "📄 ") + p["nome"],
                                 key=f"pg_{p['uid']}", width="stretch"):
                    st.session_state.pianta_idx = i
                    st.session_state.sel_zona = None
                    st.session_state.scala_temp = None
                    st.rerun()
                if c_x.button("✖", key=f"pgx_{p['uid']}",
                              help="Rimuovi questa planimetria"):
                    piante.pop(i)
                    st.session_state.pianta_idx = max(
                        0, min(st.session_state.pianta_idx, len(piante) - 1))
                    st.session_state.sel_zona = None
                    st.session_state.scala_temp = None
                    st.rerun()
                st.image(p["thumb"], width="stretch")
            st.divider()
            file_plan = st.file_uploader(
                "➕ Aggiungi planimetria",
                type=["png", "jpg", "jpeg", "pdf"],
                key=f"upl_{st.session_state.upl_count}")
            if file_plan is not None:
                try:
                    aggiungi_planimetrie(file_plan)
                    st.rerun()
                except Exception as errore:  # noqa: BLE001
                    st.error(f"Non riesco a leggere questo file: {errore}")

        # ------------------------------------------------- area di disegno
        with col_area:
            pianta = piante[st.session_state.pianta_idx]
            perc_map = mappa_percentuali()
            col_map = mappa_colori()
            nomi_cat = [c["nome"] for c in st.session_state.categorie]

            # etichette del menù categorie: "Nome — 30%"
            etichette_cat = [f"{c['nome']} — {numero_it(c['percento'], 0)}%"
                             for c in st.session_state.categorie]

            r_nome, r_cat, r_par = st.columns([2, 2, 2])
            nuovo_nome = r_nome.text_input(
                "Nome planimetria", value=pianta["nome"],
                key=f"ren_{pianta['uid']}")
            pianta["nome"] = (nuovo_nome or "").strip() or pianta["nome"]
            cat_attiva = r_cat.selectbox(
                "Categoria per le nuove aree (colore e %)",
                etichette_cat or ["Superficie interna — 100%"],
                key="cat_attiva")
            idx_attiva = (etichette_cat.index(cat_attiva)
                          if cat_attiva in etichette_cat else 0)
            cat_attiva_nome = nomi_cat[idx_attiva] if nomi_cat \
                else "Superficie interna"
            st.session_state.cat_attiva_nome = cat_attiva_nome
            colore_attivo = col_map.get(cat_attiva_nome, PALETTE_ZONE[0])

            nomi_tipi = [TIPI_PARETE[c]["nome"] for c in TIPI_PARETE_SCELTA]
            codici_tipi = list(TIPI_PARETE_SCELTA)
            tipo_scelto = r_par.selectbox(
                "Tipo per le nuove pareti 🧱", nomi_tipi, key="tipo_parete",
                help="Da demolire = rosso · Da costruire = giallo")
            st.session_state.tipo_parete_codice = codici_tipi[
                nomi_tipi.index(tipo_scelto)]

            # ---- annulla l'ultima operazione sul disegno ----
            storia = st.session_state.get("storia") or []
            c_und, c_info = st.columns([1, 3], vertical_alignment="center")
            if c_und.button(
                    f"↩️ Annulla ({len(storia)})", disabled=not storia,
                    use_container_width=True,
                    help="Torna indietro di un passo su aree, muri e scala. "
                         "Non tocca il computo né le altre schede."):
                fatto = annulla_ultima()
                if fatto:
                    st.toast(f"Annullato: {fatto} ↩️")
                st.rerun()
            if storia:
                c_info.caption(f"Ultima operazione: **{storia[-1]['descrizione']}**"
                               f" · si può tornare indietro di "
                               f"{len(storia)} pass{'o' if len(storia) == 1 else 'i'}")
            else:
                c_info.caption(":gray[Niente da annullare: non hai ancora "
                               "modificato il disegno in questa sessione.]")

            if pianta["mpp"]:
                st.caption("✅ Scala impostata — le misure sono in metri "
                           "reali. ✏️ disegna le aree, 📏 misura al volo, "
                           "↔️ per ricalibrare.")
            else:
                st.warning("⚠️ Scala non impostata per questa planimetria: "
                           "scegli **Scala** nella barra sul disegno, poi "
                           "**clicca l'inizio e la fine** di una misura nota "
                           "(es. un lato quotato). Zooma con la rotellina "
                           "per essere preciso: lo zoom non altera le misure.")

            impostazioni = {"nome": st.session_state.et_nome,
                            "m2": st.session_state.et_m2,
                            "percento": st.session_state.et_pct,
                            "perimetro": st.session_state.et_perim}
            # etichette fuori dalle aree (se l'utente non le ha spostate)
            pos_default = planimetria.posiziona_etichette(
                pianta["zone"], pianta["img"].width, pianta["img"].height,
                trasparenti=CATEGORIE_INVOLUCRO)
            zone_props = [{
                "id": z["id"], "punti": z["punti"],
                "colore": col_map.get(z["categoria"], "#9E9E9E"),
                # perimetro commerciale: solo contorno, e sotto le altre aree
                "senza_sfondo": z["categoria"] in CATEGORIE_INVOLUCRO,
                "etichetta": etichetta_zona(z, pianta["mpp"], perc_map,
                                            impostazioni),
                "etichetta_pos": (z.get("etichetta_pos")
                                  or pos_default.get(z["id"])),
                # serve alla rinomina con doppio clic sull'etichetta: si
                # modifica il nome, non la riga calcolata (m², %)
                "nome": z.get("nome") or "",
            } for z in pianta["zone"]]
            pareti_props = [{
                "id": p["id"], "p1": p["p1"], "p2": p["p2"],
                "tipo": p.get("tipo", "esistente"),
                "colore": TIPI_PARETE.get(p.get("tipo", "esistente"),
                                          TIPI_PARETE["esistente"])["colore"],
                "etichetta": etichetta_parete(p, pianta["mpp"]),
                "etichetta_pos": p.get("etichetta_pos"),
            } for p in pianta["pareti"]]

            valore = image_viewer(
                pianta["src"],
                zone=zone_props,
                pareti=pareti_props,
                scala_temp=st.session_state.scala_temp,
                colore_attivo=colore_attivo,
                mpp=pianta["mpp"] or 0.0,
                font_px=st.session_state.et_font,
                tipo_parete=st.session_state.get("tipo_parete_codice",
                                                 "demolire"),
                key=f"viewer_{pianta['uid']}",
            )
            ev = evento_viewer(valore)
            if ev:
                gestisci_evento(ev, pianta)

            # ------------------------------------ scala in attesa di misura
            if st.session_state.scala_temp:
                temp = st.session_state.scala_temp
                dist_px = planimetria.distanza_pixel(
                    tuple(temp["p1"]), tuple(temp["p2"]))
                s_in, s_ok, s_no = st.columns([2, 1, 1])
                metri = s_in.number_input(
                    "Quanto misura in metri, nella realtà, il segmento "
                    "nero tracciato?",
                    min_value=0.0, step=0.01, format="%.2f", key="scala_metri")
                s_ok.write("")
                s_no.write("")
                if s_ok.button("📏 Imposta scala", type="primary"):
                    if metri > 0:
                        registra_storia("impostazione della scala")
                        pianta["mpp"] = planimetria.metri_per_pixel(
                            dist_px, metri)
                        st.session_state.scala_temp = None
                        st.rerun()
                    else:
                        st.error("Scrivi la misura reale in metri (> 0).")
                if s_no.button("Annulla"):
                    st.session_state.scala_temp = None
                    st.rerun()

            # --------------------------------------------- zona selezionata
            zona_sel = next((z for z in pianta["zone"]
                             if z["id"] == st.session_state.sel_zona), None)
            if zona_sel is not None:
                st.markdown("**Zona selezionata**")
                a_nome, a_cat, a_add, a_del = st.columns([2, 2, 1, 1])
                nome_z = a_nome.text_input(
                    "Nome (facoltativo)", value=zona_sel.get("nome") or "",
                    key=f"zn_{pianta['uid']}_{zona_sel['id']}")
                zona_sel["nome"] = nome_z.strip() or None
                idx_cat = (nomi_cat.index(zona_sel["categoria"])
                           if zona_sel["categoria"] in nomi_cat else 0)
                cat_nuova = a_cat.selectbox(
                    "Categoria", etichette_cat or ["Superficie interna — 100%"],
                    index=idx_cat,
                    key=f"zc_{pianta['uid']}_{zona_sel['id']}")
                nome_cat_nuova = (nomi_cat[etichette_cat.index(cat_nuova)]
                                  if cat_nuova in etichette_cat else None)
                if nome_cat_nuova and nome_cat_nuova != zona_sel["categoria"]:
                    registra_storia("cambio di categoria")
                    zona_sel["categoria"] = nome_cat_nuova
                    st.rerun()
                a_add.write("")
                a_del.write("")
                if pianta["mpp"]:
                    area_sel = planimetria.area_reale_m2(
                        zona_sel["punti"], pianta["mpp"])
                    perim_sel = planimetria.perimetro_reale_m(
                        zona_sel["punti"], pianta["mpp"])
                    st.caption(f"Superficie **{numero_it(area_sel, 2)} m²** · "
                               f"Perimetro **{numero_it(perim_sel, 2)} m**")
                    if a_add.button(
                            "➕ Al computo",
                            disabled=zona_sel["categoria"] in
                            CATEGORIE_INVOLUCRO,
                            help="Aggiunge questa superficie come voce del "
                                 "computo. Il perimetro commerciale ne resta "
                                 "fuori: serve solo a misurare la superficie "
                                 "vendibile."):
                        aggiungi_voce_computo(
                            "Superfici",
                            f"{zona_sel.get('nome') or zona_sel['categoria']}"
                            f" — {pianta['nome']}",
                            "m²", round(area_sel, 2), None)
                        st.toast("Aggiunta al computo ✔")
                if a_del.button("🗑 Elimina"):
                    registra_storia("eliminazione dell'area")
                    pianta["zone"] = [z for z in pianta["zone"]
                                      if z["id"] != zona_sel["id"]]
                    st.session_state.sel_zona = None
                    st.rerun()

            # -------------------------------------------- parete selezionata
            parete_sel = next((p for p in pianta["pareti"]
                               if p["id"] == st.session_state.sel_parete),
                              None)
            if parete_sel is not None:
                st.markdown("**Parete selezionata**")
                b_tipo, b_len, b_del = st.columns([2, 1, 1])
                codice_cur = parete_sel.get("tipo", "demolire")
                # includi il tipo corrente anche se non è tra i selezionabili
                # (es. "esistente" di un vecchio progetto): niente modifiche
                # silenziose, si cambia solo se l'utente sceglie un'altra voce.
                opz_codici = (codici_tipi if codice_cur in codici_tipi
                              else [codice_cur] + codici_tipi)
                opz_nomi = [TIPI_PARETE.get(c, TIPI_PARETE["demolire"])["nome"]
                            for c in opz_codici]
                tipo_nuovo = b_tipo.selectbox(
                    "Tipo di intervento", opz_nomi,
                    index=opz_codici.index(codice_cur),
                    key=f"pt_{pianta['uid']}_{parete_sel['id']}")
                codice_nuovo = opz_codici[opz_nomi.index(tipo_nuovo)]
                if codice_nuovo != codice_cur:
                    registra_storia("cambio di tipo del muro")
                    parete_sel["tipo"] = codice_nuovo
                    st.rerun()
                b_len.metric("Lunghezza",
                             etichetta_parete(parete_sel, pianta["mpp"]))
                b_del.write("")
                if b_del.button("🗑 Elimina",
                                key=f"pdel_{parete_sel['id']}"):
                    registra_storia("eliminazione del muro")
                    pianta["pareti"] = [p for p in pianta["pareti"]
                                        if p["id"] != parete_sel["id"]]
                    st.session_state.sel_parete = None
                    st.rerun()

            # ------------------------------------- pulizia dalle scritte
            with st.expander("🧹 Pulisci la planimetria (togli le scritte)"):
                st.caption(
                    "Cancella nomi dei locali, quote e simboli ridipingendoli "
                    "con il fondo del foglio: i muri restano intatti. Serve "
                    "al **rilevamento delle stanze**, che così non può "
                    "scambiare una lettera per un muro, e libera il disegno "
                    "dalle scritte che finiscono sotto le etichette delle "
                    "aree. Le dimensioni non cambiano: **scala, zone e "
                    "pareti già impostate restano valide**.")
                forza = st.slider(
                    "Quanto insistere", 0.5, 2.5, 1.0, 0.25,
                    key=f"pul_forza_{pianta['uid']}",
                    help="Sotto 1 toglie solo il minuto (quote, simboli). "
                         "Sopra 1 prende anche le parole grandi: esagerando "
                         "iniziano a sparire i muri più corti, e lì il "
                         "rilevamento peggiora invece di migliorare.")
                p_prova, p_rip = st.columns(2)
                if p_prova.button("🧹 Prova la pulizia", type="primary",
                                  key=f"pul_prova_{pianta['uid']}",
                                  use_container_width=True):
                    with st.spinner("Ripulisco il disegno…"):
                        ripulita, rimossi = rilevamento.pulisci_planimetria(
                            pianta["img"], pianta["mpp"], forza)
                    st.session_state.anteprima_pulizia = {
                        "uid": pianta["uid"], "img": ripulita,
                        "rimossi": rimossi, "forza": forza}
                    st.rerun()
                if pianta.get("img_originale") is not None:
                    if p_rip.button("↩️ Ripristina l'originale",
                                    key=f"pul_rip_{pianta['uid']}",
                                    use_container_width=True):
                        sostituisci_immagine_pianta(
                            pianta, pianta.pop("img_originale"))
                        st.session_state.pop("anteprima_pulizia", None)
                        st.rerun()

                anteprima = st.session_state.get("anteprima_pulizia")
                if anteprima and anteprima["uid"] == pianta["uid"]:
                    if not anteprima["rimossi"]:
                        st.info("Non ho trovato scritte da togliere. Se ne "
                                "restano, alza il cursore e riprova.")
                    else:
                        a_pri, a_dop = st.columns(2)
                        a_pri.caption("Adesso")
                        a_pri.image(pianta["img"], use_container_width=True)
                        a_dop.caption(
                            f"Dopo la pulizia (forza {numero_it(anteprima['forza'], 2)})")
                        a_dop.image(anteprima["img"],
                                    use_container_width=True)
                        st.caption(
                            "Controlla che i **muri** siano tutti al loro "
                            "posto: se ne mancano, abbassa il cursore.")
                        u_si, u_no = st.columns(2)
                        if u_si.button("✅ Usa la versione pulita",
                                       type="primary",
                                       key=f"pul_ok_{pianta['uid']}",
                                       use_container_width=True):
                            # l'originale si conserva solo la prima volta,
                            # così pulizie successive non lo perdono
                            if pianta.get("img_originale") is None:
                                pianta["img_originale"] = pianta["img"]
                            sostituisci_immagine_pianta(pianta,
                                                        anteprima["img"])
                            st.session_state.pop("anteprima_pulizia", None)
                            st.toast("Planimetria pulita ✔")
                            st.rerun()
                        if u_no.button("Scarta l'anteprima",
                                       key=f"pul_no_{pianta['uid']}",
                                       use_container_width=True):
                            st.session_state.pop("anteprima_pulizia", None)
                            st.rerun()

            # ---------------------------------- rilevamento automatico (beta)
            with st.expander("🪄 Rileva stanze automaticamente (beta)"):
                st.caption(
                    "Il programma prova a riconoscere le **stanze chiuse dai "
                    "muri** (ignorando scritte e quote) e le propone come "
                    f"**{CATEGORIA_STANZE}**: sono **proposte da "
                    "rifinire** con ➤ Modifica (sposta i vertici, cambia "
                    "categoria, elimina con Canc). Le proposte **non si "
                    "sovrappongono** tra loro né alle zone già disegnate: "
                    "puoi rilanciare il rilevamento per completare. Funziona "
                    "meglio su disegni nitidi e con la **scala già "
                    "impostata**.")
                c_ril, c_ann = st.columns(2)
                if c_ril.button("🪄 Rileva le stanze su questa planimetria",
                                type="primary"):
                    with st.spinner("Analizzo la planimetria…"):
                        proposte = rilevamento.rileva_stanze(
                            pianta["img"], pianta["mpp"],
                            # il perimetro commerciale copre tutto il disegno:
                            # se lo si contasse come «già occupato» non si
                            # troverebbe più nessuna stanza
                            zone_esistenti=[
                                z["punti"] for z in pianta["zone"]
                                if z["categoria"] not in CATEGORIE_INVOLUCRO])
                    if not proposte:
                        st.warning("Non ho riconosciuto stanze chiuse su "
                                   "questo disegno. Prova a impostare prima "
                                   "la scala, o disegna le aree a mano.")
                    else:
                        registra_storia("rilevamento automatico delle stanze")
                        nuovi_id = []
                        for punti in proposte:
                            zid = nuovo_id(pianta)
                            pianta["zone"].append({
                                "id": zid,
                                # le stanze riconosciute sono locali: sempre
                                # superficie interna, mai la categoria scelta
                                # per il disegno a mano (che di norma è il
                                # perimetro commerciale, primo dell'elenco)
                                "categoria": CATEGORIA_STANZE,
                                "nome": None,
                                "punti": punti,
                            })
                            nuovi_id.append(zid)
                        st.session_state.ultimo_rilevamento = {
                            "uid": pianta["uid"], "ids": nuovi_id}
                        st.toast(f"Trovate {len(proposte)} stanze ✔")
                        st.rerun()
                ril = st.session_state.ultimo_rilevamento
                if ril and ril["uid"] == pianta["uid"]:
                    if c_ann.button("↩️ Annulla ultimo rilevamento "
                                    f"({len(ril['ids'])} aree)"):
                        pianta["zone"] = [z for z in pianta["zone"]
                                          if z["id"] not in ril["ids"]]
                        st.session_state.ultimo_rilevamento = None
                        st.session_state.sel_zona = None
                        st.rerun()

        # ----------------------------------------- legenda colori/percentuali
        legenda = " ".join(
            f'<span style="display:inline-block;margin:2px 12px 2px 0;">'
            f'<span style="display:inline-block;width:12px;height:12px;'
            f'border-radius:3px;background:{col_map.get(c["nome"], "#9E9E9E")};'
            f'margin-right:5px;vertical-align:-1px;"></span>'
            f'{c["nome"]} · {numero_it(c["percento"], 0)}%'
            + (f' <span style="color:#A9B4C9;">(oltre '
               f'{numero_it(c["soglia"], 0)} m²: '
               f'{numero_it(c["oltre"], 0)}%)</span>'
               if c.get("soglia") and c.get("oltre") is not None else "")
            + '</span>'
            for c in st.session_state.categorie)
        st.caption("Categorie di superficie (colore · peso commerciale). "
                   "Per i **giardini** l'incidenza piena vale fino a 25 m²: "
                   "l'eccedenza pesa la percentuale ridotta indicata.")
        st.markdown(legenda, unsafe_allow_html=True)

        with st.expander("🔤 Etichette sulle zone (layout)"):
            # Questi comandi stanno DOPO il disegno, e ogni gesto sul disegno
            # fa ripartire lo script a metà (st.rerun in gestisci_evento):
            # Streamlit butta via lo stato dei widget che in quel giro non ha
            # disegnato, e la dimensione del carattere tornava al minimo
            # appena si trascinava un'etichetta. Il valore buono vive quindi
            # nelle chiavi et_* — le stesse salvate nel progetto — e i widget
            # (key separata, _w) le ricaricano ogni volta con value=.
            st.session_state.et_font = st.slider(
                "Dimensione carattere", 10, 24,
                value=int(st.session_state.et_font), key="et_font_w")
            e1, e2, e3, e4 = st.columns(4)
            st.session_state.et_nome = e1.checkbox(
                "Nome / categoria", value=bool(st.session_state.et_nome),
                key="et_nome_w")
            st.session_state.et_m2 = e2.checkbox(
                "Superficie (m²)", value=bool(st.session_state.et_m2),
                key="et_m2_w")
            st.session_state.et_perim = e3.checkbox(
                "Perimetro (m)", value=bool(st.session_state.et_perim),
                key="et_perim_w")
            st.session_state.et_pct = e4.checkbox(
                "Percentuale", value=bool(st.session_state.et_pct),
                key="et_pct_w")
            st.caption("Di norma le etichette stanno **fuori dalle aree**, "
                       "collegate da una linea di richiamo. Se ne hai "
                       "trascinata qualcuna, questo tasto le rimette tutte "
                       "al loro posto.")
            spostate = sum(1 for p in piante
                           for elenco in (p["zone"], p["pareti"])
                           for e in elenco if e.get("etichetta_pos"))
            if st.button(f"↩️ Riporta le etichette fuori dal disegno "
                         f"({spostate} spostate)", disabled=not spostate):
                for p in piante:
                    for elenco in (p["zone"], p["pareti"]):
                        for elemento in elenco:
                            elemento.pop("etichetta_pos", None)
                st.rerun()

        # ------------------------------------------- superfici commerciali
        st.subheader("🧮 Superfici commerciali (tutte le planimetrie)")
        righe_sup, tot_sup, tot_comm, senza_scala = (
            planimetria.riepilogo_superfici(piante, mappa_percentuali(),
                                            escludi=CATEGORIE_SOLO_COMPUTO))
        st.caption("Le **superfici interne** non compaiono qui: servono al "
                   "computo metrico (pavimenti, battiscopa, tinteggiature). "
                   "La parte vendibile si misura col perimetro **Superficie "
                   "commerciale**, che le racchiude già — contarle entrambe "
                   "vorrebbe dire contare due volte lo stesso spazio.")
        if senza_scala:
            st.warning("Escluse dal totale perché **senza scala**: "
                       + ", ".join(senza_scala))
        # se ci sono stanze ma nessun perimetro, il totale sarebbe a zero
        # senza che si capisca il perché
        ha_interne = any(z["categoria"] in CATEGORIE_SOLO_COMPUTO
                         for p in piante for z in p["zone"])
        ha_perimetro = any(z["categoria"] in CATEGORIE_INVOLUCRO
                           for p in piante for z in p["zone"])
        if ha_interne and not ha_perimetro:
            st.warning("Hai disegnato le superfici interne ma **nessun "
                       "perimetro commerciale**: per la superficie vendibile "
                       "traccia un'area della categoria **Superficie "
                       "commerciale** attorno all'immobile.")
        if not righe_sup:
            st.info("Disegna le aree con ✏️ sulla planimetria: qui compare il "
                    "riepilogo per categoria con le percentuali applicate.")
        else:
            df_sup_vista = pd.DataFrame([{
                "Pianta": r["pianta"],
                "Categoria": r["categoria"],
                "Zone": r["zone"],
                "m² reali": numero_it(r["m2"], 2),
                "%": numero_it(r["percento"], 0) + " %",
                "m² commerciali": numero_it(r["m2_commerciale"], 2),
            } for r in righe_sup])
            st.dataframe(df_sup_vista, hide_index=True)
            m1, m2 = st.columns(2)
            m1.metric("Superficie reale totale",
                      f"{numero_it(tot_sup, 2)} m²")
            m2.metric("Superficie commerciale totale",
                      f"{numero_it(tot_comm, 2)} m²")
            if st.button("➕ Riporta la superficie commerciale nel computo",
                         type="primary"):
                aggiungi_voce_computo(
                    "Superfici",
                    "Superficie commerciale — "
                    + (st.session_state.prg_nome or "fabbricato"),
                    "m²", round(tot_comm, 2), None)
                st.toast("Superficie commerciale aggiunta al computo ✔")

        # ------------------------- dalle superfici alle voci del computo
        st.subheader("📏 Dalle superfici al computo (locale per locale)")
        righe_loc, senza_scala_loc = planimetria.riepilogo_locali(
            piante, escludi=CATEGORIE_INVOLUCRO)
        grandezze = {}
        # L'altezza serve sia ai locali (pareti da tinteggiare) sia ai muri
        # da demolire/costruire: vive in alt_locali (salvata nel progetto) e
        # la casella la ricarica ogni volta che rinasce — Streamlit scarta lo
        # stato dei widget che in un giro non ha disegnato, e ripartendo dal
        # minimo le pareti diventavano «perimetro × 1»: un numero plausibile
        # e sbagliato, che finiva dritto nel computo.
        st.session_state.setdefault("alt_locali", 2.70)
        if righe_loc or any(p.get("pareti") for p in piante):
            altezza = st.number_input(
                "Altezza dei locali e dei muri (m)", min_value=1.0,
                max_value=6.0, step=0.05, format="%.2f",
                value=float(st.session_state.alt_locali),
                key="alt_locali_widget",
                help="Usata per pareti da tinteggiare e per la superficie "
                     "dei muri da demolire o costruire (lunghezza × altezza).")
            st.session_state.alt_locali = altezza
        else:
            altezza = float(st.session_state.alt_locali)
        if senza_scala_loc:
            st.warning("Locali esclusi perché la planimetria è **senza "
                       "scala**: " + ", ".join(senza_scala_loc))
        if not righe_loc:
            st.info("Quando ci sono zone disegnate (su piante con scala), "
                    "qui trovi i perimetri per battiscopa e tinteggiature.")
        else:
            st.caption("Spunta, locale per locale, che cosa si rifà. "
                       "**Rivestito** (bagni, fascia della cucina): niente "
                       "battiscopa, e la fascia piastrellata non si rasa né "
                       "si tinteggia. Pavimento = superficie calpestabile; "
                       "pareti = perimetro × altezza; soffitti = superficie "
                       "calpestabile.")
            zona_per_rif = {(p["uid"], z["id"]): z
                            for p in piante for z in p["zone"]}
            righe_tab = []
            riferimenti = []
            for r in righe_loc:
                zona = zona_per_rif.get((r["uid"], r["id"]))
                if zona is None:
                    continue
                interna = percento_di(perc_map, r["categoria"]) >= 100.0
                bagno = any(parola in (r["nome"] + " " + r["categoria"]).lower()
                            for parola in ("bagno", "wc", "w.c"))
                batt_def = zona.get("battiscopa")
                if batt_def is None:
                    batt_def = interna and not bagno
                pitt_def = zona.get("pittura")
                if pitt_def is None:
                    pitt_def = interna
                pav_def = zona.get("pavimento")
                if pav_def is None:
                    pav_def = interna
                riv_def = zona.get("rivestito")
                if riv_def is None:
                    riv_def = bagno      # i bagni sono rivestiti quasi sempre
                righe_tab.append({
                    "Pianta": r["pianta"],
                    "Locale": r["nome"],
                    "Superficie (m²)": round(r["m2"], 2),
                    "Perimetro (m)": round(r["perimetro"], 2),
                    "Pavimento": bool(pav_def),
                    "Battiscopa": bool(batt_def),
                    "Tinteggiatura": bool(pitt_def),
                    "Rivestito": bool(riv_def),
                })
                riferimenti.append((r["uid"], r["id"]))

            chiave_tab = "edloc_" + str(abs(hash(tuple(riferimenti))) % 10 ** 8)
            # Al data_editor va passata SEMPRE la stessa tabella di partenza:
            # ricostruirla a ogni giro (dai valori appena scritti nelle zone)
            # gli faceva perdere il primo clic sulle spunte — bisognava
            # cliccare due volte. La rigeneriamo solo quando cambiano i locali.
            if st.session_state.get("loc_base_chiave") != chiave_tab:
                st.session_state.loc_base_chiave = chiave_tab
                st.session_state.loc_base_df = pd.DataFrame(righe_tab)
            df_loc = st.data_editor(
                st.session_state.loc_base_df,
                hide_index=True, key=chiave_tab,
                disabled=["Pianta", "Locale", "Superficie (m²)",
                          "Perimetro (m)"],
                column_config={
                    "Pavimento": st.column_config.CheckboxColumn(
                        "Pavimento",
                        help="Conta nella superficie da pavimentare"),
                    "Battiscopa": st.column_config.CheckboxColumn(
                        "Battiscopa", help="Conta nel totale del battiscopa"),
                    "Tinteggiatura": st.column_config.CheckboxColumn(
                        "Tinteggiatura",
                        help="Conta in pareti e soffitti da tinteggiare"),
                    "Rivestito": st.column_config.CheckboxColumn(
                        "Rivestito",
                        help="Locale piastrellato (bagno, fascia cucina): "
                             "niente battiscopa e la fascia rivestita non "
                             "si rasa né si tinteggia"),
                })

            locali_calcolo = []
            for (uid, zid), (_, riga) in zip(riferimenti, df_loc.iterrows()):
                zona = zona_per_rif.get((uid, zid))
                if zona is None:
                    continue
                zona["pavimento"] = bool(riga["Pavimento"])
                zona["battiscopa"] = bool(riga["Battiscopa"])
                zona["pittura"] = bool(riga["Tinteggiatura"])
                zona["rivestito"] = bool(riga.get("Rivestito", False))
                locali_calcolo.append({
                    "m2": float(riga["Superficie (m²)"]),
                    "perimetro": float(riga["Perimetro (m)"]),
                    "pavimento": zona["pavimento"],
                    "battiscopa": zona["battiscopa"],
                    "pittura": zona["pittura"],
                    "rivestito": zona["rivestito"],
                })

            # ---- vani porta e rivestimenti: quello che va detratto ----
            st.markdown("**🚪 Porte e rivestimenti (detrazioni)**")
            st.caption("Il vano di una porta non ha battiscopa e non si "
                       "tinteggia; nei locali rivestiti la fascia "
                       "piastrellata non si rasa né si tinteggia. Una porta "
                       "**interna** affaccia su due locali, quindi vale "
                       "**due lati**; il portoncino d'ingresso uno solo. Le "
                       "quantità qui sotto sono già al netto.")
            d1, d2, d3, d4, d5 = st.columns(5)
            larg_porta = d1.number_input(
                "Larghezza porte (m)", min_value=0.0, max_value=3.0,
                step=0.05, format="%.2f",
                value=float(st.session_state.porta_larg), key="porta_larg_w")
            st.session_state.porta_larg = larg_porta
            alt_porta = d2.number_input(
                "Altezza porte (m)", min_value=0.0, max_value=4.0,
                step=0.05, format="%.2f",
                value=float(st.session_state.porta_alt), key="porta_alt_w")
            st.session_state.porta_alt = alt_porta
            n_porte = d3.number_input(
                "Porte interne", min_value=0, max_value=200, step=1,
                value=int(st.session_state.porta_n), key="porta_n_w",
                help="Porte fra due locali: il vano vale due lati, perché "
                     "interrompe il battiscopa (e toglie parete da "
                     "tinteggiare) di qua e di là.")
            st.session_state.porta_n = n_porte
            n_porte_est = d4.number_input(
                "Porte esterne", min_value=0, max_value=50, step=1,
                value=int(st.session_state.porta_n_est), key="porta_n_est_w",
                help="Portoncino d'ingresso e porte verso l'esterno o verso "
                     "locali non computati: vale un lato solo.")
            st.session_state.porta_n_est = n_porte_est
            h_riv = d5.number_input(
                "Altezza rivestimenti (m)", min_value=0.0, max_value=4.0,
                step=0.05, format="%.2f",
                value=float(st.session_state.riv_alt), key="riv_alt_w",
                help="Fascia piastrellata nei locali spuntati «Rivestito» "
                     "(di norma 1,20 m; zona doccia anche 2,40).")
            st.session_state.riv_alt = h_riv

            q = planimetria.quantita_finiture(
                locali_calcolo, altezza, larghezza_porta=larg_porta,
                altezza_porta=alt_porta, n_porte=n_porte,
                altezza_rivestimento=h_riv, n_porte_esterne=n_porte_est)
            pav_m2 = q["pavimento"]
            batt_m = q["battiscopa"]
            pareti_m2 = q["pareti"]
            soffitti_m2 = q["soffitti"]

            t1, t2, t3, t4 = st.columns(4)
            t1.metric("Pavimento", f"{numero_it(pav_m2, 2)} m²")
            t2.metric("Battiscopa", f"{numero_it(batt_m, 2)} m",
                      delta=(f"−{numero_it(q['detr_porte_ml'], 2)} m porte"
                             if q["detr_porte_ml"] else None),
                      delta_color="off")
            t3.metric(f"Pareti (h {numero_it(altezza, 2)} m)",
                      f"{numero_it(pareti_m2, 2)} m²",
                      delta=(f"−{numero_it(q['detr_porte_m2'] + q['detr_rivestimenti'], 2)} m² "
                             "porte e rivestimenti"
                             if (q["detr_porte_m2"] or q["detr_rivestimenti"])
                             else None),
                      delta_color="off")
            t4.metric("Soffitti", f"{numero_it(soffitti_m2, 2)} m²")
            if q["detr_porte_ml"] or q["detr_rivestimenti"]:
                st.caption(
                    f":gray[Battiscopa lordo {numero_it(q['battiscopa_lordo'], 2)} m "
                    f"(i locali rivestiti sono già esclusi) − "
                    f"{numero_it(q['detr_porte_ml'], 2)} m di vani porta "
                    f"({q['lati_porta']} lati). "
                    f"Pareti lorde {numero_it(q['pareti_lorde'], 2)} m² − "
                    f"{numero_it(q['detr_rivestimenti'], 2)} m² di fasce "
                    f"rivestite − {numero_it(q['detr_porte_m2'], 2)} m² di "
                    f"vani porta.]")

            grandezze.update({
                "pavimento": pav_m2,
                # il listino chiede la superficie netta più ~5% di sfrido
                "pavimento_sfrido": pav_m2 * 1.05,
                "battiscopa": batt_m,
                "tinteggiatura": pareti_m2 + soffitti_m2,
            })

        # ------------------------------- dai muri tracciati alle demolizioni
        st.subheader("🧱 Dai muri al computo (demolire / costruire)")
        riep_muri, senza_scala_muri = planimetria.riepilogo_pareti(
            piante, altezza)
        if senza_scala_muri:
            st.warning("Muri esclusi perché la planimetria è **senza "
                       "scala**: " + ", ".join(senza_scala_muri))
        if not riep_muri:
            st.info("Traccia i muri con lo strumento **PARETE** sul disegno "
                    "(scegli sopra se sono da demolire o da costruire): qui "
                    "trovi metri lineari e superfici pronti per il computo.")
        else:
            vuoto = {"n": 0, "ml": 0.0, "m2": 0.0}
            dem = riep_muri.get("demolire", vuoto)
            cos = riep_muri.get("costruire", vuoto)
            esi = riep_muri.get("esistente", vuoto)
            st.caption(f"Superficie = lunghezza × altezza "
                       f"(**{numero_it(altezza, 2)} m**). Le aperture non "
                       "vengono detratte: se un muro ha una porta, affina la "
                       "quantità nel computo.")
            w1, w2, w3, w4 = st.columns(4)
            w1.metric(f"🔴 Da demolire ({dem['n']})",
                      f"{numero_it(dem['ml'], 2)} m")
            w2.metric("→ superficie", f"{numero_it(dem['m2'], 2)} m²")
            w3.metric(f"🟡 Da costruire ({cos['n']})",
                      f"{numero_it(cos['ml'], 2)} m")
            w4.metric("→ superficie", f"{numero_it(cos['m2'], 2)} m²")
            if esi["n"]:
                st.caption(f":gray[Esclusi {esi['n']} muri «esistenti» "
                           f"({numero_it(esi['ml'], 2)} m): non sono "
                           "lavorazioni.]")
            grandezze["muri_demolire"] = dem["m2"]
            grandezze["muri_costruire"] = cos["m2"]

        # ---------------- dalle misure della planimetria alle voci del listino
        if any(v > 0 for v in grandezze.values()):
            st.markdown("**➕ Porta queste quantità nel computo**")
            st.caption(
                "Le quantità vengono **scritte** nelle voci del listino, non "
                "sommate: puoi rifare il rilevamento, cambiare le spunte e "
                "ripremere il bottone senza contare niente due volte. I "
                "prezzi restano quelli del listino, modificabili come sempre.")
            proposte = {}
            for codice, grandezza, acceso in VOCI_DA_SUPERFICI:
                voce = listino.voce_per_codice(codice)
                quantita = round(grandezze.get(grandezza, 0.0), 2)
                if voce is None or quantita <= 0:
                    continue
                attuale = float(st.session_state.get(f"lq_{codice}") or 0.0)
                etichetta = (f"**{codice}** · {voce['descrizione']} → "
                             f"**{numero_it(quantita, 2)} {voce['um']}**")
                if attuale and abs(attuale - quantita) > 0.005:
                    etichetta += (f" :orange[(sostituisce "
                                  f"{numero_it(attuale, 2)})]")
                if st.checkbox(etichetta, value=acceso,
                               key=f"supvoce_{codice}"):
                    proposte[codice] = quantita
            if not proposte:
                st.caption(":gray[Nessuna voce selezionata.]")
            if st.button("➕ Scrivi le quantità nel listino", type="primary",
                         disabled=not proposte):
                st.session_state.listino_pending = dict(proposte)
                st.toast(f"{len(proposte)} voci aggiornate nel computo ✔")
                st.rerun()

        st.divider()
        st.download_button(
            "💾 Salva progetto (.json) — computo e planimetrie",
            # riusa il JSON già generato nella scheda Computo (stesso run),
            # con ripiego se per qualche motivo non fosse pronto
            data=(st.session_state.get("_json_progetto")
                  or progetto_json_bytes()),
            file_name=nome_file("json"),
            mime="application/json",
        )


# ======================================================= SCHEDA BUSINESS PLAN

with tab_bp:
    sotto_fatt, sotto_spese, sotto_mca = st.tabs(
        ["🏦 Studio di fattibilità", "🧾 Spese a consuntivo",
         "🏷️ MCA — prezzo di vendita"])

    # valori automatici condivisi: superficie commerciale dalla planimetria
    # e costo di ristrutturazione dal computo (imprevisti inclusi)
    _, _, mq_da_planimetria, _ = planimetria.riepilogo_superfici(
        st.session_state.piante, mappa_percentuali(),
        escludi=CATEGORIE_SOLO_COMPUTO)
    voci_bp = voci_dal_listino() + voci_da_df(st.session_state.df_voci)
    totale_computo_bp = calcoli.totale_generale(
        calcoli.calcola_computo(voci_bp))
    _, ristr_da_computo = calcoli.totale_con_imprevisti(
        totale_computo_bp, st.session_state.imprevisti)


    # ------------------------------------------------- spese a consuntivo
    with sotto_spese:
        st.caption("Il registro delle spese reali dell'operazione, come il "
                   "tuo foglio «Spese». In alto le spese già **sostenute** "
                   "(le fatture); sotto, affiancati, il **riepilogo per "
                   "categoria**, le spese ancora **da sostenere** e la "
                   "torta. La quota **cantiere** (lavori, materiale, "
                   "architetto) può sostituire la ristrutturazione stimata "
                   "nello studio di fattibilità.")

        # ---- caricamento fatture con auto-compilazione ----
        with st.expander("📎 Carica fatture (PDF o XML) e auto-compila"):
            st.caption("Trascina una o più fatture: leggo importo, IVA, data, "
                       "numero e fornitore. Controlla i dati, scegli la "
                       "**categoria** e aggiungile alle spese sostenute. "
                       "I file restano sul server, nessun dato esce. Funziona "
                       "meglio con i PDF «di cortesia» della fattura "
                       "elettronica e con gli XML; su PDF con layout insoliti "
                       "alcuni campi potrebbero restare da completare a mano.")
            file_fatture = st.file_uploader(
                "Fatture", type=["pdf", "xml"], accept_multiple_files=True,
                key=f"upl_fatture_{st.session_state.fatt_count}",
                label_visibility="collapsed")
            if file_fatture:
                righe_estratte, non_letti = [], []
                for f in file_fatture:
                    dati = dati_fattura_da_file(f)
                    if dati and (dati.get("importo") is not None
                                 or dati.get("nr_fattura")):
                        righe_estratte.append(
                            {col: dati.get(col) for col in COLONNE_SPESE})
                    else:
                        non_letti.append(f.name)
                if non_letti:
                    st.warning("Non sono riuscito a leggere: "
                               + ", ".join(non_letti)
                               + ". Aggiungile a mano nella tabella sotto.")
                if righe_estratte:
                    st.markdown(f"**{len(righe_estratte)} fattura/e lette.** "
                                "Correggi se serve e scegli la categoria:")
                    df_ant = df_spese_da_righe(righe_estratte, COLONNE_SPESE)
                    df_ant_ed = st.data_editor(
                        df_ant, hide_index=True, num_rows="fixed",
                        key=f"anteprima_fatt_{st.session_state.fatt_count}",
                        column_config=config_colonne_spese())
                    if st.button("➕ Aggiungi alle spese sostenute",
                                 type="primary", key="aggiungi_fatture"):
                        # parto dalle spese correnti (col ritorno live, che
                        # include gli edit manuali) e ci aggiungo le fatture
                        corrente = st.session_state.get(
                            "df_spese_live", st.session_state.df_spese)
                        st.session_state.df_spese = pd.concat(
                            [corrente, df_ant_ed], ignore_index=True)
                        st.session_state.pop("df_spese_live", None)
                        st.session_state.fatt_count += 1
                        st.session_state.versione_bp += 1
                        st.rerun()

        # Spese sostenute: tabella a PIENA LARGHEZZA della pagina, così tutte
        # le colonne si vedono senza dover scorrere dentro la tabella.
        st.markdown("##### 🧾 Spese sostenute")
        df_spese_ed = st.data_editor(
            st.session_state.df_spese,
            num_rows="dynamic", hide_index=True, use_container_width=True,
            key=f"editor_spese_{st.session_state.versione_bp}",
            column_config=config_colonne_spese())
        # il ritorno NON viene rimesso in df_spese: ripassare al data_editor un
        # DataFrame che cambia a ogni run gli faceva "perdere" la prima
        # selezione di categoria (da rifare due volte). df_spese resta l'input
        # stabile; il ritorno vive a parte per calcoli e salvataggio.
        st.session_state.df_spese_live = df_spese_ed
        righe_spese = spese_da_df(df_spese_ed)
        tot_sostenute = fattibilita.totale_spese(righe_spese)
        st.metric("Totale spese sostenute", euro(tot_sostenute))

        riepilogo = fattibilita.riepilogo_per_categoria(righe_spese)
        iva_totale = round(sum(v["iva"] for v in riepilogo.values()), 2)

        # sotto, affiancati: riepilogo · spese da sostenere · torta. Non si
        # comprimono: su schermi stretti scorre la pagina (non le tabelle).
        st.markdown("""
<style>
.st-key-spese_scroll { overflow-x: auto; padding-bottom: 6px; }
.st-key-spese_scroll [data-testid="stHorizontalBlock"] { min-width: 1150px; }
.st-key-spese_scroll [data-testid="stHorizontalBlock"]
 [data-testid="stHorizontalBlock"] { min-width: 0; }
</style>
""", unsafe_allow_html=True)

        with st.container(key="spese_scroll"):
            col_riep, col_prev, col_torta = st.columns(
                [1.3, 1.5, 1.2], gap="medium")

            with col_riep:
                st.markdown("##### 📊 Riepilogo per categoria")
                if riepilogo:
                    st.markdown(
                        tabella_riepilogo_spese_html(
                            riepilogo, tot_sostenute, iva_totale),
                        unsafe_allow_html=True)
                else:
                    st.caption("Nessuna spesa sostenuta ancora.")

            with col_prev:
                st.markdown("##### 🔮 Spese da sostenere")
                df_prev_ed = st.data_editor(
                    st.session_state.df_spese_prev,
                    num_rows="dynamic", hide_index=True,
                    use_container_width=True,
                    key=f"editor_spese_prev_{st.session_state.versione_bp}",
                    column_config={
                        "oggetto": st.column_config.TextColumn(
                            "Oggetto", width="medium"),
                        "importo": st.column_config.NumberColumn(
                            "€", format="%.2f"),
                        "aliquota_iva": st.column_config.NumberColumn(
                            "IVA %", min_value=0.0, max_value=22.0, step=1.0),
                        "categoria": st.column_config.SelectboxColumn(
                            "Categoria", options=CATEGORIE_SPESE_EMOJI),
                        "note": st.column_config.TextColumn("Note"),
                    })
                st.session_state.df_spese_prev_live = df_prev_ed
                righe_prev = spese_da_df(df_prev_ed)
                tot_prev = fattibilita.totale_spese(righe_prev)
                st.metric("Totale da sostenere", euro(tot_prev))

                costi_totali = round(tot_sostenute + tot_prev, 2)
                # Il totale comprende TUTTE le categorie (acquisto, agenzia,
                # costi indiretti…); allo studio di fattibilità va invece la
                # sola quota cantiere, che lì sostituisce la ristrutturazione
                # stimata. La card dice entrambe le cifre: prima l'etichetta
                # prometteva «→ business plan» su un numero che nessuno
                # leggeva.
                quota_cantiere = round(sum(
                    r["importo"] for r in righe_spese + righe_prev
                    if r["categoria"] in fattibilita.CATEGORIE_CANTIERE), 2)
                st.markdown(
                    '<div style="background:linear-gradient(135deg,#243459,'
                    '#1A2744);border:1px solid #C9A96A;border-radius:12px;'
                    'padding:12px 14px;margin:6px 0 10px;">'
                    '<div style="font-size:0.72rem;color:#C9A96A;'
                    'letter-spacing:.05em;">💠 COSTI TOTALI DELL\'OPERAZIONE'
                    '</div>'
                    '<div style="font-size:1.45rem;font-weight:700;'
                    f'color:#ECE7DA;">{euro(costi_totali)}</div>'
                    '<div style="font-size:0.72rem;color:#A9B4C9;">'
                    f'sostenute {euro(tot_sostenute)} + da sostenere '
                    f'{euro(tot_prev)}</div>'
                    '<div style="font-size:0.72rem;color:#A9B4C9;'
                    'margin-top:5px;padding-top:5px;'
                    'border-top:1px solid #3C4C6E;">di cui cantiere '
                    f'<b style="color:#ECE7DA;">{euro(quota_cantiere)}</b>'
                    ' — riportabile nello studio di fattibilità</div></div>',
                    unsafe_allow_html=True)

            with col_torta:
                st.markdown("##### 🥧 Spese per categoria")
                if riepilogo:
                    st.plotly_chart(grafico_torta_spese(riepilogo),
                                    config={"displayModeBar": False})
                else:
                    st.caption("La torta comparirà con le prime spese.")

        # confronto col preventivo del computo (su sostenute + da sostenere)
        righe_cantiere = righe_spese + righe_prev
        # Costo cantiere a consuntivo, sulle categorie che il computo
        # preventiva. Vive qui perché è qui che le tabelle delle spese
        # restituiscono i valori aggiornati; lo studio di fattibilità lo
        # riusa ed è scritto DOPO nel codice apposta, così legge i numeri di
        # questo giro e non quelli del precedente.
        cantiere_consuntivo = round(sum(
            r["importo"] for r in righe_cantiere
            if r["categoria"] in fattibilita.CATEGORIE_CANTIERE), 2)
        if righe_cantiere:
            st.divider()
            st.subheader("⚖️ Preventivo vs consuntivo (cantiere)")
            scostamento = cantiere_consuntivo - ristr_da_computo
            c1, c2, c3 = st.columns(3)
            c1.metric("Preventivo (computo + imprevisti)",
                      euro(ristr_da_computo))
            c2.metric("Consuntivo cantiere (lavori+materiali+architetto)",
                      euro(cantiere_consuntivo))
            c3.metric("Scostamento", euro(scostamento),
                      delta=euro(scostamento), delta_color="inverse")

    # ------------------------------------------------ studio di fattibilità
    with sotto_fatt:
        # impaginazione «da Excel»: tre blocchi affiancati (riepilogo,
        # matrici, dettaglio costi). La larghezza fissa a 1750px tagliava la
        # terza colonna a metà parola su uno schermo normale (un contenitore
        # da 1420px a finestra 1600px) e, per raggiungerla, lo scorrimento
        # orizzontale spingeva EBIT e ROE fuori vista: proprio i due numeri
        # contro cui la matrice va letta. Ora sotto i 1400px le tre colonne
        # si impilano, sopra stanno affiancate senza scorrimento.
        st.markdown("""
<style>
.st-key-bp_scroll { overflow-x: auto; padding-bottom: 6px; }
.st-key-bp_scroll [data-testid="stHorizontalBlock"] { min-width: 1120px; }
.st-key-bp_scroll [data-testid="stHorizontalBlock"]
 [data-testid="stHorizontalBlock"] { min-width: 0; }
@media (max-width: 1400px) {
    .st-key-bp_scroll [data-testid="stHorizontalBlock"] {
        min-width: 0; flex-wrap: wrap;
    }
    .st-key-bp_scroll > div > [data-testid="stHorizontalBlock"] > div {
        flex: 1 1 100% !important; min-width: 0 !important;
    }
}
/* prezzi base evidenziati come in Excel: acquisto giallino, vendita azzurro */
.st-key-bp_in_acq input {
    background-color: #FFF2CC !important;
    color: #7F6000 !important;
    font-weight: 700;
}
.st-key-bp_in_ven input {
    background-color: #DDEBF7 !important;
    color: #1F4E79 !important;
    font-weight: 700;
}
/* Avviso «valore digitato ma non applicato» (lo disegna guardia_prezzi_bp). */
.cme-nonapplicato {
    display: block;
    margin: 3px 0 0;
    padding: 2px 8px;
    border-radius: 4px;
    background: #C9A96A;
    color: #1A2744;
    font-size: 0.72rem;
    font-weight: 700;
}
</style>
""", unsafe_allow_html=True)

        mq_eff = st.session_state.bp_mq or mq_da_planimetria
        # ordine di precedenza della ristrutturazione: consuntivo reale se
        # richiesto esplicitamente, altrimenti la cifra a mano, altrimenti
        # il preventivo del computo.
        usa_consuntivo = (st.session_state.get("bp_usa_consuntivo")
                          and cantiere_consuntivo > 0)
        if usa_consuntivo:
            ristr_eff = cantiere_consuntivo
        else:
            ristr_eff = st.session_state.bp_ristr or ristr_da_computo
        parametri_bp = {
            "prezzo_acquisto": st.session_state.bp_acquisto,
            "prezzo_vendita": st.session_state.bp_vendita,
            "imposta_pct": st.session_state.bp_imposta,
            "imposte_fisse": st.session_state.bp_imposte_fisse,
            "notaio": st.session_state.bp_notaio,
            "agenzia_in_pct": st.session_state.bp_ag_in,
            "agenzia_out_pct": st.session_state.bp_ag_out,
            "iva_agenzia_pct": st.session_state.bp_iva_ag,
            "imprevisti": st.session_state.bp_imprevisti,
            "spese_mutuo": st.session_state.bp_mutuo,
            "ristrutturazione": ristr_eff,
            "mq": mq_eff,
            "durata_mesi": st.session_state.bp_durata,
        }
        esito = fattibilita.studio_fattibilita(parametri_bp)
        acq = esito["costi_acquisto"]
        ven = esito["costi_vendita"]

        with st.container(key="bp_scroll"):
            col_sum, col_matrici, col_costi = st.columns(
                [1.15, 2.15, 1.7], gap="large")

            # ------------------------------------------ riepilogo (Summary)
            with col_sum:
                st.number_input("Mq commerciali (0 = dalla planimetria)",
                                min_value=0.0, step=1.0, key="bp_mq")
                st.number_input("Passo sensitività (€)", min_value=1000.0,
                                step=1000.0, key="bp_passo")
                st.number_input("Durata operazione (mesi)", min_value=1,
                                max_value=120, step=1, key="bp_durata")
                st.markdown(
                    '<div style="background:#F0A84033;border:1px solid '
                    '#F0A840;padding:4px 10px;border-radius:6px;'
                    'text-align:center;font-weight:700;letter-spacing:.04em;'
                    'margin:8px 0 6px;">ESTIMATED</div>',
                    unsafe_allow_html=True)
                with st.container(key="bp_in_acq"):
                    st.number_input("Prezzo base (acquisto, €)",
                                    min_value=0.0, step=5000.0,
                                    format="%.0f", key="bp_acquisto",
                                    on_change=bp_ricalcola_euro)
                st.markdown(righe_bp([
                    ("€/mq acquisto",
                     numero_it(esito["eur_mq_acquisto"], 0) + " €"
                     if esito["eur_mq_acquisto"] else "—", None),
                    ("Buy cost", euro(acq["totale"]), None),
                    ("Prezzo netto — entry", euro(esito["entry"]), "bold"),
                ]), unsafe_allow_html=True)
                with st.container(key="bp_in_ven"):
                    st.number_input("Estimated sell price (€)",
                                    min_value=0.0, step=5000.0,
                                    format="%.0f", key="bp_vendita",
                                    on_change=bp_ricalcola_euro,
                                    help="Puoi stimarlo con l'MCA (terza "
                                         "sezione)")
                st.markdown(righe_bp([
                    ("€/mq vendita",
                     numero_it(esito["eur_mq_vendita"], 0) + " €"
                     if esito["eur_mq_vendita"] else "—", None),
                    ("Sell cost", euro(ven["totale"]), None),
                    ("Prezzo netto — exit", euro(esito["exit"]), "bold"),
                ]), unsafe_allow_html=True)
                st.markdown(
                    nota_base_calcolo(st.session_state.bp_acquisto,
                                      st.session_state.bp_vendita),
                    unsafe_allow_html=True)
                guardia_prezzi_bp(st.session_state.bp_acquisto,
                                  st.session_state.bp_vendita)
                # a 12 mesi il rendimento annualizzato COINCIDE con il ROE:
                # senza dirlo sembrano due conferme indipendenti.
                durata_bp = st.session_state.bp_durata
                etichetta_annuo = (
                    "Rendimento annuo (12 mesi: coincide col ROE)"
                    if durata_bp == 12
                    else f"Rendimento annuo ({durata_bp} mesi)")
                st.markdown(righe_bp([
                    ("Net Return (ROI)",
                     numero_it(esito["multiplo"], 2) + "x", "bold"),
                    ("Return on Equity (ROE)",
                     numero_it(esito["roe"] * 100, 1) + " %", None),
                    (etichetta_annuo,
                     numero_it((esito["roi_annuo"] or 0) * 100, 1) + " %",
                     None),
                    ("Total cost",
                     euro(acq["totale"] + ven["totale"]), "cattivo"),
                    ("EBIT", euro(esito["ebit"]),
                     "buono" if esito["ebit"] >= 0 else "cattivo"),
                ]), unsafe_allow_html=True)

            # --------------------------------------- matrici di sensitività
            with col_matrici:
                if (st.session_state.bp_acquisto > 0
                        and st.session_state.bp_vendita > 0):
                    passo = st.session_state.bp_passo
                    st.markdown("**Money multiple** "
                                ":gray[(net sell / net purchase — acquisto "
                                "sulle righe, vendita sulle colonne)]")
                    pa, pv, mat = fattibilita.matrice_sensitivita(
                        parametri_bp, passo, metrica="multiplo")
                    st.plotly_chart(
                        grafico_sensitivita(
                            pa, pv, mat, "multiplo",
                            base_acquisto=st.session_state.bp_acquisto,
                            base_vendita=st.session_state.bp_vendita),
                        config={"displayModeBar": False})
                    st.markdown(legenda_heatmap("multiplo"),
                                unsafe_allow_html=True)
                    st.markdown("**Net gain** :gray[(guadagno assoluto, €)]")
                    pa, pv, mat = fattibilita.matrice_sensitivita(
                        parametri_bp, passo, metrica="guadagno")
                    st.plotly_chart(
                        grafico_sensitivita(
                            pa, pv, mat, "guadagno",
                            base_acquisto=st.session_state.bp_acquisto,
                            base_vendita=st.session_state.bp_vendita),
                        config={"displayModeBar": False})
                    st.markdown(legenda_heatmap("guadagno"),
                                unsafe_allow_html=True)
                else:
                    st.info("Inserisci **prezzo di acquisto** e **prezzo "
                            "di vendita** per vedere le matrici di "
                            "sensitività (la vendita puoi stimarla "
                            "con l'MCA).")

            # ------------------------------------------- dettaglio costi
            with col_costi:
                st.markdown(
                    '<div style="background:#24345988;border:1px solid '
                    '#3C4C6E;padding:4px 10px;border-radius:6px;'
                    'text-align:center;font-weight:700;margin-bottom:6px;">'
                    'SPESE ACQUISTO — dettaglio</div>',
                    unsafe_allow_html=True)
                e1, e2, e3 = st.columns([1.7, 0.95, 1.35])
                e1.caption("Voce")
                e2.caption("% / €")
                e3.caption("Netto")
                riga_costo_bp(
                    "Imposte d'acquisto",
                    centro={"chiave": "bp_imposta", "min_value": 0.0,
                            "max_value": 30.0, "step": 0.5,
                            "on_change": bp_ricalcola_euro},
                    destra={"chiave": "bp_imposta_eur", "min_value": 0.0,
                            "step": 100.0, "format": "%.2f",
                            "on_change": bp_pct_da_euro_imposta})
                riga_costo_bp(
                    "Imposte fisse",
                    destra={"chiave": "bp_imposte_fisse", "min_value": 0.0,
                            "step": 50.0, "format": "%.2f"})
                riga_costo_bp(
                    "Notaio",
                    destra={"chiave": "bp_notaio", "min_value": 0.0,
                            "step": 100.0, "format": "%.2f",
                            "help": "Compreso IVA, visure, archivio "
                                    "notarile…"})
                riga_costo_bp(
                    "Spese e interessi mutuo",
                    destra={"chiave": "bp_mutuo", "min_value": 0.0,
                            "step": 100.0, "format": "%.2f"})
                riga_costo_bp(
                    "Imprevisti e condominio",
                    destra={"chiave": "bp_imprevisti", "min_value": 0.0,
                            "step": 500.0, "format": "%.2f"})
                riga_costo_bp(
                    "Agenzia IN",
                    centro={"chiave": "bp_ag_in", "min_value": 0.0,
                            "max_value": 10.0, "step": 0.5,
                            "on_change": bp_ricalcola_euro,
                            "help": "Commissione % sul prezzo di acquisto; "
                                    "il € a destra è IVA inclusa"},
                    destra={"chiave": "bp_ag_in_eur", "min_value": 0.0,
                            "step": 100.0, "format": "%.2f",
                            "on_change": bp_pct_da_euro_ag_in})
                riga_costo_bp(
                    ":orange[**Ristrutturazione stimata**] (0 = dal "
                    "computo)",
                    destra={"chiave": "bp_ristr", "min_value": 0.0,
                            "step": 1000.0, "format": "%.2f"})
                # A cantiere avviato le fatture reali valgono più di ogni
                # stima: l'opzione compare solo quando un consuntivo esiste
                # davvero, altrimenti sarebbe un interruttore che non fa nulla.
                if cantiere_consuntivo > 0:
                    st.checkbox(
                        "Usa i costi reali del cantiere "
                        f"({euro(cantiere_consuntivo)})",
                        key="bp_usa_consuntivo",
                        help="Lavori + materiale + architetto dalla scheda "
                             "«Spese a consuntivo» (sostenute e da "
                             "sostenere), al posto della stima. Ha la "
                             "precedenza sulla cifra a mano qui sopra.")
                if usa_consuntivo:
                    provenienza_ristr = "(dal consuntivo: fatture reali)"
                elif st.session_state.bp_ristr:
                    provenienza_ristr = "(a mano)"
                else:
                    provenienza_ristr = "(dal computo, imprevisti inclusi)"
                st.caption("🔗 Ristrutturazione considerata: "
                           f"**{euro(ristr_eff)}** {provenienza_ristr}"
                           + f" · mq: {numero_it(mq_eff, 0)} "
                           + ("(a mano)" if st.session_state.bp_mq
                              else "(dalla planimetria)"))
                st.markdown(righe_bp([
                    ("TOTALE SPESE ACQUISTO", euro(acq["totale"]), "bold"),
                ]), unsafe_allow_html=True)
                st.markdown("<div style='height:10px'></div>",
                            unsafe_allow_html=True)
                riga_costo_bp(
                    "Agenzia OUT",
                    centro={"chiave": "bp_ag_out", "min_value": 0.0,
                            "max_value": 10.0, "step": 0.5,
                            "on_change": bp_ricalcola_euro,
                            "help": "Commissione % sul prezzo di vendita; "
                                    "il € a destra è IVA inclusa"},
                    destra={"chiave": "bp_ag_out_eur", "min_value": 0.0,
                            "step": 100.0, "format": "%.2f",
                            "on_change": bp_pct_da_euro_ag_out})
                st.markdown(righe_bp([
                    ("TOTALE SPESE (acquisto + vendita)",
                     euro(acq["totale"] + ven["totale"]), "bold"),
                ]), unsafe_allow_html=True)

    # --------------------------------------------- MCA prezzo di vendita
    with sotto_mca:
        st.caption("Stima del prezzo di vendita col **metodo comparativo** "
                   "(il tuo foglio «MCA sell»): per ogni comparabile "
                   "inserisci prezzo, mq e il **coefficiente di merito** "
                   "complessivo (il prodotto dei fattori: vetustà, "
                   "finiture, piano, luminosità, riscaldamento… "
                   ">1 = immobile migliore della media, <1 = peggiore). "
                   "Il €/mq viene normalizzato, mediato e riproporzionato "
                   "sul tuo immobile.")
        df_mca_ed = st.data_editor(
            st.session_state.df_mca,
            num_rows="dynamic", hide_index=True,
            key=f"editor_mca_{st.session_state.versione_bp}",
            column_config={
                "nome": st.column_config.TextColumn(
                    "Comparabile", help="Es. C1 — via Roma 10"),
                "prezzo": st.column_config.NumberColumn(
                    "Prezzo richiesto (€)", format="%.0f"),
                "mq": st.column_config.NumberColumn("Mq", format="%.0f"),
                "coeff": st.column_config.NumberColumn(
                    "Coeff. di merito", format="%.3f",
                    help="Prodotto dei coefficienti (vetustà, piano, "
                         "finiture…): 1 = nella media"),
                "note": st.column_config.TextColumn(
                    "Note / link annuncio", width="large"),
            })
        st.session_state.df_mca = df_mca_ed

        m1, m2, m3 = st.columns(3)
        m1.number_input("Coeff. di merito del TUO immobile",
                        min_value=0.1, max_value=3.0, step=0.01,
                        format="%.3f", key="bp_coeff_sogg")
        m2.number_input("Sconto di trattativa (%)", min_value=0.0,
                        max_value=30.0, step=0.5, key="bp_sconto",
                        help="Differenza media tra prezzo richiesto e "
                             "prezzo di vendita reale (~13%)")
        m3.metric("Mq del soggetto", numero_it(mq_eff, 0) + " m²")

        esito_mca = fattibilita.stima_mca(
            mca_da_df(df_mca_ed), st.session_state.bp_coeff_sogg,
            mq_eff, st.session_state.bp_sconto)
        if esito_mca is None:
            st.info("Aggiungi almeno un comparabile completo (prezzo, mq e "
                    "coefficiente maggiori di zero).")
        else:
            st.dataframe(pd.DataFrame([{
                "Comparabile": d["nome"],
                "€/mq": numero_it(d["eur_mq"], 0),
                "Coeff.": numero_it(d["coeff"], 3),
                "€/mq normalizzato": numero_it(d["eur_mq_normalizzato"], 0),
            } for d in esito_mca["dettaglio"]]), hide_index=True)
            n1, n2, n3, n4 = st.columns(4)
            n1.metric("€/mq medio normalizzato",
                      numero_it(esito_mca["eur_mq_media"], 0))
            n2.metric("€/mq del soggetto",
                      numero_it(esito_mca["eur_mq_soggetto"], 0))
            n3.metric(f"€/mq −{numero_it(st.session_state.bp_sconto, 0)}%",
                      numero_it(esito_mca["eur_mq_probabile"], 0))
            n4.metric("Valore stimato",
                      euro(esito_mca["valore"])
                      if esito_mca["valore"] else "—")
            if esito_mca["valore"]:
                if st.button("📥 Usa come prezzo di vendita nello studio "
                             "di fattibilità", type="primary"):
                    st.session_state.bp_vendita_pending = float(
                        round(esito_mca["valore"], 0))
                    st.rerun()


# ---------------------------------------------------------------- lingua
# Streamlit serve la pagina con <html lang="en"> e non offre un'opzione per
# cambiarlo. Su un'interfaccia interamente italiana ogni screen reader applica
# fonetica inglese a «Computo», «Demolizioni», «Imprevisti». Il componente
# gira nella stessa origine e può correggere l'attributo sul documento padre;
# se il browser lo impedisce non succede nulla di male.
st.iframe(
    '<!doctype html><html><body><script>'
    'try { window.parent.document.documentElement.lang = "it"; }'
    ' catch (errore) {}'
    '</script></body></html>',
    height=1,
)
