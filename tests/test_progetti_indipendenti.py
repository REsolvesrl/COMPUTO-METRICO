"""Due progetti aperti di fila non si toccano.

È successo davvero, ed è il difetto più grave che questa app possa avere:
si lavorava su un cantiere, si apriva l'altro, e nell'altro comparivano i
numeri del primo — le spunte dei lavori facoltativi rimaste accese, due
quantità portate a 4, una a zero, e tutto il business plan sovrascritto.
I totali erano quelli giusti (quelli vengono dalle chiavi «di verità»), ma
a video no: e quello che si legge a video è quello su cui si decide.

Le cause erano due, e i test qui sotto le tengono chiuse tutt'e due:

1. **le caselle restavano dell'altro progetto.** Ogni casella ha, accanto,
   un segnalibro «_reso_» che dice con quale numero è nata; quel segnalibro
   non veniva buttato all'apertura, e la casella non si riscriveva. Quando i
   due progetti avevano la stessa quantità, la casella rinasceva addirittura
   dal suo minimo — zero al posto di uno.

2. **un caricamento a metà restava a metà.** Il progetto veniva tolto dalla
   coda all'INIZIO del caricamento: se il giro si fermava prima della fine —
   Streamlit interrompe lo script appena arriva un'altra interazione — si
   restava con il computo di uno e il business plan dell'altro, per sempre.

La prova regina è `test_aprire_un_altro_progetto_non_lascia_tracce`: apre un
progetto, ci lavora come una persona, ne apre un altro, e pretende che lo
stato sia identico a quello di chi quell'altro progetto l'ha aperto e basta.
"""
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

SORGENTE = Path(__file__).resolve().parent.parent / "streamlit_app.py"

# Chiavi che cambiano per forza e che non dicono niente sul progetto: i
# contatori che fanno rinascere le tabelle, gli identificativi delle
# planimetrie e lo stato interno degli editor, che da quei contatori dipende.
NON_CONTANO = ("uid_piante", "versione_bp", "versione_mat", "loc_base_chiave",
               "loc_base_df", "piante", "editor_", "edloc_", "_bp_copia",
               "cat_aperte", "pool_aperte")

VILLA = {
    "progetto": {"nome": "Villa", "committente": "Tizio", "oggetto": "Tetto",
                 "luogo": "La Spezia", "data": "2026-09-01",
                 "aliquota_iva": 10.0},
    # 2.11 e 7.3 sono scritte a mano: stessi codici nei due progetti, valori
    # diversi. È il caso che faceva più danno.
    "voci": [
        {"codice": "2.11", "categoria": "Demolizioni", "um": "a corpo",
         "descrizione": "Allestimento cantiere", "prezzo": 2500.0,
         "quantita_manuale": 1.0},
        {"codice": "7.3", "categoria": "Aree esterne", "um": "punto",
         "descrizione": "Linea elettrica dal contatore", "prezzo": 300.0,
         "quantita_manuale": 4.0},
    ],
    "listino_stato": {"2.2": {"q": 10.0, "p": 35.0},
                      "3.10": {"q": 20.0, "p": 48.0},
                      "8.2": {"q": 1.0, "p": 1000.0}},
    "testi_voci": {"3.10": {"d": "Gres della villa", "u": "m²"}},
    "voci_scelte": ["2.11", "2.2", "3.10", "7.3", "8.2"],
    "lavori_facoltativi": ["Tetto"],
    "business_plan": {"bp_acquisto": 360000.0, "bp_vendita": 900000.0,
                      "bp_durata": 12, "bp_ag_in": 4.0},
    "spese": [{"oggetto": "Notaio", "importo": 5000.0,
               "categoria": "Costi indiretti"}],
    "piante": [],
}

CASA = {
    "progetto": {"nome": "Casa", "committente": "Caio", "oggetto": "Interni",
                 "luogo": "Sarzana", "data": "2026-09-02",
                 "aliquota_iva": 22.0},
    "voci": [
        # stessa quantità della villa: è il caso in cui la casella, non
        # riscritta, rinasceva a ZERO
        {"codice": "2.11", "categoria": "Demolizioni", "um": "a corpo",
         "descrizione": "Allestimento cantiere", "prezzo": 2000.0,
         "quantita_manuale": 1.0},
        {"codice": "7.3", "categoria": "Aree esterne", "um": "punto",
         "descrizione": "Linea elettrica dal contatore", "prezzo": 300.0,
         "quantita_manuale": 1.0},
    ],
    "listino_stato": {"2.2": {"q": 5.0, "p": 40.0},
                      "3.12": {"q": 8.0, "p": 55.0}},
    "voci_scelte": ["2.11", "2.2", "3.12", "7.3"],
    "business_plan": {"bp_acquisto": 140000.0, "bp_vendita": 300000.0,
                      "bp_durata": 8, "bp_ag_in": 2.0},
    "piante": [],
}

CATEGORIE_APERTE = {"Demolizioni", "Ricostruzioni e ripristini",
                    "Aree esterne", "Tetto"}


def _avvia():
    at = AppTest.from_file(str(SORGENTE), default_timeout=300)
    at.run()
    return at


def _apri(at, progetto):
    """Come premere «Apri» in archivio, e poi guardare il computo."""
    at.session_state["da_caricare"] = dict(progetto)
    at.run()
    at.session_state["cat_aperte"] = set(CATEGORIE_APERTE)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _lavora(at):
    """I gesti di chi lavora: quantità a frecce, quantità scritte, prezzi,
    un importo del business plan."""
    at.number_input(key="qn_7.3_w").set_value(9.0).run()
    at.text_input(key="q_2.2_txt").set_value("77,00").run()
    at.text_input(key="p_3.10_txt").set_value("52,00").run()
    at.session_state["scheda_attiva"] = "📊 Business plan"
    at.run()
    at.text_input(key="bp_acquisto_txt").set_value("400.000,00").run()
    at.session_state["scheda_attiva"] = "📝 Computo metrico"
    at.run()
    assert not at.exception, [e.value for e in at.exception]


def _uguali(a, b):
    if isinstance(a, pd.DataFrame) or isinstance(b, pd.DataFrame):
        try:
            return a.equals(b)
        except Exception:                                    # noqa: BLE001
            return False
    try:
        return bool(a == b)
    except Exception:                                        # noqa: BLE001
        return repr(a) == repr(b)


@pytest.fixture(scope="module")
def solo_casa():
    return dict(_apri(_avvia(), CASA).session_state.filtered_state)


@pytest.fixture(scope="module")
def casa_dopo_villa():
    at = _apri(_avvia(), VILLA)
    _lavora(at)
    _apri(at, CASA)
    return dict(at.session_state.filtered_state)


# ------------------------------------------------------------- la guardia

def test_aprire_un_altro_progetto_non_lascia_tracce(solo_casa,
                                                    casa_dopo_villa):
    """La prova regina: stato identico, chiave per chiave."""
    diverse = [
        c for c in sorted(set(solo_casa) | set(casa_dopo_villa))
        if not c.startswith(NON_CONTANO)
        and not _uguali(solo_casa.get(c, "<assente>"),
                        casa_dopo_villa.get(c, "<assente>"))]
    assert diverse == [], [
        (c, solo_casa.get(c, "<assente>"),
         casa_dopo_villa.get(c, "<assente>")) for c in diverse]


# ------------------------------------- i sintomi visti, uno per uno

def test_la_quantita_a_corpo_uguale_nei_due_progetti_non_va_a_zero(
        casa_dopo_villa):
    """«Assistenza muraria 1» che compariva a 0: la casella era stata
    buttata e non riscritta, e Streamlit la faceva rinascere dal minimo."""
    assert casa_dopo_villa["q_2.11"] == 1.0
    assert casa_dopo_villa["qn_2.11_w"] == 1.0


def test_la_quantita_scritta_nell_altro_progetto_non_resta_a_video(
        casa_dopo_villa):
    """Sulla villa la 7.3 era stata portata a 9: sulla casa vale 1."""
    assert casa_dopo_villa["q_7.3"] == 1.0
    assert casa_dopo_villa["qn_7.3_w"] == 1.0


def test_i_prezzi_e_le_quantita_scritti_a_mano_non_passano(casa_dopo_villa):
    """Sulla villa: 2.2 portata a 77 e 3.10 a 52 €."""
    assert casa_dopo_villa["q_2.2"] == 5.0
    assert casa_dopo_villa["p_2.2"] == 40.0
    assert "q_3.10" not in casa_dopo_villa or casa_dopo_villa["q_3.10"] == 0.0


def test_le_descrizioni_riscritte_nell_altro_progetto_spariscono(
        casa_dopo_villa):
    assert "d_3.10" not in casa_dopo_villa


def test_il_business_plan_e_quello_del_progetto_aperto(casa_dopo_villa):
    assert casa_dopo_villa["bp_acquisto"] == 140000.0
    assert casa_dopo_villa["bp_vendita"] == 300000.0
    assert casa_dopo_villa["bp_durata"] == 8
    assert casa_dopo_villa["bp_ag_in"] == 2.0


def test_i_lavori_facoltativi_dell_altro_progetto_si_spengono(
        casa_dopo_villa):
    assert casa_dopo_villa["lavori_facoltativi"] == []
    assert casa_dopo_villa["voci_scelte"] == CASA["voci_scelte"]


def test_il_pdf_dell_altro_progetto_non_resta_da_scaricare():
    at = _apri(_avvia(), VILLA)
    at.session_state["_pdf_planimetrie"] = b"le planimetrie della villa"
    at.session_state["_json_pronto"] = b"il progetto della villa"
    at.run()
    _apri(at, CASA)
    assert "_pdf_planimetrie" not in at.session_state
    assert "_json_pronto" not in at.session_state


# ------------------------------------- il caricamento è tutto o niente

def test_un_progetto_rovinato_non_si_carica_a_meta():
    """Il caricamento si toglie dalla coda solo quando è finito: se il giro
    si ferma prima, quello dopo ricarica da capo invece di lasciare in
    tavola mezzo progetto e mezzo l'altro."""
    at = _apri(_avvia(), VILLA)
    rovinato = dict(CASA, business_plan={"bp_durata": "otto"})
    at.session_state["da_caricare"] = rovinato
    at.run()
    assert at.exception, "il progetto rovinato deve farsi sentire"
    # il caricamento è ancora in coda: non è stato dato per fatto
    assert "da_caricare" in at.session_state


def test_riaperto_il_progetto_buono_torna_tutto_a_posto():
    at = _apri(_avvia(), VILLA)
    at.session_state["da_caricare"] = dict(CASA, business_plan={"bp_durata":
                                                                "otto"})
    at.run()
    at.session_state["da_caricare"] = dict(CASA)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    assert at.session_state["bp_acquisto"] == 140000.0
    assert at.session_state["voci_scelte"] == CASA["voci_scelte"]
