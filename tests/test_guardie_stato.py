"""Guardie contro i difetti che sono già costati un pomeriggio intero.

Non controllano che l'app funzioni — a quello pensano gli altri test — ma
che nel codice non ricompaiano tre SCHEMI che hanno prodotto difetti veri,
tutti della stessa famiglia: un valore giusto in memoria e un altro sotto
gli occhi dell'utente.

Leggono il sorgente, non lo eseguono: costano niente e parlano prima che
il difetto arrivi allo schermo.
"""
import ast
from pathlib import Path

SORGENTE = Path(__file__).resolve().parent.parent / "streamlit_app.py"


def _albero():
    return ast.parse(SORGENTE.read_text(encoding="utf-8-sig"))


def _chiamate(nome_funzione):
    """Tutte le chiamate a `qualcosa.nome_funzione(...)` o `nome_funzione(...)."""
    trovate = []
    for nodo in ast.walk(_albero()):
        if not isinstance(nodo, ast.Call):
            continue
        f = nodo.func
        if (isinstance(f, ast.Attribute) and f.attr == nome_funzione) or \
                (isinstance(f, ast.Name) and f.id == nome_funzione):
            trovate.append(nodo)
    return trovate


# ---------------------------------------------------------------- schema 1

def test_nessuna_casella_di_testo_col_valore_passato_come_argomento():
    """`value=` su un text_input con chiave è una trappola.

    Vale solo alla PRIMA creazione: da lì in poi la casella nel browser si
    tiene quello che ha dentro e ignora il valore nuovo. Il calcolo era
    giusto e finiva nei totali, ma la colonna mostrava «0,00» — è il
    difetto che ha resistito a cinque giri di correzioni, invisibile ai
    test perché AppTest il browser non ce l'ha.

    Rimedio: scrivere il testo in `st.session_state[chiave]` PRIMA di
    creare il widget, e non passare `value=`.

    ⚠️ Vale solo per le chiavi FISSE. Con una chiave che cambia col
    contenuto (`ren_<uid>`, `zn_<uid>_<id>`) il widget è un altro widget e
    rinasce dal suo valore: lì `value=` è legittimo, e segnalarlo
    trasformerebbe questa guardia in rumore da ignorare.
    """
    colpevoli = []
    for chiamata in _chiamate("text_input"):
        argomenti = {k.arg: k.value for k in chiamata.keywords}
        if "value" not in argomenti or "key" not in argomenti:
            continue
        chiave = argomenti["key"]
        if not isinstance(chiave, ast.Constant):
            continue                      # chiave dinamica: widget diverso
        colpevoli.append(f"riga {chiamata.lineno} (key={chiave.value!r})")
    assert not colpevoli, (
        "text_input con value= E key= insieme: nel browser il campo non si "
        "aggiornerà più. Scrivi st.session_state[chiave] prima di creare il "
        "widget.\n" + "\n".join(colpevoli))


# ---------------------------------------------------------------- schema 2

CALLBACK_CHE_LEGGONO_IL_PROGETTO = ("salva_al_volo", "segna_salvato")


def test_le_callback_convertono_prima_di_leggere_il_progetto():
    """Una callback gira PRIMA dello script.

    Le caselle degli importi contengono testo finché lo script non lo
    converte in numero: una callback che legge il progetto senza convertire
    salva i valori del giro precedente. È successo col tasto Salva —
    scrivevi 145.000 e nel file finiva 0 — e le percentuali si salvavano,
    perché sono campi numerici: è per quello che sembrava colpire solo
    certi campi.
    """
    mancanti = []
    for nodo in ast.walk(_albero()):
        if not isinstance(nodo, ast.FunctionDef):
            continue
        if nodo.name not in CALLBACK_CHE_LEGGONO_IL_PROGETTO:
            continue
        corpo = ast.dump(nodo)
        if "rileggi_campi_numero_it" not in corpo:
            mancanti.append(nodo.name)
    assert not mancanti, (
        "Queste callback leggono il progetto senza convertire prima le "
        "caselle di testo: salveranno i valori di un giro fa — "
        + ", ".join(mancanti))


# ---------------------------------------------------------------- schema 3

def _caselle_non_riscritte(testo):
    """Le caselle a chiave fissa che l'apertura di un progetto non riscrive.

    Una «_w» (numero, spunta, interruttore, tendina) va ASSEGNATA nel blocco
    di caricamento; una «_txt» degli importi può anche solo sparire, perché
    `campo_numero_it` la riscrive da sé a ogni disegno.
    """
    import re
    usate = set(re.findall(r'key=f?"([A-Za-z0-9_]+_(?:w|txt))"', testo))

    inizio = testo.find('if "da_caricare" in st.session_state:')
    fine = testo.find("\nst.session_state.categorie", inizio)
    assert inizio >= 0 and fine > inizio, "blocco da_caricare non trovato"
    blocco = testo[inizio:fine]

    assegnate = set(re.findall(
        r'st\.session_state\["([A-Za-z0-9_]+_w)"\]\s*=', blocco))
    assegnate |= set(re.findall(
        r'st\.session_state\.([A-Za-z0-9_]+_w)\s*=', blocco))
    for gruppo in re.findall(
            r'for _k in \(([^)]*)\):\s*\n\s*'
            r'st\.session_state\[_k \+ "_w"\] =', blocco):
        assegnate |= {n + "_w"
                      for n in re.findall(r'"([a-z0-9_]+)"', gruppo)}

    pulite_txt = set(re.findall(r'"([A-Za-z0-9_]+_txt)"', blocco))
    if "for _chiave in CAMPI_NUMERO_IT" in blocco:
        pulite_txt |= {c + "_txt"
                       for c in re.findall(r'^\s{4}"([a-z_]+)": \(\d', testo,
                                           re.M)}
    return sorted(
        [k for k in usate if k.endswith("_w") and k not in assegnate]
        + [k for k in usate if k.endswith("_txt") and k not in pulite_txt])


def test_ogni_casella_si_riscrive_quando_si_apre_un_progetto():
    """Il valore della sessione precedente non deve sopravvivere all'apertura.

    Prima la regola era «buttarle via», ed era la metà giusta: il testo di
    una casella non buttata riscriveva i valori appena caricati (il
    progetto salvato con 145.000 € di acquisto che, riaperto, tornava a
    zero). Ma buttare non basta. È la stessa trappola dello schema 1, per
    tutte le caselle e non solo per quelle di testo: una casella buttata
    rinasce dal suo `value=` sul server, il BROWSER si tiene quello che
    aveva a video e al primo clic lo rimanda indietro. Migliarina, aperto
    dopo ENI, si è ripreso così le detrazioni e i lavori facoltativi di
    ENI, ed è stato salvato così. Scritto nello stato, il valore arriva al
    browser come un ordine, e lui si adegua.
    """
    mancanti = _caselle_non_riscritte(SORGENTE.read_text(encoding="utf-8-sig"))
    assert not mancanti, (
        "Caselle che l'apertura di un progetto non riscrive: il browser ci "
        "rimanderà i valori del progetto di prima — " + ", ".join(mancanti))


def test_la_guardia_delle_caselle_riconosce_la_casella_solo_buttata():
    """Una guardia serve solo se sa accorgersi del caso che vieta."""
    finto = (
        'st.number_input("x", key="fin_n_w")\n'
        'st.number_input("y", key="porta_n_w")\n'
        'if "da_caricare" in st.session_state:\n'
        '    st.session_state.pop("fin_n_w", None)\n'
        '    st.session_state.porta_n_w = 3\n'
        '\nst.session_state.categorie = []\n')
    assert _caselle_non_riscritte(finto) == ["fin_n_w"]


def test_la_guardia_riconosce_il_difetto_che_deve_impedire():
    """Una guardia serve solo se sa accorgersi del caso che vieta."""
    finto = ast.parse('st.text_input("x", value="5", key="k")')
    trovati = [n for n in ast.walk(finto) if isinstance(n, ast.Call)
               and getattr(n.func, "attr", "") == "text_input"
               and {k.arg for k in n.keywords} >= {"value", "key"}]
    assert len(trovati) == 1


# ---------------------------------------------------------------- schema 4

def test_ogni_tabella_modificabile_dice_come_scrivere_le_celle_vuote():
    """Senza `placeholder`, una cella vuota si stampa la parola «None».

    È il comportamento documentato di `st.data_editor` — «If this is None
    (default), missing values are displayed as "None"» — e non c'è un solo
    posto in quest'app in cui quella parola inglese abbia senso per chi
    legge.

    Difetto vero, costato tre giri di tentativi a vuoto: nell'elenco dei
    materiali la quantità è quasi sempre vuota (29 celle su 29 appena si
    apre un progetto), e la tabella si riempiva di «None». Il dato era
    perfetto — arrivava al browser come `null` dentro l'Arrow, verificato
    byte per byte — e proprio per questo nessun test lo vedeva: è la
    stessa famiglia degli altri difetti sorvegliati qui, un valore giusto
    in memoria e un altro sotto gli occhi dell'utente.

    Rimedio: `placeholder=""` su OGNI data_editor.
    """
    colpevoli = []
    for chiamata in _chiamate("data_editor"):
        if "placeholder" not in {k.arg for k in chiamata.keywords}:
            colpevoli.append(f"riga {chiamata.lineno}")
    assert not colpevoli, (
        "data_editor senza placeholder=\"\": le celle vuote mostreranno la "
        "scritta «None» nel browser.\n" + "\n".join(colpevoli))


def test_la_guardia_del_placeholder_riconosce_il_difetto():
    """Una guardia serve solo se sa accorgersi del caso che vieta."""
    finto = ast.parse('st.data_editor(df, key="k")')
    nudi = [n for n in ast.walk(finto) if isinstance(n, ast.Call)
            and getattr(n.func, "attr", "") == "data_editor"
            and "placeholder" not in {k.arg for k in n.keywords}]
    assert len(nudi) == 1
