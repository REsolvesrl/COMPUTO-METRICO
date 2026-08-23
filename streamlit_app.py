"""CME — Computo Metrico Estimativo.

Interfaccia Streamlit a due schede:
1. Computo metrico — tabella voci, quantità calcolate, totali, export.
2. Misura da planimetria — più planimetrie per progetto, zone colorate per
   categoria con percentuale commerciale, scala a vettore, misura pareti e
   riepilogo delle superfici commerciali del fabbricato.

La logica di calcolo vive in calcoli.py; la geometria in planimetria.py;
il visualizzatore interattivo in cme_viewer/.

CONTRATTO DI DIREZIONE — mondo «Campionario» (regole complete in DESIGN.md)

TESI: un campionario di materiali edili, non un gestionale. Rifiuta sia la
scheda bianca arrotondata con accento blu, sia lo scuro con i neon.
MONDO: ardesia come banco di lavoro, ottone per le azioni, travertino per il
testo; cotto, cemento e gres verde come materia. Tinte piene che occupano
superfici, mai texture; etichette in maiuscoletto spaziato con il loro codice,
come su un campione vero; cifre incolonnate.
STORIA: chi apre capisce in un attimo che è uno strumento di mestiere, e che
il pezzo da guardare è il disegno, non la cornice.
PRIMO COLPO D'OCCHIO: testata bassa col nome del progetto come etichetta di
campione; le tre schede come linguette di una cartella; sotto, il lavoro a
piena larghezza.
FORMA: settima della lista ordinata, assegnata dal sorteggio (chiave
bc421ec2), scelta dall'utente contro le alternative Mirino e Griglia.
"""

# «Scatola nera» per i crash nativi: un segmentation fault dentro una libreria
# in C (OpenCV, PyMuPDF, pyarrow…) uccide l'interprete senza traceback, e nei
# log resta solo «Segmentation fault». Con faulthandler attivo Python stampa
# comunque lo stack, quindi si vede in quale riga e in quale libreria è morto.
# Va abilitato prima delle librerie pesanti, per coprirne anche l'import.
import faulthandler

faulthandler.enable()

import base64
import copy
import hashlib
import hmac
import io
import json
import os
from datetime import date, datetime
from pathlib import Path

import fitz  # PyMuPDF, per leggere i PDF
import pandas as pd
import plotly.graph_objects as go
import streamlit as st
from PIL import Image

import archivio
import archivio_locale
import calcoli
import cantiere
import fattibilita
import fattura
import listino
import listino_personale
import materiali
import merito
import stampa
import storico
from formato import colore_testo_su, euro, numero_da_it, numero_it
from tabelle import (
    CATEGORIE_SPESE_EMOJI,
    COLONNA_IMPORTO_MAT,
    COLONNA_IVA_EUR,
    COLONNE,
    COLONNE_MATERIALI,
    COLONNE_MCA,
    COLONNE_NUMERI,
    COLONNE_SPESE,
    COLONNE_SPESE_NUM,
    COLONNE_SPESE_PREV,
    COLONNE_TESTO,
    EMOJI_CATEGORIA,
    cat_display,
    cat_pulita,
    df_materiali_da_righe,
    df_materiali_vuoto,
    df_mca_vuoto,
    df_spese_da_righe,
    df_spese_vuoto,
    df_vuoto,
    materiali_da_df,
    mca_da_df,
    senza_importo_derivato,
    senza_iva_derivata,
    spese_da_df,
    voci_da_df,
)
import planimetria
import rilevamento
from cme_viewer import image_viewer, pil_a_src


def _versioni_native():
    """Versioni delle librerie in C, scritte nei log a ogni avvio.

    requirements.txt non fissa le dipendenze indirette (pyarrow, protobuf…):
    ogni ambiente se le sceglie da sé, quindi il server può avere versioni
    diverse da quelle collaudate in locale. Quando l'app muore di
    segmentation fault, questa riga dice contro quali versioni è successo.
    """
    import sys

    voci = [f"python {sys.version.split()[0]}"]
    for nome, modulo in (("numpy", "numpy"), ("pandas", "pandas"),
                         ("pyarrow", "pyarrow"), ("streamlit", "streamlit"),
                         ("opencv", "cv2"), ("pillow", "PIL"),
                         ("pymupdf", "pymupdf")):
        try:
            voci.append(f"{nome} {__import__(modulo).__version__}")
        except Exception:
            voci.append(f"{nome} ?")
    return " · ".join(voci)


print("CME versioni native:", _versioni_native(), flush=True)

st.set_page_config(
    page_title="CME — Computo Metrico",
    page_icon="🏗️",
    layout="wide",
)

# --------------------------------------------------------- mondo «Campionario»
# I materiali del campionario. Sono variabili CSS così che una sola riga qui
# cambi tutta l'app, e sono gli stessi valori scritti in DESIGN.md.
ARDESIA = "#1A2744"
ARDESIA_CHIARA = "#243352"
OTTONE = "#C9A96A"
TRAVERTINO = "#ECE7DA"
COTTO = "#C1502E"
CEMENTO = "#6E7377"
GRES = "#4E7A5E"


def css_mondo():
    """Il foglio di stile del mondo: materia, etichette, cifre, linguette."""
    return f"""
<style>
:root {{
    --ardesia: {ARDESIA};
    --ardesia-chiara: {ARDESIA_CHIARA};
    --ottone: {OTTONE};
    --travertino: {TRAVERTINO};
    --cotto: {COTTO};
    --cemento: {CEMENTO};
    --gres: {GRES};
    /* Pila di sistema: nessun carattere scaricato dalla rete, perché il
       programma deve funzionare con la connessione staccata. */
    --testo: "Segoe UI Variable Text", "Segoe UI", system-ui, sans-serif;
}}

/* Il carattere si dichiara UNA volta sulla radice e scende per eredità.
   ⚠️ Non allargare questa regola a span/div: le icone di Streamlit sono
   legature di un carattere apposito (la parola «upload» diventa il disegno
   di una freccia). Imporre lì il carattere del testo fa comparire la parola
   al posto dell'icona, sovrapposta all'etichetta. Successo il 2026-08-08. */
.stApp {{ font-family: var(--testo); }}

/* L'eredità però non basta: Streamlit rimette «Source Sans» sui propri
   elementi con selettori più specifici, e misurando dal vivo la pila
   dichiarata perdeva 99 foglie di testo a 5. Il carattere scritto in
   DESIGN.md non era quello a schermo quasi da nessuna parte.
   ⚠️ span e div restano fuori di proposito, per l'avvertimento qui sopra:
   qui ci sono solo elementi che non possono essere un'icona. */
.stApp p, .stApp label, .stApp li, .stApp td, .stApp th,
.stApp input, .stApp textarea, .stApp button,
.stApp h1, .stApp h2, .stApp h3, .stApp h4, .stApp h5, .stApp h6 {{
    font-family: var(--testo);
}}

/* Le cifre si confrontano di continuo (quantità, prezzi, superfici): vanno
   incolonnate, altrimenti l'occhio non le può sommare a vista. Questa invece
   può essere larga: è una funzione del carattere, non il carattere. */
.stApp, .stApp p, .stApp span, .stApp div, .stApp td, .stApp th,
.stApp input, .stApp label {{
    font-variant-numeric: tabular-nums;
}}

/* Cintura e bretelle: qualunque cosa Streamlit consideri un'icona tiene il
   proprio carattere, qualsiasi altra regola dica il contrario. */
.stApp [class*="material-symbols"],
.stApp [data-testid="stIconMaterial"],
.stApp .material-icons, .stApp span[translate="no"] {{
    font-family: "Material Symbols Rounded", "Material Symbols Outlined",
                 "Material Icons" !important;
    font-variant-numeric: normal;
}}

/* ---------------------------------------------------------- testata */
/* La cartiglio: nome dello strumento e, accanto, il progetto aperto scritto
   come l'etichetta di un campione. Bassa, perché il lavoro viene prima. */
.cme-testata {{
    display: flex;
    align-items: baseline;
    gap: 1.1rem;
    flex-wrap: wrap;
    padding: .1rem 0 .55rem;
    border-bottom: 1px solid color-mix(in srgb, var(--ottone) 38%, transparent);
    margin-bottom: 1.1rem;
}}
.cme-testata h1 {{
    font-size: 2.05rem;
    font-weight: 650;
    letter-spacing: -.01em;
    margin: 0;
    color: var(--travertino);
}}
.cme-testata .sigla {{
    color: var(--ottone);
    font-weight: 700;
}}
/* L'etichetta di campione: la voce del sistema. Nomina, non racconta.
   Il cemento pieno su ardesia sta a 3,1:1, sotto la soglia di leggibilità
   proprio nella riga che nomina le cose. La miscela col travertino era già
   scritta per le metriche e non era mai arrivata qui, cioè nella classe
   che la regola nomina. Resta la voce del cemento, ma si legge. */
.cme-etichetta {{
    font-size: .7rem;
    text-transform: uppercase;
    letter-spacing: .12em;
    color: color-mix(in srgb, var(--travertino) 78%, var(--cemento));
    font-weight: 600;
}}
.cme-testata .progetto {{
    color: var(--travertino);
    font-size: .82rem;
    letter-spacing: .02em;
    padding: .12rem .5rem;
    border: 1px solid color-mix(in srgb, var(--ottone) 45%, transparent);
    background: color-mix(in srgb, var(--ottone) 12%, transparent);
}}
/* Lo stato del salvataggio, sempre sott'occhio: stava solo in fondo alla
   scheda computo, cioè proprio dove non si guarda mentre si lavora. */
/* La data del codice in funzione: serve a sapere se si sta guardando la
   versione aggiornata o quella di prima. Senza, si inseguono difetti già
   corretti convinti che siano ancora lì. */
.cme-testata .versione {{
    font-size: .68rem;
    letter-spacing: .04em;
    color: color-mix(in srgb, var(--travertino) 55%, var(--cemento));
    white-space: nowrap;
}}
.cme-testata .salvataggio {{
    margin-left: auto;
    font-size: .72rem;
    letter-spacing: .04em;
    padding: .12rem .5rem;
    white-space: nowrap;
}}
.cme-testata .salvataggio.pari {{
    color: #9FD6AC;
    border: 1px solid color-mix(in srgb, {GRES} 75%, transparent);
    background: color-mix(in srgb, {GRES} 22%, transparent);
}}
.cme-testata .salvataggio.sospeso {{
    color: #F2B79E;
    border: 1px solid color-mix(in srgb, {COTTO} 70%, transparent);
    background: color-mix(in srgb, {COTTO} 20%, transparent);
}}

/* ------------------------------------------------------- linguette */
/* Le tre schede sono le linguette di una cartella di campioni: quella aperta
   è piena d'ottone, le altre restano pietra. */
.stTabs [data-baseweb="tab-list"] {{
    gap: .35rem;
    border-bottom: 1px solid color-mix(in srgb, var(--ottone) 25%, transparent);
}}
.stTabs [data-baseweb="tab"] {{
    background: color-mix(in srgb, var(--travertino) 6%, transparent);
    border: 1px solid transparent;
    border-bottom: none;
    padding: .5rem 1.1rem;
    color: color-mix(in srgb, var(--travertino) 72%, transparent);
    font-weight: 600;
}}
.stTabs [data-baseweb="tab"]:hover {{
    background: color-mix(in srgb, var(--ottone) 14%, transparent);
    color: var(--travertino);
}}
.stTabs [aria-selected="true"] {{
    background: color-mix(in srgb, var(--ottone) 22%, transparent);
    border-color: color-mix(in srgb, var(--ottone) 55%, transparent);
    color: var(--travertino) !important;
}}
.stTabs [data-baseweb="tab-highlight"] {{ background: var(--ottone); }}

/* --------------------------------------------------------- azioni */
/* Ottone pieno per l'azione principale, contorno per le altre: due azioni
   piene affiancate si contendono lo sguardo e nessuna delle due vince. */
.stButton > button[kind="secondary"] {{
    border: 1px solid color-mix(in srgb, var(--ottone) 45%, transparent);
    background: transparent;
    color: var(--travertino);
}}
.stButton > button[kind="secondary"]:hover {{
    border-color: var(--ottone);
    background: color-mix(in srgb, var(--ottone) 14%, transparent);
    color: var(--travertino);
}}
/* Sull'ottone pieno la cifra è ardesia: la scheda del totale lo fa da
   sempre e si legge a 6,6:1, ma i bottoni primari tenevano il bianco che
   ci mette Streamlit e stavano a 2,24:1 — il contrasto peggiore di tutta
   l'app, proprio sull'azione che si preme di più. Lo stesso difetto era
   già stato corretto dentro il visualizzatore a luglio, e non era mai
   arrivato qui.
   ⚠️ Discendente, non figlio: quando un bottone ha un `help=`, Streamlit
   gli infila attorno il bersaglio del tooltip, e `.stButton > button` non
   lo raggiunge più — erano proprio «Salva» e «Prepara il file», cioè i due
   che si premono di più. E `:not(:disabled)`: un bottone spento ha il
   fondo trasparente, e l'ardesia su ardesia sparisce (misurato a 1,42:1
   su «Chiudi l'operazione» prima di questa riga). */
.stApp .stButton button[kind="primary"]:not(:disabled),
.stApp .stDownloadButton button[kind="primary"]:not(:disabled),
.stApp .stFormSubmitButton button[kind="primary"]:not(:disabled) {{
    color: var(--ardesia);
    font-weight: 650;
}}
.stApp .stButton button[kind="primary"]:not(:disabled):hover,
.stApp .stDownloadButton button[kind="primary"]:not(:disabled):hover,
.stApp .stFormSubmitButton button[kind="primary"]:not(:disabled):hover {{
    color: var(--ardesia);
}}
/* Le azioni che distruggono si vestono di cotto: non devono somigliare a
   un'azione qualsiasi, e nemmeno all'ottone che invece invita a premere. */
[class*="st-key-nuovo_dopo_ripresa"] button,
[class*="st-key-nuovo_progetto"] button {{
    border: 1px solid color-mix(in srgb, var(--cotto) 60%, transparent);
    color: var(--cotto);
    background: transparent;
}}
[class*="st-key-nuovo_dopo_ripresa"] button:hover:not(:disabled),
[class*="st-key-nuovo_progetto"] button:hover:not(:disabled) {{
    border-color: var(--cotto);
    background: color-mix(in srgb, var(--cotto) 16%, transparent);
    color: var(--travertino);
}}
.stButton > button:focus-visible,
.stDownloadButton > button:focus-visible {{
    outline: 2px solid var(--ottone);
    outline-offset: 2px;
}}
/* L'anello d'ottone copriva i bottoni e basta: su ~250 fra caselle di
   testo, numeri, date e menù non c'era nulla: il contorno a riposo del
   contenitore è dello stesso colore del suo fondo, quindi chi va con il
   Tab attraversava il computo al buio. Il fuoco si mette sul contenitore
   (`:focus-within`) perché il bordo visibile è suo, non dell'input. */
.stApp input:focus-visible,
.stApp textarea:focus-visible,
.stApp [data-baseweb="input"]:focus-within,
.stApp [data-baseweb="textarea"]:focus-within,
.stApp [data-baseweb="select"]:focus-within,
.stApp [data-baseweb="popover"] li:focus-visible,
.stApp [role="checkbox"]:focus-visible,
.stApp [role="radio"]:focus-visible,
.stApp [role="tab"]:focus-visible,
.stApp summary:focus-visible,
.stApp a:focus-visible {{
    outline: 2px solid var(--ottone);
    outline-offset: 1px;
}}
/* Il fondo del bottoncino su/giù dei campi numerici e il selettore data
   hanno un contorno proprio: senza questo l'anello resta coperto. */
.stApp [data-baseweb="input"]:focus-within,
.stApp [data-baseweb="select"]:focus-within {{
    border-color: var(--ottone);
}}

/* ------------------------------------------------ campioni di misura */
/* Ogni metrica è un campione: l'etichetta piccola in maiuscoletto nomina,
   il numero grande sotto è il protagonista. Fondo rialzato e squadrato,
   perché la profondità viene dal materiale e non da un'ombra. */
[data-testid="stMetric"] {{
    background: var(--ardesia-chiara);
    border: 1px solid color-mix(in srgb, var(--ottone) 26%, transparent);
    padding: .55rem .7rem .6rem;
}}
[data-testid="stMetricLabel"],
[data-testid="stMetricLabel"] p {{
    font-size: .7rem;
    text-transform: uppercase;
    letter-spacing: .12em;
    font-weight: 600;
    color: color-mix(in srgb, var(--travertino) 78%, var(--cemento));
}}
[data-testid="stMetricValue"] {{
    color: var(--travertino);
    font-weight: 700;
    line-height: 1.15;
}}
[data-testid="stMetricDelta"] {{ font-size: .78rem; }}
/* Un numero tagliato non è un numero: «97,32 …» non dice né quanto né di
   che cosa. Streamlit taglia con i puntini quello che non ci sta; qui si
   preferisce andare a capo, sempre — l'unità di misura fa parte del dato. */
[data-testid="stMetricLabel"],
[data-testid="stMetricLabel"] p,
[data-testid="stMetricValue"] {{
    white-space: normal;
    overflow: visible;
    text-overflow: clip;
    max-width: 100%;
}}
/* Sotto la tela i campioni sono sei in fila: la cifra scende di taglia
   quanto basta a starci intera con la sua unità. */
.st-key-totali_tela [data-testid="stMetricValue"] {{ font-size: 1.45rem; }}
.st-key-totali_tela [data-testid="stMetric"] {{
    padding: .5rem .55rem .55rem;
}}
.st-key-totali_tela [data-testid="stMetricLabel"],
.st-key-totali_tela [data-testid="stMetricLabel"] p {{
    font-size: .64rem;
    letter-spacing: .08em;
}}

/* -------------------------------------------- il disegno comanda */
/* La tela è il pezzo vero appoggiato sul piano da lavoro: fondo rialzato e
   contorno d'ottone, il contrasto più alto della scheda. */
.st-key-tela {{
    background: var(--ardesia-chiara);
    border: 1px solid color-mix(in srgb, var(--ottone) 45%, transparent);
    padding: .5rem;
    margin-bottom: .85rem;
}}
/* Il disegno comanda, ma non comandava: il componente è un iframe e
   Streamlit gli lasciava la larghezza intrinseca, 300 px dentro uno slot
   da 982. La tela restava un francobollo in mezzo alla cornice d'ottone,
   e i 682 px vuoti facevano sembrare il guasto una scelta. Stesso
   `!important` delle tabelle: la misura sbagliata Streamlit la scrive
   nello stile in riga, e solo così si vince. */
.st-key-tela [data-testid="stCustomComponentV1"] {{
    width: 100% !important;
}}
.st-key-tela [data-testid="stCustomComponentV1"] iframe {{
    width: 100% !important;
}}
/* I pannelli dei comandi stanno attorno in cemento, mai in competizione col
   disegno: raggruppano i campi che altrimenti sarebbero una fila indistinta
   di caselle. */
[class*="st-key-pan_"] {{
    border: 1px solid color-mix(in srgb, var(--cemento) 55%, transparent);
    background: color-mix(in srgb, var(--cemento) 9%, transparent);
    padding: .75rem .9rem .35rem;
    margin-bottom: .75rem;
}}

/* Contenitori tecnici: servono solo a far girare uno script, e Streamlit
   lasciava comunque il loro ingombro a video — un trattino che spuntava in
   mezzo alla pagina, su ogni scheda. Nascosti: l'iframe resta nel documento
   e lo script gira lo stesso. */
[class*="st-key-cme_script_"] {{ display: none; }}

/* ---------------------------------------------------- stato vuoto */
/* Una cartella di campioni aperta, non un riquadro grigio con una frase:
   dice cosa succede dopo e mette l'azione a portata. */
.cme-vuoto {{
    border: 1px solid color-mix(in srgb, var(--ottone) 30%, transparent);
    background: var(--ardesia-chiara);
    padding: 1.6rem 1.7rem 1.4rem;
    margin-bottom: .9rem;
}}
.cme-vuoto .campioni {{
    display: flex;
    gap: .4rem;
    margin-bottom: 1.1rem;
}}
.cme-vuoto .campioni i {{
    display: block;
    width: 46px;
    height: 30px;
}}
.cme-vuoto h3 {{
    margin: 0 0 .4rem;
    font-size: 1.15rem;
    font-weight: 650;
    color: var(--travertino);
}}
.cme-vuoto p {{
    margin: 0;
    max-width: 62ch;
    color: color-mix(in srgb, var(--travertino) 82%, transparent);
    line-height: 1.55;
}}

/* Il testo dei riquadri «info» usciva a 2,7:1 sul fondo ardesia: sotto
   qualsiasi soglia, proprio dove l'app spiega cosa fare. */
[data-testid="stAlertContentInfo"], [data-testid="stAlertContentInfo"] p {{
    color: #D7DEEA;
}}
/* Le didascalie occupavano tutta la larghezza della pagina: righe da 200
   caratteri, ben oltre la misura in cui l'occhio ritrova l'inizio della riga
   dopo. Il limite non allarga nulla, taglia solo le righe troppo lunghe. */
[data-testid="stCaptionContainer"] {{ max-width: 82ch; }}

/* ---- La tabella dei comparabili scorre di lato --------------------- */
/* Venti colonne: le tre dei dati, le quindici della griglia di merito, il
   coefficiente a mano e le note. Con le larghezze fissate delle tendine la
   tabella misura circa 2.040 px, il contenitore ne dà 1.100, e OGNI
   antenato ha `overflow-x: visible` — così le ultime colonne non finivano
   sotto una barra di scorrimento: sparivano tagliate, e «Riscaldamento»
   non esisteva per chi guardava. Misurato dal vivo: 2.046 px di contenuto
   in 1.099 di spazio.

   ⚠️ La regola va sul contenitore dell'ELEMENTO, non sulla tabella: è la
   tabella a essere larga 2.040, e un `overflow` su di lei non avrebbe
   nulla da contenere. La classe la genera la chiave del data_editor
   (`editor_mca_<versione>`), la stessa che qui sotto serve alla barra
   degli strumenti — per questo il selettore è a sottostringa. */
[class*="st-key-editor_mca"] {{ overflow-x: auto; }}

/* ---- La barra degli strumenti delle tabelle ------------------------ */
/* Aggiungi riga · mostra colonne · scarica CSV · cerca · schermo intero.
   Streamlit la tiene a opacità ZERO finché non ci passi sopra col mouse,
   con bottoni da 22 px e icone da 16: invisibile a chi non sa già che
   c'è, mentre «aggiungi riga» e «cerca» sono gesti di tutti i giorni.
   Diventa un attrezzo appoggiato sul banco — sempre in vista, squadrata,
   fondo rialzato e contorno d'ottone come i pannelli della planimetria.
 */
.st-key-editor_sal [data-testid="stElementToolbar"],
[class*="st-key-editor_spese"] [data-testid="stElementToolbar"],
[class*="st-key-editor_voci"] [data-testid="stElementToolbar"],
[class*="st-key-editor_mca"] [data-testid="stElementToolbar"],
[class*="st-key-anteprima_fatt"] [data-testid="stElementToolbar"] {{
    opacity: 1;
    /* tutta SOPRA la tabella: con lo sfondo pieno, la posizione originale
       (top -16px) coprirebbe la riga delle intestazioni */
    top: -56px;
    background: var(--ardesia-chiara);
    border: 1px solid color-mix(in srgb, var(--ottone) 45%, transparent);
    border-radius: 0;
    padding: 4px;
    gap: 2px;
}}
.st-key-editor_sal [data-testid="stElementToolbar"] button,
[class*="st-key-editor_spese"] [data-testid="stElementToolbar"] button,
[class*="st-key-editor_voci"] [data-testid="stElementToolbar"] button,
[class*="st-key-editor_mca"] [data-testid="stElementToolbar"] button,
[class*="st-key-anteprima_fatt"] [data-testid="stElementToolbar"] button {{
    width: 34px;
    height: 34px;
    padding: 7px;
    border-radius: 0;
}}
/* L'icona si prende per il suo identificativo, non con «button span»: la
   regola di Streamlit la fissa a 14,4 px e vince di specificità, quindi
   i bottoni diventavano grandi e i disegni dentro restavano piccoli.
   Il `!important` qui è la scorciatoia onesta — l'alternativa sarebbe una
   catena di selettori che si rompe al prossimo aggiornamento. */
.st-key-editor_sal [data-testid="stElementToolbarButtonIcon"],
[class*="st-key-editor_spese"] [data-testid="stElementToolbarButtonIcon"],
[class*="st-key-editor_voci"] [data-testid="stElementToolbarButtonIcon"],
[class*="st-key-editor_mca"] [data-testid="stElementToolbarButtonIcon"],
[class*="st-key-anteprima_fatt"] [data-testid="stElementToolbarButtonIcon"] {{
    font-size: 20px !important;
    width: 20px !important;
    height: 20px !important;
}}
.st-key-editor_sal [data-testid="stElementToolbar"] button:hover,
[class*="st-key-editor_spese"] [data-testid="stElementToolbar"] button:hover,
[class*="st-key-editor_voci"] [data-testid="stElementToolbar"] button:hover,
[class*="st-key-editor_mca"] [data-testid="stElementToolbar"] button:hover,
[class*="st-key-anteprima_fatt"] [data-testid="stElementToolbar"]
 button:hover {{
    background: var(--ottone);
    color: var(--ardesia);
}}
/* ⚠️ E le tabelle DEVONO essere larghe quanto il loro posto, o la barra
   non ci sta. Streamlit misura la tela al momento in cui nasce: quelle
   che nascono dentro una scheda ancora chiusa la misurano a zero e
   restano un moncone largo 52 px (misurato dal vivo su MCA e SAL, e non
   si riprendono più nemmeno riaprendo la scheda). Finché la barra era
   invisibile la cosa passava; adesso una barra da 188 px appesa al bordo
   destro di una tabella da 52 finisce fuori dallo schermo, a sinistra.
   Il `!important` serve perché la misura sbagliata Streamlit la scrive
   nello stile in riga, e solo così si vince. */
.st-key-editor_sal [data-testid="stDataFrameResizable"],
[class*="st-key-editor_spese"] [data-testid="stDataFrameResizable"],
[class*="st-key-editor_voci"] [data-testid="stDataFrameResizable"],
[class*="st-key-editor_mca"] [data-testid="stDataFrameResizable"],
[class*="st-key-anteprima_fatt"] [data-testid="stDataFrameResizable"] {{
    width: 100% !important;
    min-width: 100% !important;
    max-width: 100% !important;
}}

/* Accanto al titolo, non orfana in fondo a destra: nella colonna larga
   del registro spese la barra finiva a un metro dal nome della tabella su
   cui agisce. I due titoli misurano 195 e 220 px, quindi da 236 px in poi
   si è liberi in entrambe. Vale solo dove SOPRA c'è un titolo corto: le
   altre tabelle hanno didascalie lunghe, e lì la barra resta a destra. */
[class*="st-key-editor_spese"] [data-testid="stElementToolbar"] {{
    left: 236px;
    right: auto;
}}
</style>
"""


def campione_vuoto(titolo, testo, tinte=(COTTO, OTTONE, GRES, CEMENTO)):
    """Stato vuoto: la cartella di campioni aperta, con la sua spiegazione."""
    pastiglie = "".join(f'<i style="background:{t}"></i>' for t in tinte)
    return (f'<div class="cme-vuoto"><div class="campioni">{pastiglie}</div>'
            f'<h3>{titolo}</h3><p>{testo}</p></div>')


st.markdown(css_mondo(), unsafe_allow_html=True)

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


UM_OPZIONI = ["m", "m²", "m³", "kg", "t", "cad", "h", "a corpo",
              "punto", "utenza"]

# Colori delle categorie del listino: (pallino/hex, colore markdown titolo).
COLORI_CATEGORIE = {
    # travertino: è l'unico capitolo che non è materia da cantiere ma carta,
    # e nel campionario la carta ha il colore della carta
    "Pratiche e oneri": ("#ECE7DA", "gray"),
    "Demolizioni": ("#E57373", "red"),
    "Ricostruzioni e ripristini": ("#66BB6A", "green"),
    "Idraulico": ("#64B5F6", "blue"),
    "Elettricista": ("#F0A840", "orange"),
    "Serramenti": ("#9575CD", "violet"),
    "Aree esterne": ("#B0BEC5", "gray"),
}

# Voci del listino ricavabili dalle superfici misurate sulla planimetria:
# (codice, grandezza da cui prendere la quantità, accesa di default).
# Accese quelle che valgono in ogni ristrutturazione. La demolizione dei
# pavimenti (1.01) è fra queste: se si rifà il pavimento, prima si butta giù
# quello che c'è — e i metri sono gli stessi che si riposano. Restano spente
# la rimozione degli zoccolini, il massetto e la rasatura, che dipendono da
# cosa si trova in cantiere.
VOCI_DA_SUPERFICI = [
    # ⚠️ «pavimento» sono le stanze e basta: balconi, terrazzi e logge
    # stanno in «pavimento_esterno» e vanno nella 2.24, che è un'altra
    # lavorazione. Una demolizione di pavimenti interni non deve portarsi
    # dentro i metri del balcone.
    ("1.01", "pavimento", True),          # demolizione pavimenti
    ("1.10", "battiscopa", False),        # rimozione zoccolini
    ("2.03", "pavimento", False),         # rifacimento massetto
    ("2.10", "pavimento", True),          # posa gres
    ("2.11", "rivestimenti", True),       # rivestimenti (fascia dei bagni)
    ("2.24", "pavimento_esterno", True),  # pavimentazione di balconi e terrazzi
    ("2.14", "battiscopa", True),         # posa battiscopa
    ("2.17", "tinteggiatura", False),     # rasatura muri e soffitti
    ("2.18", "tinteggiatura", True),      # tinteggiatura muri e soffitti
    # dai muri tracciati sulla planimetria (lunghezza × altezza)
    ("1.02", "muri_demolire", True),      # demolizione murature
    ("2.01", "muri_costruire", True),     # ricostruzione muri in forati
    ("2.08", "muri_cartongesso", True),   # pareti in cartongesso
]

# Business plan: colonne delle tabelle e impostazioni predefinite
# (chiave di sessione → valore iniziale; il tipo del default comanda).
# Spese a consuntivo: due registri distinti (come il foglio «Spese» Excel).
# Sostenute = fatture reali (con data e numero); da sostenere = previsioni.

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
IMPOSTAZIONI_BP = {
    "bp_acquisto": 0.0, "bp_vendita": 0.0, "bp_mq": 0.0,
    "bp_imposta": 9.0, "bp_imposte_fisse": 0.0, "bp_notaio": 3500.0,
    "bp_ag_in": 3.0, "bp_ag_out": 2.5, "bp_iva_ag": 22.0,
    "bp_imprevisti_pct": 10.0, "bp_imprevisti": 0.0, "bp_mutuo": 0.0, "bp_durata": 12,
    "bp_ristr": 0.0, "bp_passo": 10000.0,
    # Aliquote IVA, una per voce: l'imposta di registro non ne ha (e' gia'
    # un'imposta), notaio e servizi stanno al 22%, i lavori edili al 10%.
    # Imprevisti e condominio partono da ZERO: e' una riserva, non una
    # fattura, e le spese condominiali non portano IVA da scorporare. Chi ci
    # mette dentro qualcosa che ce l'ha cambia l'aliquota sulla riga.
    "bp_iva_imposta": 0.0, "bp_iva_imposte_fisse": 0.0,
    "bp_iva_notaio": 22.0, "bp_iva_mutuo": 22.0,
    "bp_iva_imprevisti": 0.0, "bp_iva_ristr": 10.0,
    "bp_iva_ag_in": 22.0, "bp_iva_ag_out": 22.0,
    "bp_coeff_sogg": 0.0, "bp_sconto": 13.0,
    # Correzione per il taglio: i tagli piccoli costano di piu' al metro.
    # E' l'unica voce della stima che non sta nella griglia dei coefficienti
    # perche' non si sceglie da una tendina — si ricava dalla superficie, che
    # e' gia' in tabella. A zero e' spenta. Vedi merito.coefficiente_taglio
    # per il perche' di 0,15 e per il perche' NON dell'ottimo statistico.
    "bp_taglio": 0.15,
    # Il costo dei lavori e la quota che il mercato ne riconosce: da questi
    # due si ricava di quanto deve allargarsi la voce «stato dell'unita'»,
    # perche' il salto fra il finito e il da-rifare E' il costo dei lavori,
    # meno quello che il mercato non paga. Vedi merito.scala_stato_unita.
    "bp_costo_ristr_mq": 900.0, "bp_quota_mercato": 85.0,
}

# L'immobile tipo di chi usa CME: un appartamento in palazzina normale di
# venti-quarant'anni, comprato da ristrutturare e rivenduto FINEMENTE
# RISTRUTTURATO — che e' il mestiere, ed e' il motivo per cui la scheda si
# chiama «a lavori finiti». Sono i predefiniti, non un vincolo: si cambiano
# tendina per tendina.
#
# ⚠️ Piano e ascensore restano in bianco DI PROPOSITO. Sono le uniche due
# voci che cambiano a ogni immobile e sono anche quelle che pesano di piu'
# (l'ultimo piano vale 1,10 con ascensore e 0,70 senza): un predefinito li'
# sarebbe un numero deciso da nessuno dentro la stima.
PREDEFINITI_SOGGETTO = {
    "stato_edificio": "Normale",
    "eta_edificio": "20-40 anni",
    "stato_unita": "Finemente ristrutturato",
    "finiture": "Civili",
    "balconi": "Sì",
    "giardino": "No",
    "terrazzo": "No",
    "luce_vista": "Esterna e luminosa",
    "spazi_comuni": "Assenti",
    "parcheggio": "Assente",
    "riscaldamento": "Autonomo",
}

# Le voci della griglia di merito per il SOGGETTO. Stanno fuori da
# IMPOSTAZIONI_BP perche' li' i valori sono numerici — il caricamento di un
# progetto li passa tutti per int() o float() — e queste sono stringhe.
# Si costruiscono da merito.CAMPI, cosi' un fattore aggiunto alla griglia
# compare qui senza predefinito invece di sparire.
SOGGETTO_MCA = {
    f"sog_{campo}": PREDEFINITI_SOGGETTO.get(
        campo, False if campo == "ascensore" else None)
    for campo in merito.CAMPI
}

# Le tendine della griglia: chiave della colonna → (etichetta, voci).
# Una sola tabella per la riga del soggetto e per quelle dei comparabili,
# cosi' non possono divergere.
TENDINE_MERITO = {
    "stato_edificio": ("Stato edificio", merito.STATI_EDIFICIO),
    "eta_edificio": ("Età edificio", merito.FASCE_ETA),
    "stato_unita": ("Stato dell'unità", tuple(merito.STATO_UNITA)),
    "finiture": ("Finiture", tuple(merito.FINITURE)),
    "piano": ("Piano", merito.LIVELLI_PIANO),
    "balconi": ("Balconi", tuple(merito.BALCONI)),
    "giardino": ("Giardino", tuple(merito.GIARDINO)),
    "terrazzo": ("Terrazzo", tuple(merito.TERRAZZO)),
    "luce_vista": ("Luce e vista", tuple(merito.LUCE_VISTA)),
    "spazi_comuni": ("Spazi comuni", tuple(merito.SPAZI_COMUNI)),
    "parcheggio": ("Parcheggio", tuple(merito.PARCHEGGIO)),
    "riscaldamento": ("Riscaldamento", tuple(merito.RISCALDAMENTO)),
}

# Palette del brand Resolve (dark navy + oro), come MORA.
# Nomi con cui i grafici Plotly chiamano gli stessi due materiali: lì serve
# un colore vero, non una variabile CSS. Un solo valore, due nomi.
ORO = OTTONE
CREMA = TRAVERTINO
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

# Categorie che si calpestano ma stanno FUORI: la loro pavimentazione è
# un'altra lavorazione — spessoratura, pendenza, spesso un gres diverso —
# e va in una voce sua, non sommata ai metri delle stanze. I giardini non
# ci sono: non si pavimentano.
CATEGORIE_ESTERNE = (
    "Balcone", "Terrazzo", "Loggia",
    # categorie di lavori precedenti, che restano valide dove sono usate
    "Balcone scoperto", "Balcone coperto", "Balcone / Lastrico solare",
    "Terrazzo di attico (a tasca)", "Portico / Patio",
)

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
    # Il cartongesso è un'altra lavorazione dal muro in forati: altro
    # prezzo, altra impresa spesso, e sul disegno si distingue a colpo
    # d'occhio — verde.
    "cartongesso": {"nome": "Da costruire in cartongesso",
                    "colore": "#43A047"},
}
TIPI_PARETE_SCELTA = ["demolire", "costruire", "cartongesso"]


# ------------------------------------------------------------------ utilità











def config_colonne_spese():
    """Configurazione colonne condivisa tra editor spese e anteprima fatture.

    ⚠️ L'importo è il LORDO, IVA compresa: `fattibilita.iva_scorporata` la
    tira fuori da lì, e l'auto-compilazione ci mette
    `ImportoTotaleDocumento`. La colonna si chiamava «Importo (€)» e non lo
    diceva: chi digitava a mano l'imponibile otteneva un'IVA sbagliata e un
    totale sbagliato, senza un solo segnale. Il nome adesso lo dichiara.
    """
    return {
        # Larghezze in pixel, strette e su misura del contenuto: con nove
        # colonne le taglie "small/medium/large" di Streamlit sprecano spazio
        # dove non serve (una data occupa 90 px, non 200) e lo tolgono
        # all'oggetto, che è l'unica cella con del testo vero dentro. Quel
        # che avanza va in scorrimento orizzontale, non in compressione.
        # ⚠️ format="euro" e non "localized": «localized» conserva i decimali
        # del numero, e su una colonna di soldi vuol dire perdere i centesimi
        # (20000 diventerebbe «20.000», non «20.000,00»). «euro» tiene sempre
        # due decimali, la virgola italiana e il simbolo — la stessa cosa che
        # scrive euro() nel resto dell'app.
        "importo": st.column_config.NumberColumn(
            "Totale fattura", width=120, format="euro",
            help="Il LORDO, IVA compresa — il «totale documento» della "
                 "fattura. L'IVA si scorpora da qui con l'aliquota della "
                 "colonna accanto: mettendoci l'imponibile, l'IVA esce "
                 "sbagliata."),
        "aliquota_iva": st.column_config.NumberColumn(
            "IVA %", width=70, min_value=0.0, max_value=22.0, step=1.0,
            help="Aliquota della fattura, per lo scorporo (22, 10 o 0)"),
        # Derivata e NON scrivibile: è importo − importo/(1+aliquota/100).
        # Sta accanto alla sua aliquota perché è lì che si controlla se una
        # fattura è stata registrata con l'IVA giusta.
        COLONNA_IVA_EUR: st.column_config.NumberColumn(
            "di cui IVA", width=105, format="euro", disabled=True,
            help="Calcolata: l'IVA contenuta nel totale, con l'aliquota "
                 "della colonna accanto. Non si scrive a mano — cambia il "
                 "totale o l'aliquota e si rifà da sé."),
        "data": st.column_config.TextColumn(
            "Data", width=95, help="Es. 22/10/2025"),
        "nr_fattura": st.column_config.TextColumn(
            "Nr. fattura", width=105,
            help="Numero/riferimento della fattura. «//» quando non sono "
                 "riuscito a leggerlo dal file."),
        "fornitore": st.column_config.TextColumn(
            "Fornitore", width=185,
            help="La denominazione di chi ha emesso la fattura."),
        "oggetto": st.column_config.TextColumn("Oggetto", width=250),
        "categoria": st.column_config.SelectboxColumn(
            "Categoria", width=155, options=CATEGORIE_SPESE_EMOJI),
        "note": st.column_config.TextColumn("Note", width=130),
    }


def spese_con_iva(stabile, live=None):
    """Le spese con la colonna derivata «di cui IVA (€)» accanto all'aliquota.

    ⚠️ L'input del data_editor resta il DataFrame STABILE — ripassargli il
    proprio ritorno gli fa perdere la prima scelta di categoria, ed è
    spiegato dove succede. Qui cambia SOLO la colonna derivata, che guarda i
    valori live: così l'IVA segue l'importo appena lo si corregge, invece di
    aspettare il giro dopo. È una colonna che l'utente non tocca (è
    `disabled`), quindi non entra nelle modifiche che Streamlit deve
    riconciliare, e riscriverla non disturba niente.

    Derivata vuol dire anche NON salvata: nel JSON del progetto un valore
    che si ricava da altri due non ci va.
    """
    # idempotente: se la colonna e' gia' li' (ci arriva col ritorno di una
    # tabella) si rifa', non si duplica
    fuori = senza_iva_derivata(stabile.copy())
    fonte = stabile if live is None else live
    valori = []
    for i in fuori.index:
        riga = fonte.loc[i] if i in fonte.index else fuori.loc[i]
        importo = riga.get("importo")
        if importo is None or pd.isna(importo):
            valori.append(None)          # riga vuota: nessuna IVA da dire
            continue
        aliquota = riga.get("aliquota_iva")
        valori.append(fattibilita.iva_scorporata(
            importo, 0.0 if aliquota is None or pd.isna(aliquota)
            else aliquota))
    # subito dopo importo e aliquota: è lì che si controlla se una fattura
    # è stata registrata con l'IVA giusta
    fuori.insert(min(2, len(fuori.columns)), COLONNA_IVA_EUR, valori)
    return fuori


def config_colonne_materiali():
    """Le colonne dell'elenco materiali a cura del committente.

    ⚠️ Nessuna colonna è obbligatoria tranne la descrizione, ed è la
    descrizione a fare la riga: l'allegato firmato è un elenco di nomi, e
    quantità, prezzo e fornitore arrivano dopo, quando si va a comprare.
    Chiedere un prezzo per accettare una riga vorrebbe dire non poter più
    scrivere l'elenco prima di averlo quotato — cioè togliere al foglio la
    cosa per cui esiste.
    """
    return {
        "capitolo": st.column_config.SelectboxColumn(
            "Capitolo", width=170, options=materiali.CAPITOLI,
            help="Il capitolo dell'allegato: raggruppa le voci sul foglio "
                 "che si firma con l'impresa."),
        "descrizione": st.column_config.TextColumn(
            "Descrizione", width=270,
            help="Il nome della cosa, come lo scriveresti sull'allegato. "
                 "È l'unica colonna che serve perché la riga esista."),
        "um": st.column_config.TextColumn("U.M.", width=60),
        # «localized» e non «euro»: qui i decimali sono quelli del numero
        # (5 porte sono «5», 94,71 m² sono «94,71»), non due sempre.
        "quantita": st.column_config.NumberColumn(
            "Quantità", width=85, min_value=0.0, format="localized",
            help="Se manca vale 1: il box doccia è uno, e non c'è bisogno "
                 "di scriverlo."),
        "prezzo": st.column_config.NumberColumn(
            "Prezzo unit.", width=110, min_value=0.0, format="euro",
            help="IVA esclusa, come tutti i prezzi del computo. Lascialo "
                 "vuoto finché non lo sai: la voce resta nell'elenco e il "
                 "totale dichiara che è parziale."),
        COLONNA_IMPORTO_MAT: st.column_config.NumberColumn(
            "Importo", width=110, format="euro", disabled=True,
            help="Calcolato: quantità × prezzo. Non si scrive a mano."),
        "fornitore": st.column_config.TextColumn(
            "Fornitore", width=150,
            help="Da chi lo compri. Non finisce sull'allegato: è roba tua."),
        "stato": st.column_config.SelectboxColumn(
            "Stato", width=120, options=materiali.STATI,
            help="A che punto è l'acquisto. Il pagamento no: quello ha già "
                 "il suo registro nelle spese a consuntivo."),
        "note": st.column_config.TextColumn(
            "Note", width=200,
            help="Sull'allegato diventa la nota in fondo, richiamata da un "
                 "asterisco accanto alla descrizione."),
    }


def materiali_con_importo(stabile, live=None):
    """I materiali con la colonna calcolata «Importo» accanto al prezzo.

    Stesse regole di `spese_con_iva`: l'input del data_editor resta il
    DataFrame STABILE, e questa colonna — che l'utente non tocca — guarda i
    valori live, così l'importo segue il prezzo appena lo si scrive.

    ⚠️ Senza prezzo l'importo resta **vuoto**, non zero. Uno zero in
    colonna direbbe «gratis» e si sommerebbe agli altri; il vuoto dice
    «ancora da quotare», che è la verità.
    """
    fuori = senza_importo_derivato(stabile.copy())
    fonte = stabile if live is None else live
    valori = []
    for i in fuori.index:
        riga = fonte.loc[i] if i in fonte.index else fuori.loc[i]
        prezzo = riga.get("prezzo")
        if prezzo is None or pd.isna(prezzo):
            valori.append(None)
            continue
        quantita = riga.get("quantita")
        pezzi = (1.0 if quantita is None or pd.isna(quantita)
                 else float(quantita))
        valori.append(round(pezzi * float(prezzo), 2))
    # subito dopo il prezzo: è lì che si guarda se il conto torna
    fuori.insert(min(5, len(fuori.columns)), COLONNA_IMPORTO_MAT, valori)
    return fuori


def materiali_correnti():
    """Le righe dei materiali, con l'importo, dal ritorno vivo dell'editor.

    Una funzione sola perché i materiali si leggono in tre posti — il
    riepilogo costi, l'export e il business plan — e in tutt'e tre devono
    essere gli stessi. La tabella vive nella scheda Computo, che Streamlit
    disegna per prima: quando il business plan chiede questi numeri il
    ritorno vivo c'è già.
    """
    df = st.session_state.get("df_materiali_live",
                              st.session_state.get("df_materiali"))
    if df is None:
        return []
    return materiali.calcola_elenco(materiali_da_df(df))


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




# Unità di misura proposte: quelle che compaiono davvero in un computo di
# ristrutturazione. «a corpo» è a parte — non si misura, vale una volta —
# ed è per questo che la sua quantità la mette l'app.
# Le unità che si scelgono da una tendina: quelle che si usano davvero in un
# computo di ristrutturazione. «kg» e «utenza» sono usciti — il primo non
# capita mai, il secondo solo su due voci del listino, che se lo tengono:
# `unita_della_voce` mette in testa all'elenco l'unità che la voce ha già,
# anche quando non è fra le proposte.
UNITA_MISURA = ["m²", "ml", "m³", "cad", "punto", "a corpo"]
UM_A_CORPO = "a corpo"

# Un «punto» non vuol dire la stessa cosa dappertutto: dall'elettricista è
# un punto luce, dall'idraulico un punto acqua. Chiamarli tutti «punto»
# obbliga a rileggere la descrizione per capire cosa si sta contando — e su
# un computo consegnato è chi lo riceve a doverlo fare.
UNITA_DELLA_CATEGORIA = {
    "Elettricista": "punto luce",
    "Idraulico": "punto acqua",
}

# Unità che si contano a pezzi interi: qui la quantità ha le frecce su e giù
# e non i decimali. Sui metri quadri non le mettiamo — «84 m² + 1» non è un
# gesto che voglia fare nessuno, e il passo darebbe l'idea sbagliata che si
# misuri a scatti.
UM_A_PASSI = {UM_A_CORPO, "cad", "punto", "punto luce", "punto acqua",
              "utenza"}


def unita_per_categoria(categoria):
    """Le unità proposte in quella categoria, con la sua in testa."""
    propria = UNITA_DELLA_CATEGORIA.get(categoria)
    if not propria:
        return list(UNITA_MISURA)
    return [propria] + [u for u in UNITA_MISURA if u != propria]


def unita_della_voce(voce, um):
    """L'elenco per la tendina di una riga: quelle di casa più la sua.

    L'unità corrente ci sta sempre, anche se non è fra le proposte: un
    computo vecchio può portare «m», e una tendina che non contenga il
    valore che deve mostrare fa saltare Streamlit.
    """
    elenco = unita_per_categoria(voce.get("categoria"))
    return elenco if um in elenco else [um] + elenco

# Le voci aggiunte a mano prendono un codice nella stessa serie della loro
# categoria, ma da .90 in su: così si riconoscono a colpo d'occhio e non
# rischiano di scontrarsi con una voce nuova del listino.
PRIMO_CODICE_EXTRA = 90


def codice_nuovo(categoria):
    """Il prossimo codice libero per una voce aggiunta a mano.

    La serie è quella della categoria (Idraulico → 3.90, 3.91, …). Per una
    categoria che nel listino non c'è — le superfici che arrivano dal
    disegno — si riparte dal numero dopo l'ultima.
    """
    if categoria in listino.CATEGORIE:
        serie = listino.CATEGORIE.index(categoria)
    else:
        serie = len(listino.CATEGORIE)
    presi = set(st.session_state.voci_extra)
    numero = PRIMO_CODICE_EXTRA
    while f"{serie}.{numero}" in presi:
        numero += 1
    return f"{serie}.{numero}"


def voce_del_computo(codice):
    """La voce con quel codice: prima nel listino, poi fra quelle aggiunte."""
    return (listino.voce_per_codice(codice)
            or st.session_state.voci_extra.get(codice))


def aggiungi_voce_computo(categoria, descrizione, um, quantita, prezzo,
                          codice=None):
    """Crea una voce che il listino non ha e la porta NEL computo.

    Nasce direttamente NEL computo, non nel pool: una voce inventata per
    questo cantiere è già una riga del documento, non merce da scaffale.
    Nel pool ci finisce solo dopo, se la togli dal computo con la ✕ — da
    lì si ripesca come le altre. Ci arrivano le voci scritte a mano e le
    superfici portate su dalla planimetria.
    """
    codice = codice or codice_nuovo(categoria)
    st.session_state.voci_extra[codice] = {
        "codice": codice,
        "categoria": categoria,
        "descrizione": descrizione or "Voce senza descrizione",
        "um": um or "",
        "prezzo": float(prezzo or 0.0),
    }
    st.session_state[f"q_{codice}"] = float(quantita or 0.0)
    st.session_state[f"p_{codice}"] = float(prezzo or 0.0)
    for chiave in (f"q_{codice}_txt", f"p_{codice}_txt",
                   f"d_{codice}_w", f"u_{codice}_w", f"qn_{codice}_w"):
        st.session_state.pop(chiave, None)
    if codice not in st.session_state.voci_scelte:
        st.session_state.voci_scelte.append(codice)
    return codice


def scarta_voce(codice):
    """Toglie una voce dal pool di QUESTO progetto.

    Non tocca il listino, che è il catalogo e vale per tutti i cantieri:
    sparisce solo da qui, perché su questo lavoro non c'entra e sfogliare
    il pool sia più corto. Niente si perde — gli scarti si contano in
    fondo al pool e si rimettono tutti insieme.

    Vale anche per le voci scritte a mano, e allo stesso modo: scartare
    non è cancellare. La voce resta in `voci_extra` col suo codice, e
    «Rimetti tutte» la riporta a galla insieme alle altre. In questo
    programma non c'è modo di eliminare per sempre una voce tua — è una
    scelta: quel che hai scritto non lo butta via un clic.
    """
    togli_dal_computo(codice)
    if codice not in st.session_state.voci_scartate:
        st.session_state.voci_scartate.append(codice)


def ripristina_scarti():
    """Rimette nel pool tutto quello che era stato scartato."""
    st.session_state.voci_scartate = []


def e_scartata(codice):
    return codice in st.session_state.voci_scartate


def azzera_unita_nuova():
    """Cambiando categoria, l'unità riparte da quella di casa.

    L'elenco cambia sotto ai piedi del widget, e un valore che nel nuovo
    elenco non c'è («punto luce» passando a Demolizioni) farebbe sollevare
    a Streamlit un errore invece di ricadere sul primo.
    """
    st.session_state.pop("nuova_um", None)


def proponi_quantita_a_corpo():
    """Scegliendo «a corpo» la quantità si propone da sé: 1.

    Callback della tendina delle unità — solo da qui si può scrivere nella
    casella della quantità senza che Streamlit si lamenti. Propone e basta:
    se un numero c'era già, resta quello.
    """
    if (st.session_state.get("nuova_um") == UM_A_CORPO
            and not (st.session_state.get("nuova_qta") or 0.0)):
        st.session_state.nuova_qta = 1.0


def crea_voce_a_mano():
    """Crea la voce scritta nel pannello «Aggiungi una voce».

    ⚠️ È una callback e deve restarlo: qui dentro si può rimettere a zero la
    casella della descrizione, cosa che fatta nel corpo dello script — a
    widget già disegnato — Streamlit rifiuta piantando l'app.
    """
    descrizione = (st.session_state.get("nuova_desc") or "").strip()
    if not descrizione:
        st.session_state._esito_voce = (
            "errore", "Dai una descrizione alla voce: nel computo si legge "
                      "quella, non il codice.")
        return
    categoria = st.session_state.get("nuova_cat") or listino.CATEGORIE[0]
    um = st.session_state.get("nuova_um") or ""
    quantita = st.session_state.get("nuova_qta") or 0.0
    if um == UM_A_CORPO and not quantita:
        quantita = 1.0
    codice = aggiungi_voce_computo(
        categoria, descrizione, um, quantita,
        st.session_state.get("nuova_prezzo") or 0.0)
    st.session_state.cat_aperte |= {categoria}
    st.session_state.nuova_desc = ""
    st.session_state._esito_voce = (
        "ok", f"{codice} · {descrizione} → {categoria}")


def scambia_con_vicina(codice, verso):
    """Scambia la voce con quella prima (verso −1) o dopo (+1) nella sua
    categoria.

    L'ordine del computo è quello di `voci_scelte`, che tiene tutte le
    categorie di fila: qui ci si muove SOLTANTO fra le vicine di casa, così
    «su» dalla prima delle demolizioni non finisce in mezzo alle pratiche.
    """
    scelte_ora = st.session_state.voci_scelte
    voce = voce_del_computo(codice)
    if voce is None or codice not in scelte_ora:
        return
    sorelle = [c for c in scelte_ora
               if (v := voce_del_computo(c))
               and v["categoria"] == voce["categoria"]]
    posto = sorelle.index(codice) + verso
    if not 0 <= posto < len(sorelle):
        return                      # è già in cima o in fondo
    vicina = sorelle[posto]
    qui, la = scelte_ora.index(codice), scelte_ora.index(vicina)
    scelte_ora[qui], scelte_ora[la] = scelte_ora[la], scelte_ora[qui]


def sposta_voce_extra(codice):
    """Porta una voce scritta a mano in un'altra categoria.

    Il codice cambia con lei: la serie dice la categoria (Idraulico → 3.9x),
    e una voce spostata che si tenesse il numero vecchio mentirebbe sul suo
    posto. Quantità, prezzo e riscritture la seguono, e resta dov'era
    nell'ordine del computo — spostare non è togliere e rimettere in fondo.
    """
    categoria = st.session_state.get(f"spostacat_{codice}")
    voce = st.session_state.voci_extra.get(codice)
    if not voce or not categoria or categoria == voce["categoria"]:
        return
    nuovo = codice_nuovo(categoria)
    st.session_state.voci_extra[nuovo] = {**voce, "codice": nuovo,
                                          "categoria": categoria}
    del st.session_state.voci_extra[codice]
    for prefisso in ("q_", "p_", "d_", "u_"):
        if prefisso + codice in st.session_state:
            st.session_state[prefisso + nuovo] = st.session_state[
                prefisso + codice]
    for chiave in (f"q_{codice}", f"p_{codice}", f"d_{codice}",
                   f"u_{codice}", f"q_{codice}_txt", f"p_{codice}_txt",
                   f"d_{codice}_w", f"u_{codice}_w"):
        st.session_state.pop(chiave, None)
    scelte_ora = st.session_state.voci_scelte
    if codice in scelte_ora:
        scelte_ora[scelte_ora.index(codice)] = nuovo
    else:
        scelte_ora.append(nuovo)
    if codice in st.session_state.voci_scartate:
        st.session_state.voci_scartate.remove(codice)
    st.session_state.cat_aperte |= {categoria}
    st.toast(f"{codice} → {nuovo} · ora in {categoria} ✔")


def categorie_del_computo():
    """Le categorie da disegnare: quelle del listino, più le inventate.

    «Superfici» non sta nel listino ma ci finiscono le aree portate su dal
    disegno: se non la disegnassimo, quelle voci sarebbero nel computo e
    invisibili.
    """
    extra = [v["categoria"] for v in st.session_state.voci_extra.values()
             if v["categoria"] not in listino.CATEGORIE]
    return list(listino.CATEGORIE) + list(dict.fromkeys(extra))


def nome_file(estensione):
    base = (st.session_state.prg_nome or "computo").strip().replace(" ", "_")
    base = "".join(c for c in base if c.isalnum() or c in "_-") or "computo"
    return f"{base}.{estensione}"


# --------------------------------------------------- le voci del computo
# Il computo porta SOLO le voci scelte: un cantiere non è l'altro, e un
# elenco di 69 lavorazioni in cui 60 valgono zero non è un computo, è un
# catalogo. Le voci si pescano dal pool qui sotto e si tolgono con la ×.
# «scelte» è l'elenco dei codici, nell'ordine in cui sono stati aggiunti;
# i totali e la stampa lo leggono da qui.


def segna_a_mano(codice):
    """Da adesso quella quantità la decide chi l'ha scritta, non il disegno.

    Vale per TUTTE le voci: quelle che il disegno non alimenta non se ne
    accorgono nemmeno, ma l'elenco è uno solo — e il giorno in cui una
    misura nuova cominciasse ad alimentarle, troverebbe già il segno.
    """
    if codice not in st.session_state.voci_a_mano:
        st.session_state.voci_a_mano.append(codice)


def riaggancia_al_disegno(codice=None):
    """Ridà al disegno il comando: su una voce, o su tutte."""
    if codice is None:
        st.session_state.voci_a_mano = []
    elif codice in st.session_state.voci_a_mano:
        st.session_state.voci_a_mano.remove(codice)


def scelte():
    """I codici delle voci di listino portate nel computo."""
    return list(st.session_state.voci_scelte)


def e_scelta(codice):
    return codice in st.session_state.voci_scelte


def porta_nel_computo(codice):
    """Aggiunge una voce al computo (se non c'è già). True se l'ha aggiunta."""
    # Una voce che entra nel computo non è più scartata: può arrivarci dal
    # disegno anche dopo essere stata tolta dal pool, e ritrovarsela fra
    # gli scarti mentre è nel documento non vorrebbe dire niente.
    if codice in st.session_state.voci_scartate:
        st.session_state.voci_scartate.remove(codice)
    if codice in st.session_state.voci_scelte:
        return False
    st.session_state.voci_scelte.append(codice)
    return True


def togli_dal_computo(codice):
    """Toglie la voce dal computo. Quantità, prezzo e testi restano dove
    sono: se la si ripesca dal pool, si ritrova come l'avevi lasciata."""
    if codice in st.session_state.voci_scelte:
        st.session_state.voci_scelte.remove(codice)


def scelte_della_categoria(categoria):
    """Le voci scelte di una categoria, nell'ordine in cui sono entrate."""
    return [v for c in scelte()
            if (v := voce_del_computo(c))
            and v["categoria"] == categoria]


def quantita_prezzo_listino(voce):
    """Quantità e prezzo correnti di una voce del listino.

    Si leggono dalle chiavi «di verità», non dai widget: le righe delle
    categorie chiuse non esistono a video, ma i loro valori devono continuare
    a contare nei totali, nell'export e nel salvataggio.
    """
    quantita = float(st.session_state.get(f"q_{voce['codice']}") or 0.0)
    prezzo = float(st.session_state.get(f"p_{voce['codice']}")
                   or voce["prezzo"])
    return quantita, prezzo


def testi_voce(voce):
    """Descrizione e unità correnti: quelle riscritte, o quelle del listino.

    Ogni cantiere ha le sue parole («gres 60×60 posato a correre» non è
    «pavimenti in piastrelle»): la voce del listino è un punto di partenza,
    non un'etichetta da subire. Le riscritture stanno in d_/u_ e si salvano
    col progetto; il listino resta intatto per il progetto dopo.
    """
    codice = voce["codice"]
    descrizione = st.session_state.get(f"d_{codice}")
    um = st.session_state.get(f"u_{codice}")
    return (descrizione if descrizione else voce["descrizione"],
            um if um else voce["um"])


def totale_categoria_listino(categoria):
    """Somma quantità × prezzo delle voci del computo in quella categoria."""
    totale = 0.0
    for voce in scelte_della_categoria(categoria):
        quantita, prezzo = quantita_prezzo_listino(voce)
        totale += quantita * prezzo
    return round(totale, 2)


def voci_dal_listino():
    """Le voci scelte con quantità > 0, nel formato del computo.

    La scelta dice che la voce è del cantiere; la quantità dice quanto ne
    va fatto. Una voce scelta e non ancora quantificata resta a video —
    così si vede che manca — ma fuori da totali, stampa ed export: un
    computo consegnato non porta righe da zero.
    """
    voci = []
    for codice in scelte():
        voce = voce_del_computo(codice)
        if voce is None:
            continue
        quantita, prezzo = quantita_prezzo_listino(voce)
        if quantita <= 0:
            continue
        descrizione, um = testi_voce(voce)
        voci.append({"categoria": voce["categoria"],
                     "codice": voce["codice"],
                     "descrizione": descrizione,
                     "um": um, "parti": None, "lunghezza": None,
                     "larghezza": None, "altezza": None,
                     "quantita_manuale": quantita, "prezzo": prezzo})
    return voci


# La casella della descrizione si misura sul testo che porta. Sotto: quanti
# caratteri stanno in una riga della colonna «Voce» (308 px a 0,86rem), e
# quante righe al massimo — oltre, il testo scorre dentro la casella.
# 291 px utili a 13,76 px di corpo: il carattere medio di questo font sta
# in 6,17 px, e in una riga ci vanno 47 caratteri. Con 42 la stima
# sbagliava per eccesso e lasciava una riga vuota in fondo alle voci
# lunghe «quasi» due righe.
CARATTERI_PER_RIGA = 47
RIGHE_DESCRIZIONE_MAX = 3
# altezza di una riga di testo e aria sopra+sotto, in rem: 0,86 × 1,3
RIGA_TESTO_REM = 1.118
ARIA_DESCRIZIONE_REM = 0.4


def righe_descrizione(testo):
    """Quante righe occupa la descrizione, da 1 a RIGHE_DESCRIZIONE_MAX.

    Una stima sui caratteri, non una misura: il conto esatto lo saprebbe
    solo il browser. Sbagliare per eccesso di una riga costa venti pixel;
    tenere tutte le caselle alte quanto la più lunga costava venti pixel
    su OGNI riga, comprese quelle da tre parole.
    """
    if not testo:
        return 1
    righe = 0
    for paragrafo in testo.splitlines() or [""]:
        righe += max(1, -(-len(paragrafo) // CARATTERI_PER_RIGA))
    return min(RIGHE_DESCRIZIONE_MAX, max(1, righe))


def css_altezze_descrizioni():
    """Le altezze stimate, per i browser senza `field-sizing`.

    Dove c'è, la casella si misura da sé sul testo e queste regole non
    servono; dove non c'è — Safari, Firefox — resta la stima sui
    caratteri, che sbaglia di una riga ogni tanto ma è meglio di tre
    righe fisse per tutti. La chiave del widget diventa una classe (i
    punti del codice diventano trattini), e da lì si veste la casella.
    """
    regole = []
    for codice in scelte():
        voce = voce_del_computo(codice)
        if voce is None:
            continue
        descrizione, _ = testi_voce(voce)
        alta = (righe_descrizione(descrizione) * RIGA_TESTO_REM
                + ARIA_DESCRIZIONE_REM)
        regole.append(
            f'.st-key-d_{codice.replace(".", "-")}_w textarea '
            f"{{height:{alta:.2f}rem !important;"
            f"min-height:{alta:.2f}rem !important;}}")
    if not regole:
        return ""
    return ("<style>@supports not (field-sizing: content) {"
            + "".join(regole) + "}</style>")


def css_schede_computo():
    """CSS dei campioni del computo: una categoria, una tinta, un totale.

    Ogni scheda è avvolta in un st.container(key="card_…"): Streamlit le
    assegna la classe .st-key-card_… e da lì si veste il campione.

    L'intestazione è un bottone (key «apri_N») e si compone di tre parti,
    due delle quali le disegna il CSS perché nell'etichetta di un bottone
    non ci sta altro che una riga di testo:
    - `button::before` è la **pastiglia**: la tinta piena del materiale, una
      superficie da guardare. Non una banda sul bordo, che è l'abitudine
      del gestionale travestita da campionario;
    - il contenitore markdown porta l'**etichetta campione** (codice e
      numero di voci) sopra il nome della categoria;
    - `button::after` è il **totale**, il numero grande a destra.

    IMPORTANTE: il totale è disegnato dal CSS, NON scritto nell'etichetta.
    Se stesse nel titolo, a ogni modifica il titolo cambierebbe e Streamlit
    tratterebbe il bottone come un widget nuovo; con il CSS il titolo resta
    identico e la categoria rimane aperta mentre si lavora.
    """
    regole = ["""
/* Categorie: il titolo è un bottone (key «apri_N») travestito da
   intestazione di tendina, così l'apertura passa dal server e possiamo
   disegnare le righe della sola categoria aperta. */
[class*="st-key-apri_"] button {
    display: grid;
    grid-template-columns: 44px 1fr auto;
    align-items: center;
    column-gap: 0.85rem;
    background: transparent;
    border: none;
    border-radius: 0;
    box-shadow: none;
    text-align: left;
    padding: 0.6rem 0.9rem;
    width: 100%;
}
/* La pastiglia: tinta piena, alta quanto l'intestazione, col numero della
   categoria stampato sopra come il codice su un campione vero. Il numero sta
   lì e non accanto al nome: serve a ritrovare la categoria, non a leggerla. */
[class*="st-key-apri_"] button::before {
    align-self: stretch;
    min-height: 44px;
    display: flex;
    align-items: center;
    justify-content: center;
    font-size: 0.72rem;
    font-weight: 700;
    letter-spacing: 0.06em;
}
/* il nome della categoria è la cosa che si legge: niente lo sovrasta */
[class*="st-key-apri_"] button [data-testid="stMarkdownContainer"] {
    text-align: left;
    width: 100%;
}
[class*="st-key-apri_"] button p {
    margin: 0;
    font-size: 1.35rem;
    font-weight: 650;
    line-height: 1.25;
    text-align: left;
}
/* il numero è il protagonista: più grande del nome che lo intesta */
[class*="st-key-apri_"] button::after {
    justify-self: end;
    font-size: 1.4rem;
    font-weight: 700;
    white-space: nowrap;
    color: var(--travertino);
}
"""]
    for indice, cat in enumerate(categorie_del_computo(), start=1):
        colore = COLORI_CATEGORIE.get(cat, (OTTONE, "orange"))[0]
        totale = totale_categoria_listino(cat)
        aperta = cat in st.session_state.get("cat_aperte", set())
        # aperta: il contorno del materiale si fa più netto, come il campione
        # tirato fuori dalla cartella
        bordo = "E6" if aperta else "99"
        regole.append(f"""
.st-key-card_{indice} {{
    background: {colore}26;
    border: 1px solid {colore}{bordo};
    border-radius: 0;
    margin-bottom: 0.55rem;
    padding-bottom: 0.2rem;
}}
.st-key-apri_{indice} button::before {{
    content: "{indice:02d}";
    background: {colore};
    color: {colore_testo_su(colore)};
}}
.st-key-apri_{indice} button:hover {{
    background: {colore}1F;
}}
.st-key-apri_{indice} button::after {{
    content: "{euro(totale)}";
}}
/* Il filo che separa due voci: il bordo alto della riga, della tinta
   della categoria. `:has(textarea)` sceglie le righe delle voci e lascia
   fuori l'intestazione, che una linea sopra non la vuole. */
.st-key-card_{indice} [data-testid="stHorizontalBlock"]:has(textarea) {{
    border-top: 1px solid {colore}99;
}}
""")
    # Il pool: il magazzino, non il documento. Stessa famiglia di forme —
    # squadrata, contorno sottile — ma spenta: fondo neutro e nessuna tinta
    # piena, così a colpo d'occhio si vede che il computo è quello sopra.
    regole.append(f"""
.st-key-card_pool {{
    background: color-mix(in srgb, var(--cemento) 8%, transparent);
    border: 1px solid color-mix(in srgb, var(--cemento) 45%, transparent);
    border-radius: 0;
    padding: 0.7rem 0.9rem 0.3rem;
    margin-top: 0.9rem;
}}
/* Il titolo della scheda: un paragrafo, vestito da titolo.
   ⚠️ Il margine sotto sta sul CONTENITORE, ed è di un rem esatto: il
   guscio che Streamlit mette attorno a un testo è alto SEDICI PIXEL MENO
   del testo che contiene (misurato: contenuto 30,7 → guscio 14,7;
   contenuto 22,4 → guscio 6,4). Quello che segue si posiziona sul guscio,
   e la casella della ricerca finiva addosso al titolo, tagliandolo a
   metà. Il rem qui rimette i sedici pixel che il guscio si mangia. */
.st-key-card_pool > [data-testid="stElementContainer"]:first-child {{
    margin-bottom: 1rem;
}}
.st-key-card_pool > [data-testid="stElementContainer"]:first-child p {{
    font-size: 1.05rem;
    font-weight: 650;
    line-height: 1.4;
    margin: 0;
}}
.st-key-card_pool [data-testid="stExpander"] details {{
    background: transparent;
    border: none;
    border-top: 1px solid {ARDESIA}33;
    border-radius: 0;
}}
.st-key-card_pool summary p {{
    font-size: 1rem;
    font-weight: 600;
}}
/* il ＋ è un quadretto, non una pastiglia: si preme cento volte di fila */
.st-key-card_pool [class*="st-key-prendi_"] button {{
    border-radius: 0;
    padding: 0.1rem 0;
    min-height: 1.9rem;
    font-weight: 700;
}}
.st-key-card_pool hr {{
    margin: 0.2rem 0;
}}
""")
    # L'allegato dei materiali: contorno d'ottone, non una delle sette tinte
    # dei mestieri. È il capitolo del committente — quello che compra lui —
    # e l'ottone in questo mondo è il metallo di casa, quello del marchio.
    # Un colore da mestiere direbbe che è un mestiere in più; l'ottone dice
    # che è roba di chi paga, e sta accanto al computo senza entrarci.
    regole.append("""
.st-key-card_materiali {
    background: color-mix(in srgb, var(--ottone) 9%, transparent);
    border: 1px solid color-mix(in srgb, var(--ottone) 55%, transparent);
    border-radius: 0;
    padding: 0.7rem 0.9rem 0.5rem;
    margin-top: 0.9rem;
}
/* stessa correzione del pool: il guscio di Streamlit è più basso del testo
   che contiene, e senza questo margine la didascalia sale addosso al
   titolo */
.st-key-card_materiali > [data-testid="stElementContainer"]:first-child {
    margin-bottom: 0.6rem;
}
.st-key-card_materiali > [data-testid="stElementContainer"]:first-child p {
    font-size: 1.05rem;
    font-weight: 650;
    line-height: 1.4;
    margin: 0;
    color: var(--ottone);
}
""")
    # --------------------------------------------- le righe del computo
    # Il computo è una tabella, non un modulo: le celle stanno vicine, i
    # bordi si vedono appena e l'aria va tolta dove non dice niente. Prima
    # ogni cella era una casella di Streamlit con la sua imbottitura da
    # form, e fra una colonna e l'altra passava un dito di vuoto.
    regole.append(f"""
/* Le colonne di una riga: quasi attaccate, con un filo d'aria sopra e
   sotto — uguale da tutte e due le parti. */
[class*="st-key-card_"] [data-testid="stHorizontalBlock"] {{
    gap: 0.35rem;
    padding: 0.3rem 0;
}}
/* ⚠️ QUI stava lo spazio vero. Dentro le celle si era stretto tutto, ma
   fra una riga e l'altra ne restavano 32 px: la riga misura 45 e il passo
   era 77. Sono i 16 px di «gap» che Streamlit mette fra gli elementi
   impilati, due volte (sopra e sotto il filo di separazione), più i
   margini del filo. Senza !important non si sposta: la regola di Streamlit
   nasce da una classe generata, più specifica di questa. */
/* ⚠️⚠️ Il selettore NON ha lo spazio: quei 16 px stanno sulla scheda
   STESSA, che è essa stessa un «stVerticalBlock» — scritto come
   discendente non trovava niente, e lo spazio restava tale e quale. */
[class*="st-key-card_"][data-testid="stVerticalBlock"],
[class*="st-key-card_"] [data-testid="stVerticalBlock"] {{
    gap: 0.25rem !important;
}}
/* ⚠️ LE CELLE SI STRINGONO ATTORNO AL TESTO. Un campo di Streamlit nasce
   alto 40 px perché è pensato per un modulo, dove le caselle stanno larghe
   e distanti; qui sono le celle di una tabella, e per una riga di testo
   alta 17 px c'erano 23 px di aria — più di quanta ne occupasse la scritta.
   Sopra e sotto resta un filo, quel tanto che serve a non far toccare il
   testo al bordo. */
[class*="st-key-card_"] textarea {{
    /* ⚠️ `field-sizing: content` fa crescere la casella col testo che
       porta, ESATTAMENTE: una riga se il testo sta in una, tre se ne
       servono tre, mai una riga vuota in fondo. È il browser a misurare,
       e il browser è l'unico che sappia dove va a capo una parola — la
       stima sui caratteri sbagliava di una riga su tre voci su quindici.
       min/max tengono il conto fra una riga e tre; oltre, il testo scorre.
       Dove `field-sizing` non c'è, subentra la stima: vedi il blocco
       @supports in css_altezze_descrizioni(). */
    field-sizing: content;
    height: auto !important;
    min-height: 1.52rem !important;
    max-height: 3.85rem !important;
    padding: 0.2rem 0.5rem;
    line-height: 1.3;
    font-size: 0.86rem;
    resize: none;
    overflow-y: auto;
}}
/* ⚠️ I gusci della descrizione seguono la sua altezza, non la impongono:
   con un'altezza fissa addosso stringevano il testo e la seconda riga
   veniva tagliata a metà. */
[class*="st-key-card_"] [data-testid="stTextAreaRootElement"],
[class*="st-key-card_"] [data-testid="stTextArea"] > div {{
    height: auto;
    min-height: 0;
}}
/* Le celle dei NUMERI e dell'unità: qui lo spazio vuoto c'è davvero — una
   riga di testo alta 17 px dentro una casella da 40. Si stringe a 30, che
   è la scritta più un filo sopra e sotto.
   ⚠️ Il bersaglio sono le caselle di testo e i campi numerici per nome, non
   un generico «base-input»: quello prende anche il guscio della
   descrizione, che è un'area e ha bisogno di crescere. */
[class*="st-key-card_"] [data-testid="stHorizontalBlock"] input {{
    padding: 0.1rem 0.5rem;
    line-height: 1.3;
}}
[class*="st-key-card_"] [data-testid="stTextInput"] [data-baseweb="base-input"],
[class*="st-key-card_"] [data-testid="stNumberInput"] [data-baseweb="base-input"],
[class*="st-key-card_"] [data-testid="stTextInput"] [data-baseweb="input"],
[class*="st-key-card_"] [data-testid="stNumberInput"] [data-baseweb="input"] {{
    min-height: 1.85rem;
    height: 1.85rem;
}}
/* la casella con le frecce: il guscio restava alto 40 px anche con la
   casella dentro a 30, e la cella della quantità sporgeva sulle vicine */
[class*="st-key-card_"] [data-testid="stNumberInputContainer"] {{
    height: 1.85rem;
    min-height: 1.85rem;
}}
/* la tendina dell'unità: baseweb le imbottisce il valore di 8 px per lato */
[class*="st-key-card_"] [data-testid="stHorizontalBlock"]
div[data-baseweb="select"] > div,
[class*="st-key-card_"] [data-testid="stHorizontalBlock"]
div[data-baseweb="select"] > div > div {{
    min-height: 1.85rem;
    height: 1.85rem;
}}
[class*="st-key-card_"] [data-testid="stHorizontalBlock"]
div[data-baseweb="select"] > div > div:first-child {{
    padding: 0 0.4rem;
}}
/* Streamlit tiene sotto ogni casella lo spazio per il messaggio d'errore:
   qui non ce ne sono, ed erano dieci righe di vuoto su un computo lungo */
[class*="st-key-card_"] [data-testid="stElementContainer"] {{
    margin-bottom: 0;
}}
/* ⚠️ UNA SOLA MISURA per tutta la riga. Ogni cella nasceva col corpo che
   Streamlit dà al suo tipo di widget: il codice di una voce di listino era
   testo (16 px), quello di una voce tua un bottone (13,8), il parziale
   ancora testo (16) e la ✕ un'icona (15,2). Sei misure diverse su una
   riga sola, e la colonna dei codici sembrava scritta da due persone. */
[class*="st-key-card_"] [data-testid="stHorizontalBlock"] {{
    font-size: 0.86rem;
}}
/* e nessuno se ne riprende una sua: la misura si eredita e basta. Elencare
   i tipi di elemento non bastava — il valore di una tendina è un div, il
   parziale un altro, e ognuno tornava al corpo suo. */
[class*="st-key-card_"] [data-testid="stHorizontalBlock"] * {{
    font-size: inherit;
}}
/* Il codice di una voce tua è un menù (ci si sposta di categoria), ma
   deve restare un codice: stesso grigio, stesso peso, nessuna pastiglia.
   Un bottone vero in quella colonna farebbe sembrare la riga piena di
   comandi, e il codice non si legge più.
   ⚠️ Il bersaglio è «stPopoverButton»: dentro «stPopover» non c'è: sta in
   un portale suo, e la regola scritta così non toccava niente. */
[class*="st-key-card_"] [data-testid="stPopoverButton"] {{
    background: transparent;
    border: none;
    box-shadow: none;
    padding: 0;
    min-height: 0;
    color: {TRAVERTINO}99;
    font-weight: 700;
    white-space: nowrap;
}}
[class*="st-key-card_"] [data-testid="stPopoverButton"] p {{
    white-space: nowrap;
    font-weight: 700;
}}
[class*="st-key-card_"] [data-testid="stPopoverButton"]:hover {{
    color: {OTTONE};
    background: transparent;
}}
/* il codice di una voce di listino ha accanto il punto interrogativo della
   nota: in 45 px andava a capo, e il codice diventava alto due righe */
[class*="st-key-card_"] [data-testid="stHorizontalBlock"]
[data-testid="stMarkdownContainer"] p {{
    white-space: nowrap;
}}
/* Il parziale, incolonnato a destra: è la cifra della riga, e a filo si
   legge scorrendo il computo invece di ballare dietro alla lunghezza del
   prezzo. L'allineamento sta qui e non nel testo proprio per poter usare
   il markdown normale di Streamlit — vedi il commento in riga_voce_computo. */
[class*="st-key-parz_"] {{
    text-align: right;
    /* ⚠️ IL NUMERO STRANO. Una colonna che contiene solo testo — niente
       caselle — collassa ad altezza ZERO, e Streamlit centra le colonne
       con un margine calcolato sulla loro altezza: centrava il vuoto, e
       il testo cominciava dal centro andando in giù. Il parziale finiva
       sette pixel sotto le cifre accanto, in OGNI riga.
       Dare un'altezza alla colonna peggiora (il margine resta quello di
       prima e si somma), toglierlo non si può — è calcolato a valle.
       Resta lo scarto: −0,63rem, misurato in pagina finché le due cifre
       non stanno sullo stesso filo. Vale a qualunque altezza di riga:
       provato a 41, 54, 72 e 74 px, residuo un decimo di pixel. */
    margin-top: -0.674rem;
}}
/* Le cifre del parziale, un punto più grandi del resto della riga: sono
   il numero che si legge scorrendo il computo. L'intestazione no — è una
   didascalia, e resta della misura delle altre.
   ⚠️ Serve la specificità della scheda: la regola che uniforma i corpi
   («… stHorizontalBlock *») è più specifica di un solo attributo, e senza
   il prefisso vincerebbe lei. */
[class*="st-key-card_"] [class*="st-key-parz_"] p {{
    text-align: right;
    margin: 0;
    font-size: 0.94rem;
}}
/* L'intestazione della colonna: a destra come le cifre che intesta, ma
   senza la correzione — è una didascalia in fila con le altre. */
[class*="st-key-tparz_"],
[class*="st-key-tparz_"] p {{
    text-align: right;
}}
/* ⚠️ IL FILO FRA DUE VOCI È IL BORDO DELLA RIGA, non un elemento a sé.
   Come <hr> era una cosa in mezzo a due righe, con l'aria del blocco sopra
   e la sua sotto: cadeva storto nel vuoto — otto pixel da una parte e tre
   dall'altra — e ogni tentativo di centrarlo si scontrava con margini che
   si sommano fra loro. Da bordo sta esattamente sul confine, e l'aria è
   quella della riga: uguale sopra e sotto per costruzione.
   La tinta la mette la regola della categoria, qui sotto. */
""")

    # ------------------------------------------------ la ✕ che toglie la voce
    # Non è un bottone come gli altri: è il gesto che smonta una riga del
    # documento, e deve stare in disparte finché non lo si cerca. Quindi
    # niente pastiglia — solo il segno, spento, centrato nella sua colonna.
    # Passandoci sopra si accende di rosso: sfumato dal centro, così il
    # colore nasce sotto la ✕ e sfuma via prima del bordo, invece di
    # accendersi come un quadrato pieno in mezzo alla riga.
    regole.append(f"""
/* Streamlit avvolge il bottone in tre gusci che si stringono sul contenuto:
   senza questi, la ✕ resta un segno da 16 px in una colonna da 25 e il
   bersaglio non si centra in niente. */
[class*="st-key-togli_"],
[class*="st-key-togli_"] .stButton,
[class*="st-key-togli_"] .stTooltipIcon,
[class*="st-key-togli_"] [data-testid="stTooltipHoverTarget"] {{
    width: 100%;
}}
[class*="st-key-togli_"] button {{
    display: flex;
    align-items: center;
    justify-content: center;
    width: 100%;
    min-height: 1.9rem;
    padding: 0;
    border: none;
    border-radius: 999px;
    background: transparent;
    color: {TRAVERTINO}80;
    font-size: 0.95rem;
    line-height: 1;
    transition: color .15s ease, background .15s ease;
}}
/* la ✕ è l'unico contenuto: si centra anche il suo paragrafo, che di suo
   nasce con i margini del testo e la spinge in alto a sinistra */
[class*="st-key-togli_"] button p {{
    margin: 0;
    line-height: 1;
}}
[class*="st-key-togli_"] button:hover,
[class*="st-key-togli_"] button:focus-visible {{
    color: {TRAVERTINO};
    background: radial-gradient(circle at center,
                                {COTTO}D9 0%, {COTTO}8C 55%,
                                {COTTO}00 100%);
    border: none;
    box-shadow: none;
}}
[class*="st-key-togli_"] button:active {{
    color: {TRAVERTINO};
    background: radial-gradient(circle at center,
                                {COTTO}FF 0%, {COTTO}B3 60%,
                                {COTTO}00 100%);
}}
""")
    return "<style>" + "".join(regole) + "</style>"


PASSI_STORIA_COMPUTO = 15


def registra_storia_computo(descrizione):
    """Istantanea di quantità e prezzi PRIMA di un'azione che li cambia.

    L'annulla del disegno non copriva il computo: svuotare una categoria per
    sbaglio, o riscrivere i prezzi col listino personale, era senza ritorno.

    Si registrano solo le azioni che cambiano tutto in un colpo — non la
    singola cifra battuta a mano, che si ricorregge da sé, e nemmeno le
    quantità che arrivano dal disegno quando il computo è agganciato: lì
    cambiano a ogni gesto, e la storia si riempirebbe di passi identici.
    """
    st.session_state.storia_computo.append({
        "descrizione": descrizione,
        "q": {v["codice"]: st.session_state.get(f"q_{v['codice']}") or 0.0
              for v in listino.VOCI},
        "p": {v["codice"]: st.session_state.get(f"p_{v['codice']}")
              or v["prezzo"] for v in listino.VOCI},
        "scelte": list(st.session_state.voci_scelte),
        "extra": dict(st.session_state.voci_extra),
        "scartate": list(st.session_state.voci_scartate),
    })
    del st.session_state.storia_computo[:-PASSI_STORIA_COMPUTO]


def annulla_computo():
    """Riporta indietro di un passo. Ritorna la descrizione, o None."""
    storia = st.session_state.storia_computo
    if not storia:
        return None
    passo = storia.pop()
    # Come per la planimetria: quantità e prezzi si riscrivono al giro dopo,
    # prima che i campi rinascano.
    st.session_state.listino_pending = passo["q"]
    st.session_state.prezzi_pending = passo["p"]
    st.session_state.voci_scelte = list(passo["scelte"])
    st.session_state.voci_extra = dict(passo["extra"])
    st.session_state.voci_scartate = list(passo["scartate"])
    return passo["descrizione"]


def barra_annulla_computo():
    """Il tasto per tornare indietro, con l'ultima operazione registrata."""
    storia = st.session_state.storia_computo
    if not storia:
        return
    c_und, c_info = st.columns([1, 3], vertical_alignment="center")
    if c_und.button(f"↩️ Annulla ({len(storia)})", width="stretch",
                    key="annulla_computo",
                    help="Torna indietro di un passo su quantità e prezzi "
                         "del computo. Non tocca le planimetrie."):
        fatto = annulla_computo()
        if fatto:
            st.toast(f"Annullato: {fatto} ↩️")
        st.rerun()
    c_info.caption(f"Ultima operazione sul computo: "
                   f"**{storia[-1]['descrizione']}**")


def pannello_listino_personale():
    """I tuoi prezzi, quelli che non se ne vanno col progetto.

    Il listino guida ha prezzi indicativi: correggerli a ogni operazione da
    capo era il lavoro che si rifaceva ogni volta. Qui si mettono da parte
    una volta e si riapplicano.
    """
    prezzi_salvati, quando = listino_personale.carica()
    correnti = {v["codice"]: st.session_state.get(f"p_{v['codice']}")
                for v in listino.VOCI}
    miei = listino_personale.scostamenti(listino.VOCI, correnti)
    da_scrivere = listino_personale.da_applicare(
        prezzi_salvati, listino.VOCI, correnti)

    if prezzi_salvati:
        titolo = (f"📓 Il mio listino — {len(prezzi_salvati)} prezzi"
                  + (f", aggiornato il {quando}" if quando else ""))
    else:
        titolo = "📓 Il mio listino — non ancora salvato"

    with st.expander(titolo):
        st.caption(
            "I prezzi del listino guida sono indicativi: quando li correggi "
            "valgono **solo per questo progetto**. Qui li metti da parte una "
            "volta sola e li ritrovi in tutti i progetti che verranno. Si "
            "salvano **solo quelli che hai cambiato**: le voci che non hai "
            "toccato continuano a seguire il listino guida.")
        s1, s2 = st.columns(2)
        if s1.button(f"💾 Salva i {len(miei)} prezzi di questo progetto",
                     disabled=not miei, width="stretch",
                     help="Sovrascrive il listino personale con i prezzi "
                          "che hai corretto qui."):
            try:
                file = listino_personale.salva(miei)
                st.toast(f"Listino personale salvato: {len(miei)} prezzi ✔")
                st.caption(f":gray[{file}]")
                st.rerun()
            except OSError as errore:
                st.error(f"Non sono riuscito a salvare il listino: {errore}")
        if s2.button(f"📥 Applica il mio listino ({len(da_scrivere)} voci)",
                     disabled=not da_scrivere, width="stretch",
                     help="Riscrive i prezzi di questo progetto con i tuoi. "
                          "Le quantità non si toccano."):
            registra_storia_computo("applicazione del listino personale")
            st.session_state.prezzi_pending = dict(da_scrivere)
            st.toast(f"{len(da_scrivere)} prezzi aggiornati ✔")
            st.rerun()

        if not miei and not prezzi_salvati:
            st.caption(":gray[Correggi il prezzo di qualche voce qui sotto: "
                       "poi potrai metterlo da parte.]")
        elif prezzi_salvati and not da_scrivere:
            st.caption(":green[Questo progetto usa già i tuoi prezzi.]")

        if prezzi_salvati:
            if st.checkbox("Voglio cancellare il mio listino",
                           key="conf_elimina_listino"):
                if st.button("🗑️ Cancella il listino personale"):
                    listino_personale.elimina()
                    st.toast("Listino personale cancellato")
                    st.rerun()


def scrivi_testo_voce(chiave):
    """Riporta il testo della casella nella chiave di verità."""
    st.session_state[chiave] = (
        st.session_state.get(f"{chiave}_w") or "").strip()


def scrivi_unita_voce(codice):
    """L'unità riscritta, con la proposta del «a corpo».

    Una voce a corpo di norma vale una volta, e il prezzo È l'importo:
    lasciarla a zero la farebbe sparire dai totali senza spiegare perché.
    Quindi passando ad «a corpo» la quantità diventa 1 — ma solo se era
    ancora vuota, e resta una casella come le altre: due volte lo stesso
    intervento a corpo è un caso normale, e chi scrive 2 ha ragione lui.
    """
    scrivi_testo_voce(f"u_{codice}")
    if (st.session_state.get(f"u_{codice}") == UM_A_CORPO
            and not float(st.session_state.get(f"q_{codice}") or 0.0)):
        st.session_state[f"q_{codice}"] = 1.0
        st.session_state.pop(f"q_{codice}_txt", None)


def scrivi_quantita_a_passi(codice):
    """Riporta la quantità della casella a frecce nella chiave di verità."""
    nuovo = float(st.session_state.get(f"qn_{codice}_w") or 0.0)
    reso = st.session_state.get(f"_reso_qn_{codice}")
    if reso is not None and abs(nuovo - float(reso)) > 0.005:
        segna_a_mano(codice)       # l'hai premuta tu: da ora comandi tu
    st.session_state[f"q_{codice}"] = nuovo
    st.session_state.pop(f"q_{codice}_txt", None)


def campo_quantita(colonna, codice, um):
    """La quantità: a frecce dove si contano pezzi, scritta dove si misura.

    Le voci «a corpo», «cad» e i punti si contano: due interventi, tre punti
    luce. Lì le frecce su e giù sono il gesto giusto e i decimali non
    servono. I metri quadri no: si misurano, spesso al centesimo, e un
    passo da 1 sarebbe d'intralcio.
    """
    if um not in UM_A_PASSI:
        st.session_state.pop(f"qn_{codice}_w", None)
        st.session_state.pop(f"_reso_qn_{codice}", None)
        campo_numero_it(colonna, f"Quantità {codice}", f"q_{codice}",
                        decimali=2)
        return
    # Stessa cautela di campo_numero_it: se il valore di verità è cambiato
    # da fuori (una quantità arrivata dal disegno, un progetto riaperto) la
    # casella va riscritta, altrimenti mostra il numero di prima.
    atteso = float(st.session_state.get(f"q_{codice}") or 0.0)
    if st.session_state.get(f"_reso_qn_{codice}") != atteso:
        st.session_state[f"_reso_qn_{codice}"] = atteso
        st.session_state[f"qn_{codice}_w"] = atteso
    colonna.number_input(
        f"Quantità {codice}", min_value=0.0, step=1.0, format="%.0f",
        key=f"qn_{codice}_w", label_visibility="collapsed",
        on_change=scrivi_quantita_a_passi, args=(codice,))


def riga_voce_computo(voce):
    """Una riga del computo: tutto modificabile, e la ✕ per toglierla.

    Descrizione e unità sono caselle come la quantità e il prezzo: la voce
    del listino è una bozza da adattare al cantiere, non un'etichetta da
    subire. Il codice resta quello del listino — è l'unica cosa che non si
    tocca, perché è la chiave con cui il disegno ritrova la voce da
    aggiornare e con cui il pool sa che questa voce è già presa.
    """
    codice = voce["codice"]
    c_cod, c_desc, c_um, c_qta, c_prezzo, c_parz, c_x = st.columns(
        [0.5, 3.17, 1.2, 0.85, 0.8, 1.0, 0.45],
        vertical_alignment="center")
    aiuto = voce.get("nota")
    if voce.get("analisi"):
        aiuto = (aiuto + "\n\n" if aiuto else "") + voce["analisi"]
    descrizione, um = testi_voce(voce)
    # Il CODICE è la maniglia della riga: si preme e si apre il pannellino
    # con tutto quello che riguarda la riga in quanto riga — l'ordine, la
    # categoria — più la nota del listino, che come suggerimento appeso a
    # un punto interrogativo in 45 px non si leggeva.
    # La ✎ accanto al codice dice che quella quantità l'hai scritta tu e
    # che il disegno non la tocca: senza un segno, una voce sganciata è
    # indistinguibile da una che il disegno aggiorna ancora.
    a_mano = codice in st.session_state.voci_a_mano
    with c_cod.popover(codice + (" ✎" if a_mano else ""),
                       help="Ordine, categoria e nota della voce"):
        st.markdown(f"**{codice}** · {descrizione}")
        if a_mano:
            st.caption(":orange[✎ Quantità scritta a mano: il disegno non "
                       "la aggiorna più.]")
            st.button("↺ Riaggancia al disegno", key=f"riagg_{codice}",
                      width="stretch", on_click=riaggancia_al_disegno,
                      args=(codice,))
        su, giu = st.columns(2)
        su.button("↑ Su", key=f"su_{codice}", width="stretch",
                  on_click=scambia_con_vicina, args=(codice, -1),
                  help="Scambia con la voce sopra, nella sua categoria")
        giu.button("↓ Giù", key=f"giu_{codice}", width="stretch",
                   on_click=scambia_con_vicina, args=(codice, 1),
                   help="Scambia con la voce sotto, nella sua categoria")
        if listino.voce_per_codice(codice) is None:
            # Una voce tua può anche aver sbagliato casa. Quelle di listino
            # no: la categoria è del catalogo, e vale per tutti i cantieri.
            st.divider()
            st.selectbox(
                "Sposta nella categoria", listino.CATEGORIE,
                index=(listino.CATEGORIE.index(voce["categoria"])
                       if voce["categoria"] in listino.CATEGORIE else 0),
                key=f"spostacat_{codice}")
            st.button("↔️ Sposta", key=f"sposta_{codice}",
                      on_click=sposta_voce_extra, args=(codice,),
                      help="Il codice cambia con la categoria: la serie "
                           "dice dove sta di casa la voce.")
        if aiuto:
            st.divider()
            st.caption(aiuto)
    # Un'AREA di testo, non una casella: le descrizioni vere sono lunghe
    # («Realizzazione di impianti di riscaldamento e raffrescamento in pompa
    # di calore canalizzata a soffitto…») e in una riga sola se ne leggeva
    # il primo terzo. Qui vanno a capo, su due righe; l'altezza la stringe
    # il CSS, perché Streamlit da sé non scende sotto i 68 px.
    c_desc.text_area(
        f"Descrizione {codice}", value=descrizione, key=f"d_{codice}_w",
        label_visibility="collapsed", height=68,
        on_change=scrivi_testo_voce, args=(f"d_{codice}",))
    # L'unità è una tendina, non una casella libera: le unità di un computo
    # sono sei o sette, e scriverle a mano vuol dire ritrovarsi «mq», «m2» e
    # «m²» sulla stessa stampa. In testa c'è quella di casa della categoria.
    scelte_um = unita_della_voce(voce, um)
    c_um.selectbox(
        f"Unità {codice}", scelte_um, index=scelte_um.index(um),
        key=f"u_{codice}_w", label_visibility="collapsed",
        on_change=scrivi_unita_voce, args=(codice,))
    campo_quantita(c_qta, codice, um)
    campo_numero_it(c_prezzo, f"Prezzo € {codice}", f"p_{codice}",
                    decimali=2)
    quantita = float(st.session_state.get(f"q_{codice}") or 0.0)
    prezzo = float(st.session_state.get(f"p_{codice}") or voce["prezzo"])
    # Il parziale sta a DESTRA nella sua colonna: è la cifra della riga, e
    # incolonnata a filo si legge scorrendo il computo — a sinistra ballava
    # dietro alla lunghezza del prezzo.
    # ⚠️ Al parziale NON si dà un'altezza. Gliene avevo messa una (1,85rem,
    # quanto le caselle) per allinearlo: il guscio che Streamlit mette
    # attorno a un markdown resta però alto quanto una riga di testo, e il
    # riquadro gli traboccava sotto — le cifre finivano sette pixel più in
    # basso di quelle accanto. Senza altezza il guscio cresce col contenuto
    # e ci pensa Streamlit a centrare la colonna, come fa per il codice.
    # ⚠️ Un <p>, non un <div>. Streamlit avvolge il markdown in un guscio
    # alto quanto UNA RIGA DI TESTO, e un <div> con la sua interlinea gli
    # traboccava sotto: le cifre del parziale finivano sette pixel più in
    # basso di quelle accanto, in ogni riga. Un <p> è esattamente quello
    # che Streamlit stesso scrive per il codice della voce — che infatti
    # era l'unica cella allineata — e si comporta come lui.
    # ⚠️ Markdown NORMALE, non HTML grezzo. Una colonna che contiene solo
    # HTML nostro collassa ad altezza ZERO, e Streamlit — che centra le
    # colonne con un margine calcolato sulla loro altezza — la centrava
    # come se fosse vuota: il testo finiva sette pixel sotto le cifre
    # accanto, in ogni riga. Col markdown suo la colonna ha un'altezza
    # vera, come quella del codice, che infatti era l'unica allineata.
    # A destra ci va per via del contenitore, che il CSS riconosce dalla
    # chiave.
    with c_parz.container(key=f"parz_{codice}"):
        if quantita > 0:
            st.markdown(f"**{euro(quantita * prezzo)}**")
        else:
            # non è uno zero come gli altri: è una voce che hai scelto e
            # non hai ancora quantificato, e fuori di qui (totali, PDF)
            # non esiste
            st.markdown(":orange[da quantificare]")
    # Anche le voci scritte a mano tornano nel pool: una lavorazione
    # inventata per questo cantiere si toglie e si rimette come le altre, e
    # buttarla via al primo ripensamento vorrebbe dire riscriverla da capo.
    # Nemmeno il cestino nel pool la cancella: la mette fra gli scarti, da
    # cui «Rimetti tutte» la ripesca. Non c'è una via per perderla.
    c_x.button("✕", key=f"togli_{codice}", on_click=togli_dal_computo,
               args=(codice,), help="Rimanda la voce nel pool")


def voce_trovata(voce, termine):
    """La voce risponde alla ricerca? Codice, descrizione, unità e nota.

    Più parole = tutte devono comparire: «posa gres» trova la voce anche se
    nel listino le due parole sono lontane.
    """
    if not termine:
        return True
    descrizione, um = testi_voce(voce)
    testo = (f"{voce['codice']} {descrizione} {um} "
             f"{voce.get('nota') or ''}").lower()
    return all(parola in testo for parola in termine.lower().split())


def grafico_totali(totali):
    """Barre orizzontali: una barra, la tinta della sua categoria.

    Le stesse tinte delle schede e delle pastiglie del riepilogo: il colore
    qui non decora, è il modo in cui si riconosce una categoria in tutta la
    pagina. Con un solo oro per tutte, questo grafico era l'unico posto in
    cui bisognava rileggere l'etichetta per sapere di che si parla.
    """
    categorie = sorted(totali, key=totali.get)
    valori = [totali[c] for c in categorie]
    fig = go.Figure(go.Bar(
        x=valori,
        y=categorie,
        orientation="h",
        marker_color=[COLORI_CATEGORIE.get(c, (OTTONE, ""))[0]
                      for c in categorie],
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
        textfont=dict(color=[colore_testo_su(c) for c in colori], size=11),
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
            f'color:{colore_testo_su(colore)};'
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
        # intestazioni come etichette campione: nominano le colonne
        '<thead><tr style="color:#C3C8CE;font-size:0.7rem;text-align:left;'
        'text-transform:uppercase;letter-spacing:.12em;font-weight:600;">'
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
    chip = ("display:inline-block;width:11px;height:11px;"
            "margin-right:5px;vertical-align:-1px;border:1px solid #3C4C6E;")
    return (
        '<div style="font-size:0.72rem;color:#A9B4C9;margin:-6px 0 10px;">'
        f'<span style="{chip}background:#F8696B;"></span>in perdita'
        '&nbsp;&nbsp;·&nbsp;&nbsp;'
        f'<span style="{chip}background:#FFFFFF;"></span>pareggio '
        f'({pareggio})&nbsp;&nbsp;·&nbsp;&nbsp;'
        f'<span style="{chip}background:#63BE7B;"></span>in utile</div>')


def intestazione_bp(testo):
    """Testata di colonna dello studio di fattibilità.

    È un'etichetta campione a piena larghezza: nomina la colonna e basta.
    ⚠️ Il testo inglese («ESTIMATED») è il vocabolario con cui l'utente
    legge quei numeri dal suo foglio Excel: si veste, non si traduce.
    """
    return (
        f'<div style="background:{ARDESIA_CHIARA};'
        f'border:1px solid {OTTONE}73;padding:5px 10px;margin:8px 0 6px;'
        f'text-align:center;font-size:.7rem;font-weight:700;'
        f'text-transform:uppercase;letter-spacing:.12em;'
        f'color:{TRAVERTINO};">{testo}</div>')


def righe_bp(righe):
    """Blocchetto riepilogo stile Excel: righe etichetta/valore compatte.

    righe: [(etichetta, valore, stile)] con stile None | "bold" |
    "buono" (verde) | "cattivo" (rosso).
    """
    pezzi = []
    for etichetta, valore, stile in righe:
        # Una riga senza valore non si scrive: il trattino che ci stava al
        # posto del numero non diceva niente e compariva a mezz'aria in
        # varie schede, sembrando un difetto della pagina.
        if valore is None or str(valore).strip() in ("", "—"):
            continue
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
        f'<div style="font-size:0.72rem;color:#A9B4C9;margin:10px 0 2px;'
        f'padding:6px 9px;border:1px solid {CEMENTO}66;line-height:1.5;">'
        f'Risultati calcolati su<br>acquisto <b style="color:{TRAVERTINO};">'
        f'{cifra(acquisto)}</b> · vendita <b style="color:{TRAVERTINO};">'
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
    # dentro un contenitore nascosto: l'iframe è solo un modo per far
    # girare uno script, ma Streamlit gli lascia comunque un ingombro a
    # video — un trattino che compariva in mezzo alla pagina
    with st.container(key="cme_script_prezzi"):
        st.iframe("""<!doctype html><html><body><script>
(function () {
  var doc;
  try { doc = window.parent.document; } catch (errore) { return; }
  if (doc.__cmeGuardiaPrezzi) return;
  doc.__cmeGuardiaPrezzi = true;
  var CAMPI = [["bp_in_acq", "acq"], ["bp_in_ven", "ven"]];
  // Il campo contiene un numero all'italiana — «140.000» — e parseFloat lì
  // legge 140. Il confronto con l'applicato (140000) risultava sempre
  // diverso, quindi l'avviso «premi Invio» restava acceso PER SEMPRE su
  // ogni importo da mille euro in su, e premere Invio non lo spegneva mai:
  // l'unico avviso che avrebbe dovuto contare era diventato rumore fisso
  // sotto i due numeri principali del business plan.
  // Queste sono le stesse regole di numero_da_it() in formato.py.
  function numeroDaIt(testo) {
    var t = String(testo == null ? "" : testo)
              .replace(/[€%]/g, "").replace(/[\\s\\u00A0]/g, "");
    if (!t) return NaN;
    if (t.indexOf(",") >= 0) {
      t = t.replace(/\\./g, "").replace(",", ".");
    } else if (t.indexOf(".") >= 0) {
      var pezzi = t.replace(/^[+-]/, "").split(".");
      var migliaia = pezzi.length > 1 && pezzi[0] !== ""
                     && pezzi.slice(1).every(function (p) {
                          return p.length === 3;
                        });
      if (migliaia) t = t.replace(/\\./g, "");
    }
    return Number(t);
  }
  function controlla() {
    var marcatore = doc.getElementById("cme-prezzi-applicati");
    if (!marcatore) return;
    CAMPI.forEach(function (campo) {
      var cella = doc.querySelector(".st-key-" + campo[0]);
      if (!cella) return;
      var input = cella.querySelector("input");
      if (!input) return;
      var applicato = parseFloat(marcatore.dataset[campo[1]] || "0");
      var digitato = numeroDaIt(input.value);
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


def riga_costo_bp(etichetta, centro=None, destra=None, iva=None,
                  imponibile=None):
    """Riga del dettaglio costi: etichetta | % | netto | IVA % | IVA €.

    centro e destra possono essere: None (mostra «/»), una stringa (testo
    di sola lettura) oppure un dizionario {"chiave": …, **kwargs} che
    diventa un campo modificabile.

    iva: la chiave dell'aliquota di questa voce (`bp_iva_notaio`…). L'IVA
    in euro non è modificabile: è il prodotto di due numeri che stanno lì
    accanto, e lasciarla scrivere aprirebbe una terza sincronizzazione da
    tenere allineata — di quelle in questa scheda ne bastano due.
    """
    # la colonna «Netto» ospita cifre a 7 numeri con i loro stepper: stretta
    # com'era, i valori uscivano troncati a metà ("16200,0(")
    c_eti, c_inp, c_val, c_ivapct, c_ivaeur = st.columns(
        [1.5, 0.75, 1.15, 0.7, 1.0], vertical_alignment="center")
    c_eti.markdown(f":gray[{etichetta}]")

    # ⚠️ L'etichetta accessibile portava la chiave di sessione — «Imposte
    # d'acquisto bp_imposta», «… bp_imposta_eur», «… bp_iva_imposta» — che
    # serviva a distinguere i campi fra loro ma è finita dritta in ciò che
    # legge uno screen reader: tre caselle della stessa riga annunciate con
    # il nome di una variabile Python. La chiave la unicità la dà già da
    # sola (`key=`); l'etichetta può quindi dire il ruolo, in italiano.
    def cella(colonna, contenuto, a_destra=False, ruolo=""):
        nome = f"{etichetta} · {ruolo}" if ruolo else etichetta
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
            if chiave in CAMPI_NUMERO_IT:
                # gli importi: casella di testo, per avere le migliaia
                campo_numero_it(colonna, nome, chiave,
                                decimali=CAMPI_NUMERO_IT[chiave][0],
                                segnaposto=None,
                                aiuto=impostazioni.get("help"))
            else:
                # le percentuali restano numeriche: niente migliaia da
                # separare, e il passo a freccette lì serve davvero
                colonna.number_input(nome, key=chiave,
                                     label_visibility="collapsed",
                                     **impostazioni)

    cella(c_inp, centro, ruolo="percentuale")
    cella(c_val, destra, a_destra=True, ruolo="importo netto")

    if iva is None:
        cella(c_ivapct, None)
        cella(c_ivaeur, None)
        return 0.0
    c_ivapct.number_input(
        f"{etichetta} · aliquota IVA", key=iva,
        min_value=0.0, max_value=50.0,
        step=1.0, format="%.2f", label_visibility="collapsed",
        help="Aliquota di questa voce: 22% è l'ordinaria, 10% i lavori "
             "edili, 0% le voci che l'IVA non ce l'hanno (l'imposta di "
             "registro è già un'imposta).")
    if imponibile is None:
        imponibile = float(st.session_state.get(destra["chiave"], 0.0)
                           if isinstance(destra, dict) else 0.0)
    importo_iva = fattibilita.iva_su(imponibile, st.session_state[iva])
    cella(c_ivaeur, euro(importo_iva), a_destra=True, ruolo="IVA in euro")
    return importo_iva


def campo_numero_it(colonna, etichetta, chiave, decimali=2,
                    label_visibility="collapsed", aiuto=None,
                    segnaposto=None):
    """Casella per un importo, scritta e riletta all'italiana.

    `st.number_input` non sa raggruppare le migliaia — accetta solo formati
    printf — quindi mostrava `145000` dove serve `145.000`. Qui la casella è
    di testo: la formattazione la fa l'app.

    ⚠️ Qui si DISEGNA soltanto. Il testo viene riletto a inizio pagina
    (`rileggi_campi_numero_it`), prima di ogni calcolo: farlo qui, dove il
    campo sta sotto ai risultati, li lascerebbe indietro di
    un'interazione. Il valore di verità resta in `chiave`, la casella vive
    in «chiave_txt».
    """
    valore = float(st.session_state.get(chiave) or 0.0)
    # Si annota il valore con cui la casella nasce. Serve a riconoscere il
    # testo VECCHIO: se al giro dopo il valore di verità non è più questo,
    # vuol dire che l'ha cambiato qualcun altro — un progetto aperto, un
    # prezzo arrivato dall'MCA — e allora il testo nella casella non va
    # riletto, va buttato. Senza questa annotazione il testo di prima
    # riscriveva il valore appena caricato, e i numeri di un progetto
    # salvato sparivano riaprendolo.
    st.session_state[f"_reso_{chiave}"] = valore
    # ⚠️⚠️ Il testo si scrive DIRETTAMENTE nello stato del widget, non con
    # `value=`. Passare `value=` funziona solo la prima volta: da lì in poi
    # la casella nel BROWSER si tiene quello che ha dentro e ignora il
    # valore nuovo. È la differenza che è costata più tempo di ogni altra in
    # questo progetto — nei test con AppTest il browser non c'è, `value=`
    # sembra funzionare, e il difetto resta invisibile: nella pagina vera si
    # vedeva «9,00 %» accanto a «0,00 €» mentre il calcolo era giusto e
    # finiva regolarmente nei totali.
    testo = numero_it(valore, decimali)
    if st.session_state.get(f"{chiave}_txt") != testo:
        st.session_state[f"{chiave}_txt"] = testo
    return colonna.text_input(
        etichetta, key=f"{chiave}_txt", help=aiuto, placeholder=segnaposto,
        label_visibility=label_visibility)


# Campi in cui l'utente scrive un importo: quanti decimali mostrare e che
# cosa ricalcolare quando cambiano (il sincronismo %↔€ del business plan).
# Le voci del dettaglio costi che hanno un'IVA, con l'aliquota che la
# governa. La ristrutturazione sta fuori: il suo imponibile non è un campo
# ma il valore effettivo (computo, consuntivo o cifra a mano).
VOCI_CON_IVA = (
    ("bp_imposta_eur", "bp_iva_imposta"),
    ("bp_imposte_fisse", "bp_iva_imposte_fisse"),
    ("bp_notaio", "bp_iva_notaio"),
    ("bp_mutuo", "bp_iva_mutuo"),
    ("bp_imprevisti", "bp_iva_imprevisti"),
    ("bp_ag_in_eur", "bp_iva_ag_in"),
)

# chiave: (decimali, cosa ricalcolare, minimo)
CAMPI_NUMERO_IT = {
    "bp_acquisto": (0, "bp_ricalcola_euro", 0.0),
    "bp_vendita": (0, "bp_ricalcola_euro", 0.0),
    # il passo delle matrici non può essere zero: le colonne diventerebbero
    # tutte lo stesso prezzo
    "bp_passo": (0, None, 1000.0),
    "bp_imposta_eur": (2, "bp_pct_da_euro_imposta", 0.0),
    "bp_imposte_fisse": (2, None, 0.0),
    "bp_notaio": (2, None, 0.0),
    "bp_mutuo": (2, None, 0.0),
    "bp_imprevisti": (2, "bp_pct_da_euro_imprevisti", 0.0),
    "bp_ag_in_eur": (2, "bp_pct_da_euro_ag_in", 0.0),
    "bp_ag_out_eur": (2, "bp_pct_da_euro_ag_out", 0.0),
    "bp_ristr": (2, None, 0.0),
    "cant_contratto": (2, None, 0.0),
    "cant_extra": (2, None, 0.0),
}


def rileggi_campi_numero_it():
    """Da testo a numero, a inizio pagina e prima di ogni calcolo.

    Tre passaggi, in quest'ordine: si rileggono le caselle, si ricalcolano i
    campi che dipendono da loro, e solo allora si buttano via le caselle il
    cui testo non è più la scrittura corretta del valore — così rinascono
    formattate («145000» diventa «145.000») senza che l'utente perda quello
    che stava battendo. Buttarle via QUI, prima che i widget nascano, è
    l'unico momento in cui Streamlit lo consente.

    Quello che non è un numero non si applica e non si cancella: resta
    scritto nella casella, e il valore di prima continua a valere.
    """
    da_ricalcolare = []
    for chiave, (_, ricalcolo, minimo) in CAMPI_NUMERO_IT.items():
        testo = st.session_state.get(f"{chiave}_txt")
        if testo is None:
            continue
        # Il valore è cambiato dopo che la casella era stata disegnata:
        # quel testo racconta il passato e non deve tornare a comandare.
        reso = st.session_state.get(f"_reso_{chiave}")
        attuale = float(st.session_state.get(chiave) or 0.0)
        if reso is not None and abs(attuale - reso) > 0.0005:
            st.session_state.pop(f"{chiave}_txt")
            continue
        valore = numero_da_it(testo)
        if valore is None:
            continue
        valore = max(minimo, valore)
        if abs(valore - float(st.session_state.get(chiave) or 0.0)) > 0.0005:
            st.session_state[chiave] = valore
            if ricalcolo:
                da_ricalcolare.append(ricalcolo)
    for nome in dict.fromkeys(da_ricalcolare):      # una volta sola ciascuno
        globals()[nome]()
    for chiave, (decimali, _, _minimo) in CAMPI_NUMERO_IT.items():
        testo = st.session_state.get(f"{chiave}_txt")
        if testo is None or numero_da_it(testo) is None:
            continue
        if testo != numero_it(st.session_state.get(chiave) or 0.0, decimali):
            st.session_state.pop(f"{chiave}_txt")


def _percentuale_da_importo(chiave_pct, chiave_euro, base):
    """Ricava la percentuale da un importo scritto a mano.

    ⚠️ SEI decimali, non tre. Con tre, l'importo rifatto all'indietro non
    tornava: 6.000 € su 145.000 fanno il 4,137931%, che arrotondato a 4,138
    ridà 6.000,10 — e l'utente vedeva comparire dieci centesimi dal nulla.

    E per quel giro l'importo non si tocca: l'ha appena scritto una persona,
    e nessun ricalcolo deve permettersi di correggerla di un centesimo.
    """
    st.session_state[chiave_pct] = round(
        float(st.session_state.get(chiave_euro) or 0.0) / base * 100, 6)
    st.session_state.setdefault("_importi_scritti_a_mano", set()).add(
        chiave_euro)


def _importo_derivato(chiave, valore):
    """Scrive un importo calcolato e BUTTA VIA la sua casella di testo.

    ⚠️ Senza il secondo passaggio la percentuale scritta a mano tornava
    indietro da sola: la casella dell'importo conserva il testo del valore
    VECCHIO, a inizio pagina quel testo viene riletto e riscrive l'importo
    appena calcolato, e da lì la percentuale si ricostruisce all'indietro
    sul numero sbagliato. Scriveva 4% e si ritrovava 9%.

    Buttandola via qui — dentro una callback, prima che i widget del giro
    nuovo nascano — la casella rinasce dal valore giusto.
    """
    if chiave in st.session_state.get("_importi_scritti_a_mano", ()):
        return          # l'ha scritto l'utente in questo giro: comanda lui
    st.session_state[chiave] = round(valore, 2)
    st.session_state.pop(f"{chiave}_txt", None)


def bp_ricalcola_euro():
    """Aggiorna i campi € derivati dalle percentuali del business plan.

    Da chiamare quando cambiano i prezzi o le percentuali: tiene i campi
    € (modificabili) allineati alle % — la sincronizzazione inversa la
    fanno bp_pct_da_euro_*.
    """
    prezzo_a = st.session_state.get("bp_acquisto") or 0.0
    prezzo_v = st.session_state.get("bp_vendita") or 0.0
    iva = 1 + (st.session_state.get("bp_iva_ag") or 0.0) / 100
    _importo_derivato("bp_imposta_eur",
                      prezzo_a * st.session_state.bp_imposta / 100)
    # ⚠️ IMPONIBILI: l'IVA delle provvigioni sta nella sua colonna, come
    # per tutte le altre voci. Lasciarla dentro l'importo la nascondeva
    # proprio dove serve vederla.
    _importo_derivato("bp_ag_in_eur",
                      prezzo_a * st.session_state.bp_ag_in / 100)
    _importo_derivato("bp_ag_out_eur",
                      prezzo_v * st.session_state.bp_ag_out / 100)
    # Gli imprevisti dell'operazione si calcolano sull'IMPORTO DEI LAVORI,
    # non sul prezzo d'acquisto: la base la deposita la scheda quando sa
    # quale ristrutturazione sta considerando (computo, consuntivo o cifra
    # a mano). Senza base restano quello che sono.
    base = st.session_state.get("_base_imprevisti")
    if base:
        _importo_derivato("bp_imprevisti",
                          base * st.session_state.bp_imprevisti_pct / 100)


def bp_pct_da_euro_imprevisti():
    """Se scrivi l'importo, la percentuale si adegua (come per le agenzie)."""
    base = st.session_state.get("_base_imprevisti") or 0.0
    if base > 0:
        _percentuale_da_importo("bp_imprevisti_pct", "bp_imprevisti", base)


def bp_pct_da_euro_imposta():
    prezzo = st.session_state.get("bp_acquisto") or 0.0
    if prezzo > 0:
        _percentuale_da_importo("bp_imposta", "bp_imposta_eur", prezzo)


def bp_pct_da_euro_ag_in():
    prezzo = st.session_state.get("bp_acquisto") or 0.0
    if prezzo > 0:
        _percentuale_da_importo("bp_ag_in", "bp_ag_in_eur", prezzo)


def bp_pct_da_euro_ag_out():
    prezzo = st.session_state.get("bp_vendita") or 0.0
    if prezzo > 0:
        _percentuale_da_importo("bp_ag_out", "bp_ag_out_eur", prezzo)


@st.cache_data(show_spinner=False, max_entries=4)
def excel_bytes(df_computo, df_riepilogo, df_progetto, df_superfici=None,
                df_materiali=None):
    """Il file Excel da scaricare.

    Il bottone di scaricamento vuole i byte già pronti, quindi il file veniva
    ricostruito a OGNI interazione con l'app — 70 millisecondi buttati per un
    bottone che magari non premi mai. Con la cache si ricostruisce solo quando
    cambiano davvero le tabelle.

    I materiali stanno in un foglio LORO, non in coda al computo: non sono
    voci di computo, e sommarli lì sotto rifarebbe con Excel proprio la
    confusione che l'allegato esiste per evitare.
    """
    buffer = io.BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df_computo.to_excel(writer, sheet_name="Computo", index=False)
        df_riepilogo.to_excel(writer, sheet_name="Riepilogo", index=False)
        if df_materiali is not None and len(df_materiali):
            df_materiali.to_excel(writer, sheet_name="Materiali", index=False)
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
    """Riporta zone, muri e scala com'erano prima dell'ultima operazione.

    Restituisce {descrizione, scala_persa}. La scala fa parte di ciò che si
    annulla — deve esserlo, altrimenti una calibrazione sbagliata sarebbe
    irrimediabile — ma tornando indietro oltre il momento in cui è stata
    impostata la planimetria resta SENZA scala, e da lì in poi le misure non
    sono più in metri: niente cifre mentre si traccia, niente m² sulle aree.
    Succede in silenzio e sembra un guasto, quindi va detto (2026-08-09).
    """
    storia = st.session_state.get("storia") or []
    if not storia:
        return None
    passo = storia.pop()
    per_uid = {s["uid"]: s for s in passo["piante"]}
    scala_persa = False
    for pianta in st.session_state.piante:
        salvata = per_uid.get(pianta["uid"])
        if salvata is None:
            continue
        if pianta["mpp"] and not salvata["mpp"]:
            scala_persa = True
        pianta["mpp"] = salvata["mpp"]
        pianta["prossimo_id"] = salvata["prossimo_id"]
        pianta["zone"] = copy.deepcopy(salvata["zone"])
        pianta["pareti"] = copy.deepcopy(salvata["pareti"])
    # le selezioni potrebbero puntare a roba che non esiste più
    st.session_state.sel_zona = None
    st.session_state.sel_parete = None
    st.session_state.scala_temp = None
    st.session_state.pop("ultimo_rilevamento", None)
    return {"descrizione": passo["descrizione"], "scala_persa": scala_persa}


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


def _payload_progetto():
    """Il progetto come dizionario: la fonte sia del file sia della firma."""
    payload = {
        "progetto": {
            "nome": st.session_state.prg_nome,
            "committente": st.session_state.prg_committente,
            "oggetto": st.session_state.prg_oggetto,
            "luogo": st.session_state.prg_luogo,
            "data": st.session_state.prg_data.isoformat(),
            "aliquota_iva": st.session_state.iva,
        },
        # le voci inventate: si salvano per intero, il listino non le ha
        "voci": [
            {"categoria": v["categoria"], "codice": codice,
             "descrizione": v["descrizione"], "um": v["um"],
             "parti": None, "lunghezza": None, "larghezza": None,
             "altezza": None,
             "quantita_manuale": st.session_state.get(f"q_{codice}") or 0.0,
             "prezzo": st.session_state.get(f"p_{codice}") or v["prezzo"]}
            for codice, v in st.session_state.voci_extra.items()
        ],
        "listino_stato": {
            v["codice"]: {
                "q": float(st.session_state.get(f"q_{v['codice']}") or 0.0),
                "p": float(st.session_state.get(f"p_{v['codice']}")
                           or v["prezzo"]),
            }
            for v in listino.VOCI
            if (st.session_state.get(f"q_{v['codice']}") or 0.0) > 0
            or float(st.session_state.get(f"p_{v['codice']}")
                     or v["prezzo"]) != v["prezzo"]
        },
        # quali voci sono nel computo, nell'ordine in cui ci sono entrate
        "voci_scelte": list(st.session_state.voci_scelte),
        # e quali sono state tolte dal pool: è una scelta del progetto,
        # non una modifica al listino, e va con lui
        "voci_scartate": list(st.session_state.voci_scartate),
        # le quantità scritte a mano restano a mano anche riaprendo: sono
        # una decisione, non un caso
        "voci_a_mano": list(st.session_state.voci_a_mano),
        # l'allegato dei materiali: elenco suo, fuori dal computo, e infatti
        # fuori anche da "voci"
        "materiali": materiali_da_df(st.session_state.get(
            "df_materiali_live", st.session_state.df_materiali)),
        # e come sono state riscritte: solo quelle che si discostano dal
        # listino, così il file non porta 69 copie di quello che c'è già
        "testi_voci": {
            v["codice"]: {
                "d": st.session_state.get(f"d_{v['codice']}") or None,
                "u": st.session_state.get(f"u_{v['codice']}") or None,
            }
            for v in listino.VOCI
            if (st.session_state.get(f"d_{v['codice']}")
                or st.session_state.get(f"u_{v['codice']}"))
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
        # ⚠️ Il trattino delle tendine è "non indicato", non una voce: nel
        # progetto ci va None, o riaprendolo la griglia cercherebbe "—"
        # fra i coefficienti e non lo troverebbe.
        "mca_soggetto": {
            campo: (None if st.session_state.get(f"sog_{campo}") == "—"
                    else st.session_state.get(f"sog_{campo}"))
            for campo in merito.CAMPI
        },
        "mca_statistica": st.session_state.mca_statistica,
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
                     "riv_alt": st.session_state.riv_alt,
                     "riv_porte_n": st.session_state.riv_porte_n,
                     "riv_finestre_n": st.session_state.riv_finestre_n,
                     "fin_n": st.session_state.fin_n,
                     "fin_larg": st.session_state.fin_larg,
                     "fin_alt": st.session_state.fin_alt,
                     "pf_n": st.session_state.pf_n,
                     "pf_larg": st.session_state.pf_larg,
                     "pf_alt": st.session_state.pf_alt,
                     "apert_dem_n": st.session_state.apert_dem_n,
                     "apert_cos_n": st.session_state.apert_cos_n,
                     "apert_car_n": st.session_state.apert_car_n,
                     "apert_larg": st.session_state.apert_larg,
                     "apert_alt": st.session_state.apert_alt},
        "auto_computo": st.session_state.auto_computo,
        "cantiere": {"contratto": st.session_state.cant_contratto,
                     "extra": st.session_state.cant_extra,
                     "sal": st.session_state.cant_sal},
        "piante": [pianta_a_json(p) for p in st.session_state.piante],
    }
    return payload


def progetto_json_bytes():
    """L'intero progetto (computo + planimetrie) come JSON scaricabile."""
    return json.dumps(_payload_progetto(), ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


def firma_progetto():
    """Firma del progetto SENZA le immagini: dice se qualcosa è cambiato.

    Serializzare tutto per accorgersi di una modifica costa quanto salvare:
    con sei planimetrie sono quasi 9 MB di base64 a ogni riesecuzione. Qui le
    immagini si riducono alla loro lunghezza — cambiano solo se la planimetria
    cambia davvero — e il resto del progetto viaggia intero, perché è la parte
    che si modifica di continuo e leggera.
    """
    payload = _payload_progetto()
    # ⚠️ La chiave dell'immagine è «immagine» (vedi pianta_a_json), non «src»:
    # sbagliarla non dà errore, lascia semplicemente il base64 dentro il
    # calcolo e la firma torna a costare quanto un salvataggio.
    payload["piante"] = [{**p, "immagine": len(p.get("immagine") or "")}
                         for p in payload["piante"]]
    return hashlib.md5(json.dumps(payload, ensure_ascii=False, default=str,
                                  separators=(",", ":"))
                       .encode("utf-8")).hexdigest()


# ----------------------------------------- il salvataggio è solo manuale
# ⚠️ Qui c'era un salvataggio automatico su un file di appoggio, riscritto
# ogni quindici secondi e offerto come ripristino alla partenza. È stato
# TOLTO, e non per semplificare: faceva danno.
#
# Il file conteneva una fotografia dello stato in un momento qualunque, e
# quello stato poteva essere già svuotato — Streamlit cancella i valori dei
# widget che non ridisegna, quindi bastava un errore a metà pagina perché
# la fotografia successiva contenesse i predefiniti al posto dei numeri
# scritti a mano. Riprendendo quel file si rimettevano in tavola proprio i
# valori che si volevano recuperare, ma di fabbrica. È l'utente ad averlo
# riconosciuto, dopo esserci incappato tre volte.
#
# Un salvataggio è un gesto: quel momento lo sceglie una persona, e quello
# che c'era dentro andava bene. Un'istantanea presa da sola non ha nessuno
# che risponda della sua correttezza — e su un'app che decide acquisti da
# centinaia di migliaia di euro, una rete di sicurezza che restituisce dati
# sbagliati è peggio di nessuna rete: quella la si guarda con sospetto,
# questa ti convince di aver recuperato.
#
# Resta il tasto Salva, che scrive in archivio e funziona; resta la
# riapertura automatica dell'ultimo salvataggio MANUALE; e resta l'avviso
# di modifiche non salvate, che adesso è l'unica cosa fra il lavoro e un
# F5 — motivo per cui sta in testata e non in fondo alla pagina.


def impronta(dati):
    """Firma breve del progetto, per capire se è cambiato dall'ultimo salvataggio."""
    return hashlib.md5(dati or b"").hexdigest()


def salva_e_ripristina_bp(stato, copia, predefiniti=None):
    """Tiene in vita i valori del business plan scritti a mano.

    Aggiorna `copia` con quello che c'è in `stato`, e rimette in `stato`
    quello che manca — prima da `copia`, poi dai predefiniti.

    ⚠️ Perché serve: molti campi del business plan sono `st.number_input`
    che usano la chiave come valore, e quella chiave è dello WIDGET.
    **Streamlit cancella lo stato dei widget che non ridisegna**: basta che
    un errore fermi lo script prima della scheda fattibilità e quei valori
    spariscono, per poi tornare ai predefiniti al giro successivo — senza
    ricaricare niente e senza che nessuno lo dica. È successo davvero: 6.000 €
    forzati su Agenzia IN tornati a 3,00%, due volte.

    Gli importi scritti con `campo_numero_it` non ne soffrivano, perché lì il
    valore vero sta in `chiave` e il widget è `chiave_txt` — la stessa
    separazione che il computo usa da sempre per quantità e prezzi
    (le «chiavi di verità»). Questa funzione la porta anche qui.

    La copia insegue i valori, non li congela: se il campo cambia, cambia
    anche lei. Altrimenti dopo un «Progetto nuovo» rimetterebbe in tavola i
    numeri di prima, che sarebbe un difetto peggiore di quello che cura.
    """
    if predefiniti is None:
        # la spunta del consuntivo sta fuori da IMPOSTAZIONI_BP (lì i valori
        # sono numerici e il caricamento li converte in int/float, che per una
        # casella non va bene) ma è un widget come gli altri
        # ⚠️ E così le tendine della griglia di merito: sono widget della
        # scheda fattibilità, quindi soffrono dello stesso difetto descritto
        # qui sopra — quindici caselle compilate a mano che sparivano al
        # primo errore prima di quella scheda.
        predefiniti = dict(
            IMPOSTAZIONI_BP, bp_usa_consuntivo=False, mca_statistica="media",
            **{chiave: ("—" if valore is None else valore)
               for chiave, valore in SOGGETTO_MCA.items()})
    for chiave, valore in predefiniti.items():
        if chiave in stato:
            copia[chiave] = stato[chiave]
        else:
            stato[chiave] = copia.get(chiave, valore)


def progetto_e_vuoto():
    """True se in sessione non c'è ancora nulla da perdere.

    Serve a riaprire l'ultimo lavoro solo su una sessione pulita: farlo
    mentre si lavora sarebbe un invito a sovrascriversi da soli.
    """
    if st.session_state.piante:
        return False

    if st.session_state.get("voci_scelte"):
        return False
    if st.session_state.get("bp_acquisto") or st.session_state.get("bp_vendita"):
        return False
    if len(spese_da_df(st.session_state.df_spese)):
        return False
    if len(materiali_da_df(st.session_state.df_materiali)):
        return False
    return True


def segna_salvato():
    """Registra che il progetto attuale è stato messo al sicuro.

    Gira come callback, cioè PRIMA dello script: le caselle di testo vanno
    convertite qui, o la firma nasce dai valori del giro precedente e l'app
    dichiara «sei in pari» su un file che l'ultima cifra non ce l'ha.
    """
    rileggi_campi_numero_it()
    st.session_state.ultimo_salvataggio = datetime.now()
    st.session_state.firma_salvata = firma_progetto()


def riapri_ultimo_lavoro():
    """Rimette in tavola l'ultimo lavoro. Ritorna cosa ha ripreso, o None.

    All'avvio l'app riapre da sé dov'era rimasta, senza chiedere: è quello
    che fa qualunque programma con cui si lavora tutti i giorni.

    ⚠️ SOLO i salvataggi fatti col tasto Salva. Il file di ripristino
    automatico resta al suo posto e si può riprendere a mano dal pannello
    del progetto, ma non si apre da sé: l'utente ha visto ripristini
    automatici arrivare incompleti — la planimetria che non tornava — e un
    avvio che riapre da solo qualcosa di monco è peggio di un avvio vuoto.
    Un salvataggio manuale invece è un gesto: quel momento lì l'ha scelto
    una persona, e quello che c'era dentro andava bene.

    Un file illeggibile non deve impedire l'avvio: in quel caso si parte da
    un progetto vuoto, come se non ci fosse niente da riprendere.
    """
    nome, quando = archivio_locale.ultimo_progetto()
    if not nome:
        return None
    try:
        dati = archivio_locale.carica_progetto(nome)
    except Exception:  # noqa: BLE001 — file illeggibile: si parte puliti
        return None
    st.session_state.da_caricare = dati
    return {"nome": nome, "quando": quando, "origine": "salvato"}


def nome_archivio_corrente():
    """Il nome con cui salvare al volo. Mai vuoto.

    Senza nome il salvataggio non può fermarsi a chiederlo — il tasto in
    testata serve proprio a non interrompere il lavoro — quindi si usa un
    nome di ripiego che si riconosce a colpo d'occhio in archivio.
    """
    return (st.session_state.prg_nome or "").strip() or "Progetto senza nome"


def salva_al_volo():
    """Salva subito in archivio, sovrascrivendo, senza chiedere niente.

    ⚠️ Sovrascrive di proposito: è il tasto «Salva» di qualunque programma,
    e chiedere conferma a ogni salvataggio del progetto su cui si sta
    lavorando sarebbe una domanda a cui si risponde sempre sì. La conferma
    resta dov'è utile — nell'archivio, quando si salva **con un altro
    nome** sopra un progetto diverso da quello aperto.
    """
    # ⚠️ PRIMA di leggere il progetto, si convertono le caselle di testo.
    # Questa funzione gira come callback del bottone, cioè PRIMA dello
    # script — e la conversione da testo a numero avviene dentro lo script.
    # Senza questa riga si salvava il valore di prima: scrivevi 145.000 nel
    # prezzo d'acquisto, premevi Salva e nel file finiva 0. Le percentuali
    # invece si salvavano, perché sono campi numerici e non passano di qui:
    # è per quello che il difetto sembrava colpire solo certi campi.
    rileggi_campi_numero_it()
    nome = nome_archivio_corrente()
    try:
        archivio_locale.salva_progetto(nome, progetto_json_bytes())
    except OSError as errore:
        st.session_state._esito_salva = ("errore", f"Non sono riuscito a "
                                                   f"salvare: {errore}")
        return
    segna_salvato()
    st.session_state._esito_salva = (
        "ok", f"«{nome}» salvato alle "
              f"{st.session_state.ultimo_salvataggio.strftime('%H:%M')}")


def riprendi_mq_planimetria(valore):
    """Rimette i mq della planimetria dopo che sono stati scritti a mano.

    Da usare come on_click: il campo è già stato disegnato quando il bottone
    viene premuto, e Streamlit vieta di riscriverlo fuori da una callback.
    """
    st.session_state.bp_mq = float(valore)
    st.session_state._mq_automatici = float(valore)


def applica_imprevisti(percentuale):
    """Tara la riserva del business plan sui cantieri già chiusi.

    La riserva sta nel business plan, non nel computo: il computo è il
    documento dei lavori, e quanto tenere da parte è una scelta di chi fa
    l'operazione. Qui arriva il numero che i cantieri chiusi hanno detto.

    Da usare come on_click, mai nel corpo dello script: il campo nasce nel
    sotto-pannello «Studio di fattibilità» e Streamlit vieta di riscriverlo
    dopo che è stato disegnato.
    """
    st.session_state.bp_imprevisti_pct = float(percentuale)
    bp_ricalcola_euro()


def azzera_progetto():
    """Svuota il progetto. Da usare come on_click, mai nel corpo dello script.

    Rimettere a zero la spunta di conferma è legittimo solo dentro una
    callback: fatto dopo che la spunta è stata disegnata, Streamlit solleva
    «cannot be modified after the widget is instantiated» e l'app si pianta.
    """
    st.session_state.da_caricare = {}
    st.session_state.conf_nuovo_progetto = False


def elimina_dallarchivio(deposito, nome):
    """Elimina un progetto archiviato (anche questa è una callback)."""
    try:
        deposito.elimina_progetto(nome)
        st.session_state.conf_del_online = False
        st.session_state._esito_archivio = (
            "ok", f"Progetto «{nome}» eliminato dall'archivio.")
    except Exception as errore:                              # noqa: BLE001
        st.session_state._esito_archivio = (
            "errore", f"Non riesco a eliminarlo: {errore}")


def bottone_salva_json(contenitore, chiave, firma,
                       etichetta="💾 Salva progetto (.json)", primario=False):
    """Salvataggio in file, costruito SOLO quando lo si chiede.

    Il bottone di scaricamento di Streamlit vuole i byte già pronti, e li
    rispedisce al browser a ogni riesecuzione: con sei planimetrie erano quasi
    9 MB per clic — moltiplicati per due, perché un bottone uguale stava anche
    nella scheda planimetria. Da lì l'app che sembrava bloccata dopo un
    salvataggio. Ora il file si costruisce al primo clic e resta pronto finché
    il progetto non cambia; poi il bottone torna a proporre di prepararlo.
    """
    pronto = (st.session_state.get("_json_pronto_firma") == firma
              and st.session_state.get("_json_pronto"))
    tipo = "primary" if primario else "secondary"
    if pronto:
        contenitore.download_button(
            etichetta, data=st.session_state._json_pronto,
            file_name=nome_file("json"), mime="application/json",
            key=f"scarica_{chiave}", type=tipo, width="stretch",
            on_click=segna_salvato)
    elif contenitore.button(
            "📦 Prepara il file (.json)", key=f"prepara_{chiave}", type=tipo,
            width="stretch",
            help="Il file contiene anche le planimetrie e pesa qualche MB: "
                 "si costruisce quando serve, non a ogni clic."):
        st.session_state._json_pronto = progetto_json_bytes()
        st.session_state._json_pronto_firma = firma
        st.rerun()


def stato_salvataggio(firma):
    """Riga di stato: quando si è salvato e se ci sono modifiche successive."""
    ultimo = st.session_state.get("ultimo_salvataggio")
    modificato = firma != st.session_state.get("firma_salvata")
    if ultimo is None:
        # ⚠️ Diceva che il .json era «l'unico salvataggio completo»: non è
        # vero da quando c'è il tasto Salva in testata, che scrive in
        # archivio ed è la fonte da cui riapri_ultimo_lavoro() rimette in
        # tavola il lavoro al prossimo avvio. Dire a qualcuno che il suo
        # lavoro è in pericolo quando non lo è brucia il canale d'allarme
        # per il giorno in cui lo sarà davvero.
        return (":orange[**Mai salvato in questa sessione.**] Il tasto "
                "💾 Salva in cima alla pagina scrive in archivio, ed è da "
                "lì che l'app riapre da sola al prossimo avvio. Il .json è "
                "la copia da portarsi altrove. Finché non fai né l'uno né "
                "l'altro, un aggiornamento della pagina perde tutto.")
    quando = ultimo.strftime("%H:%M")
    if modificato:
        return (f":orange[**Modifiche non salvate.**] Ultimo salvataggio "
                f"alle {quando}.")
    return f":green[**Salvato**] alle {quando}: sei in pari."


# ------------------------------------------------- stato iniziale e caricamento

# le voci inventate per questo cantiere: {codice: {categoria, descrizione,
# um, prezzo}}. Quantità e prezzo vivono nelle stesse chiavi q_/p_ delle
# voci di listino — una riga di computo è una riga di computo.
st.session_state.setdefault("voci_extra", {})
st.session_state.setdefault("prg_nome", "")
st.session_state.setdefault("prg_committente", "")
st.session_state.setdefault("prg_oggetto", "")
# Il luogo della firma: «La Spezia, lì 29/11/2025». Serve all'allegato dei
# materiali, che è un foglio che si sottoscrive in due, e in Italia un
# documento firmato porta sempre luogo e data.
st.session_state.setdefault("prg_luogo", "")
st.session_state.setdefault("prg_data", date.today())
st.session_state.setdefault("iva", 10.0)   # 10%: aliquota tipica in edilizia
# 10%: è la quota prevista dal contratto d'appalto, non una convenzione.
# Lo storico dei cantieri chiusi può poi tararla sul tuo sforamento reale.
# contratto d'appalto: importo, quote dei SAL, extra di fine lavori
st.session_state.setdefault("cant_contratto", 0.0)
st.session_state.setdefault("cant_extra", 0.0)
st.session_state.setdefault("cant_sal", [])
for _voce in listino.VOCI:
    # chiavi «di verità»: sopravvivono anche quando la categoria è chiusa e
    # le sue righe non vengono disegnate (vedi il riallineamento più sotto)
    st.session_state.setdefault(f"q_{_voce['codice']}", 0.0)
    st.session_state.setdefault(f"p_{_voce['codice']}", float(_voce["prezzo"]))
# le voci portate nel computo: il computo è questo elenco, non tutto il
# listino. Nasce vuoto — un cantiere non è l'altro — e si riempie dal pool.
st.session_state.setdefault("voci_scelte", [])
# le categorie del pool aperte: il pool si sfoglia a lungo, e ogni ＋ è una
# riesecuzione — senza memoria si richiuderebbe a ogni voce presa
st.session_state.setdefault("pool_aperte", set())
# le voci tolte dal pool di questo progetto: il listino resta intero, qui si
# tiene solo l'elenco di quelle che su QUESTO cantiere non c'entrano
st.session_state.setdefault("voci_scartate", [])
# le voci la cui quantità è stata scritta a mano: il disegno le lascia stare
st.session_state.setdefault("voci_a_mano", [])
# i materiali a cura del committente: elenco a parte, non voci del computo.
# Il contatore serve a far ripartire il data_editor quando si apre un altro
# progetto — senza, la tabella resterebbe quella di prima.
st.session_state.setdefault("df_materiali", df_materiali_vuoto())
st.session_state.setdefault("versione_mat", 0)
# porte e finestre dei locali rivestiti: interrompono la fascia piastrellata
st.session_state.setdefault("apert_car_n", 0)
st.session_state.setdefault("riv_porte_n", 1)
st.session_state.setdefault("riv_finestre_n", 0)
# categorie del listino aperte in questo momento: solo le loro righe vengono
# disegnate. Con tutte e 58 le voci a video una riesecuzione costava 390 ms su
# 595 totali — due terzi del tempo speso per righe che l'utente non guarda.
st.session_state.setdefault("cat_aperte", set())
# business plan
st.session_state.setdefault("df_spese", df_spese_vuoto())
st.session_state.setdefault("df_spese_prev",
                            df_spese_vuoto(COLONNE_SPESE_PREV))
st.session_state.setdefault("df_mca", df_mca_vuoto())
st.session_state.setdefault("versione_bp", 0)
# la griglia di merito del soggetto e il modo di riassumere i comparabili:
# stringhe e una spunta, quindi fuori da IMPOSTAZIONI_BP come sopra
for _chiave, _valore in SOGGETTO_MCA.items():
    st.session_state.setdefault(_chiave, "—" if _valore is None else _valore)
st.session_state.setdefault("mca_statistica", "media")
# tenuto fuori da IMPOSTAZIONI_BP: lì i valori sono numerici e il
# caricamento li converte in int/float, che per una checkbox non va bene
st.session_state.setdefault("fatt_count", 0)  # svuota l'uploader fatture
# ⚠️⚠️ CHIAVI DI VERITÀ ANCHE QUI, come per quantità e prezzi del computo.
# Molti campi del business plan (le percentuali, le aliquote, la durata)
# sono `st.number_input` cheusano la chiave come valore: quella chiave è
# dello WIDGET, e **Streamlit cancella lo stato dei widget che non
# ridisegna**. Basta che un errore fermi lo script prima della scheda
# fattibilità — o che quella scheda per un giro non venga disegnata — e
# quei valori spariscono; al giro dopo `setdefault` rimette i predefiniti
# e uno si ritrova «Agenzia IN 3,00%» dove aveva scritto 6.000 €, senza
# aver ricaricato niente e senza che nessuno gliel'abbia detto.
#
# Riprodotto: scritto 6,5 in un campo, un errore che ferma lo script, e al
# giro seguente il campo vale di nuovo 3,0. Gli importi scritti con
# `campo_numero_it` non ne soffrivano — lì il valore vero sta in `chiave` e
# il widget è `chiave_txt`, che è appunto la differenza — ed è il motivo per
# cui la ristrutturazione restava al suo posto mentre le agenzie tornavano
# ai predefiniti.
#
# La copia vive in un dizionario normale, che non è di nessun widget e
# quindi non viene mai raccolto: si aggiorna con quello che c'è, e rimette
# quello che manca.
salva_e_ripristina_bp(st.session_state,
                      st.session_state.setdefault("_bp_copia", {}))
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
st.session_state.setdefault("storia_computo", [])   # annulla (quantità, prezzi)
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
# finestre e porte finestra: misure correnti, da cambiare se le proprie
# sono diverse
st.session_state.setdefault("fin_n", 0)
st.session_state.setdefault("fin_larg", 1.20)
st.session_state.setdefault("fin_alt", 1.40)
st.session_state.setdefault("pf_n", 0)
st.session_state.setdefault("pf_larg", 1.20)
st.session_state.setdefault("pf_alt", 2.30)
# vani contenuti nei muri da demolire e da costruire: si dichiara QUANTI
# sono, la misura della porta tipo li converte in m²
st.session_state.setdefault("apert_dem_n", 0)
st.session_state.setdefault("apert_cos_n", 0)
st.session_state.setdefault("apert_larg", 0.80)
st.session_state.setdefault("apert_alt", 2.10)
# il computo segue il disegno da sé (si può sganciare dalla planimetria)
st.session_state.setdefault("auto_computo", True)

# Un caricamento (o azzeramento) va applicato PRIMA di creare i widget.
if "da_caricare" in st.session_state:
    dati = st.session_state.pop("da_caricare")
    progetto = dati.get("progetto", {})
    st.session_state.prg_nome = progetto.get("nome", "")
    st.session_state.prg_committente = progetto.get("committente", "")
    st.session_state.prg_oggetto = progetto.get("oggetto", "")
    st.session_state.prg_luogo = progetto.get("luogo", "")
    st.session_state.iva = float(progetto.get("aliquota_iva", 10.0))
    stato_listino = dati.get("listino_stato") or {}
    testi_salvati = dati.get("testi_voci") or {}
    for _voce in listino.VOCI:
        _cod = _voce["codice"]
        elemento = stato_listino.get(_cod) or {}
        st.session_state[f"q_{_cod}"] = float(elemento.get("q", 0.0))
        st.session_state[f"p_{_cod}"] = float(
            elemento.get("p", _voce["prezzo"]))
        _testi = testi_salvati.get(_cod) or {}
        st.session_state[f"d_{_cod}"] = _testi.get("d") or ""
        st.session_state[f"u_{_cod}"] = _testi.get("u") or ""
        # via i widget della sessione precedente: se restassero, le righe
        # rinascerebbero coi valori del progetto vecchio invece che con questi
        for _w in (f"q_{_cod}_txt", f"p_{_cod}_txt",
                   f"d_{_cod}_w", f"u_{_cod}_w", f"qn_{_cod}_w"):
            st.session_state.pop(_w, None)
    # Le voci inventate del progetto. Ci passano anche i vecchi computi,
    # dove questa tabella era libera: quello che aveva una descrizione
    # diventa una voce come le altre, con il suo codice e la sua categoria.
    st.session_state.voci_extra = {}
    for _riga in dati.get("voci") or []:
        _cod = _riga.get("codice") or codice_nuovo(
            _riga.get("categoria") or calcoli.SENZA_CATEGORIA)
        _descr = (_riga.get("descrizione") or "").strip()
        if not _descr:
            continue
        st.session_state.voci_extra[_cod] = {
            "codice": _cod,
            "categoria": _riga.get("categoria") or calcoli.SENZA_CATEGORIA,
            "descrizione": _descr,
            "um": _riga.get("um") or "",
            "prezzo": float(_riga.get("prezzo") or 0.0),
        }
        st.session_state[f"q_{_cod}"] = float(
            _riga.get("quantita_manuale") or 0.0)
        st.session_state[f"p_{_cod}"] = float(_riga.get("prezzo") or 0.0)
        for _w in (f"q_{_cod}_txt", f"p_{_cod}_txt",
                   f"d_{_cod}_w", f"u_{_cod}_w", f"qn_{_cod}_w"):
            st.session_state.pop(_w, None)
    # Quali voci sono nel computo. I progetti salvati prima non hanno
    # l'elenco: si ricava da quelli che erano gli unici a comparire, cioè
    # le voci con una quantità — così un vecchio computo si riapre uguale.
    scelte_salvate = dati.get("voci_scelte")
    if scelte_salvate is None:
        scelte_salvate = [c for c, e in stato_listino.items()
                          if float((e or {}).get("q") or 0.0) > 0]
        scelte_salvate.sort()
    st.session_state.voci_scelte = [
        c for c in scelte_salvate
        if listino.voce_per_codice(c) or c in st.session_state.voci_extra]
    st.session_state.voci_scartate = [
        c for c in (dati.get("voci_scartate") or [])
        if c not in st.session_state.voci_scelte]
    st.session_state.voci_a_mano = list(dati.get("voci_a_mano") or [])
    if dati.get("voci_scelte") is None:
        # Progetto vecchio: non c'era un elenco, e le voci scritte a mano
        # erano nel computo per definizione. Con l'elenco, invece, comanda
        # lui: una voce tua messa da parte nel pool deve restarci.
        for _cod in st.session_state.voci_extra:
            if _cod not in st.session_state.voci_scelte:
                st.session_state.voci_scelte.append(_cod)
    # I materiali a cura del committente. I progetti salvati prima non ce
    # l'hanno: la tabella nasce vuota, e il computo resta identico a com'era
    # — questo elenco non ha mai fatto parte dei suoi totali.
    _df_mat = df_materiali_da_righe(dati.get("materiali") or [])
    st.session_state.df_materiali = (_df_mat if len(_df_mat)
                                     else df_materiali_vuoto())
    st.session_state.pop("df_materiali_live", None)
    st.session_state.versione_mat = st.session_state.get(
        "versione_mat", 0) + 1
    try:
        st.session_state.prg_data = date.fromisoformat(progetto.get("data", ""))
    except (TypeError, ValueError):
        st.session_state.prg_data = date.today()
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
    st.session_state.riv_porte_n = int(finiture.get("riv_porte_n", 1))
    st.session_state.riv_finestre_n = int(finiture.get("riv_finestre_n", 0))
    st.session_state.fin_n = int(finiture.get("fin_n", 0))
    st.session_state.fin_larg = float(finiture.get("fin_larg", 1.20))
    st.session_state.fin_alt = float(finiture.get("fin_alt", 1.40))
    st.session_state.pf_n = int(finiture.get("pf_n", 0))
    st.session_state.pf_larg = float(finiture.get("pf_larg", 1.20))
    st.session_state.pf_alt = float(finiture.get("pf_alt", 2.30))
    st.session_state.apert_dem_n = int(finiture.get("apert_dem_n", 0))
    st.session_state.apert_cos_n = int(finiture.get("apert_cos_n", 0))
    st.session_state.apert_car_n = int(finiture.get("apert_car_n", 0))
    st.session_state.apert_larg = float(finiture.get("apert_larg", 0.80))
    st.session_state.apert_alt = float(finiture.get("apert_alt", 2.10))
    st.session_state.auto_computo = bool(dati.get("auto_computo", True))
    _cant = dati.get("cantiere") or {}
    st.session_state.cant_contratto = float(_cant.get("contratto", 0.0))
    st.session_state.cant_extra = float(_cant.get("extra", 0.0))
    st.session_state.cant_sal = list(_cant.get("sal") or [])
    # ⚠️ Via TUTTE le caselle della sessione precedente, senza elencarle a
    # mano. Dimenticarne una costava carissimo: il progetto veniva caricato
    # con i suoi valori, ma la casella conservava il testo di prima e la
    # rilettura a inizio pagina — che gira DOPO questo blocco — lo riscriveva
    # sopra. Aprire un progetto salvato con 145.000 € di acquisto dentro una
    # sessione vuota lo riportava a zero, e i numeri sembravano non essersi
    # mai salvati.
    for _k in ("porta_larg_w", "porta_alt_w", "porta_n_w", "porta_n_est_w",
               "riv_alt_w", "riv_porte_n_w", "riv_finestre_n_w",
               "fin_n_w", "fin_larg_w", "fin_alt_w", "pf_n_w",
               "pf_larg_w", "pf_alt_w", "apert_dem_n_w", "apert_cos_n_w",
               "apert_car_n_w", "apert_larg_w", "apert_alt_w",
               "auto_computo_w", "iva_w"):
        st.session_state.pop(_k, None)
    for _chiave in CAMPI_NUMERO_IT:
        st.session_state.pop(f"{_chiave}_txt", None)
    # e i segnalibri dei campi che si compilano da soli: il progetto nuovo
    # ha i suoi mq e la sua base per gli imprevisti
    st.session_state.pop("_mq_automatici", None)
    st.session_state.pop("_base_imprevisti", None)
    # Una per una, non tutte insieme: un'immagine rovinata deve costare
    # quella planimetria, non l'intero elenco. Prima bastava un foglio
    # illeggibile per riaprire il progetto senza più nessun disegno, e
    # senza che l'app lo dicesse.
    piante_lette = []
    piante_scartate = []
    for _p in dati.get("piante") or []:
        try:
            piante_lette.append(pianta_da_json(_p))
        except Exception:  # noqa: BLE001 — foglio rovinato: si tiene il resto
            piante_scartate.append(_p.get("nome") or "planimetria senza nome")
    st.session_state.piante = piante_lette
    st.session_state._piante_scartate = piante_scartate
    st.session_state.pianta_idx = 0
    st.session_state.sel_zona = None
    st.session_state.sel_parete = None
    st.session_state.scala_temp = None
    st.session_state.ultimo_seq = None
    st.session_state.ultimo_rilevamento = None
    # le istantanee dell'annulla riguardano il progetto precedente
    st.session_state.storia = []
    st.session_state.storia_computo = []
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
    # ⚠️ La traduzione dalla griglia di prima va fatta QUI, prima del
    # reindex: le colonne vecchie («condizioni», «degrado», «luminosità»,
    # «esposizione») non sono più in COLONNE_MCA, e il reindex le butta.
    # Dopo non ci sarebbe più niente da tradurre — e le tendine vuote non
    # sono un errore visibile: la stima uscirebbe lo stesso, solo più
    # bassa, senza che nessuno lo dica.
    df_mc = pd.DataFrame(
        [merito.migra_scelte(riga)
         for riga in (dati.get("mca_comparabili") or [])]).reindex(
        columns=COLONNE_MCA)
    for col in ("prezzo", "mq", "coeff"):
        df_mc[col] = pd.to_numeric(df_mc[col], errors="coerce")
    st.session_state.df_mca = df_mc if len(df_mc) else df_mca_vuoto()
    # ⚠️ Chiave ASSENTE e chiave con dentro dei vuoti sono due cose diverse,
    # e confonderle si vede subito. Un progetto salvato prima della griglia
    # non ha «mca_soggetto» per niente: vuol dire «di questo non si sa», e
    # allora valgono i predefiniti, se no chi riapre il lavoro di sempre
    # trova quattordici tendine vuote e i predefiniti non li vede mai.
    # Un progetto salvato DOPO ce l'ha, e allora comanda lui: se una voce
    # è a None è perché è stata messa a «—» apposta, e rimetterci il
    # predefinito sarebbe riempire una casella che l'utente ha svuotato.
    # In tutti e due i casi il coefficiente battuto a mano, se c'è, resta
    # al comando: i numeri dei progetti vecchi non si muovono.
    sog_salvato = dati.get("mca_soggetto")
    if sog_salvato is not None:
        sog_salvato = merito.migra_scelte(sog_salvato)
    for _campo in merito.CAMPI:
        _chiave = f"sog_{_campo}"
        if sog_salvato is None:
            _valore = SOGGETTO_MCA[_chiave]
        else:
            _valore = sog_salvato.get(_campo)
        if _campo == "ascensore":
            st.session_state[_chiave] = bool(_valore)
        else:
            st.session_state[_chiave] = (
                "—" if _valore in (None, "") else str(_valore))
    st.session_state.mca_statistica = (
        dati.get("mca_statistica") or "media")
    st.session_state.versione_bp += 1
    bp_ricalcola_euro()

# Il bottone «usa come prezzo di vendita» (MCA) scrive qui: va applicato
# PRIMA che il widget bp_vendita venga creato.
if "bp_vendita_pending" in st.session_state:
    st.session_state.bp_vendita = st.session_state.pop("bp_vendita_pending")
    st.session_state.pop("bp_vendita_txt", None)    # la casella si rifà
    bp_ricalcola_euro()

# Le quantità che la planimetria porta nel listino passano di qui. Quando si
# preme il bottone, la scheda Computo è già stata disegnata e le caselle…
# esistono: Streamlit vieta di riscriverli a quel punto. Come sopra, si
# applicano al giro successivo, prima che i widget nascano.
if "listino_pending" in st.session_state:
    for _cod, _quantita in st.session_state.pop("listino_pending").items():
        st.session_state[f"q_{_cod}"] = _quantita
        st.session_state.pop(f"q_{_cod}_txt", None)   # rinasce col nuovo

# Una quantità che arriva dal DISEGNO porta anche la voce nel computo: il
# computo mostra solo le voci scelte, e una quantità scritta in una voce che
# nessuno ha scelto sarebbe un numero invisibile. Le stesse quantità
# riscritte dall'annulla non fanno scattare niente — l'elenco delle voci
# l'annulla se lo ripristina da sé, e una voce appena tolta non deve
# rientrare dalla finestra.
for _cod in st.session_state.pop("scelte_pending", []):
    if _cod not in st.session_state.voci_scelte:
        st.session_state.voci_scelte.append(_cod)

# Stessa strada per i PREZZI del listino personale: si applicano prima che i
# caselle dei prezzi nascano, altrimenti Streamlit rifiuta di riscriverle.
if "prezzi_pending" in st.session_state:
    for _cod, _prezzo in st.session_state.pop("prezzi_pending").items():
        st.session_state[f"p_{_cod}"] = _prezzo
        st.session_state.pop(f"p_{_cod}_txt", None)

# Gli importi si scrivono in caselle di testo (le migliaia vogliono il punto,
# e il campo numerico di Streamlit non lo sa fare): qui si rileggono, PRIMA
# di ogni calcolo, così il valore appena scritto vale già in questo giro.
# Il registro degli importi scritti a mano vale un giro solo: si azzera qui
# e lo riempie la rilettura, se in questo giro qualcuno ne ha battuto uno.
st.session_state._importi_scritti_a_mano = set()
rileggi_campi_numero_it()

# E subito dopo si riallinea la colonna dei netti alle percentuali. Prima il
# calcolo partiva SOLO quando qualcosa cambiava: se lo stato arrivava già
# storto — un progetto salvato da una versione difettosa, un giro interrotto
# a metà, una percentuale riscritta uguale a sé stessa (per Streamlit non è
# un cambiamento) — restava storto per sempre. Si vedeva «9,00 %» accanto a
# «0,00 €» senza modo di uscirne, nemmeno riscrivendo il 9.
# Rifarlo a ogni giro costa tre moltiplicazioni e rende il difetto
# impossibile: il netto È la percentuale del suo prezzo, sempre.
bp_ricalcola_euro()

# I comandi delle etichette stanno SOTTO il disegno, ma il disegno legge i
# loro valori PRIMA: senza questo riallineamento userebbe quelli del giro
# precedente (portando il cursore da 10 a 11 le etichette rimpicciolivano,
# perché mostravano ancora il 10 di prima). Qui le chiavi «di verità» si
# aggiornano al valore corrente dei widget, che Streamlit ha già applicato a
# inizio giro; se un widget non esiste — perché lo script era ripartito a
# metà — resta l'ultimo valore buono.
for _et in ("et_font", "et_nome", "et_m2", "et_pct", "et_perim",
            "porta_larg", "porta_alt", "porta_n", "porta_n_est", "riv_alt",
            "riv_porte_n", "riv_finestre_n",
            "fin_n", "fin_larg", "fin_alt", "pf_n", "pf_larg", "pf_alt",
            "apert_dem_n", "apert_cos_n", "apert_car_n",
            "apert_larg", "apert_alt",
            "auto_computo", "iva"):
    if _et + "_w" in st.session_state:
        st.session_state[_et] = st.session_state[_et + "_w"]

# Stesso principio per le voci di listino, ma per un motivo in più: le righe
# delle categorie CHIUSE non vengono disegnate (è ciò che rende l'app veloce),
# e Streamlit cancella lo stato dei widget che non ridisegna. Le quantità e i
# prezzi vivono quindi in chiavi «di verità» (q_/p_), che sopravvivono a
# tutto; le caselle (q_…_txt / p_…_txt) nascono da quelle e ci riversano
# dentro il valore appena l'utente lo cambia.
# ⚠️ Il giro passa da TUTTI i codici del computo, non dalle sole voci di
# listino. Le voci scritte a mano restavano fuori, e siccome è QUI che il
# testo digitato torna a essere un numero, le loro quantità e i loro prezzi
# non si potevano più cambiare: si scriveva nella casella, si premeva
# invio, e al giro dopo ricompariva la cifra di prima. Il valore c'era
# — nella casella — ma non arrivava mai alla chiave di verità.
for _cod in ([v["codice"] for v in listino.VOCI]
             + list(st.session_state.voci_extra)):
    # Quantità e prezzo si scrivono all'italiana in caselle di testo: si
    # rileggono qui, prima che i totali delle categorie vengano calcolati
    # (li disegna il CSS, molto più in alto delle righe). Il testo che non è
    # un numero non si applica e non si cancella.
    for _verita in ("q_" + _cod, "p_" + _cod):
        _testo = st.session_state.get(_verita + "_txt")
        if _testo is None:
            continue
        _valore = numero_da_it(_testo)
        if _valore is None:
            continue
        _nuovo = max(0.0, _valore)
        # ⚠️ Se il numero è DIVERSO da quello con cui la casella è nata, l'ha
        # cambiato una persona: da quel momento quella quantità è sua e il
        # disegno non gliela riscrive più sopra. Prima l'aggancio automatico
        # la rimetteva com'era al giro dopo, e la modifica spariva sotto gli
        # occhi senza che niente lo spiegasse.
        if _verita.startswith("q_"):
            _reso = st.session_state.get("_reso_" + _verita)
            if _reso is not None and abs(_nuovo - float(_reso)) > 0.005:
                segna_a_mano(_cod)
        st.session_state[_verita] = _nuovo
        if _testo != numero_it(st.session_state[_verita], 2):
            st.session_state.pop(_verita + "_txt")   # rinasce formattato

# Le categorie si ricostruiscono a ogni giro dalle zone effettivamente
# disegnate: così i pesi aggiornati valgono subito e una zona marcata con una
# categoria di ieri (es. «Giardino di appartamento») porta con sé la sua
# regola completa — scaglione compreso — invece di finire al 100%.
st.session_state.categorie = categorie_per_progetto(st.session_state.piante)


# ------------------------------------------------------------------ pagina

# Testata: il cartiglio. Il nome del progetto sta accanto al titolo come
# l'etichetta di un campione, non sotto come una didascalia — è l'unica cosa
# che cambia da un progetto all'altro, e va vista subito.
# «Nessun progetto aperto» vale solo a sessione VUOTA: dirlo mentre ci sono
# voci compilate o planimetrie caricate è semplicemente falso — il progetto
# c'è, gli manca il nome.
def versione_codice():
    """Quando è stato scritto il programma che sta girando ADESSO.

    Streamlit rilegge ed esegue questo file a ogni giro, quindi la data qui
    sotto è quella del codice davvero in funzione — non quella del file sul
    disco. Serve a chiudere in un secondo la domanda «sto provando la
    versione nuova o quella di prima?», che da sola è costata più tempo di
    parecchi difetti veri.
    """
    try:
        quando = datetime.fromtimestamp(Path(__file__).stat().st_mtime)
        return quando.strftime("codice del %d/%m alle %H:%M")
    except OSError:
        return ""


_progetto_aperto = (st.session_state.prg_nome or "").strip()
if _progetto_aperto:
    _cartiglio = (f'<span class="cme-etichetta">progetto</span>'
                  f'<span class="progetto">{_progetto_aperto}</span>')
elif not progetto_e_vuoto():
    _cartiglio = ('<span class="cme-etichetta">progetto</span>'
                  '<span class="progetto">senza nome</span>')
else:
    _cartiglio = '<span class="cme-etichetta">nessun progetto aperto</span>'
# Lo stato del salvataggio va detto QUI, non solo in fondo alla scheda
# computo. La firma si ricalcola apposta a inizio pagina: costa millesimi di
# secondo (le immagini non ci entrano) e leggere quella dell'ultimo giro
# direbbe «sei in pari» un istante dopo che hai cambiato qualcosa.
if progetto_e_vuoto():
    _stato = ""
elif st.session_state.get("ultimo_salvataggio") is None:
    # «mai salvato» tutto solo contraddiceva a vista il banner di ripresa
    # che quattro righe più su dice «Ripreso X, salvato il 21/08 alle 15:28»:
    # sono due verità diverse — questa sessione contro l'archivio — e senza
    # dirlo sembravano una bugia.
    _stato = ('<span class="salvataggio sospeso">'
              'mai salvato in questa sessione</span>')
elif firma_progetto() != st.session_state.get("firma_salvata"):
    _stato = ('<span class="salvataggio sospeso">modifiche non salvate</span>')
else:
    _stato = ('<span class="salvataggio pari">salvato alle '
              + st.session_state.ultimo_salvataggio.strftime("%H:%M")
              + '</span>')
# Il tasto «Salva» sta in alto a destra, dove lo si cerca: due colonne, il
# cartiglio a sinistra e il comando a filo con esso.
_t_titolo, _t_salva = st.columns([6, 1], vertical_alignment="center")
with _t_titolo:
    st.markdown(
        '<div class="cme-testata">'
        '<h1><span class="sigla">CME</span> Computo Metrico Estimativo</h1>'
        + _cartiglio
        + f'<span class="versione">{versione_codice()}</span>'
        + _stato + '</div>', unsafe_allow_html=True)
with _t_salva:
    st.button("💾 Salva", type="primary", width="stretch",
              on_click=salva_al_volo, key="salva_testata",
              help=f"Salva subito in archivio come "
                   f"«{nome_archivio_corrente()}», sovrascrivendo la "
                   f"versione precedente. Cartella: "
                   f"{archivio_locale.cartella()}")
_esito = st.session_state.pop("_esito_salva", None)
if _esito:
    (st.error if _esito[0] == "errore" else st.toast)(_esito[1])

# Le planimetrie che non si sono lasciate rileggere: dirlo, e dire anche
# che il resto del progetto è arrivato intero. Un disegno che sparisce in
# silenzio è peggio di un disegno che sparisce.
_scartate = st.session_state.pop("_piante_scartate", None)
if _scartate:
    st.warning(
        f"⚠️ **{len(_scartate)} "
        f"{'planimetria' if len(_scartate) == 1 else 'planimetrie'} "
        "non si sono potute rileggere** dal file del progetto: "
        + ", ".join(f"«{n}»" for n in _scartate)
        + ". Tutto il resto — computo, spese, business plan e le altre "
        "planimetrie — è stato caricato regolarmente. Ricarica il disegno "
        "mancante dalla scheda **Misura da planimetria**.")

tab_computo, tab_plan, tab_bp = st.tabs(
    ["📝 Computo metrico", "📐 Misura da planimetria", "📊 Business plan"])


# ============================================================ SCHEDA COMPUTO

with tab_computo:
    # Offerta di ripristino: solo a sessione pulita e solo finché non si è
    # risposto, così non si trasforma in un banner che chiede sempre la stessa
    # cosa mentre si lavora.
    if (not st.session_state.get("_ripristino_valutato")
            and progetto_e_vuoto()):
        st.session_state._ripristino_valutato = True
        _ripreso = riapri_ultimo_lavoro()
        if _ripreso:
            st.session_state._ripreso = _ripreso
            st.rerun()

    # Si dice sempre COSA è stato riaperto: un'app che si apre già piena
    # senza spiegare da dove viene quella roba è un'app che fa paura.
    _ripreso = st.session_state.pop("_ripreso", None)
    if _ripreso:
        r_testo, r_nuovo = st.columns([4, 1], vertical_alignment="center")
        r_testo.info(f"↩️ Ripreso **{_ripreso['nome']}**, "
                     f"{_ripreso['origine']} il "
                     f"{_ripreso['quando'].strftime('%d/%m')} alle "
                     f"{_ripreso['quando'].strftime('%H:%M')}.")
        # Questo bottone stava accanto al banner di ripresa ed era il PRIMO
        # controllo interattivo della pagina: un click, senza conferma,
        # svuotava computo, planimetrie con la scala calibrata e le zone
        # disegnate a mano, business plan, spese e MCA. L'azione identica
        # dentro il pannello pretende una spunta; qui, dove la mano arriva
        # per sbaglio mentre legge il banner, non pretendeva niente.
        # Ora la conferma c'è, e dice cosa si perde.
        with r_nuovo.popover("Progetto nuovo", width="stretch"):
            st.markdown(
                "Svuota **computo, planimetrie, business plan e spese**.\n\n"
                "Le planimetrie perdono la scala calibrata e le zone "
                "disegnate a mano: l'annulla non le riporta indietro.")
            st.button("🗑️ Sì, svuota tutto", width="stretch",
                      key="nuovo_dopo_ripresa", on_click=azzera_progetto)

    # Dati del progetto e archivio (una volta erano nella barra laterale;
    # tolta per dare tutta la larghezza alla planimetria).
    with st.expander("📋 Dati del progetto · Apri / Nuovo"):
        d1, d2 = st.columns(2)
        d1.text_input("Nome del computo", key="prg_nome",
                      placeholder="Es. Ristrutturazione app.to Via Roma 1")
        d2.text_input("Committente", key="prg_committente")
        # Qui sta l'anagrafica del progetto, e basta: l'aliquota IVA è
        # andata nel riepilogo costi, accanto alle righe che governa.
        # Stava fra il committente e la data come se fosse un dato del
        # committente, e per vederne l'effetto bisognava chiudere il
        # pannello. Gli imprevisti non ci sono più: sono del business plan.
        # Il luogo sta accanto alla data perché con la data fa una cosa
        # sola: la riga «La Spezia, lì 29/11/2025» che precede le firme
        # sull'allegato dei materiali.
        d3, d4, d5 = st.columns([3, 1.2, 1])
        d3.text_input("Oggetto dei lavori", key="prg_oggetto")
        d4.text_input("Luogo", key="prg_luogo", placeholder="Es. La Spezia",
                      help="Compare come «Luogo, lì data» sopra le firme "
                           "dell'allegato materiali.")
        d5.date_input("Data", key="prg_data", format="DD/MM/YYYY")

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

        # ------------------------------------------------------- archivio
        # Due depositi, stessa interfaccia: la cartella sul computer quando
        # l'app gira in locale, Supabase quando c'è la configurazione online
        # (su Streamlit Cloud il disco si azzera a ogni riavvio, quindi lì la
        # cartella non servirebbe a niente). Il titolo dice sempre quale dei
        # due è in uso: sapere dove finiscono i propri progetti non è un
        # dettaglio da nascondere.
        st.divider()
        in_rete = archivio.configurato()
        deposito = archivio if in_rete else archivio_locale
        if in_rete:
            st.markdown("**☁️ Progetti in archivio** :gray[— online]")
        else:
            st.markdown("**💾 Progetti in archivio** :gray[— sul tuo computer]")
            st.caption(f"Cartella: `{archivio_locale.cartella()}`")
        try:
            progetti_arch = deposito.elenco_progetti()
        except Exception as errore:
            progetti_arch = []
            st.error(f"Non riesco a leggere l'archivio: {errore}")

        o_sel, o_apri, o_del = st.columns([3, 1, 1],
                                          vertical_alignment="bottom")
        if progetti_arch:
            scelto = o_sel.selectbox("Apri un progetto archiviato",
                                     progetti_arch, key="prog_online_sel")
            if o_apri.button("📂 Apri", key="apri_online",
                             use_container_width=True):
                try:
                    st.session_state.da_caricare = \
                        deposito.carica_progetto(scelto)
                    st.rerun()
                except Exception as errore:
                    st.error(f"Errore nell'apertura: {errore}")
            conferma_del = o_del.checkbox("elimina", key="conf_del_online",
                                          help="Spunta e premi Elimina per "
                                               "rimuovere definitivamente "
                                               "il progetto selezionato")
            # L'eliminazione vive in una funzione richiamata da on_click, non
            # nel corpo dello script: lì si può rimettere a zero la spunta di
            # conferma, mentre farlo dopo che la spunta è stata disegnata fa
            # sollevare a Streamlit un'eccezione che pianta l'app.
            o_del.button("🗑️", key="del_online", width="stretch",
                         disabled=not conferma_del,
                         on_click=elimina_dallarchivio,
                         args=(deposito, scelto))
            if st.session_state.get("_esito_archivio"):
                tipo, testo = st.session_state.pop("_esito_archivio")
                (st.error if tipo == "errore" else st.success)(testo)
        else:
            o_sel.caption("Nessun progetto ancora archiviato.")

        s_nome, s_btn = st.columns([3, 1], vertical_alignment="bottom")
        # La casella segue il nome del progetto, ma appena ci scrivi sopra
        # comanda quello che hai scritto. ⚠️ Passare `value=` non bastava:
        # a widget già esistente Streamlit lo ignora, e chi rinominava il
        # progetto si ritrovava qui il nome di prima — archiviandolo col
        # nome sbagliato senza accorgersene.
        _nome_progetto = (st.session_state.prg_nome or "").strip()
        if st.session_state.get("_nome_archivio_auto") != _nome_progetto:
            st.session_state._nome_archivio_auto = _nome_progetto
            st.session_state.nome_salva_online = _nome_progetto
        nome_archivio = s_nome.text_input(
            "Nome con cui archiviare",
            key="nome_salva_online",
            placeholder="Es. Ristrutturazione Via Roma 1")
        nome_pulito = (nome_archivio or "").strip()
        # salvare su un nome già in archivio sostituiva la versione
        # precedente senza dire niente: ora lo si conferma
        esiste_gia = nome_pulito in progetti_arch
        if esiste_gia:
            conferma_sovra = st.checkbox(
                f"Sovrascrivi «{nome_pulito}», già presente in archivio",
                key="conf_sovrascrivi_online",
                help="Senza la spunta il salvataggio non parte: la "
                     "versione archiviata resta quella di prima.")
        else:
            conferma_sovra = True
        if s_btn.button("💾 Archivia", key="salva_online",
                        use_container_width=True):
            if not nome_pulito:
                st.warning("Dai un nome al progetto prima di archiviarlo.")
            elif not conferma_sovra:
                st.warning(f"«{nome_pulito}» esiste già in archivio: spunta "
                           "la conferma qui sopra, oppure cambia nome.")
            else:
                try:
                    deposito.salva_progetto(nome_pulito,
                                            progetto_json_bytes())
                    segna_salvato()
                    st.success(f"Progetto «{nome_pulito}» archiviato.")
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
        n_btn.button("🗑️ Svuota tutto", key="nuovo_progetto", width="stretch",
                     disabled=not conferma_nuovo, on_click=azzera_progetto)

        # ------------------------------------------- versioni precedenti
        # In fondo al pannello: è la cosa che si cerca di rado — quando si
        # è sovrascritto il lavoro buono — e non deve stare fra i piedi
        # tutte le altre volte. Non è un salvataggio automatico
        # travestito: ogni versione qui dentro è uno stato che una persona
        # ha deciso di salvare, e che il salvataggio dopo avrebbe
        # cancellato.
        _versioni = archivio_locale.versioni(nome_archivio_corrente())
        if _versioni:
            st.divider()
            # Tutto su una riga per versione, didascalia compresa: prima
            # ogni voce si prendeva tre righe fra testo, bottone e aria in
            # mezzo, per un pannello che si apre già lungo.
            st.markdown(
                f"**🕘 Versioni precedenti** :gray[— le ultime "
                f"{archivio_locale.VERSIONI_TENUTE} contando questa; "
                "riaprirne una **sostituisce** il lavoro in corso]")
            for _n, _v in enumerate(_versioni):
                _quando = archivio_locale.quando_versione(_v)
                _c_txt, _c_btn = st.columns([4, 1],
                                            vertical_alignment="center")
                # coi secondi: due versioni dello stesso minuto sono
                # frequenti (si salva, si cambia una cifra, si risalva) e
                # senza secondi diventano due righe identiche fra cui non
                # si può scegliere
                _c_txt.markdown(
                    f":gray[{_quando.strftime('%d/%m')} alle "
                    f"**{_quando.strftime('%H:%M:%S')}** · "
                    f"{round(_v.stat().st_size / 1024)} KB]")
                if _c_btn.button("↩️ Riapri", key=f"versione_{_n}",
                                 width="stretch"):
                    try:
                        st.session_state.da_caricare = (
                            archivio_locale.carica_versione(_v))
                        st.rerun()
                    except (OSError, json.JSONDecodeError,
                            UnicodeDecodeError):
                        st.error("Questa versione non è leggibile.")

    # ------------------------------------------------------ listino guida
    # -------------------------------------- categorie (sx) e riepilogo (dx)
    st.markdown(css_schede_computo(), unsafe_allow_html=True)
    st.markdown(css_altezze_descrizioni(), unsafe_allow_html=True)
    # 0,7 su 4 non bastava: «Somma parziali» andava a capo e i totali si
    # troncavano in «12.215…», cioè proprio la cifra per cui esiste la
    # colonna. Il computo perde poco, i numeri si leggono per intero.
    col_sx, col_dx = st.columns([2.9, 1.1], gap="medium")

    with col_sx:
        barra_annulla_computo()
        pannello_listino_personale()
        # --------------------------------------------- il computo effettivo
        # Le categorie ci sono sempre — sono l'ossatura del documento — ma
        # dentro c'è solo quello che è stato scelto. Un cantiere non è
        # l'altro: le voci si pescano dal pool qui sotto.
        for indice, cat in enumerate(categorie_del_computo(), start=1):
            colore_md = COLORI_CATEGORIE.get(cat, (OTTONE, "orange"))[1]
            aperta = cat in st.session_state.cat_aperte
            voci_cat = scelte_della_categoria(cat)
            # Un bottone al posto della tendina di Streamlit: la tendina si
            # apre e chiude nel browser SENZA avvisare il server, quindi non
            # potremmo sapere quali voci disegnare. Il bottone invece ce lo
            # dice, ed è ciò che permette di disegnare solo le righe aperte.
            # Niente totale nell'etichetta: lo scrive il CSS (::after), che
            # disegna anche la pastiglia del materiale e l'etichetta campione
            # con codice e numero di voci. L'etichetta del bottone porta solo
            # il nome, tutto dentro un'unica marcatura di colore: due nodi
            # affiancati (la freccia fuori dal colore) sarebbero due elementi
            # distinti e il CSS li impaginerebbe uno sotto l'altro.
            # Il grigio di Streamlit è rgba(250,250,250,.6): accanto a
            # cinque titoli a tinta piena, «Pratiche e oneri» e «Aree
            # esterne» non si leggevano come grigie ma come DISATTIVATE.
            # Senza involucro restano travertino, il colore normale del
            # testo: la tinta della categoria continua a portarla la
            # pastiglia, che è il posto dove il campionario la vuole.
            _eti_cat = f"**{'▾' if aperta else '▸'} {cat}**"
            if colore_md != "gray":
                _eti_cat = f":{colore_md}[{_eti_cat}]"
            with st.container(key=f"card_{indice}"):
                if st.button(_eti_cat,
                             key=f"apri_{indice}", width="stretch"):
                    st.session_state.cat_aperte ^= {cat}   # apre o chiude
                    st.rerun()
                if aperta and voci_cat:
                    (h_cod, h_voce, h_um, h_qta, h_prezzo, h_parz,
                     h_x) = st.columns(
                        [0.5, 3.17, 1.2, 0.85, 0.8, 1.0, 0.45])
                    h_cod.caption("Cod.")
                    h_voce.caption("Voce")
                    h_um.caption("U.M.")
                    h_qta.caption("Quantità")
                    h_prezzo.caption("Prezzo €")
                    # ⚠️ Chiave DIVERSA da quella delle righe: la
                    # correzione di −0,63rem serve al parziale delle voci,
                    # che sta in una colonna collassata; l'intestazione sta
                    # in fila con le altre didascalie, e con quella
                    # correzione addosso finiva dieci pixel più in alto.
                    with h_parz.container(key=f"tparz_{indice}"):
                        st.caption("Parziale")
                    for voce in voci_cat:
                        riga_voce_computo(voce)
                elif aperta:
                    st.caption(":gray[Nessuna voce in questa categoria. "
                               "Prendile dal pool in fondo alla pagina.]")

        # ----------------------------------------- aggiungere una voce tua
        # Non tutto sta in un listino: l'allestimento del cantiere, il
        # noleggio del ponteggio, la lavorazione che quell'impresa chiama a
        # modo suo. Si scrive qui e finisce dritta nella sua categoria del
        # computo — non nel pool, che è il magazzino del listino.
        with st.container(key="card_aggiungi"):
            with st.expander("**➕ Aggiungi una voce tua**"):
                st.caption("Va nella categoria che scegli, insieme alle "
                           "altre. Il codice lo mette l'app, nella serie "
                           "della categoria. Con **a corpo** la quantità "
                           "si propone da sé — **1**, il prezzo è già "
                           "l'importo — e la puoi cambiare.")
                n1, n2 = st.columns([1, 2])
                n1.selectbox("Categoria", listino.CATEGORIE, key="nuova_cat",
                             on_change=azzera_unita_nuova)
                n2.text_input("Descrizione", key="nuova_desc",
                              placeholder="Es. Allestimento del cantiere")
                n3, n4, n5, n6 = st.columns([1, 1, 1, 1.1],
                                            vertical_alignment="bottom")
                n3.selectbox(
                    "U.M.",
                    unita_per_categoria(st.session_state.get("nuova_cat")),
                    key="nuova_um", on_change=proponi_quantita_a_corpo)
                # La casella c'è sempre, «a corpo» compreso: lì dentro ci
                # trovi 1, che è il caso normale, e se le volte sono due lo
                # scrivi. Prima la casella spariva e la quantità la decideva
                # l'app: comodo nove volte su dieci, muto la decima.
                n4.number_input("Quantità", min_value=0.0, step=1.0,
                                format="%.2f", key="nuova_qta")
                n5.number_input("Prezzo €", min_value=0.0, step=10.0,
                                format="%.2f", key="nuova_prezzo")
                n6.button("➕ Al computo", type="primary", width="stretch",
                          key="crea_voce", on_click=crea_voce_a_mano)
                if st.session_state.get("_esito_voce"):
                    tipo, testo = st.session_state.pop("_esito_voce")
                    (st.warning if tipo == "errore" else st.success)(testo)

        # ------------------------------------------------- il pool di voci
        # Il magazzino: tutte le voci del listino che NON sono nel computo.
        # Sta sotto perché è l'attrezzo, non il documento — si apre quando
        # serve pescare, e il resto del tempo non occupa la pagina.
        st.markdown("")
        with st.container(key="card_pool"):
            # ⚠️ Non un «####». Il titolo di Streamlit esce dal contenitore
            # che lo ospita — 53 px di riquadro dentro 37 di guscio, anche
            # senza una riga di CSS nostra — e in una scheda stretta ci
            # finisce sotto la casella della ricerca, tagliato a metà.
            # Un paragrafo normale, vestito da titolo dal CSS, sta al posto
            # suo: le dimensioni le decide chi legge, non l'anchor link.
            st.markdown("🧰 **Pool voci** · scegli cosa portare nel computo")
            # La ricerca è una casella sola e senza etichetta: si vede che è
            # una ricerca dalla lente e dal testo dentro. Cerca su tutte le
            # categorie insieme, anche quelle chiuse — è l'unico modo di
            # trovare una voce quando non ci si ricorda dove sta di casa.
            termine = st.text_input(
                "Cerca una voce", key="cerca_voce",
                placeholder="🔎  Cerca fra le voci — codice, descrizione, "
                            "unità",
                label_visibility="collapsed").strip()
            aggiunte = 0
            for indice, cat in enumerate(categorie_del_computo(), start=1):
                # Le voci del listino di questa categoria, più quelle che ci
                # hai scritto tu e che al momento non sono nel computo: una
                # volta inventata, una voce resta a disposizione: si toglie
                # dal foglio e si ripesca, esattamente come le altre.
                candidate = list(listino.voci_della_categoria(cat)) + [
                    v for v in st.session_state.voci_extra.values()
                    if v["categoria"] == cat]
                disponibili = [v for v in candidate
                               if not e_scelta(v["codice"])
                               and not e_scartata(v["codice"])
                               and voce_trovata(v, termine)]
                if not disponibili:
                    continue
                aggiunte += len(disponibili)
                colore_md = COLORI_CATEGORIE.get(cat, (OTTONE, "orange"))[1]
                # Stesso bottone delle categorie del computo, e per lo stesso
                # motivo: la tendina di Streamlit si richiude a ogni giro, e
                # QUI ogni ＋ è un giro. Si prendeva una voce e la tendina si
                # chiudeva in faccia, da riaprire per prendere la successiva.
                # Con il bottone l'apertura la ricorda il server.
                # Cercando si aprono da sole: se hai scritto «gres» vuoi
                # vedere le voci, non le categorie che le contengono.
                aperta_pool = bool(termine) or cat in st.session_state.pool_aperte
                # Stesso motivo della scheda computo: il grigio di Streamlit
                # legge «disattivato», non «grigio».
                _eti_pool = f"{'▾' if aperta_pool else '▸'} **{cat}**"
                if colore_md != "gray":
                    _eti_pool = f":{colore_md}[{_eti_pool}]"
                if st.button(f"{_eti_pool} :gray[· {len(disponibili)}]",
                             key=f"pool_{indice}", width="stretch"):
                    st.session_state.pool_aperte ^= {cat}
                    st.rerun()
                if aperta_pool:
                    for voce in disponibili:
                        codice_voce = voce["codice"]
                        tua = listino.voce_per_codice(codice_voce) is None
                        descrizione, um = testi_voce(voce)
                        # il cestino c'è solo sulle voci tue: quelle del
                        # listino non si cancellano, sono il catalogo
                        c_btn, c_txt, c_prezzo, c_del = st.columns(
                            [0.4, 3.9, 1.1, 0.3],
                            vertical_alignment="center")
                        c_btn.button(
                            "＋", key=f"prendi_{codice_voce}",
                            on_click=porta_nel_computo, args=(codice_voce,),
                            help="Porta la voce nel computo")
                        c_txt.markdown(
                            f":gray[**{codice_voce}**] {descrizione} "
                            f":gray[· {um}]"
                            + (" :orange[· tua]" if tua else ""),
                            help=voce.get("nota"))
                        c_prezzo.markdown(
                            f":gray[{euro(voce['prezzo'])}]")
                        c_del.button(
                            "🗑", key=f"cestina_{codice_voce}",
                            on_click=scarta_voce, args=(codice_voce,),
                            help="Togli la voce dal pool di questo "
                                 "progetto (si rimette dal fondo)")

            # Gli scarti: quanti sono e come si rimettono. In fondo e in
            # grigio, perché è l'uscita di sicurezza di un clic sbagliato,
            # non un comando di tutti i giorni.
            if st.session_state.voci_scartate:
                s_txt, s_btn = st.columns([4, 1],
                                          vertical_alignment="center")
                quante = len(st.session_state.voci_scartate)
                s_txt.caption(
                    f":gray[🗑 {quante} "
                    f"{'voce scartata' if quante == 1 else 'voci scartate'} "
                    "da questo progetto — il listino non è stato toccato]")
                s_btn.button("↩️ Rimetti tutte", key="ripristina_scarti",
                             width="stretch", on_click=ripristina_scarti)

            if not aggiunte:
                st.caption(
                    ":gray[Nessuna voce da aggiungere: sono già tutte nel "
                    "computo.]" if not termine else
                    f":gray[Nessuna voce trovata per «{termine}». Le voci "
                    "che hai già preso non compaiono qui: cercale nel "
                    "computo qui sopra.]")

    # --------------------------------------------------- riepilogo costi
    with col_dx:
        st.markdown("#### 💰 Riepilogo costi")
        voci_calcolate = calcoli.calcola_computo(voci_dal_listino())
        totale = calcoli.totale_generale(voci_calcolate)

        if totale == 0:
            st.caption("Inserisci le quantità nelle categorie per vedere "
                       "la distribuzione dei costi.")
        righe_dot = [(f"{i}. {cat}",
                      COLORI_CATEGORIE.get(cat, (OTTONE, "orange"))[0],
                      totale_categoria_listino(cat))
                     for i, cat in enumerate(categorie_del_computo(),
                                             start=1)]
        # pastiglie quadrate, non pallini: sono campioni di materiale, e
        # richiamano la tinta piena in testa a ogni categoria
        html_dot = "".join(
            f'<div style="display:flex;justify-content:space-between;'
            f'align-items:center;margin:4px 0;font-size:0.9rem;">'
            f'<span><span style="display:inline-block;width:12px;'
            f'height:12px;background:{colore};'
            f'margin-right:9px;vertical-align:-1px;"></span>{nome}</span>'
            f'<b>{euro(importo)}</b></div>'
            for nome, colore, importo in righe_dot)
        st.markdown(html_dot, unsafe_allow_html=True)
        st.divider()

        # ⚠️ L'IVA si comanda DA QUI, non più dal pannello «Dati del
        # progetto». Là stava fra il nome del committente e la data, come se
        # fosse anagrafica; è invece il parametro che decide la coda del
        # computo, e sta accanto alle righe che governa.
        # ⚠️⚠️ Gli IMPREVISTI non sono più qui. Il computo è il documento
        # dei lavori: quello che si consegna all'impresa sono le lavorazioni
        # computate, non i lavori più una riserva che riguarda chi paga.
        # La riserva è una scelta dell'operazione e vive nel business plan,
        # riga «Imprevisti e condominio», dove sta accanto alle altre spese
        # e si vede quanto pesa. Tenerla in due posti voleva dire, prima o
        # poi, contarla due volte.
        iva_importo, totale_ivato = calcoli.totale_con_iva(
            totale, st.session_state.iva)
        totale_lavori = totale

        st.metric("Totale lavori (IVA esclusa)", euro(totale))
        # ⚠️ Il valore buono vive in `iva`, il widget in `iva_w`. Con la sola
        # chiave del widget l'aliquota tornava al 10% da sola: Streamlit
        # tiene lo stato dei widget legato a com'è fatta la pagina, e ogni
        # volta che il sorgente cambia — cioè a ogni aggiornamento dell'app —
        # quel legame si spezza e il campo rinasce col valore predefinito.
        # Chi aveva messo il 22% se lo ritrovava al 10% senza toccare niente,
        # e il totale finale con lui.
        st.number_input(
            "Aliquota IVA (%)", min_value=0.0, max_value=100.0, step=1.0,
            value=float(st.session_state.iva), key="iva_w",
            help="10% ristrutturazioni (predefinita), 22% ordinaria, "
                 "4% prima casa")
        st.metric(f"IVA {numero_it(st.session_state.iva, 0)}%",
                  euro(iva_importo))
        # La card d'oro incoronava il totale PRIMA dell'IVA, mentre l'export
        # Excel chiama «Totale finale (IVA inclusa)» quello DOPO: lo stesso
        # nome su due cifre diverse, sullo strumento in cui il numero giusto
        # è tutto. Il finale è uno solo, ed è quello che si paga.
        # Il campione più pieno della pagina: qui la tinta non contorna, è
        # tutta la superficie. È il numero che si paga, e nella colonna deve
        # vincere su ogni altra cifra. Niente sfumatura, niente angoli
        # arrotondati: la materia è piatta e squadrata come un campione vero.
        st.markdown(
            f'<div style="background:{OTTONE};padding:13px 15px;'
            'margin:6px 0 10px;">'
            f'<div style="font-size:.7rem;color:{ARDESIA};font-weight:700;'
            'text-transform:uppercase;letter-spacing:.12em;opacity:.85;">'
            'Totale finale · IVA inclusa</div>'
            f'<div style="font-size:1.8rem;font-weight:700;color:{ARDESIA};'
            'line-height:1.2;">'
            f'{euro(totale_ivato)}</div></div>',
            unsafe_allow_html=True)

        totali = calcoli.totali_per_categoria(voci_calcolate)
        if len(totali) >= 2:
            st.plotly_chart(grafico_totali(totali),
                            config={"displayModeBar": False})

    # ----------------------------- materiali a cura del committente
    # Sta QUI, sotto il computo e a tutta larghezza, per due ragioni. La
    # prima è che nove colonne dentro una colonna da tre quarti di pagina
    # si leggono di sbieco. La seconda è che questo è un ALLEGATO, e un
    # allegato viene dopo il documento a cui è allegato — come sul foglio
    # vero, dove sta dietro al computo e si firma insieme a lui.
    st.markdown("")
    with st.container(key="card_materiali"):
        st.markdown("🛒 Materiali · a cura del Committente")
        st.caption(
            "Quello che compri **tu**, e che l'impresa non fornisce: è "
            "l'**Allegato 1** del computo, il foglio che si firma in due "
            "per segnare il confine dell'appalto. Questi importi **non "
            "entrano nel totale dei lavori** — sono soldi tuoi, non della "
            "fattura dell'impresa — ma entrano nel costo dell'operazione, "
            "e li ritrovi nel business plan. Il **prezzo puoi lasciarlo "
            "vuoto**: la voce resta nell'elenco e il totale dichiara che "
            "è parziale.")
        df_mat_ed = st.data_editor(
            materiali_con_importo(
                st.session_state.df_materiali,
                st.session_state.get("df_materiali_live")),
            num_rows="dynamic", hide_index=True, width="stretch",
            key=f"editor_materiali_{st.session_state.versione_mat}",
            column_config=config_colonne_materiali())
        # come per le spese: l'input del data_editor resta il DataFrame
        # stabile, il ritorno vive a parte per calcoli e salvataggio
        st.session_state.df_materiali_live = df_mat_ed
        righe_materiali = materiali.calcola_elenco(materiali_da_df(df_mat_ed))
        totale_materiali = materiali.totale(righe_materiali)
        mancano_prezzi = materiali.da_quotare(righe_materiali)
        per_stato = materiali.totali_per_stato(righe_materiali)

        if righe_materiali:
            m1, m2, m3, m4 = st.columns(4)
            m1.metric("Totale materiali (IVA esclusa)",
                      euro(totale_materiali))
            for colonna, stato in zip((m2, m3, m4), materiali.STATI):
                quota = per_stato.get(stato) or {"importo": 0.0, "voci": 0}
                colonna.metric(
                    stato, euro(quota["importo"]),
                    delta=(f"{quota['voci']} "
                           + ("voce" if quota["voci"] == 1 else "voci")),
                    delta_color="off")
            if mancano_prezzi:
                st.caption(
                    f":orange[⚠️ {mancano_prezzi} "
                    + ("voce senza prezzo" if mancano_prezzi == 1
                       else "voci senza prezzo")
                    + ": il totale qui sopra è **parziale**.]")
            # Il conto della serva, in una riga: quanto costa il cantiere
            # per intero. Sta qui e non nel riepilogo costi perché è qui
            # che i due numeri esistono tutt'e due nello stesso istante —
            # e un totale che si aggiorna un giro dopo è un totale stantio.
            st.markdown(
                f"Lavori **{euro(totale)}** + materiali "
                f"**{euro(totale_materiali)}** → **intervento completo "
                f"{euro(round(totale + totale_materiali, 2))}**, IVA "
                "esclusa.")

            # I due PDF stanno QUI e non fra gli export in fondo: sono i
            # documenti di questo elenco, e chi ha appena finito di
            # scriverlo è già dove serve premerli.
            # ⚠️ La data all'italiana, non l'ISO: questo foglio si firma, e
            # su un documento da firmare «2025-11-29» non ci va.
            _prg_allegato = {
                "nome": st.session_state.prg_nome,
                "committente": st.session_state.prg_committente,
                "oggetto": st.session_state.prg_oggetto,
                "luogo": st.session_state.prg_luogo,
                "data": st.session_state.prg_data.strftime("%d/%m/%Y"),
            }
            a1, a2, _ = st.columns([1.3, 1.3, 2])
            a1.download_button(
                "🖨️ Allegato 1 (da firmare)",
                data=stampa.pdf_materiali(_prg_allegato, righe_materiali),
                help="L'elenco per capitoli, senza prezzi, con la clausola e "
                     "le due firme: è il foglio che si allega al computo e "
                     "si sottoscrive con l'impresa.",
                file_name=nome_file("pdf").replace(
                    ".pdf", "_allegato_materiali.pdf"),
                mime="application/pdf", width="stretch")
            a2.download_button(
                "💶 Allegato con i prezzi",
                data=stampa.pdf_materiali(_prg_allegato, righe_materiali,
                                          con_prezzi=True),
                help="La tua copia: stesso elenco con prezzi, importi, "
                     "totali per capitolo e il conto delle voci ancora da "
                     "quotare. Non si consegna all'impresa.",
                file_name=nome_file("pdf").replace(
                    ".pdf", "_allegato_materiali_prezzi.pdf"),
                mime="application/pdf", width="stretch")
        else:
            st.markdown(
                campione_vuoto(
                    "Nessun materiale in elenco",
                    "Scrivi nella riga vuota qui sopra che cosa compri tu — "
                    "il gres, i sanitari, le porte. Basta la descrizione: "
                    "il prezzo lo aggiungi quando lo sai. Da qui esce "
                    "l'Allegato 1 da firmare con l'impresa."),
                unsafe_allow_html=True)

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
                # due decimali come nelle righe qui sopra e nel PDF:
                # la stessa quantità non deve avere due forme nella stessa
                # pagina (94,710 sotto e 94,71 sopra)
                "Quantità": df_calcolato["quantita"].map(
                    lambda q: numero_it(q, 2)),
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
               "pagina. Il **PDF** è il computo completo, con i totali e le "
               "firme; il **PDF senza prezzi** è lo stesso elenco di "
               "lavorazioni e quantità da mandare alle imprese perché ci "
               "facciano il preventivo. Excel e CSV servono a rielaborare "
               "i numeri. L'**Allegato 1 dei materiali** si scarica dalla "
               "sua sezione qui sopra: è un documento suo, e si firma a "
               "parte.")

    progetto = {
        "nome": st.session_state.prg_nome,
        "committente": st.session_state.prg_committente,
        "oggetto": st.session_state.prg_oggetto,
        "luogo": st.session_state.prg_luogo,
        "data": st.session_state.prg_data.isoformat(),
        "aliquota_iva": st.session_state.iva,
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
                "Totale lavori (IVA esclusa)",
                f"IVA {numero_it(st.session_state.iva, 0)}%",
                "Totale finale (IVA inclusa)"],
            "Importo": [totale_lavori, iva_importo, totale_ivato],
            "Incidenza %": [100.0, None, None],
        }),
    ], ignore_index=True)
    df_progetto_excel = pd.DataFrame({
        "Campo": ["Nome", "Committente", "Oggetto", "Luogo", "Data",
                  "Aliquota IVA %"],
        "Valore": [progetto["nome"], progetto["committente"],
                   progetto["oggetto"], progetto["luogo"], progetto["data"],
                   progetto["aliquota_iva"]],
    })

    # I materiali per Excel: il foglio dell'allegato, con l'importo già
    # fatto. Le voci senza prezzo restano vuote — non zero — così una somma
    # fatta nel foglio non le conta come regalate.
    df_materiali_excel = None
    if righe_materiali:
        df_materiali_excel = pd.DataFrame([{
            "Capitolo": r.get("capitolo") or "",
            "Descrizione": r.get("descrizione") or "",
            "U.M.": r.get("um") or "",
            "Quantità": r.get("quantita"),
            "Prezzo unit.": r.get("prezzo"),
            "Importo": r.get("importo"),
            "Fornitore": r.get("fornitore") or "",
            "Stato": r.get("stato") or "",
            "Note": r.get("note") or "",
        } for r in righe_materiali])
        df_materiali_excel = pd.concat([
            df_materiali_excel,
            pd.DataFrame([{
                "Capitolo": "TOTALE MATERIALI",
                "Descrizione": (f"{mancano_prezzi} voci senza prezzo"
                                if mancano_prezzi else ""),
                "Importo": totale_materiali}]),
        ], ignore_index=True)

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

    # La firma costa millesimi di secondo; il file intero costa secondi e
    # attraversa il collegamento col browser. Qui gira solo la firma, che
    # serve a dire se ci sono modifiche non salvate.
    st.session_state._firma_progetto = firma_progetto()
    # Tre bottoni grigi identici non dicevano che solo il primo mette al
    # sicuro il lavoro: quello resta in evidenza, con accanto il suo stato.
    st.markdown(stato_salvataggio(st.session_state._firma_progetto))
    (col_json, col_pdf, col_pdf_muto, col_xlsx,
     col_csv) = st.columns(5)
    bottone_salva_json(col_json, "computo", st.session_state._firma_progetto,
                       primario=True)
    _totali_pdf = {"somma": totale, "totale_lavori": totale_lavori,
                   "iva_pct": st.session_state.iva, "iva": iva_importo,
                   "totale": totale_ivato}
    _tinte_pdf = {cat: COLORI_CATEGORIE[cat][0] for cat in COLORI_CATEGORIE}
    col_pdf.download_button(
        "🖨️ Stampa PDF",
        data=stampa.pdf_computo(progetto, voci_calcolate, _totali_pdf,
                                tinte=_tinte_pdf),
        help="Il computo come documento da consegnare: le voci per "
             "categoria, i totali e le firme.",
        file_name=nome_file("pdf"),
        mime="application/pdf",
    )
    # Lo stesso computo senza una cifra: è quello che si manda alle imprese
    # perché ci scrivano la LORO offerta. Un prezzo già stampato sopra non
    # è una richiesta di preventivo, è una proposta — e quello che torna
    # indietro non è più un confronto.
    col_pdf_muto.download_button(
        "📄 PDF senza prezzi",
        data=stampa.pdf_computo(progetto, voci_calcolate, _totali_pdf,
                                tinte=_tinte_pdf, con_prezzi=False),
        help="Da mandare alle imprese per il preventivo: lavorazioni e "
             "quantità, senza prezzi né importi.",
        file_name=nome_file("pdf").replace(".pdf", "_senza_prezzi.pdf"),
        mime="application/pdf",
    )
    col_xlsx.download_button(
        "📊 Esporta Excel (.xlsx)",
        data=excel_bytes(df_calcolato, df_riepilogo_excel,
                         df_progetto_excel, df_superfici_excel,
                         df_materiali_excel),
        help="Fogli: Computo, Riepilogo, Materiali, Superfici e Dati "
             "progetto.",
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
    # il segnaposto dei totali sotto la tela: esiste solo se una tela c'è
    riepilogo_vicino = None

    if not piante:
        st.markdown(campione_vuoto(
            "Il banco è sgombro",
            "Porta qui la planimetria — una foto, una scansione o il PDF del "
            "progetto — e da lì si misurano le superfici, si contano i muri e "
            "le quantità passano nel computo. Un PDF di più pagine diventa "
            "una planimetria per foglio: piano terra, piano primo, e così via."),
            unsafe_allow_html=True)
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
                help="Da demolire = rosso · Da costruire = giallo · "
                     "In cartongesso = verde")
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
                    st.toast(f"Annullato: {fatto['descrizione']} ↩️")
                    # Il messaggio deve sopravvivere al rerun che segue,
                    # altrimenti sparisce prima di essere letto.
                    st.session_state._scala_persa = fatto["scala_persa"]
                st.rerun()
            if st.session_state.pop("_scala_persa", False):
                st.warning(
                    "↩️ Tornando indietro è stata annullata anche **la "
                    "scala**: questa planimetria non è più calibrata, quindi "
                    "le misure non sono in metri finché non la reimposti con "
                    "lo strumento ↔️. Le aree disegnate restano dove sono.")
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

            # La tela sul piano da lavoro: è il pezzo vero, e nella scheda
            # deve avere il contrasto più alto: tutto il resto le sta attorno.
            with st.container(key="tela"):
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
            # Il posto dove finiranno i totali, subito sotto la tela. I numeri
            # si calcolano molto più giù, dopo le spunte dei locali: senza
            # questo segnaposto bisognava scorrere fino in fondo e tornare su
            # per vedere che cosa aveva cambiato una spunta. Si riempie nello
            # STESSO giro, quindi non è mai in ritardo di un'interazione.
            # la chiave sta sul contenitore ESTERNO, non dentro il segnaposto:
            # così la classe che il CSS aggancia c'è di sicuro
            with st.container(key="totali_tela"):
                riepilogo_vicino = st.empty()

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
            f'background:{col_map.get(c["nome"], "#9E9E9E")};'
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

            # ⚠️ L'IMPRONTA fa da chiave, e comprende TUTTO quello che la
            # tabella mostra senza che lo si possa scrivere qui dentro: quali
            # locali ci sono, come si chiamano, quanto misurano. Prima era il
            # solo elenco degli id, e allora ogni modifica che non fosse
            # aggiungere o togliere una zona lasciava la tabella indietro:
            # rinominare un locale non ne cambiava il nome in elenco, e —
            # molto peggio — ALLARGARE una stanza sul disegno non ne cambiava
            # i metri quadri. Quei metri sono quelli che finiscono nel
            # computo: la stanza cresceva e il computo restava fermo alla
            # misura di prima, fino a quando non si chiudeva l'app.
            # Le colonne che si spuntano QUI (pavimento, battiscopa,
            # tinteggiatura, rivestito) restano fuori dall'impronta di
            # proposito: se ci fossero, ogni clic rifarebbe la tabella e il
            # primo clic andrebbe perso — bisognava cliccare due volte.
            # Rifarla non perde le spunte: rinascono da zona[...], dove le
            # riversiamo a ogni giro poche righe più sotto.
            impronta = tuple(
                (rif, riga["Locale"], riga["Superficie (m²)"],
                 riga["Perimetro (m)"])
                for rif, riga in zip(riferimenti, righe_tab))
            chiave_tab = "edloc_" + str(abs(hash(impronta)) % 10 ** 8)
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
                    "esterno": (zona.get("categoria") or "")
                    in CATEGORIE_ESTERNE,
                })

            # ---- vani porta e rivestimenti: quello che va detratto ----
            with st.container(key="pan_porte"):
                st.markdown("**🚪 Porte e rivestimenti (detrazioni)**")
                st.caption("Il vano di una porta non ha battiscopa e non si "
                           "tinteggia; nei locali rivestiti la fascia "
                           "piastrellata non si rasa né si tinteggia. Una "
                           "porta **interna** affaccia su due locali, quindi "
                           "vale **due lati**; il portoncino d'ingresso uno "
                           "solo. Le quantità qui sotto sono già al netto.")
                d1, d2, d3, d4, d5 = st.columns(5)
                larg_porta = d1.number_input(
                    "Larghezza porte (m)", min_value=0.0, max_value=3.0,
                    step=0.05, format="%.2f",
                    value=float(st.session_state.porta_larg),
                    key="porta_larg_w")
                st.session_state.porta_larg = larg_porta
                alt_porta = d2.number_input(
                    "Altezza porte (m)", min_value=0.0, max_value=4.0,
                    step=0.05, format="%.2f",
                    value=float(st.session_state.porta_alt),
                    key="porta_alt_w")
                st.session_state.porta_alt = alt_porta
                n_porte = d3.number_input(
                    "Porte interne", min_value=0, max_value=200, step=1,
                    value=int(st.session_state.porta_n), key="porta_n_w",
                    help="Porte fra due locali: il vano vale due lati, "
                         "perché interrompe il battiscopa (e toglie parete "
                         "da tinteggiare) di qua e di là.")
                st.session_state.porta_n = n_porte
                n_porte_est = d4.number_input(
                    "Porte esterne", min_value=0, max_value=50, step=1,
                    value=int(st.session_state.porta_n_est),
                    key="porta_n_est_w",
                    help="Portoncino d'ingresso e porte verso l'esterno o "
                         "verso locali non computati: vale un lato solo.")
                st.session_state.porta_n_est = n_porte_est
                h_riv = d5.number_input(
                    "Altezza rivestimenti (m)", min_value=0.0, max_value=4.0,
                    step=0.05, format="%.2f",
                    value=float(st.session_state.riv_alt), key="riv_alt_w",
                    help="Fascia piastrellata nei locali spuntati «Rivestito» "
                         "(di norma 1,20 m; zona doccia anche 2,40).")
                st.session_state.riv_alt = h_riv
                # Quanti vani interrompono la fascia. Sono un dato a parte
                # dalle porte di tutta la casa: qui contano solo quelle dei
                # locali rivestiti, e di ciascuna vale UN lato — quello
                # dentro il bagno, che è l'unico piastrellato.
                r1, r2 = st.columns(2)
                n_riv_porte = r1.number_input(
                    "Porte nei locali rivestiti", min_value=0, max_value=50,
                    step=1, value=int(st.session_state.riv_porte_n),
                    key="riv_porte_n_w",
                    help="Di norma una per bagno. Vale un lato solo: "
                         "l'altra faccia del vano è fuori dal rivestimento.")
                st.session_state.riv_porte_n = n_riv_porte
                n_riv_finestre = r2.number_input(
                    "Finestre nei locali rivestiti", min_value=0,
                    max_value=50, step=1,
                    value=int(st.session_state.riv_finestre_n),
                    key="riv_finestre_n_w",
                    help="Zero nei bagni ciechi. Si toglie solo la parte "
                         "che cade dentro la fascia.")
                st.session_state.riv_finestre_n = n_riv_finestre

            # ---- finestre e porte finestra ----
            with st.container(key="pan_finestre"):
                st.markdown("**🪟 Finestre e porte finestra (detrazioni)**")
                st.caption("Stanno su un muro perimetrale, quindi affacciano "
                           "su **un solo locale**: valgono un lato. La "
                           "finestra ha il davanzale in alto e il battiscopa "
                           "ci passa sotto, quindi toglie superficie **solo** "
                           "a rasatura e tinteggiatura; la **porta finestra** "
                           "arriva a terra e interrompe anche il battiscopa. "
                           "Le misure predefinite sono quelle correnti: "
                           "cambiale se le tue sono diverse.")
                f1, f2, f3, f4, f5, f6 = st.columns(6)
                n_fin = f1.number_input(
                    "Finestre", min_value=0, max_value=200, step=1,
                    value=int(st.session_state.fin_n), key="fin_n_w",
                    help="Quante finestre nei locali spuntati "
                         "«Tinteggiatura».")
                st.session_state.fin_n = n_fin
                larg_fin = f2.number_input(
                    "Larghezza finestra (m)", min_value=0.0, max_value=6.0,
                    step=0.05, format="%.2f",
                    value=float(st.session_state.fin_larg), key="fin_larg_w")
                st.session_state.fin_larg = larg_fin
                alt_fin = f3.number_input(
                    "Altezza finestra (m)", min_value=0.0, max_value=4.0,
                    step=0.05, format="%.2f",
                    value=float(st.session_state.fin_alt), key="fin_alt_w")
                st.session_state.fin_alt = alt_fin
                n_pf = f4.number_input(
                    "Porte finestra", min_value=0, max_value=200, step=1,
                    value=int(st.session_state.pf_n), key="pf_n_w",
                    help="Vanno a terra: tolgono anche battiscopa.")
                st.session_state.pf_n = n_pf
                larg_pf = f5.number_input(
                    "Larghezza p. finestra (m)", min_value=0.0, max_value=6.0,
                    step=0.05, format="%.2f",
                    value=float(st.session_state.pf_larg), key="pf_larg_w")
                st.session_state.pf_larg = larg_pf
                alt_pf = f6.number_input(
                    "Altezza p. finestra (m)", min_value=0.0, max_value=4.0,
                    step=0.05, format="%.2f",
                    value=float(st.session_state.pf_alt), key="pf_alt_w")
                st.session_state.pf_alt = alt_pf

            aperture = [
                {"n": n_fin, "larghezza": larg_fin, "altezza": alt_fin,
                 "battiscopa": False},
                {"n": n_pf, "larghezza": larg_pf, "altezza": alt_pf,
                 "battiscopa": True},
            ]

            q = planimetria.quantita_finiture(
                locali_calcolo, altezza, larghezza_porta=larg_porta,
                altezza_porta=alt_porta, n_porte=n_porte,
                altezza_rivestimento=h_riv, n_porte_esterne=n_porte_est,
                aperture=aperture, n_porte_rivestiti=n_riv_porte,
                n_finestre_rivestiti=n_riv_finestre,
                larghezza_finestra=larg_fin, altezza_finestra=alt_fin)
            pav_m2 = q["pavimento"]
            pav_est_m2 = q["pavimento_esterno"]
            riv_m2 = q["rivestimenti"]
            batt_m = q["battiscopa"]
            pareti_m2 = q["pareti"]
            soffitti_m2 = q["soffitti"]

            detr_ml = q["detr_porte_ml"] + q["detr_aperture_ml"]
            detr_m2 = (q["detr_porte_m2"] + q["detr_aperture_m2"]
                       + q["detr_rivestimenti"])
            t1, t2, t3, t4 = st.columns(4)
            t1.metric("Pavimento (interni)", f"{numero_it(pav_m2, 2)} m²")
            t2.metric("Battiscopa", f"{numero_it(batt_m, 2)} m",
                      delta=(f"−{numero_it(detr_ml, 2)} m vani"
                             if detr_ml else None),
                      delta_color="off")
            t3.metric(f"Pareti (h {numero_it(altezza, 2)} m)",
                      f"{numero_it(pareti_m2, 2)} m²",
                      delta=(f"−{numero_it(detr_m2, 2)} m² "
                             "vani e rivestimenti" if detr_m2 else None),
                      delta_color="off")
            t4.metric("Soffitti", f"{numero_it(soffitti_m2, 2)} m²")
            # I due che non stavano in nessuna voce: i metri dei balconi,
            # che finivano sommati a quelli delle stanze, e la fascia
            # rivestita, che si scontava dalla tinteggiatura senza mai
            # diventare una quantità da pagare a nessuno.
            t5, t6 = st.columns(2)
            t5.metric("Pavimento esterno (balconi, terrazzi)",
                      f"{numero_it(pav_est_m2, 2)} m²")
            t6.metric(f"Rivestimenti (fascia h {numero_it(h_riv, 2)} m)",
                      f"{numero_it(riv_m2, 2)} m²",
                      # niente detrazione da mostrare se non c'è fascia:
                      # «0,00 m² −0,96 di vani» non vuol dire niente
                      delta=(f"−{numero_it(q['detr_riv_porte'] + q['detr_riv_finestre'], 2)} m² vani"
                             if q["rivestimenti_lordi"]
                             and (q["detr_riv_porte"] or q["detr_riv_finestre"])
                             else None),
                      delta_color="off")
            if q["rivestimenti_lordi"]:
                st.caption(
                    f":gray[Fascia lorda {numero_it(q['rivestimenti_lordi'], 2)} m² "
                    f"(perimetro dei locali rivestiti × {numero_it(h_riv, 2)} m) − "
                    f"{numero_it(q['detr_riv_porte'], 2)} m² di vani porta − "
                    f"{numero_it(q['detr_riv_finestre'], 2)} m² di finestre. "
                    "Dei vani si toglie solo la parte che cade dentro la "
                    "fascia: una porta alta 2,10 su una fascia da 1,20 vale "
                    "0,80 × 1,20.]")
            elif any(l.get("rivestito") for l in locali_calcolo) is False:
                st.caption(
                    ":gray[Nessun locale spuntato **Rivestito**: la voce dei "
                    "rivestimenti resta a zero. La spunta è nella tabella "
                    "dei locali qui sopra — di norma i bagni e la fascia "
                    "della cucina.]")
            if detr_ml or detr_m2:
                st.caption(
                    f":gray[Battiscopa lordo {numero_it(q['battiscopa_lordo'], 2)} m "
                    f"(i locali rivestiti sono già esclusi) − "
                    f"{numero_it(q['detr_porte_ml'], 2)} m di vani porta "
                    f"({q['lati_porta']} lati) − "
                    f"{numero_it(q['detr_aperture_ml'], 2)} m di porte "
                    f"finestra. "
                    f"Pareti lorde {numero_it(q['pareti_lorde'], 2)} m² − "
                    f"{numero_it(q['detr_rivestimenti'], 2)} m² di fasce "
                    f"rivestite − {numero_it(q['detr_porte_m2'], 2)} m² di "
                    f"vani porta − {numero_it(q['detr_aperture_m2'], 2)} m² "
                    f"di finestre e porte finestra.]")

            grandezze.update({
                "pavimento": pav_m2,
                "pavimento_esterno": pav_est_m2,
                "rivestimenti": riv_m2,
                "battiscopa": batt_m,
                "tinteggiatura": pareti_m2 + soffitti_m2,
            })

        # ------------------------------- dai muri tracciati alle demolizioni
        st.subheader("🧱 Dai muri al computo "
                     "(demolire / costruire / cartongesso)")
        riep_muri, senza_scala_muri = planimetria.riepilogo_pareti(
            piante, altezza)
        if senza_scala_muri:
            st.warning("Muri esclusi perché la planimetria è **senza "
                       "scala**: " + ", ".join(senza_scala_muri))
        if not riep_muri:
            st.info("Traccia i muri con lo strumento **PARETE** sul disegno "
                    "(scegli sopra se sono da demolire, da costruire o in "
                    "cartongesso): qui trovi metri lineari e superfici "
                    "pronti per il computo.")
        else:
            vuoto = {"n": 0, "ml": 0.0, "m2": 0.0}
            dem = riep_muri.get("demolire", vuoto)
            cos = riep_muri.get("costruire", vuoto)
            car = riep_muri.get("cartongesso", vuoto)
            esi = riep_muri.get("esistente", vuoto)
            st.caption(f"Superficie = lunghezza × altezza "
                       f"(**{numero_it(altezza, 2)} m**), al netto delle "
                       "aperture dichiarate qui sotto: dove c'è un vano non "
                       "c'è muratura da buttare giù né da tirare su.")
            with st.container(key="pan_aperture"):
                a1, a2, a5, a3, a4 = st.columns(5)
                n_apert_dem = a1.number_input(
                    "Aperture nei muri da demolire", min_value=0,
                    max_value=200, step=1,
                    value=int(st.session_state.apert_dem_n),
                    key="apert_dem_n_w",
                    help="Quanti vani (porte, passaggi, finestre) ci sono nei "
                         "muri rossi. I m² li fa l'app, con le misure qui "
                         "accanto.")
                st.session_state.apert_dem_n = n_apert_dem
                n_apert_cos = a2.number_input(
                    "Aperture nei muri da costruire", min_value=0,
                    max_value=200, step=1,
                    value=int(st.session_state.apert_cos_n),
                    key="apert_cos_n_w",
                    help="Vani previsti nei muri gialli: quella superficie "
                         "non va murata.")
                st.session_state.apert_cos_n = n_apert_cos
                n_apert_car = a5.number_input(
                    "Aperture nei muri in cartongesso", min_value=0,
                    max_value=200, step=1,
                    value=int(st.session_state.apert_car_n),
                    key="apert_car_n_w",
                    help="Vani previsti nei muri verdi: quella superficie "
                         "non va lastrata.")
                st.session_state.apert_car_n = n_apert_car
                larg_apert = a3.number_input(
                    "Larghezza apertura (m)", min_value=0.0, max_value=6.0,
                    step=0.05, format="%.2f",
                    value=float(st.session_state.apert_larg),
                    key="apert_larg_w",
                    help="Misura della porta tipo: 0,80 × 2,10 nelle case. "
                         "Cambiala se i tuoi vani sono diversi.")
                st.session_state.apert_larg = larg_apert
                alt_apert = a4.number_input(
                    "Altezza apertura (m)", min_value=0.0, max_value=4.0,
                    step=0.05, format="%.2f",
                    value=float(st.session_state.apert_alt),
                    key="apert_alt_w")
                st.session_state.apert_alt = alt_apert

            apert_dem = planimetria.superficie_aperture(
                n_apert_dem, larg_apert, alt_apert)
            apert_cos = planimetria.superficie_aperture(
                n_apert_cos, larg_apert, alt_apert)
            apert_car = planimetria.superficie_aperture(
                n_apert_car, larg_apert, alt_apert)
            if apert_dem or apert_cos or apert_car:
                st.caption(
                    f":gray[Un vano da {numero_it(larg_apert, 2)} × "
                    f"{numero_it(alt_apert, 2)} m vale "
                    f"**{numero_it(larg_apert * alt_apert, 2)} m²**: "
                    f"{n_apert_dem} da demolire = "
                    f"{numero_it(apert_dem, 2)} m², {n_apert_cos} da "
                    f"costruire = {numero_it(apert_cos, 2)} m², "
                    f"{n_apert_car} in cartongesso = "
                    f"{numero_it(apert_car, 2)} m².]")

            dem_netto = planimetria.muri_al_netto(dem["m2"], apert_dem)
            cos_netto = planimetria.muri_al_netto(cos["m2"], apert_cos)
            car_netto = planimetria.muri_al_netto(car["m2"], apert_car)
            w1, w2, w3, w4 = st.columns(4)
            w1.metric(f"🔴 Da demolire ({dem['n']})",
                      f"{numero_it(dem['ml'], 2)} m")
            w2.metric("→ superficie", f"{numero_it(dem_netto, 2)} m²",
                      delta=(f"−{numero_it(apert_dem, 2)} m² aperture"
                             if apert_dem else None), delta_color="off")
            w3.metric(f"🟡 Da costruire ({cos['n']})",
                      f"{numero_it(cos['ml'], 2)} m")
            w4.metric("→ superficie", f"{numero_it(cos_netto, 2)} m²",
                      delta=(f"−{numero_it(apert_cos, 2)} m² aperture"
                             if apert_cos else None), delta_color="off")
            w5, w6 = st.columns(2)
            w5.metric(f"🟢 In cartongesso ({car['n']})",
                      f"{numero_it(car['ml'], 2)} m")
            w6.metric("→ superficie", f"{numero_it(car_netto, 2)} m²",
                      delta=(f"−{numero_it(apert_car, 2)} m² aperture"
                             if apert_car else None), delta_color="off")
            if apert_dem or apert_cos or apert_car:
                st.caption(f":gray[Muri lordi: "
                           f"{numero_it(dem['m2'], 2)} m² da demolire, "
                           f"{numero_it(cos['m2'], 2)} m² da costruire e "
                           f"{numero_it(car['m2'], 2)} m² in cartongesso.]")
            if esi["n"]:
                st.caption(f":gray[Esclusi {esi['n']} muri «esistenti» "
                           f"({numero_it(esi['ml'], 2)} m): non sono "
                           "lavorazioni.]")
            grandezze["muri_demolire"] = dem_netto
            grandezze["muri_costruire"] = cos_netto
            grandezze["muri_cartongesso"] = car_netto

        # ------------------------- i totali tornano su, accanto al disegno
        # Adesso i numeri ci sono: si scrivono nel segnaposto lasciato sotto
        # la tela. Chi disegna vede subito l'effetto del proprio gesto senza
        # scorrere due schermate e tornare indietro.
        _vicino = [
            ("Superficie commerciale", tot_comm, "m²"),
            ("Pavimento", grandezze.get("pavimento"), "m²"),
            ("Battiscopa", grandezze.get("battiscopa"), "m"),
            ("Tinteggiatura", grandezze.get("tinteggiatura"), "m²"),
            ("Muri da demolire", grandezze.get("muri_demolire"), "m²"),
            ("Muri da costruire", grandezze.get("muri_costruire"), "m²"),
        ]
        _vicino = [(nome, valore, um) for nome, valore, um in _vicino
                   if valore]
        if _vicino and riepilogo_vicino is not None:
            with riepilogo_vicino.container():
                for colonna, (nome, valore, um) in zip(
                        st.columns(len(_vicino)), _vicino):
                    colonna.metric(nome, f"{numero_it(valore, 2)} {um}")

        # ---------------- dalle misure della planimetria alle voci del listino
        if any(v > 0 for v in grandezze.values()):
            st.markdown("**➕ Porta queste quantità nel computo**")
            auto = st.toggle(
                "🔗 Tieni il computo agganciato al disegno",
                value=bool(st.session_state.auto_computo),
                key="auto_computo_w",
                help="Acceso: sposti un muro o cambi una spunta e la quantità "
                     "nel computo si aggiorna da sé. Spento: la porti tu, con "
                     "il bottone.")
            st.session_state.auto_computo = auto
            st.caption(
                "Le quantità vengono **scritte** nelle voci del listino, non "
                "sommate: si può rifare il rilevamento e cambiare le spunte "
                "senza contare niente due volte. I prezzi restano quelli del "
                "listino, modificabili come sempre. Le voci non spuntate qui "
                "sotto non vengono mai toccate, e una misura che scende a "
                "zero (nessun muro tracciato) **non cancella** un numero "
                "battuto a mano.")
            selezionate = []
            for codice, grandezza, acceso in VOCI_DA_SUPERFICI:
                voce = listino.voce_per_codice(codice)
                quantita = round(grandezze.get(grandezza, 0.0), 2)
                if voce is None or quantita <= 0:
                    continue
                attuale = float(st.session_state.get(f"q_{codice}") or 0.0)
                etichetta = (f"**{codice}** · {voce['descrizione']} → "
                             f"**{numero_it(quantita, 2)} {voce['um']}**")
                if attuale and abs(attuale - quantita) > 0.005:
                    etichetta += (f" :orange[(sostituisce "
                                  f"{numero_it(attuale, 2)})]")
                if st.checkbox(etichetta, value=acceso,
                               key=f"supvoce_{codice}"):
                    selezionate.append((codice, grandezza))
            if not selezionate:
                st.caption(":gray[Nessuna voce selezionata.]")

            # Le voci scritte a mano restano fuori: chi ha battuto quel
            # numero ha deciso lui, e riscriverglielo sopra al giro dopo è
            # il modo più sicuro di far perdere fiducia a uno strumento.
            a_mano_qui = [c for c, _ in selezionate
                          if c in st.session_state.voci_a_mano]
            proposte = planimetria.voci_da_riscrivere(
                selezionate, grandezze,
                {c: st.session_state.get(f"q_{c}") for c, _ in selezionate},
                escluse=a_mano_qui)
            if a_mano_qui:
                m_txt, m_btn = st.columns([4, 1],
                                          vertical_alignment="center")
                m_txt.caption(
                    ":orange[✎ Scritte a mano, quindi non aggiornate dal "
                    "disegno: " + ", ".join(sorted(a_mano_qui)) + ".]")
                m_btn.button("↺ Riaggancia", key="riaggancia_tutte",
                             width="stretch",
                             on_click=riaggancia_al_disegno,
                             help="Ridà al disegno il comando su queste "
                                  "voci: le quantità tornano quelle "
                                  "misurate.")

            if auto:
                if proposte:
                    # Le quantità si applicano a inizio del giro successivo:
                    # qui la scheda Computo è già disegnata e Streamlit vieta
                    # di riscrivere i widget dopo che sono nati.
                    st.session_state.listino_pending = dict(proposte)
                    st.session_state.scelte_pending = list(proposte)
                    st.rerun()
                st.caption(
                    f":green[✔ Computo allineato al disegno — "
                    f"{len(selezionate)} "
                    f"{'voce' if len(selezionate) == 1 else 'voci'} "
                    f"che si aggiornano da sé.]")
            elif st.button("➕ Scrivi le quantità nel listino", type="primary",
                           disabled=not proposte):
                # registrata solo qui: col computo agganciato le quantità
                # cambiano a ogni gesto sul disegno, e la storia si
                # riempirebbe di passi tutti uguali
                registra_storia_computo("quantità portate dalla planimetria")
                st.session_state.listino_pending = dict(proposte)
                st.session_state.scelte_pending = list(proposte)
                st.toast(f"{len(proposte)} voci aggiornate nel computo ✔")
                st.rerun()

        st.divider()
        bottone_salva_json(
            st, "planimetria",
            st.session_state.get("_firma_progetto") or firma_progetto(),
            etichetta="💾 Salva progetto (.json) — computo e planimetrie")


# ======================================================= SCHEDA BUSINESS PLAN

with tab_bp:
    sotto_fatt, sotto_spese, sotto_cant, sotto_mca = st.tabs(
        ["🏦 Studio di fattibilità", "🧾 Spese a consuntivo",
         "🏗️ Cantiere — contratto e SAL", "🏷️ MCA — prezzo di vendita"])

    # valori automatici condivisi: superficie commerciale dalla planimetria
    # e costo di ristrutturazione dal computo
    _, _, mq_da_planimetria, _ = planimetria.riepilogo_superfici(
        st.session_state.piante, mappa_percentuali(),
        escludi=CATEGORIE_SOLO_COMPUTO)
    # I mq su cui si divide il costo dei LAVORI sono un'altra cosa: le stanze
    # vere, non la commerciale (che comprende balconi e vano scale, superfici
    # che si vendono ma non si ristrutturano).
    mq_calpestabili, _senza_scala_calp = planimetria.superficie_calpestabile(
        st.session_state.piante, mappa_percentuali(),
        escludi=CATEGORIE_INVOLUCRO)
    voci_bp = voci_dal_listino()
    totale_computo_bp = calcoli.totale_generale(
        calcoli.calcola_computo(voci_bp))
    # I lavori NUDI: il computo non porta più nessuna riserva: la riserva
    # è UNA sola, la riga «Imprevisti e condominio» qui sotto, dove si vede
    # quanto pesa ed è modificabile. Tenerla anche nel computo voleva dire,
    # prima o poi, contarla due volte.
    #
    # I materiali a cura del committente si sommano QUI, e solo qui. Nel
    # computo non entrano — quel documento è dell'impresa, e questi soldi
    # dalla sua fattura non passano — ma l'operazione li paga lo stesso, ed
    # è l'operazione che questa scheda misura.
    # ⚠️ Senza di loro il confronto col cantiere era ASIMMETRICO: il
    # consuntivo conta le spese MATERIALE (stanno in CATEGORIE_CANTIERE), il
    # preventivo non aveva nessun capitolo materiali da mettergli davanti.
    # Ogni operazione in cui le finiture le compri tu risultava sforata del
    # loro intero importo — uno sforamento che non c'era mai stato.
    materiali_bp = materiali.totale(materiali_correnti())
    ristr_da_computo = round(totale_computo_bp + materiali_bp, 2)


    # ------------------------------------------------- spese a consuntivo
    with sotto_spese:
        st.caption("Il registro delle spese reali dell'operazione, come il "
                   "tuo foglio «Spese». A sinistra le spese già "
                   "**sostenute** (le fatture); **accanto**, senza scendere "
                   "in fondo alla pagina, il **riepilogo per categoria**, "
                   "le spese ancora **da sostenere** e la torta. La quota "
                   "**cantiere** (lavori, materiale, architetto) può "
                   "sostituire la ristrutturazione stimata nello studio di "
                   "fattibilità.")

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
                    # ⚠️ Il numero non è più una prova di riuscita: da quando
                    # vale «//» quando non si legge, è sempre pieno. Vale
                    # solo se è un numero VERO — altrimenti questo controllo
                    # accetterebbe qualunque cosa l'estrazione restituisca.
                    numero_letto = (dati or {}).get("nr_fattura")
                    if dati and (dati.get("importo") is not None
                                 or (numero_letto
                                     and numero_letto
                                     != fattura.NUMERO_MANCANTE)):
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
                    df_ant = spese_con_iva(
                        df_spese_da_righe(righe_estratte, COLONNE_SPESE))
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
                        # la colonna dell'IVA calcolata non e' un dato: si
                        # toglie prima di rimettere tutto insieme, o
                        # rientrerebbe nel progetto salvato
                        st.session_state.df_spese = senza_iva_derivata(
                            pd.concat([corrente, df_ant_ed],
                                      ignore_index=True))
                        st.session_state.pop("df_spese_live", None)
                        st.session_state.fatt_count += 1
                        st.session_state.versione_bp += 1
                        st.rerun()

        # Il registro a SINISTRA e tutto il resto ACCANTO, non sotto: con
        # trenta fatture in tabella, il riepilogo e la torta finivano sotto
        # centinaia di pixel di righe, e per guardare un totale mentre si
        # registra una spesa bisognava perdere di vista la spesa. Quel che
        # non entra nello schermo si raggiunge scorrendo la fascia in
        # orizzontale — è un banco da lavoro largo, non una pagina stretta.
        st.markdown(f"""
<style>
.st-key-spese_banco {{ overflow-x: auto; padding-top: 16px;
                       padding-bottom: 6px; }}
.st-key-spese_banco > div > [data-testid="stHorizontalBlock"]
                                                    {{ min-width: 1900px; }}
.st-key-spese_banco [data-testid="stHorizontalBlock"]
 [data-testid="stHorizontalBlock"] {{ min-width: 0; }}
</style>
""", unsafe_allow_html=True)

        with st.container(key="spese_banco"):
            col_registro, col_lato = st.columns([2.2, 1.1], gap="medium")

            with col_registro:
                st.markdown("##### 🧾 Spese sostenute")
                df_spese_ed = st.data_editor(
                    spese_con_iva(st.session_state.df_spese,
                                  st.session_state.get("df_spese_live")),
                    num_rows="dynamic", hide_index=True, width="stretch",
                    key=f"editor_spese_{st.session_state.versione_bp}",
                    column_config=config_colonne_spese())
                # il ritorno NON viene rimesso in df_spese: ripassare al
                # data_editor un DataFrame che cambia a ogni run gli faceva
                # "perdere" la prima selezione di categoria (da rifare due
                # volte). df_spese resta l'input stabile; il ritorno vive a
                # parte per calcoli e salvataggio.
                st.session_state.df_spese_live = df_spese_ed
                righe_spese = spese_da_df(df_spese_ed)
                tot_sostenute = fattibilita.totale_spese(righe_spese)
                st.metric("Totale spese sostenute", euro(tot_sostenute))

            riepilogo = fattibilita.riepilogo_per_categoria(righe_spese)
            iva_totale = round(sum(v["iva"] for v in riepilogo.values()), 2)

            with col_lato:
                # Il riepilogo e la torta girano sulle SOLE sostenute, la card
                # più sotto somma anche le da sostenere: due basi diverse
                # nella stessa colonna, e nessuna delle due lo diceva.
                st.markdown("##### 📊 Riepilogo — solo le sostenute")
                if riepilogo:
                    st.markdown(
                        tabella_riepilogo_spese_html(
                            riepilogo, tot_sostenute, iva_totale),
                        unsafe_allow_html=True)
                else:
                    st.caption("Nessuna spesa sostenuta ancora.")

            with col_lato:
                st.markdown("##### 🔮 Spese da sostenere")
                df_prev_ed = st.data_editor(
                    st.session_state.df_spese_prev,
                    num_rows="dynamic", hide_index=True, width="stretch",
                    key=f"editor_spese_prev_{st.session_state.versione_bp}",
                    column_config={
                        "oggetto": st.column_config.TextColumn(
                            "Oggetto", width=190),
                        # Anche qui il lordo: le due tabelle si sommano nella
                        # stessa card e nella stessa quota cantiere, e una
                        # colonna chiamata solo «€» non diceva quale dei due.
                        "importo": st.column_config.NumberColumn(
                            "Importo previsto", width=125, format="euro",
                            help="IVA compresa, come le spese sostenute: i "
                                 "due registri si sommano."),
                        "aliquota_iva": st.column_config.NumberColumn(
                            "IVA %", width=70, min_value=0.0, max_value=22.0,
                            step=1.0),
                        "categoria": st.column_config.SelectboxColumn(
                            "Categoria", width=150,
                            options=CATEGORIE_SPESE_EMOJI),
                        "note": st.column_config.TextColumn("Note", width=110),
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
                # ⚠️ E non si chiama più «Costi totali dell'operazione»:
                # ACQUISTO e AGENZIA qui dentro, di là, sono già contati nel
                # prezzo d'acquisto e nei suoi oneri (l'«entry»). Erano due
                # totali che si sovrapponevano senza mai incontrarsi, e
                # quello col nome più grosso non era il costo dell'operazione
                # ma il totale di questo registro.
                quota_cantiere = round(sum(
                    r["importo"] for r in righe_spese + righe_prev
                    if r["categoria"] in fattibilita.CATEGORIE_CANTIERE), 2)
                # Il numero che comanda la scheda, come il totale finale del
                # computo: ottone su tutta la superficie, non una scheda con
                # la sfumatura. Le righe di dettaglio stanno in ardesia
                # sull'ottone, che le tiene leggibili senza farle gridare.
                st.markdown(
                    f'<div style="background:{OTTONE};padding:13px 15px;'
                    'margin:6px 0 10px;">'
                    f'<div style="font-size:.7rem;color:{ARDESIA};'
                    'font-weight:700;text-transform:uppercase;'
                    'letter-spacing:.12em;opacity:.85;">'
                    'Totale del registro spese</div>'
                    f'<div style="font-size:1.8rem;font-weight:700;'
                    f'color:{ARDESIA};line-height:1.2;">'
                    f'{euro(costi_totali)}</div>'
                    f'<div style="font-size:0.74rem;color:{ARDESIA};'
                    'opacity:.8;">'
                    f'sostenute {euro(tot_sostenute)} + da sostenere '
                    f'{euro(tot_prev)}</div>'
                    f'<div style="font-size:0.74rem;color:{ARDESIA};'
                    'margin-top:6px;padding-top:6px;'
                    f'border-top:1px solid {ARDESIA}40;">di cui cantiere '
                    f'<b>{euro(quota_cantiere)}</b>'
                    ' — riportabile nello studio di fattibilità</div></div>',
                    unsafe_allow_html=True)
                st.caption(
                    ":gray[Non è il costo dell'operazione: **ACQUISTO** e "
                    "**AGENZIA** qui dentro, nello studio di fattibilità, "
                    "sono già contati nel prezzo d'acquisto e nei suoi "
                    "oneri. Di qua passa solo la quota **cantiere**.]")

            with col_lato:
                st.markdown("##### 🥧 Sostenute per categoria")
                if riepilogo:
                    st.plotly_chart(grafico_torta_spese(riepilogo),
                                    config={"displayModeBar": False})
                else:
                    st.caption("La torta comparirà con le prime spese.")

        # confronto col preventivo del computo (su sostenute + da sostenere)
        # ⚠️ Solo le righe di CANTIERE aprono il confronto. Bastava una
        # spesa qualsiasi — un acconto, la provvigione dell'agenzia — e il
        # blocco compariva con «Scostamento −100,0 %» in rosso: il computo
        # intero dato per non speso, su una scheda dove non si era ancora
        # aperto il cantiere. È lo stesso difetto del «ROE −100 %» prima di
        # digitare qualcosa, e va evitato allo stesso modo: finché non c'è
        # una spesa di cantiere non c'è niente da confrontare.
        righe_cantiere = [r for r in righe_spese + righe_prev
                          if r["categoria"] in fattibilita.CATEGORIE_CANTIERE]
        # Costo cantiere a consuntivo, sulle categorie che il computo
        # preventiva. Vive qui perché è qui che le tabelle delle spese
        # restituiscono i valori aggiornati; lo studio di fattibilità lo
        # riusa ed è scritto DOPO nel codice apposta, così legge i numeri di
        # questo giro e non quelli del precedente.
        # ⚠️ Le due metà si tengono separate. «Consuntivo» ha una definizione
        # sola in questo mestiere — soldi usciti — e qui dentro ci finivano
        # anche le spese DA SOSTENERE, che sono previsioni. Il totale che
        # serve allo studio di fattibilità le comprende entrambe (è il costo
        # atteso del cantiere), ma la scheda deve dire quale pezzo è già
        # fattura e quale è ancora una stima.
        def _quota_cantiere(righe):
            return round(sum(r["importo"] for r in righe
                             if r["categoria"]
                             in fattibilita.CATEGORIE_CANTIERE), 2)

        cantiere_sostenuto = _quota_cantiere(righe_spese)
        cantiere_previsto = _quota_cantiere(righe_prev)
        cantiere_consuntivo = round(cantiere_sostenuto + cantiere_previsto, 2)
        if righe_cantiere:
            st.divider()
            st.subheader("⚖️ Il computo alla prova del cantiere")
            scostamento = round(cantiere_consuntivo - ristr_da_computo, 2)
            # La percentuale è il numero che conta davvero: è la stessa
            # grandezza con cui lo storico tara la riserva del business plan.
            # Prima il valore grande e il delta erano la stessa cifra in €,
            # scritta due volte, e la percentuale non c'era.
            scost_pct = (round(scostamento / ristr_da_computo * 100, 2)
                         if ristr_da_computo else None)
            c1, c2, c3, c4 = st.columns(4)
            c1.metric("Preventivo (computo + materiali)",
                      euro(ristr_da_computo),
                      delta=(f"di cui {euro(materiali_bp)} materiali"
                             if materiali_bp else None), delta_color="off")
            c2.metric("Speso davvero (fatture)", euro(cantiere_sostenuto))
            c3.metric("Ancora da sostenere (stime)", euro(cantiere_previsto))
            c4.metric("Scostamento sul preventivo",
                      (numero_it(scost_pct, 1) + " %"
                       if scost_pct is not None else "—"),
                      delta=euro(scostamento), delta_color="inverse")
            st.caption(
                ":gray[Lavori, materiale e architetto da una parte; dall'altra "
                "il computo **più l'allegato dei materiali**, così le due "
                "metà parlano delle stesse cose. Il confronto usa "
                "**entrambe** le colonne — speso più da sostenere — perché è "
                "il costo atteso del cantiere; finché la seconda non è "
                "vuota, lo scostamento è in parte una previsione.]")

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
.st-key-bp_scroll [data-testid="stHorizontalBlock"] { min-width: 1560px; }
.st-key-bp_scroll [data-testid="stHorizontalBlock"]
 [data-testid="stHorizontalBlock"] { min-width: 0; }
/* Su schermo stretto la scheda SCORRE, non si impila: c'era una regola che
   sotto i 1400 px mandava le tre colonne una sotto l'altra, ed era il
   contrario di quello che serve — un foglio di conti si legge affiancato,
   come nell'Excel da cui viene, e comprimerlo tronca i numeri. */
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
    background: #C9A96A;
    color: #1A2744;
    font-size: 0.72rem;
    font-weight: 700;
}
</style>
""", unsafe_allow_html=True)

        # I mq si COMPILANO da sé con quello che dice la planimetria, e
        # restano modificabili. Prima il campo restava a zero con la
        # promessa «0 = dalla planimetria»: il valore veniva usato davvero,
        # ma a vederlo sembrava che l'app non l'avesse preso.
        # Il segnalibro dice qual è l'ultimo valore scritto in automatico: se
        # il campo non combacia più, l'ha cambiato l'utente e non si tocca.
        if (mq_da_planimetria
                and st.session_state.bp_mq == st.session_state.get(
                    "_mq_automatici", 0.0)):
            st.session_state.bp_mq = mq_da_planimetria
            st.session_state._mq_automatici = mq_da_planimetria
        mq_a_mano = bool(st.session_state.bp_mq
                         and st.session_state.bp_mq
                         != st.session_state.get("_mq_automatici"))
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
            "mq_calpestabile": mq_calpestabili,
            "durata_mesi": st.session_state.bp_durata,
        }
        # Gli imprevisti dell'operazione sono una percentuale dell'IMPORTO DEI
        # LAVORI: qui la scheda deposita la base, perché le callback del
        # sincronismo %↔€ (che girano a inizio pagina) non sanno da sole
        # quale ristrutturazione si sta considerando. Quando la base cambia
        # l'importo si rifà subito, e la casella rinasce col valore nuovo.
        # Col consuntivo la base è ZERO: quei numeri sono soldi già usciti,
        # una riserva sopra a una spesa reale non ha senso. La riga resta
        # scrivibile a mano, per il condominio.
        base_imprevisti = 0.0 if usa_consuntivo else ristr_eff
        if st.session_state.get("_base_imprevisti") != base_imprevisti:
            st.session_state._base_imprevisti = base_imprevisti
            bp_ricalcola_euro()

        # L'IVA di ogni voce, sommata PRIMA dei totali: le righe più sotto
        # la ridisegnano soltanto. Il conto sta qui perché «TOTALE SPESE»
        # deve comprenderla — è tutta la ragione per cui la si traccia.
        _iva_voci = [
            fattibilita.iva_su(st.session_state.get(campo, 0.0),
                               st.session_state.get(aliquota, 0.0))
            for campo, aliquota in VOCI_CON_IVA
        ]
        # la ristrutturazione paga l'IVA sul valore EFFETTIVO: quando il
        # campo è a zero l'importo arriva dal computo
        _iva_voci.append(fattibilita.iva_su(
            ristr_eff, st.session_state.get("bp_iva_ristr", 0.0)))
        parametri_bp["iva_costi"] = round(sum(_iva_voci), 2)
        parametri_bp["iva_costi_vendita"] = fattibilita.iva_su(
            st.session_state.get("bp_ag_out_eur", 0.0),
            st.session_state.get("bp_iva_ag_out", 0.0))
        # le provvigioni arrivano gia' imponibili: l'IVA la porta la colonna
        parametri_bp["iva_agenzia_pct"] = 0.0
        esito = fattibilita.studio_fattibilita(parametri_bp)
        acq = esito["costi_acquisto"]
        ven = esito["costi_vendita"]

        with st.container(key="bp_scroll"):
            # il dettaglio costi ha cinque colonne (voce, %, netto, IVA %,
            # IVA €): gli si dà più spazio, e la pagina scorre invece di
            # comprimerle fino a troncare i numeri
            col_sum, col_matrici, col_costi = st.columns(
                [1.0, 1.85, 2.15], gap="large")

            # ------------------------------------------ riepilogo (Summary)
            with col_sum:
                st.number_input("Mq commerciali", min_value=0.0, step=1.0,
                                key="bp_mq",
                                help="Si compila da sé con la superficie "
                                     "commerciale della planimetria. "
                                     "Scrivici sopra quando serve: da quel "
                                     "momento comanda la tua cifra.")
                # Il campo dice sempre da dove viene quello che c'è dentro.
                if mq_a_mano:
                    st.caption(":orange[Cifra scritta a mano.]"
                               + (f" :gray[La planimetria dice "
                                  f"**{numero_it(mq_da_planimetria, 2)} m²**.]"
                                  if mq_da_planimetria else ""))
                    if mq_da_planimetria:
                        st.button("↩️ Riprendi dalla planimetria",
                                  key="mq_da_planim",
                                  on_click=riprendi_mq_planimetria,
                                  args=(mq_da_planimetria,))
                elif mq_da_planimetria:
                    st.caption(f":green[Compilato dalla planimetria: "
                               f"**{numero_it(mq_da_planimetria, 2)} m²** "
                               "commerciali.]")
                elif not st.session_state.piante:
                    st.caption(":gray[Nessuna planimetria caricata: scrivi "
                               "qui i mq, oppure disegnale nella scheda "
                               "**Misura da planimetria**.]")
                elif mq_calpestabili:
                    # il caso che confonde: stanze disegnate, ma nessun
                    # perimetro d'ingombro — e la commerciale resta zero
                    st.warning(
                        "Nella planimetria ci sono stanze "
                        f"(**{numero_it(mq_calpestabili, 2)} m²** "
                        "calpestabili) ma **nessun perimetro «Superficie "
                        "commerciale»**, e le stanze interne da sole non "
                        "fanno superficie commerciale: il perimetro le "
                        "racchiude già, contarle in due posti gonfierebbe "
                        "il totale. Disegna il perimetro d'ingombro con la "
                        "categoria **Superficie commerciale**, oppure "
                        "scrivi qui i mq a mano.")
                else:
                    st.caption(":gray[La planimetria non ha ancora aree "
                               "disegnate con una scala: scrivi qui i mq, "
                               "oppure disegnale.]")
                campo_numero_it(st, "Passo sensitività (€)", "bp_passo",
                                decimali=0, label_visibility="visible")
                st.number_input("Durata operazione (mesi)", min_value=1,
                                max_value=120, step=1, key="bp_durata")
                # Testata di colonna: etichetta campione, non un bottone
                # arrotondato. Le due colonne (qui e «spese acquisto») sono
                # sorelle e si vestono uguale.
                st.markdown(intestazione_bp("ESTIMATED"),
                            unsafe_allow_html=True)
                with st.container(key="bp_in_acq"):
                    campo_numero_it(st, "Prezzo base (acquisto, €)",
                                    "bp_acquisto", decimali=0,
                                    label_visibility="visible")
                st.markdown(righe_bp([
                    ("€/mq acquisto",
                     numero_it(esito["eur_mq_acquisto"], 0) + " €"
                     if esito["eur_mq_acquisto"] else "—", None),
                    ("Buy cost", euro(acq["totale"]), None),
                    ("Prezzo netto — entry", euro(esito["entry"]), "bold"),
                ]), unsafe_allow_html=True)
                with st.container(key="bp_in_ven"):
                    campo_numero_it(st, "Estimated sell price (€)",
                                    "bp_vendita", decimali=0,
                                    label_visibility="visible",
                                    aiuto="Puoi stimarlo con l'MCA (terza "
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
                    intestazione_bp("Spese acquisto — dettaglio"),
                    unsafe_allow_html=True)
                # Una percentuale senza il prezzo su cui applicarla dà zero,
                # e uno zero muto accanto a un «9,00» scritto a mano sembra
                # un difetto. Qui si dice quale prezzo manca.
                _senza_base = []
                if not st.session_state.bp_acquisto:
                    _senza_base.append("il **prezzo di acquisto** (imposte e "
                                       "agenzia IN)")
                if not st.session_state.bp_vendita:
                    _senza_base.append("il **prezzo di vendita** "
                                       "(agenzia OUT)")
                if not ristr_eff:
                    _senza_base.append("l'**importo dei lavori** "
                                       "(imprevisti)")
                if _senza_base:
                    st.caption(
                        ":orange[Le percentuali qui sotto restano a zero "
                        "finché manca " + " · ".join(_senza_base)
                        + ": non c'è ancora un importo su cui calcolarle.]")
                e1, e2, e3, e4, e5 = st.columns(
                    [1.5, 0.75, 1.15, 0.7, 1.0])
                e1.caption("Voce")
                e2.caption("%")
                e3.caption("Netto")
                e4.caption("IVA %")
                e5.caption("IVA €")
                iva_voci = []
                iva_voci.append(riga_costo_bp(
                    "Imposte d'acquisto",
                    centro={"chiave": "bp_imposta", "min_value": 0.0,
                            "max_value": 30.0, "step": 0.5,
                            "on_change": bp_ricalcola_euro},
                    destra={"chiave": "bp_imposta_eur", "min_value": 0.0,
                            "step": 100.0, "format": "%.2f",
                            "on_change": bp_pct_da_euro_imposta},
                    iva="bp_iva_imposta"))
                iva_voci.append(riga_costo_bp(
                    "Imposte fisse",
                    destra={"chiave": "bp_imposte_fisse", "min_value": 0.0,
                            "step": 50.0, "format": "%.2f"},
                    iva="bp_iva_imposte_fisse"))
                iva_voci.append(riga_costo_bp(
                    "Notaio",
                    destra={"chiave": "bp_notaio", "min_value": 0.0,
                            "step": 100.0, "format": "%.2f",
                            "help": "Compreso IVA, visure, archivio "
                                    "notarile…"},
                    iva="bp_iva_notaio"))
                iva_voci.append(riga_costo_bp(
                    "Spese e interessi mutuo",
                    destra={"chiave": "bp_mutuo", "min_value": 0.0,
                            "step": 100.0, "format": "%.2f"},
                    iva="bp_iva_mutuo"))
                iva_voci.append(riga_costo_bp(
                    "Imprevisti e condominio",
                    centro={"chiave": "bp_imprevisti_pct", "min_value": 0.0,
                            "max_value": 50.0, "step": 1.0, "format": "%.2f",
                            "on_change": bp_ricalcola_euro,
                            "help": "Percentuale sull'importo dei lavori "
                                    "considerato qui sotto. Il 10% e' la "
                                    "quota del contratto d'appalto: "
                                    "cambiala quando serve, oppure scrivi "
                                    "l'importo a destra e la percentuale si "
                                    "adegua."},
                    destra={"chiave": "bp_imprevisti", "min_value": 0.0,
                            "step": 500.0, "format": "%.2f"},
                    iva="bp_iva_imprevisti"))
                riga_costo_bp(
                    "Agenzia IN",
                    centro={"chiave": "bp_ag_in", "min_value": 0.0,
                            "max_value": 10.0, "step": 0.5,
                            "on_change": bp_ricalcola_euro,
                            "help": "Commissione % sul prezzo di acquisto; "
                                    "l'importo a destra è imponibile, "
                                    "l'IVA sta nella sua colonna"},
                    destra={"chiave": "bp_ag_in_eur", "min_value": 0.0,
                            "step": 100.0, "format": "%.2f",
                            "on_change": bp_pct_da_euro_ag_in},
                    iva="bp_iva_ag_in")
                iva_voci.append(riga_costo_bp(
                    ":orange[**Ristrutturazione stimata**] (0 = dal "
                    "computo)",
                    destra={"chiave": "bp_ristr", "min_value": 0.0,
                            "step": 1000.0, "format": "%.2f",
                            "help": "I lavori NUDI, senza riserva: gli "
                                    "imprevisti sono la riga qui sopra e "
                                    "si contano una volta sola. Lasciando "
                                    "0 arrivano il totale del computo e "
                                    "l'allegato dei materiali a cura tua, "
                                    "sommati: l'operazione li paga "
                                    "entrambi."},
                    iva="bp_iva_ristr", imponibile=ristr_eff))
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
                # La didascalia che ripeteva ristrutturazione e mq è stata
                # tolta: adesso ogni campo si compila da sé e dichiara da
                # dove viene il proprio numero, quindi ripeterli qui sotto
                # era rumore.
                # Il parametro con cui si ragiona davvero in questo mestiere:
                # «quella la rifai con 600 al metro». Diviso per i mq
                # CALPESTABILI — sulla commerciale uscirebbe più basso del
                # vero, perché comprende superfici che non si ristrutturano.
                if esito["eur_mq_ristrutturazione"]:
                    st.markdown(
                        f'<div style="background:{ARDESIA_CHIARA};'
                        f'border:1px solid {OTTONE}73;padding:8px 11px;'
                        'margin:2px 0 8px;display:flex;'
                        'justify-content:space-between;align-items:baseline;'
                        'gap:.6rem;">'
                        f'<span style="font-size:.7rem;font-weight:600;'
                        'text-transform:uppercase;letter-spacing:.12em;'
                        f'color:{OTTONE};">Ristrutturazione al mq</span>'
                        f'<span style="font-size:1.35rem;font-weight:700;'
                        f'color:{TRAVERTINO};white-space:nowrap;">'
                        f'{numero_it(esito["eur_mq_ristrutturazione"], 0)}'
                        ' €/mq</span></div>', unsafe_allow_html=True)
                    st.caption(
                        f":gray[Su **{numero_it(mq_calpestabili, 2)} mq "
                        "calpestabili** — le stanze disegnate in "
                        "planimetria, non la superficie commerciale: "
                        "balconi, vano scale e perimetro si vendono ma non "
                        "si ristrutturano.]")
                elif mq_calpestabili <= 0 and ristr_eff:
                    st.caption(
                        ":orange[Per avere il costo al mq disegna le stanze "
                        "in planimetria: servono i **mq calpestabili**, e "
                        "la superficie commerciale non va bene come "
                        "ripiego.]")
                st.markdown(righe_bp([
                    ("di cui IVA", euro(acq["iva"]), None),
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
                                    "l'importo a destra è imponibile, "
                                    "l'IVA sta nella sua colonna"},
                    destra={"chiave": "bp_ag_out_eur", "min_value": 0.0,
                            "step": 100.0, "format": "%.2f",
                            "on_change": bp_pct_da_euro_ag_out},
                    iva="bp_iva_ag_out")
                st.markdown(righe_bp([
                    ("di cui IVA (vendita)",
                     euro(ven["iva"]) if ven.get("iva") else None, None),
                    ("TOTALE SPESE (acquisto + vendita)",
                     euro(acq["totale"] + ven["totale"]), "bold"),
                ]), unsafe_allow_html=True)
                # L'IVA pagata sui costi è un CREDITO, non una spesa: per una
                # società torna indietro. Tenerla in fondo, sommata e da
                # sola, è il numero che serve quando si guarda la cassa —
                # nelle righe qui sopra è sparsa voce per voce.
                iva_credito = round(acq["iva"] + ven["iva"], 2)
                if iva_credito:
                    st.markdown(righe_bp([
                        ("TOTALE IVA A CREDITO", euro(iva_credito), "buono"),
                    ]), unsafe_allow_html=True)
                    st.caption(
                        ":gray[L'IVA pagata su queste voci è **a credito**: "
                        "resta nel totale delle spese perché va anticipata, "
                        "ma per la società rientra con la liquidazione.]")

    # --------------------------------------------- MCA prezzo di vendita
    # ============================ CANTIERE: contratto, SAL, extra finali
    with sotto_cant:
        st.subheader("🏗️ Contratto d'appalto e stati di avanzamento")
        st.caption(
            "Le imprese si pagano a **SAL**, concordati nel contratto prima "
            "che il cantiere apra (spesso 20-30-30-20, ma ogni cantiere fa "
            "storia a sé). Gli **extra** non si vedono lungo la strada: si "
            "calcolano a cantiere chiuso, quando ci si siede con le parti e "
            "si fa il SAL finale. Qui si tiene il conto, e alla chiusura si "
            "impara quanto si è sforato — che è il numero che serve "
            "all'operazione dopo.")

        c_imp, c_ext = st.columns(2)
        with c_imp:
            campo_numero_it(st, "Importo di contratto (€)", "cant_contratto",
                            decimali=2, label_visibility="visible",
                            aiuto="Quanto hai firmato con l'impresa. Se lo "
                                  "lasci a zero non c'è niente da ripartire.")
            # ⚠️ Il COMPUTO NUDO, non il computo più i materiali. Qui si
            # scrive quanto hai firmato con l'impresa, e i materiali a cura
            # del committente sono per definizione quello che l'impresa non
            # ti fattura: metterli nel contratto d'appalto vorrebbe dire
            # cancellare con un bottone il confine che l'allegato traccia.
            if not st.session_state.cant_contratto and totale_computo_bp:
                if st.button(f"Usa il computo: {euro(totale_computo_bp)}",
                             key="cant_da_computo",
                             help="Solo le lavorazioni del computo: i "
                                  "materiali a cura tua non fanno parte "
                                  "dell'appalto."):
                    st.session_state.cant_contratto = totale_computo_bp
                    st.session_state.pop("cant_contratto_txt", None)
                    st.rerun()
        with c_ext:
            campo_numero_it(st, "Extra finali (€)", "cant_extra",
                            decimali=2, label_visibility="visible",
                            aiuto="Si compila a cantiere chiuso, dopo il SAL "
                                  "finale concordato con le parti.")

        st.markdown("**Stati di avanzamento**")
        st.caption("Le quote del contratto. Spunta i SAL già saldati.")
        quote = st.session_state.cant_sal or [
            {"percento": p, "pagato": False} for p in cantiere.SAL_PREDEFINITI]
        df_sal = st.data_editor(
            pd.DataFrame([{"SAL": f"SAL {i}", "%": q.get("percento", 0.0),
                           "Pagato": bool(q.get("pagato"))}
                          for i, q in enumerate(quote, start=1)]),
            hide_index=True, num_rows="dynamic", key="editor_sal",
            width="stretch",
            column_config={
                "SAL": st.column_config.TextColumn("Stato", disabled=True),
                "%": st.column_config.NumberColumn(
                    "% del contratto", min_value=0.0, max_value=100.0,
                    step=5.0, format="%.1f"),
                "Pagato": st.column_config.CheckboxColumn("Saldato"),
            })
        st.session_state.cant_sal = [
            {"percento": float(r["%"] or 0.0), "pagato": bool(r["Pagato"])}
            for _, r in df_sal.iterrows()]

        percentuali = [q["percento"] for q in st.session_state.cant_sal]
        somma = cantiere.somma_percentuali(percentuali)
        if percentuali and abs(somma - 100.0) > 0.01:
            st.warning(f"⚠️ Le quote fanno **{numero_it(somma, 1)}%**, non "
                       "100: il contratto non è ripartito per intero. Non "
                       "correggo io — è un numero da guardare.")
        stato = cantiere.stato_cantiere(
            st.session_state.cant_contratto, percentuali,
            pagati=[i for i, q in enumerate(st.session_state.cant_sal,
                                            start=1) if q["pagato"]],
            extra=st.session_state.cant_extra)

        if stato["contratto"]:
            st.dataframe(pd.DataFrame([{
                "Stato": f"SAL {s['n']}",
                "% del contratto": numero_it(s["percento"], 1) + " %",
                "Importo": euro(s["importo"]),
                "Saldato": "sì" if st.session_state.cant_sal[s["n"] - 1]
                                   ["pagato"] else "—",
            } for s in stato["piano"]]), hide_index=True, width="stretch")

            # «Residuo» e «ancora da pagare» differiscono SOLO per gli extra:
            # finché non ce ne sono è lo stesso numero sotto due nomi, e due
            # nomi sullo stesso numero si leggono come due conferme
            # indipendenti. Stessa cura già usata per ROE e rendimento annuo
            # a 12 mesi: l'etichetta lo dichiara.
            etichetta_da_pagare = ("Ancora da pagare" if stato["extra"]
                                   else "Ancora da pagare (= il residuo: "
                                        "nessun extra)")
            m1, m2, m3, m4 = st.columns(4)
            # «Saldato» in tutta la scheda: è la parola della colonna
            # dell'editor e della tabella del piano.
            m1.metric("Saldato", euro(stato["pagato"]))
            m2.metric("Residuo di contratto", euro(stato["residuo"]))
            # Non «Totale finale»: nel computo quella è la card d'ottone del
            # totale lavori, un'altra cosa.
            m3.metric("Totale a fine cantiere", euro(stato["totale_finale"]),
                      delta=(f"+{euro(stato['extra'])} extra"
                             if stato["extra"] else None), delta_color="off")
            m4.metric(etichetta_da_pagare, euro(stato["da_pagare"]))

            # Il residuo negativo adesso si vede (cantiere.stato_cantiere non
            # lo azzera più): qui si dice cosa significa.
            if stato["residuo"] < 0:
                somma_saldate = cantiere.somma_percentuali(
                    [q["percento"] for q in st.session_state.cant_sal
                     if q["pagato"]])
                st.warning(
                    f"⚠️ Hai saldato **{euro(-stato['residuo'])} in più** "
                    "dell'importo di contratto: i SAL spuntati fanno "
                    f"**{numero_it(somma_saldate, 1)}%** di un contratto che "
                    "ne vale 100. O il contratto è stato integrato e "
                    "l'importo qui sopra va aggiornato, oppure c'è una "
                    "spunta di troppo.")

            if stato["extra"]:
                segno = "+" if stato["scostamento"] >= 0 else ""
                st.markdown(
                    f'<div style="background:{OTTONE};padding:13px 15px;'
                    'margin:6px 0 10px;">'
                    f'<div style="font-size:.7rem;color:{ARDESIA};'
                    'font-weight:700;text-transform:uppercase;'
                    'letter-spacing:.12em;opacity:.85;">'
                    'Scostamento dal contratto</div>'
                    f'<div style="font-size:1.8rem;font-weight:700;'
                    f'color:{ARDESIA};line-height:1.2;">'
                    f'{segno}{numero_it(stato["scostamento"], 2)} %</div>'
                    '</div>', unsafe_allow_html=True)

        # ------------------------------------------- chiusura e storico
        st.divider()
        st.markdown("**📕 Chiudi l'operazione**")
        st.caption(
            "A cantiere concluso l'operazione entra nello storico, che vive "
            "**fuori dai progetti**. Da tre operazioni in poi lo storico "
            "smette di essere un archivio e diventa una misura: quanto "
            "sfori tu, con le tue imprese.")
        nome_op = st.session_state.prg_nome or "Progetto senza nome"
        eur_mq_lav = (round(stato["totale_finale"] / mq_calpestabili, 2)
                      if mq_calpestabili and stato["totale_finale"] else None)
        if st.button(f"📕 Chiudi «{nome_op}» e mettila nello storico",
                     type="primary", key="chiudi_operazione",
                     disabled=not stato["contratto"]):
            try:
                storico.registra({
                    "nome": nome_op,
                    "contratto": stato["contratto"],
                    "extra": stato["extra"],
                    "scostamento": stato["scostamento"],
                    "mq_calpestabili": mq_calpestabili or None,
                    "eur_mq": eur_mq_lav,
                })
                st.toast(f"«{nome_op}» è nello storico ✔")
                st.rerun()
            except OSError as errore:
                st.error(f"Non sono riuscito a scrivere lo storico: {errore}")

        chiuse = storico.carica()
        if not chiuse:
            st.caption(":gray[Nessuna operazione chiusa: lo storico comincia "
                       "dalla prima.]")
        else:
            st.dataframe(pd.DataFrame([{
                "Operazione": r.get("nome"),
                "Chiusa il": r.get("chiusa_il"),
                "Contratto": euro(r.get("contratto")),
                "Extra": euro(r.get("extra")),
                "Scostamento": (numero_it(r.get("scostamento"), 2) + " %"
                                if r.get("scostamento") is not None else "—"),
                "€/mq lavori": (numero_it(r.get("eur_mq"), 0) + " €"
                                if r.get("eur_mq") else "—"),
            } for r in chiuse]), hide_index=True, width="stretch")

            consigliati = cantiere.imprevisti_consigliati(
                storico.scostamenti(chiuse))
            media_mq = storico.media(storico.costi_al_mq(chiuse))
            s1, s2 = st.columns(2)
            if consigliati is not None:
                # Il segno lo porta il numero: negativo = chiuso sotto
                # contratto, e l'etichetta non deve smentirlo.
                s1.metric(f"Scostamento medio su {len(chiuse)} "
                          f"{'operazione' if len(chiuse) == 1 else 'operazioni'}",
                          f"{numero_it(consigliati, 2)} %")
            if media_mq:
                s2.metric("Costo medio dei lavori",
                          f"{numero_it(media_mq, 0)} €/mq")
            if consigliati is not None:
                # La MISURA e la PROPOSTA sono due cose diverse, e prima erano
                # la stessa: `imprevisti_consigliati` troncava a zero, così
                # chi chiude sotto contratto si sentiva dire «i tuoi cantieri
                # dicono 0,00%» invece di «−3%». Adesso la misura dice il
                # vero; è qui che si decide cosa proporne, e una riserva
                # negativa non esiste.
                proposta = max(0.0, consigliati)
                riserva = float(
                    st.session_state.get("bp_imprevisti_pct") or 0.0)
                if consigliati < 0:
                    st.info(
                        f"I tuoi cantieri chiusi hanno chiuso in media "
                        f"**sotto contratto** "
                        f"({numero_it(consigliati, 2)}%): la riserva del "
                        f"business plan, oggi al "
                        f"**{numero_it(riserva, 1)}%**, non è tarata sui "
                        "tuoi fatti — è prudenza. Tienila se la vuoi, ma "
                        "sappi che la stai pagando nel conto dell'operazione.")
                elif abs(consigliati - riserva) > 0.5:
                    st.info(
                        f"Nel business plan la riserva per imprevisti è al "
                        f"**{numero_it(riserva, 1)}%**, ma i tuoi cantieri "
                        f"chiusi dicono **{numero_it(consigliati, 2)}%**. "
                        "È la riga «Imprevisti e condominio» dello studio di "
                        "fattibilità: è lì che si decide se l'affare sta in "
                        "piedi.")
                if abs(proposta - riserva) > 0.5:
                    # ⚠️ La riscrittura va in una callback: il campo nasce
                    # nel sotto-pannello «Studio di fattibilità», disegnato
                    # prima di questo, e scriverci sopra qui pianterebbe
                    # l'app («cannot be modified after the widget is
                    # instantiated»). Dentro on_click Streamlit lo consente.
                    st.button(f"Porta la riserva a "
                              f"{numero_it(proposta, 2)}%",
                              key="applica_imprevisti",
                              on_click=applica_imprevisti,
                              args=(proposta,))

    with sotto_mca:
        st.caption("Stima del prezzo di vendita col **metodo comparativo** "
                   "(il tuo foglio «MCA sell»): per ogni comparabile "
                   "inserisci prezzo, mq e **com'è fatto** — vetustà, "
                   "finiture, piano, luminosità, riscaldamento… Il "
                   "**coefficiente di merito** lo calcola CME dalle voci "
                   "scelte (>1 = immobile migliore della media, <1 = "
                   "peggiore); il €/mq viene normalizzato, mediato e "
                   "riproporzionato sul tuo immobile. La colonna "
                   "**Coeff. a mano** serve solo a scavalcare la griglia "
                   "quando non la si condivide.")
        # ⚠️ width="stretch" non è cosmesi: senza, una tabella VUOTA si
        # stringe alla larghezza delle sue intestazioni (52 px misurati) e
        # la barra degli strumenti, che sta appesa al bordo destro, le esce
        # a sinistra e finisce fuori dallo schermo. Finché la barra era
        # invisibile non se ne accorgeva nessuno.
        # Le tendine della griglia sono quattordici (l'ascensore e' una
        # spunta, non una tendina): si costruiscono da
        # TENDINE_MERITO, che e' la stessa tabella da cui le legge il
        # blocco del soggetto qui sotto. Aggiungere un fattore a merito.py
        # lo fa comparire in tutti e due i posti senza toccare la scheda.
        config_mca = {
            campo: st.column_config.SelectboxColumn(
                etichetta, options=list(voci), width="small")
            for campo, (etichetta, voci) in TENDINE_MERITO.items()
        }
        config_mca["ascensore"] = st.column_config.CheckboxColumn(
            "Ascensore", width="small",
            help="⚠️ Pesa più di ogni altra voce: l'ultimo piano vale 1,10 "
                 "con ascensore e 0,70 senza. Non spuntato = assente.")
        df_mca_ed = st.data_editor(
            st.session_state.df_mca,
            num_rows="dynamic", hide_index=True, width="stretch",
            key=f"editor_mca_{st.session_state.versione_bp}",
            column_config={
                **config_mca,
                "nome": st.column_config.TextColumn(
                    "Comparabile", help="Es. C1 — via Roma 10"),
                # I prezzi dei comparabili si confrontano FRA LORO: è tutto il
                # senso della tabella, ed è il posto dove il separatore delle
                # migliaia smette di essere estetica («310000» si contava con
                # il dito). Stesso formato del registro spese.
                "prezzo": st.column_config.NumberColumn(
                    "Prezzo richiesto", width=145, format="euro"),
                # ⚠️ Il soggetto porta i mq COMMERCIALI (dalla planimetria o
                # scritti a mano nello studio di fattibilità). Se qui si
                # copiano i calpestabili di un annuncio, il €/mq dei
                # comparabili e quello del soggetto non sono la stessa
                # grandezza — e l'errore non si vede mai: si porta dentro il
                # prezzo di vendita. La colonna lo dice.
                "mq": st.column_config.NumberColumn(
                    "Mq commerciali", format="%.0f",
                    help="La stessa grandezza dei mq del soggetto: "
                         "superficie commerciale, non calpestabile. È quella "
                         "che scrivono gli annunci."),
                "coeff": st.column_config.NumberColumn(
                    "Coeff. a mano", format="%.3f", width="small",
                    help="Lascia VUOTO per usare il coefficiente calcolato "
                         "dalle voci qui accanto. Un numero qui scavalca la "
                         "griglia: serve ai progetti salvati prima che la "
                         "griglia esistesse, e a chi davanti all'immobile "
                         "sa che il modello ha torto."),
                "note": st.column_config.TextColumn(
                    "Note / link annuncio", width="large"),
            })
        # ⚠️ Le colonne non si perdono per strada. Il ritorno della tabella
        # torna a essere il dato di partenza del giro dopo: basta che una
        # volta arrivi senza intestazioni e la tabella resta per sempre un
        # moncone largo 52 px — misurato dal vivo su un progetto reale — con
        # la barra degli strumenti, appesa al bordo destro, che finisce
        # fuori dallo schermo. Il reindex ristabilisce le colonne e non
        # tocca i dati.
        st.session_state.df_mca = df_mca_ed.reindex(columns=COLONNE_MCA)

        # --- quanto vale, qui, essere già ristrutturati -------------------
        # ⚠️ Il livello di prezzo della zona si prende dai €/mq RICHIESTI,
        # cioè da un dato che NON passa per i coefficienti. Se si usasse il
        # normalizzato si entrerebbe in un giro chiuso: la scala serve a
        # calcolare i coefficienti che servono a calcolare la scala.
        righe_mca = mca_da_df(df_mca_ed)
        lordi = [r["prezzo"] / r["mq"] for r in righe_mca
                 if (r.get("prezzo") or 0) > 0 and (r.get("mq") or 0) > 0]
        valore_zona = sum(lordi) / len(lordi) if lordi else None
        scala_stato = merito.scala_stato_unita(
            valore_zona, st.session_state.bp_costo_ristr_mq,
            st.session_state.bp_quota_mercato / 100)

        # --- il TUO immobile, com'è a fine ristrutturazione ---------------
        st.markdown("##### Il tuo immobile a lavori finiti")
        st.caption(":gray[Le stesse voci dei comparabili, ma sul tuo — "
                   "**com'è quando lo vendi**, non com'è adesso: se lo "
                   "ristrutturi integralmente, «Condizioni» è *Finemente "
                   "ristrutturato*, non *Da ristrutturare*.]")
        # quattro per riga: quindici voci in una colonna sola sarebbero uno
        # scroll lungo quanto la scheda
        scelte_sog = {}
        for blocco in range(0, len(merito.CAMPI), 4):
            colonne_sog = st.columns(4)
            for colonna, campo in zip(colonne_sog,
                                      merito.CAMPI[blocco:blocco + 4]):
                chiave = f"sog_{campo}"
                if campo == "ascensore":
                    colonna.checkbox("Ascensore", key=chiave,
                                     help="Non spuntato = assente.")
                else:
                    etichetta, voci = TENDINE_MERITO[campo]
                    colonna.selectbox(etichetta, ("—",) + tuple(voci),
                                      key=chiave)
                valore = st.session_state.get(chiave)
                scelte_sog[campo] = None if valore == "—" else valore

        merito_sog = merito.coefficiente_effettivo(
            scelte_sog, st.session_state.bp_coeff_sogg, scala_stato)
        # ⚠️ Per un COMPARABILE la griglia in bianco vale zero, e lo fa
        # scartare: uno di cui non si sa nulla non deve entrare nella media.
        # Il soggetto invece è uno solo ed è il motivo per cui si sta
        # stimando — scartarlo vorrebbe dire non dare nessun numero. Vale
        # 1,00, cioè «nella media dei comparabili», e la scheda lo dice.
        coeff_sog = merito_sog["totale"] or 1.0

        # ⚠️ Cinque colonne, e la correzione per il taglio sta QUI e non fra
        # i risultati: il suo effetto — il coefficiente sotto i mq — si vede
        # sempre, mentre il blocco dei risultati compare solo quando c'è
        # almeno un comparabile buono. Un comando invisibile accanto a un
        # effetto visibile è il modo più rapido di far credere che il numero
        # lo decida il programma.
        m1, m2, m5, m3, m4 = st.columns(5)
        m1.metric("Coeff. di merito del tuo immobile",
                  numero_it(coeff_sog, 3))
        if merito_sog["fonte"] == "a mano":
            m1.caption(":gray[Scritto **a mano** nel campo qui accanto.]")
        elif merito_sog["fonte"] == "assente":
            m1.caption(":gray[Griglia **non compilata**: vale 1,000, cioè "
                       "«nella media dei comparabili».]")
        else:
            m1.caption(":gray[Calcolato dalle voci qui sopra.]")
        m2.number_input("Coeff. a mano (0 = usa la griglia)",
                        min_value=0.0, max_value=3.0, step=0.01,
                        format="%.3f", key="bp_coeff_sogg",
                        help="A zero comanda la griglia qui sopra. Un "
                             "numero diverso da zero la scavalca: è così "
                             "che continuano a tornare i progetti salvati "
                             "prima che la griglia esistesse.")
        m5.number_input("Correzione per il taglio", min_value=0.0,
                        max_value=0.60, step=0.05, format="%.2f",
                        key="bp_taglio",
                        help="I tagli piccoli costano di più al metro, e la "
                             "griglia non ha una voce per la superficie. "
                             "0 = spenta. 0,15 = un 50 m² vale l'11% in più "
                             "al metro di un 100 m². È l'unico parametro "
                             "che puoi TARARE: alzalo o abbassalo e guarda "
                             "la dispersione dei comparabili — se scende, "
                             "quel valore descrive meglio il tuo mercato.")
        m3.number_input("Sconto di trattativa (%)", min_value=0.0,
                        max_value=30.0, step=0.5, key="bp_sconto",
                        help="Differenza media tra prezzo richiesto e "
                             "prezzo di vendita reale (~13%)")
        m4.metric("Mq commerciali del soggetto", numero_it(mq_eff, 0) + " m²")
        taglio_sog = merito.coefficiente_taglio(
            mq_eff, st.session_state.bp_taglio)
        if taglio_sog and st.session_state.bp_taglio:
            m4.caption(f":gray[Coeff. di taglio **{numero_it(taglio_sog, 3)}** "
                       "— dalla superficie, non da una tendina.]")
        else:
            m4.caption(":gray[Dal campo **Mq commerciali** dello studio di "
                       "fattibilità.]")
        # ⚠️ Un progetto salvato prima della griglia porta dentro il suo
        # coefficiente scritto a mano — spesso 1,00, che era il predefinito
        # di allora. Senza questo avviso, chi apre quel progetto e compila
        # le tendine non vede cambiare NIENTE e non capisce perché: il
        # numero vecchio sta zitto e vince.
        if merito_sog["fonte"] == "a mano" and merito_sog["dettaglio"]:
            st.warning(
                "⚠️ Hai compilato la griglia, ma comanda il **coefficiente "
                f"a mano ({numero_it(merito_sog['totale'], 3)})**: dalle "
                f"voci scelte uscirebbe "
                f"**{numero_it(merito_sog['calcolato'], 3)}**. Metti "
                "**0** in «Coeff. a mano» per usare la griglia.")
        if merito_sog["fonte"] == "griglia" and merito_sog["mancanti"]:
            st.caption(":gray[Voci non indicate, che valgono 1,00: **"
                       + "**, **".join(merito_sog["mancanti"]) + "**.]")

        # --- lo stato tarato sul costo dei lavori -------------------------
        st.markdown("###### Quanto vale, qui, essere già ristrutturati")
        r1, r2, r3 = st.columns([1, 1, 2])
        r1.number_input("Costo lavori (€/m² comm.)", min_value=0.0,
                        max_value=3000.0, step=50.0, format="%.0f",
                        key="bp_costo_ristr_mq",
                        help="Quanto costa ristrutturare, al metro quadro "
                             "COMMERCIALE (la stessa base dei €/mq della "
                             "stima, non il calpestabile). A zero la voce "
                             "«Stato dell'unità» resta sulla tabella fissa.")
        r2.number_input("Quota riconosciuta (%)", min_value=0.0,
                        max_value=130.0, step=5.0, format="%.0f",
                        key="bp_quota_mercato",
                        help="Quanto di quel costo il mercato te lo ripaga "
                             "sul prezzo. Non è mai tutto: chi compra da "
                             "ristrutturare vuole anche il compenso per il "
                             "rischio, il tempo e la seccatura. È anche il "
                             "margine del tuo mestiere — sotto il 100% ci "
                             "guadagni, sopra il 100% il mercato paga il "
                             "ristrutturato più di quanto ti costa farlo.")
        if valore_zona:
            finito = scala_stato["Finemente ristrutturato"]
            grezzo = scala_stato["Da ristrutturare integralmente"]
            salto = (finito - grezzo) / finito * valore_zona
            r3.caption(
                f":gray[Coi comparabili in tabella la zona sta sui "
                f"**{numero_it(valore_zona, 0)} €/m²** richiesti. Su quel "
                f"livello, «finemente ristrutturato» vale "
                f"**{numero_it(finito, 3)}** e «da ristrutturare "
                f"integralmente» **{numero_it(grezzo, 3)}**: un salto di "
                f"**{numero_it(salto, 0)} €/m²**, che è il costo dei lavori "
                "per la quota qui accanto.]")
            # ⚠️ Lo stesso costo pesa il 60% del valore in una zona da
            # 1.500 €/m² e il 18% in una da 5.000: una tabella fissa dello
            # stato non può essere giusta in tutt'e due. Qui si riscala.
            r3.caption(":gray[Una tabella fissa varrebbe solo per un unico "
                       "livello di prezzo: lo stesso costo pesa il 60% del "
                       "valore in una zona da 1.500 €/m² e il 18% in una da "
                       "5.000.]")
        else:
            r3.caption(":gray[Servono dei comparabili con prezzo e mq per "
                       "sapere su che livello di prezzo sta la zona. Senza, "
                       "«Stato dell'unità» resta sulla tabella fissa "
                       "0,82–1,18, che vale per una zona da ~2.500 €/m².]")

        # Il coefficiente di ogni comparabile esce dalla sua riga: le voci
        # scelte, oppure il numero scritto a mano se c'è.
        comparabili = []
        for riga in righe_mca:
            eff = merito.coefficiente_effettivo(
                merito.scelte_da_riga(riga), riga.get("coeff"), scala_stato)
            comparabili.append({**riga, "coeff": eff["totale"]})

        esito_mca = fattibilita.stima_mca(
            comparabili, coeff_sog, mq_eff,
            st.session_state.bp_sconto,
            statistica=st.session_state.mca_statistica,
            elasticita_taglio=st.session_state.bp_taglio)
        if esito_mca is None:
            st.info("Aggiungi almeno un comparabile completo (prezzo, mq e "
                    "coefficiente maggiori di zero).")
        else:
            st.dataframe(pd.DataFrame([{
                "Comparabile": d["nome"],
                "m²": numero_it(d["mq"], 0),
                "€/mq": numero_it(d["eur_mq"], 0),
                "Coeff. merito": numero_it(d["coeff"], 3),
                "Coeff. taglio": (numero_it(d["coeff_taglio"], 3)
                                  if d["coeff_taglio"] else "—"),
                "€/mq normalizzato": numero_it(d["eur_mq_normalizzato"], 0),
                "Scarto dalla mediana": f"{numero_it(d['scarto_pct'], 1)}%",
            } for d in esito_mca["dettaglio"]]), hide_index=True)
            # ⚠️ Le righe incomplete sparivano in silenzio: con cinque
            # comparabili in tabella e due senza coefficiente, la stima era
            # su tre e nessuna etichetta lo diceva. Qui si dichiarano il
            # numero e il metodo — media aritmetica, non ponderata sui mq.
            usati = esito_mca["usati"]
            if esito_mca["scartati"]:
                st.warning(
                    f"⚠️ **{esito_mca['scartati']} comparabile/i** "
                    f"incompleto/i **non entra/entrano** nella stima: serve "
                    "che prezzo, mq e coefficiente siano tutti maggiori di "
                    f"zero. La media qui sotto è su **{usati}**.")

            # Il controllo di qualità del metodo: normalizzati i €/mq, quel
            # che resta è il valore della zona — e la zona è una sola. Se
            # non convergono, la stima non è pronta.
            cv = esito_mca["cv"]
            if usati > 1:
                if cv <= 15:
                    st.success(f"✅ I €/mq normalizzati **convergono** "
                               f"(dispersione {numero_it(cv, 1)}%): "
                               "i comparabili raccontano tutti la stessa "
                               "zona.")
                elif cv <= 25:
                    st.warning(f"⚠️ Dispersione **{numero_it(cv, 1)}%**: i "
                               "comparabili non concordano del tutto. "
                               "Guarda gli scarti qui sopra prima di usare "
                               "il numero.")
                else:
                    st.error(f"🚨 Dispersione **{numero_it(cv, 1)}%**: "
                             "normalizzati, i comparabili dovrebbero dire "
                             "lo stesso €/mq e non lo dicono. O non sono "
                             "confrontabili, o una voce della griglia è "
                             "sbagliata: **il numero non è pronto**.")
            if esito_mca["outlier"]:
                st.info(
                    "🔎 Fuori scala di oltre il 25% dalla mediana: **"
                    + "**, **".join(esito_mca["outlier"]) + "**. Spesso è "
                    "una questione di taglio — i tagli piccoli costano di "
                    "più al metro e la griglia non ha un fattore per la "
                    "superficie. Con la **mediana** pesano molto meno; "
                    "toglierli del tutto è un'altra scelta ancora, e la "
                    "fai tu.")

            s1, s2 = st.columns([1, 3])
            s1.selectbox("Come si riassumono", ("media", "mediana"),
                         key="mca_statistica",
                         help="La mediana non si fa spostare da un "
                              "comparabile fuori scala. La media è quella "
                              "del foglio Excel.")
            # ⚠️ «aritmetica» non è un vezzo: dice che la media NON è
            # ponderata sui mq, cioè che un bilocale pesa quanto un
            # quadrilocale. È l'avvertenza che regge tutto il metodo, e un
            # test la protegge — se cambia la parola, cambiala anche lì
            # sapendo cosa stai togliendo.
            riassunto = ("Media **aritmetica**"
                         if esito_mca["statistica"] == "media"
                         else "**Mediana**")
            s2.caption(
                f":gray[{riassunto} dei €/mq "
                f"normalizzati di **{usati}** "
                f"{'comparabile' if usati == 1 else 'comparabili'}: un "
                "bilocale pesa quanto un quadrilocale — a riproporzionare "
                "ci pensa il coefficiente di merito, non la superficie. "
                f"Media {numero_it(esito_mca['eur_mq_media'], 0)} €/mq, "
                f"mediana {numero_it(esito_mca['eur_mq_mediana'], 0)} €/mq.]")

            n1, n2, n3, n4 = st.columns(4)
            n1.metric(f"€/mq normalizzato ({esito_mca['statistica']}, "
                      f"su {usati})",
                      numero_it(esito_mca["eur_mq_media"]
                                if esito_mca["statistica"] == "media"
                                else esito_mca["eur_mq_mediana"], 0))
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
with st.container(key="cme_script_lingua"):
    st.iframe(
        '<!doctype html><html><body><script>'
        'try { window.parent.document.documentElement.lang = "it"; }'
        ' catch (errore) {}'
        '</script></body></html>',
        height=1,
)
