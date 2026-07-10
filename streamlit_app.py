"""CME — Computo Metrico Estimativo.

Interfaccia Streamlit a due schede:
1. Computo metrico — tabella voci, quantità calcolate, totali, export.
2. Misura da planimetria — carichi un'immagine/PDF, calibri la scala su una
   misura nota e disegni le stanze per ottenere i m², da riversare nel computo.

La logica di calcolo vive in calcoli.py; la geometria in planimetria.py.
"""

import io
import json
from datetime import date

import fitz  # PyMuPDF, per leggere i PDF
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from PIL import Image, ImageDraw
from streamlit_image_coordinates import streamlit_image_coordinates

import calcoli
import planimetria

st.set_page_config(
    page_title="CME — Computo Metrico",
    page_icon="🏗️",
    layout="wide",
)

COLONNE_TESTO = ["categoria", "codice", "descrizione", "um"]
COLONNE_NUMERI = ["parti", "lunghezza", "larghezza", "altezza",
                  "quantita_manuale", "prezzo"]
COLONNE = COLONNE_TESTO + COLONNE_NUMERI

UM_OPZIONI = ["m", "m²", "m³", "kg", "t", "cad", "h", "a corpo"]

BLU_SERIE = "#2a78d6"
GRIGIO_GRIGLIA = "#e1e0d9"
GRIGIO_ETICHETTE = "#898781"

# Larghezza di lavoro della planimetria (px): la libreria di disegno
# restituisce le coordinate nello spazio dell'immagine mostrata, perciò
# fissiamo questa larghezza e ci lavoriamo sempre dentro.
LARGHEZZA_PLAN = 820
COL_CAL_LINEA = (235, 104, 52, 255)     # arancione — calibrazione
COL_CAL_PUNTO = (235, 104, 52, 255)
COL_ST_LINEA = (42, 120, 214, 255)      # blu — stanza
COL_ST_PUNTO = (42, 120, 214, 255)
COL_ST_FILL = (42, 120, 214, 70)


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


def aggiungi_voce_computo(categoria, descrizione, um, quantita, prezzo):
    """Appende una voce alla tabella del computo (usata dalla planimetria)."""
    riga = {col: None for col in COLONNE}
    riga["categoria"] = categoria or None
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


def grafico_totali(totali):
    """Barre orizzontali: una serie, un solo colore, etichette dirette."""
    categorie = sorted(totali, key=totali.get)
    valori = [totali[c] for c in categorie]
    fig = go.Figure(go.Bar(
        x=valori,
        y=categorie,
        orientation="h",
        marker_color=BLU_SERIE,
        text=[euro(v) for v in valori],
        textposition="outside",
        cliponaxis=False,
        hovertemplate="%{y}: %{text}<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=80, t=10, b=10),
        height=max(200, 60 + 40 * len(categorie)),
        showlegend=False,
        font=dict(family='system-ui, -apple-system, "Segoe UI", sans-serif'),
        xaxis=dict(showgrid=True, gridcolor=GRIGIO_GRIGLIA, zeroline=False,
                   tickfont=dict(color=GRIGIO_ETICHETTE)),
        yaxis=dict(showgrid=False),
    )
    return fig


def excel_bytes(df_computo, df_riepilogo, df_progetto):
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_computo.to_excel(writer, sheet_name="Computo", index=False)
        df_riepilogo.to_excel(writer, sheet_name="Riepilogo", index=False)
        df_progetto.to_excel(writer, sheet_name="Dati progetto", index=False)
    return buffer.getvalue()


# -------------------------------------------------------------- planimetria

def carica_immagine(file):
    """Legge il file caricato e restituisce un'immagine RGB ridimensionata.

    Accetta immagini (PNG/JPG…) e PDF (di cui si usa la prima pagina).
    """
    dati = file.getvalue()
    if file.name.lower().endswith(".pdf") or file.type == "application/pdf":
        documento = fitz.open(stream=dati, filetype="pdf")
        pagina = documento[0]
        pix = pagina.get_pixmap(dpi=150)
        img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    else:
        img = Image.open(io.BytesIO(dati)).convert("RGB")
    if img.width > LARGHEZZA_PLAN:
        altezza = round(img.height * LARGHEZZA_PLAN / img.width)
        img = img.resize((LARGHEZZA_PLAN, altezza))
    return img


def disegna_overlay(base, punti, col_linea, col_punto, chiudi, riempi_col=None):
    """Disegna punti, segmenti (ed eventuale poligono) sopra l'immagine base."""
    punti_int = [(int(x), int(y)) for x, y in punti]
    img = base.convert("RGBA")
    strato = Image.new("RGBA", img.size, (0, 0, 0, 0))
    dis = ImageDraw.Draw(strato)
    if riempi_col and len(punti_int) >= 3:
        dis.polygon(punti_int, fill=riempi_col)
    if len(punti_int) >= 2:
        sequenza = punti_int + ([punti_int[0]] if chiudi else [])
        dis.line(sequenza, fill=col_linea, width=3, joint="curve")
    for x, y in punti_int:
        dis.ellipse([x - 5, y - 5, x + 5, y + 5],
                    fill=col_punto, outline=(255, 255, 255, 255), width=2)
    return Image.alpha_composite(img, strato).convert("RGB")


def gestisci_click(valore, chiave_ts, lista, massimo=None):
    """Aggiunge un nuovo click alla lista di punti, evitando i duplicati.

    Ogni click ha un timestamp: lo confrontiamo con l'ultimo elaborato così
    i rerun di Streamlit non re-inseriscono lo stesso punto. Restituisce True
    se è stato aggiunto un punto (per far ridisegnare l'immagine).
    """
    if not valore:
        return False
    ts = valore.get("unix_time")
    if ts == st.session_state.get(chiave_ts):
        return False
    st.session_state[chiave_ts] = ts
    if massimo is not None and len(lista) >= massimo:
        return False
    lista.append((valore["x"], valore["y"]))
    return True


# ------------------------------------------------- stato iniziale e caricamento

st.session_state.setdefault("df_voci", df_vuoto())
st.session_state.setdefault("versione_editor", 0)
st.session_state.setdefault("prg_nome", "")
st.session_state.setdefault("prg_committente", "")
st.session_state.setdefault("prg_oggetto", "")
st.session_state.setdefault("prg_data", date.today())
st.session_state.setdefault("iva", 22.0)
# planimetria
st.session_state.setdefault("plan_img", None)
st.session_state.setdefault("plan_sig", None)
st.session_state.setdefault("mpp", None)
st.session_state.setdefault("punti_cal", [])
st.session_state.setdefault("punti_stanza", [])
st.session_state.setdefault("ts_cal", None)
st.session_state.setdefault("ts_st", None)

# Un caricamento (o azzeramento) va applicato PRIMA di creare i widget.
if "da_caricare" in st.session_state:
    dati = st.session_state.pop("da_caricare")
    progetto = dati.get("progetto", {})
    st.session_state.prg_nome = progetto.get("nome", "")
    st.session_state.prg_committente = progetto.get("committente", "")
    st.session_state.prg_oggetto = progetto.get("oggetto", "")
    st.session_state.iva = float(progetto.get("aliquota_iva", 22.0))
    try:
        st.session_state.prg_data = date.fromisoformat(progetto.get("data", ""))
    except (TypeError, ValueError):
        st.session_state.prg_data = date.today()
    df = pd.DataFrame(dati.get("voci", [])).reindex(columns=COLONNE)
    for col in COLONNE_NUMERI:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    st.session_state.df_voci = df if len(df) else df_vuoto()
    st.session_state.versione_editor += 1


# ------------------------------------------------------------------ sidebar

with st.sidebar:
    st.header("📋 Dati del progetto")
    st.text_input("Nome del computo", key="prg_nome",
                  placeholder="Es. Ristrutturazione app.to Via Roma 1")
    st.text_input("Committente", key="prg_committente")
    st.text_input("Oggetto dei lavori", key="prg_oggetto")
    st.date_input("Data", key="prg_data", format="DD/MM/YYYY")
    st.number_input("Aliquota IVA (%)", min_value=0.0, max_value=100.0,
                    step=1.0, key="iva",
                    help="22% ordinaria, 10% ristrutturazioni, 4% prima casa")

    st.divider()
    st.subheader("📂 Apri un computo salvato")
    file_json = st.file_uploader(
        "Scegli un file .json salvato in precedenza", type=["json"])
    if file_json is not None and st.button("Carica nel programma"):
        try:
            st.session_state.da_caricare = json.load(file_json)
            st.rerun()
        except (json.JSONDecodeError, UnicodeDecodeError):
            st.error("Il file non sembra un computo salvato da questa app.")

    st.divider()
    if st.button("🗑️ Nuovo computo (svuota tutto)"):
        st.session_state.da_caricare = {}
        st.rerun()


# ------------------------------------------------------------------ pagina

st.title("🏗️ Computo Metrico Estimativo")
if st.session_state.prg_nome:
    st.caption(st.session_state.prg_nome)

tab_computo, tab_plan = st.tabs(["📝 Computo metrico", "📐 Misura da planimetria"])


# ============================================================ SCHEDA COMPUTO

with tab_computo:
    with st.expander("ℹ️ Come si usa"):
        st.markdown("""
1. Compila i **dati del progetto** nella barra laterale.
2. Aggiungi le **voci di lavorazione** nella tabella: clicca sull'ultima
   riga vuota per aggiungerne una.
3. Per ogni voce indica le **dimensioni** (parti uguali, lunghezza,
   larghezza, altezza/peso): la quantità si calcola da sola moltiplicando i
   campi compilati. Le caselle vuote non contano. *In alternativa* lascia
   vuote le dimensioni e scrivi la **quantità manuale**.
4. Per una **detrazione** (es. scomputare il vano di una porta) usa un
   numero di **parti negativo**, es. `-1`.
5. Le superfici misurate nella scheda **Misura da planimetria** finiscono
   qui automaticamente come nuove voci.
""")

    st.subheader("1 · Voci di lavorazione")
    st.caption("Doppio clic su una cella per scriverci. La riga vuota in fondo "
               "aggiunge una voce; per cancellare una riga selezionala "
               "(casella a sinistra) e premi Canc.")

    df_editato = st.data_editor(
        st.session_state.df_voci,
        num_rows="dynamic",
        hide_index=True,
        key=f"editor_voci_{st.session_state.versione_editor}",
        column_config={
            "categoria": st.column_config.TextColumn(
                "Categoria", help="Es. Demolizioni, Murature, Impianti…"),
            "codice": st.column_config.TextColumn(
                "Codice", help="Codice voce, facoltativo (es. 01.A01.001)"),
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
                "Alt. / Peso", help="Altezza in m, oppure peso unitario"),
            "quantita_manuale": st.column_config.NumberColumn(
                "Quantità (manuale)",
                help="Compilala solo se lasci vuote le dimensioni"),
            "prezzo": st.column_config.NumberColumn(
                "Prezzo unit. (€)", format="%.2f"),
        },
    )
    st.session_state.df_voci = df_editato

    voci = voci_da_df(df_editato)
    voci_calcolate = calcoli.calcola_computo(voci)

    if not voci_calcolate:
        st.info("Aggiungi la prima voce nella tabella qui sopra, oppure misura "
                "una stanza nella scheda «Misura da planimetria».")
    else:
        st.subheader("2 · Computo calcolato")
        df_calcolato = pd.DataFrame(voci_calcolate).reindex(
            columns=COLONNE + ["quantita", "importo"])
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

        st.subheader("3 · Riepilogo")
        totali = calcoli.totali_per_categoria(voci_calcolate)
        totale = calcoli.totale_generale(voci_calcolate)
        incidenze = calcoli.incidenze_percentuali(totali, totale)
        iva_importo, totale_ivato = calcoli.totale_con_iva(
            totale, st.session_state.iva)

        df_riepilogo = pd.DataFrame({
            "Categoria": list(totali),
            "Importo": [totali[c] for c in totali],
            "Incidenza %": [incidenze[c] for c in totali],
        }).sort_values("Importo", ascending=False, ignore_index=True)

        col_tabella, col_grafico = st.columns([2, 3])
        with col_tabella:
            st.dataframe(
                pd.DataFrame({
                    "Categoria": df_riepilogo["Categoria"],
                    "Importo": df_riepilogo["Importo"].map(euro),
                    "Incidenza": df_riepilogo["Incidenza %"].map(
                        lambda p: numero_it(p, 2) + " %"),
                }),
                hide_index=True,
            )
        with col_grafico:
            if len(totali) >= 2:
                st.plotly_chart(grafico_totali(totali),
                                config={"displayModeBar": False})

        col1, col2, col3 = st.columns(3)
        col1.metric("Totale lavori", euro(totale))
        col2.metric(f"IVA {numero_it(st.session_state.iva, 0)}%",
                    euro(iva_importo))
        col3.metric("Totale IVA inclusa", euro(totale_ivato))

        st.subheader("4 · Salva ed esporta")
        st.caption("Il file **.json** è il salvataggio del lavoro: conservalo e "
                   "ricaricalo dalla barra laterale per riprendere. Excel e CSV "
                   "servono per consegnare o rielaborare il computo.")

        progetto = {
            "nome": st.session_state.prg_nome,
            "committente": st.session_state.prg_committente,
            "oggetto": st.session_state.prg_oggetto,
            "data": st.session_state.prg_data.isoformat(),
            "aliquota_iva": st.session_state.iva,
        }
        df_riepilogo_excel = pd.concat([
            df_riepilogo,
            pd.DataFrame({
                "Categoria": ["Totale lavori",
                              f"IVA {numero_it(st.session_state.iva, 0)}%",
                              "Totale IVA inclusa"],
                "Importo": [totale, iva_importo, totale_ivato],
                "Incidenza %": [100.0, None, None],
            }),
        ], ignore_index=True)
        df_progetto_excel = pd.DataFrame({
            "Campo": ["Nome", "Committente", "Oggetto", "Data", "Aliquota IVA %"],
            "Valore": [progetto["nome"], progetto["committente"],
                       progetto["oggetto"], progetto["data"],
                       progetto["aliquota_iva"]],
        })

        col_json, col_xlsx, col_csv = st.columns(3)
        col_json.download_button(
            "💾 Salva computo (.json)",
            data=json.dumps({"progetto": progetto, "voci": voci},
                            ensure_ascii=False, indent=2).encode("utf-8"),
            file_name=nome_file("json"),
            mime="application/json",
        )
        col_xlsx.download_button(
            "📊 Esporta Excel (.xlsx)",
            data=excel_bytes(df_calcolato, df_riepilogo_excel, df_progetto_excel),
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
    st.subheader("Misura le superfici da una planimetria")
    with st.expander("ℹ️ Come funziona (leggimi la prima volta)"):
        st.markdown("""
Il metodo è quello dei software professionali: si dice al programma **quanto
vale una misura nota** sul disegno, e da lì calcola tutte le altre.

1. **Carica** la planimetria (foto, scansione o PDF). Deve avere almeno una
   **quota nota** (una misura scritta, es. un lato di 4,50 m).
2. **Calibra la scala**: clicca i due estremi di quella misura nota sul
   disegno e scrivi quanti metri vale. *Più lungo è il segmento che scegli,
   più precisa sarà la misura.*
3. **Misura le stanze**: clicca uno dopo l'altro gli angoli di una stanza; il
   perimetro si chiude da solo e ottieni la **superficie in m²**.
4. **Aggiungi al computo**: la superficie diventa una voce nella scheda
   «Computo metrico».

⚠️ La precisione dipende dalla qualità del disegno e dalla cura dei click:
è pensata per stime e computi, non per usi catastali di precisione.
""")

    file_plan = st.file_uploader(
        "Carica la planimetria (PNG, JPG o PDF)",
        type=["png", "jpg", "jpeg", "pdf"])

    if file_plan is not None:
        sig = (file_plan.name, file_plan.size)
        if sig != st.session_state.plan_sig:
            try:
                st.session_state.plan_img = carica_immagine(file_plan)
                st.session_state.plan_sig = sig
                st.session_state.mpp = None
                st.session_state.punti_cal = []
                st.session_state.punti_stanza = []
                st.session_state.ts_cal = None
                st.session_state.ts_st = None
            except Exception as errore:  # noqa: BLE001
                st.error(f"Non riesco a leggere questo file: {errore}")

    base = st.session_state.plan_img
    if base is None:
        st.info("Carica una planimetria qui sopra per iniziare.")
    else:
        if st.session_state.mpp:
            st.success(
                f"✅ Scala impostata: 1 metro = "
                f"{numero_it(1 / st.session_state.mpp, 1)} px sul disegno.")
        else:
            st.warning("⚠️ Scala non ancora impostata: comincia dal passo 1.")

        modo = st.radio(
            "Cosa vuoi fare?",
            ["1 · Calibra la scala", "2 · Misura una stanza"],
            horizontal=True)

        # ---------------------------------------------------- calibrazione
        if modo.startswith("1"):
            st.caption("Clicca i **due estremi** di una misura che conosci "
                       "(es. un lato quotato). Puoi rifare il tiro col "
                       "bottone «Ricomincia».")
            punti = st.session_state.punti_cal
            img_cal = disegna_overlay(base, punti, COL_CAL_LINEA,
                                      COL_CAL_PUNTO, chiudi=False)
            valore = streamlit_image_coordinates(
                img_cal, width=base.width, key="click_cal", cursor="crosshair")
            if gestisci_click(valore, "ts_cal", punti, massimo=2):
                st.rerun()

            col_a, col_b = st.columns(2)
            with col_a:
                if st.button("↩️ Ricomincia calibrazione"):
                    st.session_state.punti_cal = []
                    st.rerun()
            if len(punti) < 2:
                st.info(f"Punti inseriti: {len(punti)} di 2.")
            else:
                dist_px = planimetria.distanza_pixel(punti[0], punti[1])
                st.write(f"Segmento tracciato: **{numero_it(dist_px, 0)} px**.")
                with col_b:
                    reale = st.number_input(
                        "Quanto misura realmente? (metri)",
                        min_value=0.0, step=0.01, value=0.0, format="%.2f",
                        key="cal_reale")
                if st.button("📏 Imposta la scala", type="primary"):
                    if reale > 0:
                        st.session_state.mpp = planimetria.metri_per_pixel(
                            dist_px, reale)
                        st.success("Scala impostata! Passa al punto 2.")
                        st.rerun()
                    else:
                        st.error("Scrivi la misura reale in metri (> 0).")

        # ------------------------------------------------------- misura stanza
        else:
            if not st.session_state.mpp:
                st.info("Prima imposta la scala (punto 1).")
            else:
                st.caption("Clicca **uno dopo l'altro gli angoli** della "
                           "stanza. Servono almeno 3 punti; il perimetro si "
                           "chiude da solo.")
                punti = st.session_state.punti_stanza
                img_st = disegna_overlay(base, punti, COL_ST_LINEA,
                                         COL_ST_PUNTO, chiudi=True,
                                         riempi_col=COL_ST_FILL)
                valore = streamlit_image_coordinates(
                    img_st, width=base.width, key="click_st",
                    cursor="crosshair")
                if gestisci_click(valore, "ts_st", punti):
                    st.rerun()

                col_x, col_y = st.columns(2)
                with col_x:
                    if st.button("↩️ Annulla ultimo punto") and punti:
                        punti.pop()
                        st.rerun()
                with col_y:
                    if st.button("🔄 Nuova stanza (cancella punti)"):
                        st.session_state.punti_stanza = []
                        st.rerun()

                if len(punti) < 3:
                    st.info(f"Angoli inseriti: {len(punti)} (min. 3).")
                else:
                    mpp = st.session_state.mpp
                    area = planimetria.area_reale_m2(punti, mpp)
                    perim = planimetria.perimetro_reale_m(punti, mpp)
                    c1, c2 = st.columns(2)
                    c1.metric("Superficie", f"{numero_it(area, 2)} m²")
                    c2.metric("Perimetro", f"{numero_it(perim, 2)} m")

                    st.markdown("**Aggiungi questa stanza al computo:**")
                    d1, d2, d3 = st.columns(3)
                    nome_stanza = d1.text_input(
                        "Descrizione", value="Superficie stanza",
                        key="st_nome")
                    cat_stanza = d2.text_input(
                        "Categoria", value="Superfici", key="st_cat")
                    prezzo_stanza = d3.number_input(
                        "Prezzo €/m² (facolt.)", min_value=0.0, step=0.01,
                        value=0.0, format="%.2f", key="st_prezzo")
                    if st.button("➕ Aggiungi al computo", type="primary"):
                        aggiungi_voce_computo(
                            cat_stanza, nome_stanza, "m²",
                            round(area, 2), prezzo_stanza)
                        st.session_state.punti_stanza = []
                        st.success(
                            f"«{nome_stanza}» ({numero_it(area, 2)} m²) "
                            "aggiunta al computo. La trovi nella scheda "
                            "«Computo metrico».")
                        st.rerun()
