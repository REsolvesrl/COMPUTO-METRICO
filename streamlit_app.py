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
import io
import json
from datetime import date

import fitz  # PyMuPDF, per leggere i PDF
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from PIL import Image

import calcoli
import fattibilita
import listino
import planimetria
import rilevamento
from cme_viewer import image_viewer, pil_a_src

st.set_page_config(
    page_title="CME — Computo Metrico",
    page_icon="🏗️",
    layout="wide",
)

COLONNE_TESTO = ["categoria", "codice", "descrizione", "um"]
COLONNE_NUMERI = ["parti", "lunghezza", "larghezza", "altezza",
                  "quantita_manuale", "prezzo"]
COLONNE = COLONNE_TESTO + COLONNE_NUMERI

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

# Business plan: colonne delle tabelle e impostazioni predefinite
# (chiave di sessione → valore iniziale; il tipo del default comanda).
COLONNE_SPESE = ["data", "oggetto", "categoria", "importo",
                 "aliquota_iva", "stato", "note"]
COLONNE_MCA = ["nome", "prezzo", "mq", "coeff", "note"]
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

CATEGORIE_DEFAULT = [
    {"nome": "Superficie interna", "percento": 100.0},
    {"nome": "Balcone scoperto", "percento": 30.0},
    {"nome": "Balcone coperto", "percento": 35.0},
    {"nome": "Terrazzo", "percento": 25.0},
    {"nome": "Giardino", "percento": 10.0},
    {"nome": "Garage / Box", "percento": 50.0},
    {"nome": "Cantina / Soffitta", "percento": 25.0},
]

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


def df_spese_vuoto():
    colonne = {}
    for col in COLONNE_SPESE:
        tipo = "float64" if col in ("importo", "aliquota_iva") else "object"
        colonne[col] = pd.Series(dtype=tipo)
    return pd.DataFrame(colonne)


def spese_da_df(df):
    """La tabella delle spese come lista di dizionari (righe con importo)."""
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
            "data": testo("data"),
            "oggetto": testo("oggetto"),
            "categoria": testo("categoria", "ALTRO") or "ALTRO",
            "importo": float(importo),
            "aliquota_iva": (0.0 if aliquota is None or pd.isna(aliquota)
                             else float(aliquota)),
            "stato": testo("stato", "Sostenuta") or "Sostenuta",
            "note": testo("note"),
        })
    return righe


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
    """Una riga della checklist: descrizione, quantità, prezzo, parziale."""
    c_voce, c_qta, c_prezzo, c_parz = st.columns(
        [3.4, 1, 1, 1], vertical_alignment="center")
    aiuto = voce.get("nota")
    if voce.get("analisi"):
        aiuto = (aiuto + "\n\n" if aiuto else "") + voce["analisi"]
    c_voce.markdown(f"**{voce['codice']}** {voce['descrizione']} · "
                    f":gray[{voce['um']}]", help=aiuto)
    quantita = c_qta.number_input(
        "Quantità", min_value=0.0, step=1.0, format="%.2f",
        key=f"lq_{voce['codice']}", label_visibility="collapsed")
    prezzo = c_prezzo.number_input(
        "Prezzo €", min_value=0.0, step=1.0, format="%.2f",
        key=f"lp_{voce['codice']}", label_visibility="collapsed")
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


def grafico_sensitivita(prezzi_acquisto, prezzi_vendita, matrice, metrica,
                        base_acquisto=None, base_vendita=None, altezza=330):
    """Matrice di sensitività come mappa di calore stile Excel.

    Colori come la formattazione condizionale del foglio: minimo → rosso,
    massimo → verde e il BIANCO sulla MEDIANA dei valori (Excel usa il 50°
    percentile, non la metà aritmetica: è questo che rende uniformi le due
    matrici). Il prezzo base di acquisto/vendita è evidenziato in
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
    mediana = piatti[len(piatti) // 2]
    frazione_bianco = (mediana - minimo) / (massimo - minimo)
    frazione_bianco = min(0.95, max(0.05, frazione_bianco))
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
    # sfondo azzurro dietro la colonna base: xref="x" segue il dato (giusto
    # a qualunque larghezza), yref="paper" si estende nel margine superiore
    # (l'altezza del grafico è fissa, quindi affidabile). layer="below"
    # tiene il rettangolo sotto le celle della heatmap.
    if idx_v is not None:
        fig.add_shape(type="rect", xref="x", x0=idx_v - 0.5, x1=idx_v + 0.5,
                      yref="paper", y0=1.0, y1=1.16,
                      fillcolor="#DDEBF7", line=dict(width=0),
                      layer="below")
    # sfondo giallo dietro la riga base: yref="y" segue il dato (sempre
    # giusto), xref="paper" si estende nel margine sinistro — qui non serve
    # precisione al pixel, è solo una macchia di colore decorativa.
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
        margin=dict(l=48, r=0, t=26, b=0),
        height=altezza,
        font=dict(family='system-ui, -apple-system, "Segoe UI", sans-serif',
                  color=CREMA),
        xaxis=dict(title=None, side="top",
                   tickfont=dict(color=ETICHETTE)),
        yaxis=dict(title=None, autorange="reversed",
                   tickfont=dict(color=ETICHETTE)),
    )
    return fig


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


def riga_costo_bp(etichetta, centro=None, destra=None):
    """Riga del dettaglio costi stile Excel: etichetta | %/€ | netto.

    centro e destra possono essere: None (mostra «/»), una stringa (testo
    di sola lettura) oppure un dizionario {"chiave": …, **kwargs} che
    diventa un number_input modificabile.
    """
    c_eti, c_inp, c_val = st.columns([1.9, 1.0, 1.2],
                                     vertical_alignment="center")
    c_eti.markdown(f":gray[{etichetta}]")

    def cella(colonna, contenuto, a_destra=False):
        if contenuto is None:
            colonna.markdown('<div style="text-align:center;'
                             'color:#5B688A;">/</div>',
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


def mappa_percentuali():
    return {c["nome"]: float(c["percento"]) for c in st.session_state.categorie}


def mappa_colori():
    return {c["nome"]: PALETTE_ZONE[i % len(PALETTE_ZONE)]
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
        perc = perc_map.get(zona["categoria"], 100.0)
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


def gestisci_evento(ev, pianta):
    """Applica l'evento del visualizzatore allo stato e riesegue la pagina."""
    tipo = ev.get("tipo")
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
        "business_plan": {chiave: st.session_state.get(chiave, valore)
                          for chiave, valore in IMPOSTAZIONI_BP.items()},
        "spese": spese_da_df(st.session_state.df_spese),
        "mca_comparabili": mca_da_df(st.session_state.df_mca),
        "categorie": st.session_state.categorie,
        "etichette": {"font": st.session_state.et_font,
                      "nome": st.session_state.et_nome,
                      "m2": st.session_state.et_m2,
                      "percento": st.session_state.et_pct,
                      "perimetro": st.session_state.et_perim},
        "altezza_locali": st.session_state.alt_locali,
        "piante": [pianta_a_json(p) for p in st.session_state.piante],
    }
    return json.dumps(payload, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


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
# business plan
st.session_state.setdefault("df_spese", df_spese_vuoto())
st.session_state.setdefault("df_mca", df_mca_vuoto())
st.session_state.setdefault("versione_bp", 0)
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
st.session_state.setdefault("et_font", 14)
st.session_state.setdefault("et_nome", True)
st.session_state.setdefault("et_m2", True)
st.session_state.setdefault("et_pct", True)
st.session_state.setdefault("et_perim", False)
st.session_state.setdefault("alt_locali", 2.70)

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
    for _voce in listino.VOCI:
        elemento = stato_listino.get(_voce["codice"]) or {}
        st.session_state[f"lq_{_voce['codice']}"] = float(
            elemento.get("q", 0.0))
        st.session_state[f"lp_{_voce['codice']}"] = float(
            elemento.get("p", _voce["prezzo"]))
    try:
        st.session_state.prg_data = date.fromisoformat(progetto.get("data", ""))
    except (TypeError, ValueError):
        st.session_state.prg_data = date.today()
    df = pd.DataFrame(dati.get("voci", [])).reindex(columns=COLONNE)
    for col in COLONNE_NUMERI:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    st.session_state.df_voci = df if len(df) else df_vuoto()
    st.session_state.versione_editor += 1
    # planimetrie e impostazioni
    st.session_state.categorie = (dati.get("categorie")
                                  or [dict(c) for c in CATEGORIE_DEFAULT])
    etichette = dati.get("etichette") or {}
    st.session_state.et_font = int(etichette.get("font", 14))
    st.session_state.et_nome = bool(etichette.get("nome", True))
    st.session_state.et_m2 = bool(etichette.get("m2", True))
    st.session_state.et_pct = bool(etichette.get("percento", True))
    st.session_state.et_perim = bool(etichette.get("perimetro", False))
    st.session_state.alt_locali = float(dati.get("altezza_locali", 2.70))
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
    st.session_state.pop("cat_attiva", None)
    st.session_state.pop("tipo_parete", None)
    st.session_state.pop("scala_metri", None)
    # business plan
    bp_salvato = dati.get("business_plan") or {}
    for _chiave, _valore in IMPOSTAZIONI_BP.items():
        nuovo = bp_salvato.get(_chiave, _valore)
        st.session_state[_chiave] = (int(nuovo) if isinstance(_valore, int)
                                     else float(nuovo))
    df_sp = pd.DataFrame(dati.get("spese") or []).reindex(
        columns=COLONNE_SPESE)
    for col in ("importo", "aliquota_iva"):
        df_sp[col] = pd.to_numeric(df_sp[col], errors="coerce")
    st.session_state.df_spese = df_sp if len(df_sp) else df_spese_vuoto()
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


# ------------------------------------------------------------------ pagina

st.title("🏗️ Computo Metrico Estimativo")
if st.session_state.prg_nome:
    st.caption(st.session_state.prg_nome)

tab_computo, tab_plan, tab_bp = st.tabs(
    ["📝 Computo metrico", "📐 Misura da planimetria", "📊 Business plan"])


# ============================================================ SCHEDA COMPUTO

with tab_computo:
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
        a_apri, a_nuovo = st.columns([3, 1])
        with a_apri:
            file_json = st.file_uploader(
                "📂 Apri un progetto salvato (.json)", type=["json"])
            if file_json is not None and st.button("Carica nel programma"):
                try:
                    st.session_state.da_caricare = json.load(file_json)
                    st.rerun()
                except (json.JSONDecodeError, UnicodeDecodeError):
                    st.error("Il file non sembra un progetto salvato da "
                             "questa app.")
        with a_nuovo:
            st.write("")
            st.write("")
            if st.button("🗑️ Nuovo progetto (svuota tutto)"):
                st.session_state.da_caricare = {}
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
        st.markdown(
            '<div style="background:linear-gradient(135deg,#243459,#1A2744);'
            'border:1px solid #C9A96A;border-radius:12px;'
            'padding:12px 14px;margin:6px 0 10px;">'
            '<div style="font-size:0.72rem;color:#C9A96A;'
            'letter-spacing:.05em;">💎 TOTALE FINALE</div>'
            '<div style="font-size:1.45rem;font-weight:700;color:#ECE7DA;">'
            f'{euro(totale_imprevisti)}</div></div>',
            unsafe_allow_html=True)
        st.metric(f"IVA {numero_it(st.session_state.iva, 0)}%",
                  euro(iva_importo))
        st.metric("Totale IVA inclusa", euro(totale_ivato))

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
        st.session_state.piante, mappa_percentuali())
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

    col_json, col_xlsx, col_csv = st.columns(3)
    col_json.download_button(
        "💾 Salva progetto (.json)",
        data=progetto_json_bytes(),
        file_name=nome_file("json"),
        mime="application/json",
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

            if pianta["mpp"]:
                st.caption("✅ Scala impostata — le misure sono in metri "
                           "reali. ✏️ disegna le aree, 📏 misura al volo, "
                           "↔️ per ricalibrare.")
            else:
                st.warning("⚠️ Scala non impostata per questa planimetria: "
                           "scegli **↔️ Scala** nella barra sul disegno e "
                           "trascina lungo una misura nota (es. lato quotato).")

            impostazioni = {"nome": st.session_state.et_nome,
                            "m2": st.session_state.et_m2,
                            "percento": st.session_state.et_pct,
                            "perimetro": st.session_state.et_perim}
            # etichette fuori dalle aree (se l'utente non le ha spostate)
            pos_default = planimetria.posiziona_etichette(
                pianta["zone"], pianta["img"].width, pianta["img"].height)
            zone_props = [{
                "id": z["id"], "punti": z["punti"],
                "colore": col_map.get(z["categoria"], "#9E9E9E"),
                "etichetta": etichetta_zona(z, pianta["mpp"], perc_map,
                                            impostazioni),
                "etichetta_pos": (z.get("etichetta_pos")
                                  or pos_default.get(z["id"])),
            } for z in pianta["zone"]]
            pareti_props = [{
                "id": p["id"], "p1": p["p1"], "p2": p["p2"],
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
                    if a_add.button("➕ Al computo",
                                    help="Aggiunge questa superficie come "
                                         "voce del computo"):
                        aggiungi_voce_computo(
                            "Superfici",
                            f"{zona_sel.get('nome') or zona_sel['categoria']}"
                            f" — {pianta['nome']}",
                            "m²", round(area_sel, 2), None)
                        st.toast("Aggiunta al computo ✔")
                if a_del.button("🗑 Elimina"):
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
                    parete_sel["tipo"] = codice_nuovo
                    st.rerun()
                b_len.metric("Lunghezza",
                             etichetta_parete(parete_sel, pianta["mpp"]))
                b_del.write("")
                if b_del.button("🗑 Elimina",
                                key=f"pdel_{parete_sel['id']}"):
                    pianta["pareti"] = [p for p in pianta["pareti"]
                                        if p["id"] != parete_sel["id"]]
                    st.session_state.sel_parete = None
                    st.rerun()

            # ---------------------------------- rilevamento automatico (beta)
            with st.expander("🪄 Rileva stanze automaticamente (beta)"):
                st.caption(
                    "Il programma prova a riconoscere le **stanze chiuse dai "
                    "muri** (ignorando scritte e quote) e le propone come "
                    "aree della categoria scelta sopra: sono **proposte da "
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
                            zone_esistenti=[z["punti"]
                                            for z in pianta["zone"]])
                    if not proposte:
                        st.warning("Non ho riconosciuto stanze chiuse su "
                                   "questo disegno. Prova a impostare prima "
                                   "la scala, o disegna le aree a mano.")
                    else:
                        nuovi_id = []
                        for punti in proposte:
                            zid = nuovo_id(pianta)
                            pianta["zone"].append({
                                "id": zid,
                                "categoria": cat_attiva_nome,
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
            f'{c["nome"]} · {numero_it(c["percento"], 0)}%</span>'
            for c in st.session_state.categorie)
        st.caption("Categorie di superficie (colore · peso commerciale):")
        st.markdown(legenda, unsafe_allow_html=True)

        with st.expander("🔤 Etichette sulle zone (layout)"):
            st.slider("Dimensione carattere", 10, 24, key="et_font")
            e1, e2, e3, e4 = st.columns(4)
            e1.checkbox("Nome / categoria", key="et_nome")
            e2.checkbox("Superficie (m²)", key="et_m2")
            e3.checkbox("Perimetro (m)", key="et_perim")
            e4.checkbox("Percentuale", key="et_pct")

        # ------------------------------------------- superfici commerciali
        st.subheader("🧮 Superfici commerciali (tutte le planimetrie)")
        righe_sup, tot_sup, tot_comm, senza_scala = (
            planimetria.riepilogo_superfici(piante, mappa_percentuali()))
        if senza_scala:
            st.warning("Escluse dal totale perché **senza scala**: "
                       + ", ".join(senza_scala))
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

        # ------------------------------------- battiscopa e tinteggiature
        st.subheader("📏 Battiscopa e tinteggiature (perimetri dei locali)")
        righe_loc, senza_scala_loc = planimetria.riepilogo_locali(piante)
        if senza_scala_loc:
            st.warning("Locali esclusi perché la planimetria è **senza "
                       "scala**: " + ", ".join(senza_scala_loc))
        if not righe_loc:
            st.info("Quando ci sono zone disegnate (su piante con scala), "
                    "qui trovi i perimetri per battiscopa e tinteggiature.")
        else:
            st.caption("Spunta i locali da considerare (di solito **bagni e "
                       "balconi si escludono** dal battiscopa). Pareti = "
                       "perimetro × altezza; soffitti = superficie "
                       "calpestabile. Le aperture (porte/finestre) non "
                       "vengono detratte: affina tu le quantità nel computo "
                       "se serve.")
            altezza = st.number_input(
                "Altezza dei locali (m)", min_value=1.0, max_value=6.0,
                step=0.05, format="%.2f", key="alt_locali")

            zona_per_rif = {(p["uid"], z["id"]): z
                            for p in piante for z in p["zone"]}
            righe_tab = []
            riferimenti = []
            for r in righe_loc:
                zona = zona_per_rif.get((r["uid"], r["id"]))
                if zona is None:
                    continue
                interna = perc_map.get(r["categoria"], 100.0) >= 100.0
                bagno = any(parola in (r["nome"] + " " + r["categoria"]).lower()
                            for parola in ("bagno", "wc", "w.c"))
                batt_def = zona.get("battiscopa")
                if batt_def is None:
                    batt_def = interna and not bagno
                pitt_def = zona.get("pittura")
                if pitt_def is None:
                    pitt_def = interna
                righe_tab.append({
                    "Pianta": r["pianta"],
                    "Locale": r["nome"],
                    "Superficie (m²)": round(r["m2"], 2),
                    "Perimetro (m)": round(r["perimetro"], 2),
                    "Battiscopa": bool(batt_def),
                    "Tinteggiatura": bool(pitt_def),
                })
                riferimenti.append((r["uid"], r["id"]))

            chiave_tab = "edloc_" + str(abs(hash(tuple(riferimenti))) % 10 ** 8)
            df_loc = st.data_editor(
                pd.DataFrame(righe_tab),
                hide_index=True, key=chiave_tab,
                disabled=["Pianta", "Locale", "Superficie (m²)",
                          "Perimetro (m)"],
                column_config={
                    "Battiscopa": st.column_config.CheckboxColumn(
                        "Battiscopa", help="Conta nel totale del battiscopa"),
                    "Tinteggiatura": st.column_config.CheckboxColumn(
                        "Tinteggiatura",
                        help="Conta in pareti e soffitti da tinteggiare"),
                })

            batt_m = 0.0
            pareti_m2 = 0.0
            soffitti_m2 = 0.0
            for (uid, zid), (_, riga) in zip(riferimenti, df_loc.iterrows()):
                zona = zona_per_rif.get((uid, zid))
                if zona is None:
                    continue
                zona["battiscopa"] = bool(riga["Battiscopa"])
                zona["pittura"] = bool(riga["Tinteggiatura"])
                if zona["battiscopa"]:
                    batt_m += float(riga["Perimetro (m)"])
                if zona["pittura"]:
                    pareti_m2 += float(riga["Perimetro (m)"]) * altezza
                    soffitti_m2 += float(riga["Superficie (m²)"])

            t1, t2, t3 = st.columns(3)
            t1.metric("Battiscopa", f"{numero_it(batt_m, 2)} m")
            t2.metric(f"Pareti (h {numero_it(altezza, 2)} m)",
                      f"{numero_it(pareti_m2, 2)} m²")
            t3.metric("Soffitti", f"{numero_it(soffitti_m2, 2)} m²")

            v1, v2 = st.columns(2)
            if v1.button("➕ Battiscopa nel computo (rimozione + posa)"):
                aggiungi_voce_computo(
                    "Battiscopa", "Rimozione battiscopa esistente",
                    "m", round(batt_m, 2), None)
                aggiungi_voce_computo(
                    "Battiscopa", "Fornitura e posa nuovo battiscopa",
                    "m", round(batt_m, 2), None)
                st.toast("Battiscopa aggiunto al computo (2 voci) ✔")
            if v2.button("➕ Tinteggiatura nel computo (pareti + soffitti)"):
                aggiungi_voce_computo(
                    "Tinteggiature",
                    f"Tinteggiatura pareti (h {numero_it(altezza, 2)} m)",
                    "m²", round(pareti_m2, 2), None)
                aggiungi_voce_computo(
                    "Tinteggiature", "Tinteggiatura soffitti",
                    "m²", round(soffitti_m2, 2), None)
                st.toast("Tinteggiature aggiunte al computo (2 voci) ✔")

        st.divider()
        st.download_button(
            "💾 Salva progetto (.json) — computo e planimetrie",
            data=progetto_json_bytes(),
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
        st.session_state.piante, mappa_percentuali())
    voci_bp = voci_dal_listino() + voci_da_df(st.session_state.df_voci)
    totale_computo_bp = calcoli.totale_generale(
        calcoli.calcola_computo(voci_bp))
    _, ristr_da_computo = calcoli.totale_con_imprevisti(
        totale_computo_bp, st.session_state.imprevisti)

    # ------------------------------------------------ studio di fattibilità
    with sotto_fatt:
        # impaginazione «da Excel»: tre blocchi affiancati (riepilogo,
        # matrici, dettaglio costi) su una larghezza fissa; se lo schermo
        # è più stretto compare lo scorrimento orizzontale.
        st.markdown("""
<style>
.st-key-bp_scroll { overflow-x: auto; padding-bottom: 6px; }
.st-key-bp_scroll [data-testid="stHorizontalBlock"] { min-width: 1750px; }
.st-key-bp_scroll [data-testid="stHorizontalBlock"]
 [data-testid="stHorizontalBlock"] { min-width: 0; }
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
</style>
""", unsafe_allow_html=True)

        mq_eff = st.session_state.bp_mq or mq_da_planimetria
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
                [1.05, 2.3, 1.5], gap="large")

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
                st.markdown("<div style='height:8px'></div>",
                            unsafe_allow_html=True)
                st.markdown(righe_bp([
                    ("Net Return (ROI)",
                     numero_it(esito["multiplo"], 2) + "x", "bold"),
                    ("Return of Equity (ROE)",
                     numero_it(esito["roe"] * 100, 1) + " %", None),
                    (f"Rendimento annuo ({st.session_state.bp_durata} mesi)",
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
                    st.markdown("**Net gain** :gray[(guadagno assoluto, €)]")
                    pa, pv, mat = fattibilita.matrice_sensitivita(
                        parametri_bp, passo, metrica="guadagno")
                    st.plotly_chart(
                        grafico_sensitivita(
                            pa, pv, mat, "guadagno",
                            base_acquisto=st.session_state.bp_acquisto,
                            base_vendita=st.session_state.bp_vendita),
                        config={"displayModeBar": False})
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
                e1, e2, e3 = st.columns([1.9, 1.0, 1.2])
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
                st.caption("🔗 Ristrutturazione considerata: "
                           f"**{euro(ristr_eff)}** "
                           + ("(a mano)" if st.session_state.bp_ristr
                              else "(dal computo, imprevisti inclusi)")
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

    # ------------------------------------------------- spese a consuntivo
    with sotto_spese:
        st.caption("Il registro delle spese reali dell'operazione (come il "
                   "tuo foglio «Spese»): segna ogni uscita con categoria, "
                   "IVA e stato. Sotto trovi i totali e il **confronto col "
                   "preventivo del computo**.")
        df_spese_ed = st.data_editor(
            st.session_state.df_spese,
            num_rows="dynamic", hide_index=True,
            key=f"editor_spese_{st.session_state.versione_bp}",
            column_config={
                "data": st.column_config.TextColumn(
                    "Data", help="Es. 22/10/2025"),
                "oggetto": st.column_config.TextColumn(
                    "Oggetto", width="large"),
                "categoria": st.column_config.SelectboxColumn(
                    "Categoria", options=fattibilita.CATEGORIE_SPESE),
                "importo": st.column_config.NumberColumn(
                    "Importo (€)", format="%.2f"),
                "aliquota_iva": st.column_config.NumberColumn(
                    "IVA %", min_value=0.0, max_value=22.0, step=1.0,
                    help="Aliquota della fattura, per lo scorporo "
                         "(22, 10 o 0)"),
                "stato": st.column_config.SelectboxColumn(
                    "Stato", options=fattibilita.STATI_SPESA),
                "note": st.column_config.TextColumn("Note"),
            })
        st.session_state.df_spese = df_spese_ed

        righe_spese = spese_da_df(df_spese_ed)
        if not righe_spese:
            st.info("Aggiungi la prima spesa nella tabella (riga vuota in "
                    "fondo).")
        else:
            sostenute = sum(r["importo"] for r in righe_spese
                            if r["stato"] == "Sostenuta")
            da_sostenere = sum(r["importo"] for r in righe_spese
                               if r["stato"] != "Sostenuta")
            iva_scorporata = sum(
                r["importo"] / (1 + r["aliquota_iva"] / 100)
                * r["aliquota_iva"] / 100
                for r in righe_spese if r["aliquota_iva"] > 0)
            t1, t2, t3, t4 = st.columns(4)
            t1.metric("Sostenute", euro(sostenute))
            t2.metric("Da sostenere", euro(da_sostenere))
            t3.metric("Spesa finale prevista",
                      euro(sostenute + da_sostenere))
            t4.metric("di cui IVA (scorporata)", euro(iva_scorporata))

            per_categoria = {}
            for r in righe_spese:
                voce = per_categoria.setdefault(
                    r["categoria"], {"Sostenute": 0.0, "Da sostenere": 0.0})
                chiave = ("Sostenute" if r["stato"] == "Sostenuta"
                          else "Da sostenere")
                voce[chiave] += r["importo"]
            st.dataframe(pd.DataFrame([{
                "Categoria": cat,
                "Sostenute": euro(v["Sostenute"]),
                "Da sostenere": euro(v["Da sostenere"]),
                "Totale": euro(v["Sostenute"] + v["Da sostenere"]),
            } for cat, v in per_categoria.items()]), hide_index=True)

            st.subheader("⚖️ Preventivo vs consuntivo (cantiere)")
            consuntivo_cantiere = sum(
                r["importo"] for r in righe_spese
                if r["categoria"] in fattibilita.CATEGORIE_CANTIERE)
            scostamento = consuntivo_cantiere - ristr_da_computo
            c1, c2, c3 = st.columns(3)
            c1.metric("Preventivo (computo + imprevisti)",
                      euro(ristr_da_computo))
            c2.metric("Consuntivo cantiere (lavori+materiali+architetto)",
                      euro(consuntivo_cantiere))
            c3.metric("Scostamento", euro(scostamento),
                      delta=euro(scostamento), delta_color="inverse")

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
