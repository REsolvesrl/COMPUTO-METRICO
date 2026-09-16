"""Tetto e facciata: lavori che non ci sono in ogni cantiere.

Si accendono con un interruttore per progetto. Spenti non si vedono e non
contano da nessuna parte; accesi portano le loro voci del listino. Spegnere
non cancella niente: riaccendendo si ritrova tutto com'era.
"""
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import listino

SORGENTE = Path(__file__).resolve().parent.parent / "streamlit_app.py"
VOCI_TETTO = [v["codice"] for v in listino.voci_della_categoria("Tetto")]


def _avvia():
    at = AppTest.from_file(str(SORGENTE), default_timeout=240)
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _interruttore(at, categoria, acceso):
    at.toggle(key=f"facoltativa_{categoria}_w").set_value(acceso).run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _totale_lavori(at):
    return next(m.value for m in at.metric
                if m.label == "Totale lavori (IVA esclusa)")


def _schede(at):
    """Le categorie disegnate nel computo, dai loro bottoni."""
    return [b.label for b in at.button if (b.key or "").startswith("apri_")]


@pytest.fixture(scope="module")
def nuovo():
    return _avvia()


# ------------------------------------------------- di norma sono spenti

def test_in_un_progetto_nuovo_sono_spenti(nuovo):
    assert nuovo.session_state["lavori_facoltativi"] == []
    assert nuovo.toggle(key="facoltativa_Tetto_w").value is False
    assert nuovo.toggle(key="facoltativa_Facciata_w").value is False


def test_spenti_non_hanno_scheda_nel_computo(nuovo):
    schede = " ".join(_schede(nuovo))
    assert "Demolizioni" in schede
    assert "Tetto" not in schede and "Facciata" not in schede


def test_spenti_non_si_pescano_dal_pool():
    at = _avvia()
    at.session_state["pool_aperte"] = set(listino.CATEGORIE)
    at.run()
    prendibili = {b.key for b in at.button
                  if (b.key or "").startswith("prendi_")}
    assert "prendi_2.2" in prendibili
    assert not any(k.startswith(("prendi_8.", "prendi_9.")) for k in prendibili)


# ------------------------------------------------- accendere

def test_accendere_il_tetto_porta_le_sue_voci():
    at = _interruttore(_avvia(), "Tetto", True)
    assert at.session_state["lavori_facoltativi"] == ["Tetto"]
    assert at.session_state["voci_scelte"] == VOCI_TETTO
    assert "Tetto" in " ".join(_schede(at))
    assert "Facciata" not in " ".join(_schede(at))


def test_accendere_non_ripesca_le_voci_scartate():
    at = _avvia()
    at.session_state["voci_scartate"] = ["8.6"]
    at.run()
    _interruttore(at, "Tetto", True)
    assert "8.6" not in at.session_state["voci_scelte"]
    assert len(at.session_state["voci_scelte"]) == len(VOCI_TETTO) - 1


def test_accendere_una_categoria_che_ha_gia_voci_non_ne_aggiunge():
    """Se nel computo c'è già qualcosa del tetto, è una scelta fatta."""
    at = _avvia()
    at.session_state["voci_scelte"] = ["8.3"]
    at.run()
    _interruttore(at, "Tetto", True)
    assert at.session_state["voci_scelte"] == ["8.3"]


# ------------------------------------------------- contare e non contare

def test_la_facciata_conta_solo_se_accesa():
    at = _interruttore(_avvia(), "Facciata", True)
    at.session_state["q_9.8"] = 100.0          # 100 m² × 22 €
    at.run()
    assert _totale_lavori(at) == "2.200,00 €"
    _interruttore(at, "Facciata", False)
    assert _totale_lavori(at) == "0,00 €"
    assert "Facciata" not in " ".join(_schede(at))


def test_spegnere_non_cancella_niente():
    at = _interruttore(_avvia(), "Facciata", True)
    at.session_state["q_9.8"] = 100.0
    at.session_state["p_9.8"] = 18.0
    at.run()
    _interruttore(at, "Facciata", False)
    assert "9.8" in at.session_state["voci_scelte"]
    assert at.session_state["q_9.8"] == 100.0
    _interruttore(at, "Facciata", True)
    assert _totale_lavori(at) == "1.800,00 €"
    # riaccendendo non si raddoppia niente
    assert at.session_state["voci_scelte"].count("9.8") == 1


def test_una_voce_tua_nel_tetto_si_spegne_col_tetto():
    at = _interruttore(_avvia(), "Tetto", True)
    at.session_state["voci_extra"] = {"8.14": {
        "codice": "8.14", "categoria": "Tetto", "descrizione": "Lucernario",
        "um": "cad", "prezzo": 900.0}}
    at.session_state["voci_scelte"] = ["8.14"]
    at.session_state["q_8.14"] = 1.0
    at.session_state["p_8.14"] = 900.0
    at.run()
    assert _totale_lavori(at) == "900,00 €"
    _interruttore(at, "Tetto", False)
    assert _totale_lavori(at) == "0,00 €"


def test_il_numero_della_facciata_resta_nove_anche_col_tetto_spento():
    """Il numero del riepilogo è la serie dei codici, non la posizione."""
    at = _interruttore(_avvia(), "Facciata", True)
    testo = " ".join(m.value for m in at.markdown)
    assert "9. Facciata" in testo
    assert "8. Facciata" not in testo


# ------------------------------------------------- viaggiano col progetto

def test_si_salvano_e_tornano():
    at = _interruttore(_avvia(), "Facciata", True)
    at.session_state["q_9.8"] = 100.0
    at.run()
    salvato = at.session_state["voci_scelte"]
    at.session_state["da_caricare"] = {
        "voci_scelte": list(salvato),
        "listino_stato": {"9.8": {"q": 100.0, "p": 22.0}},
        "lavori_facoltativi": ["Facciata"],
    }
    at.run()
    assert at.session_state["lavori_facoltativi"] == ["Facciata"]
    assert at.toggle(key="facoltativa_Facciata_w").value is True
    assert _totale_lavori(at) == "2.200,00 €"


def test_un_progetto_di_prima_li_apre_spenti():
    at = _interruttore(_avvia(), "Tetto", True)
    at.session_state["da_caricare"] = {"voci_scelte": ["2.2"],
                                       "listino_stato": {"2.2": {"q": 10.0}}}
    at.run()
    assert at.session_state["lavori_facoltativi"] == []
    assert at.toggle(key="facoltativa_Tetto_w").value is False


def test_una_categoria_sconosciuta_non_si_accende():
    at = _avvia()
    at.session_state["da_caricare"] = {"lavori_facoltativi": ["Piscina"]}
    at.run()
    assert at.session_state["lavori_facoltativi"] == []


def test_un_progetto_nuovo_li_rispegne():
    at = _interruttore(_avvia(), "Tetto", True)
    at.checkbox(key="conf_nuovo_progetto").check().run()
    at.button(key="nuovo_progetto").click().run()
    assert at.session_state["lavori_facoltativi"] == []
    assert at.toggle(key="facoltativa_Tetto_w").value is False
