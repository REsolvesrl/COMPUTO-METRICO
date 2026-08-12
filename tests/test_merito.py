"""La griglia dei coefficienti deve dare gli stessi numeri del foglio.

I casi qui sotto sono ricalcati sulle colonne di «MCA sell»: se un giorno
un coefficiente della griglia cambia, questi test dicono di quanto si e'
spostata la stima rispetto al modello di partenza.
"""

import pytest

from merito import (BALCONI, CONDIZIONI, FINITURE, PIANO_CON_ASCENSORE,
                    PIANO_SENZA_ASCENSORE, coefficiente_merito)


# Il soggetto del foglio (colonna N): normale 20-40 anni, finiture civili,
# finemente ristrutturato ma corretto a mano da 1,10 a 1,12, manutenzione
# ottima, primo piano con ascensore, balconi e terrazzo, posto auto.
SOGGETTO = {
    "stato_edificio": "Normale", "eta_edificio": "20-40 anni",
    "finiture": "Civili",
    "condizioni": 1.12,
    "degrado": "Assente/ottima",
    "piano": "Primo", "ascensore": True,
    "balconi": "Sì", "giardino": "No", "terrazzo": "Sì",
    "luminosita": "Mediamente luminoso",
    "spazi_comuni": "Assenti",
    "parcheggio": "Posto auto per UI",
    "esposizione": "Mista",
    "riscaldamento": "Autonomo",
}

# Il comparabile C4 (colonna G), quello col coefficiente piu' alto del
# gruppo: finiture signorili, terzo piano con ascensore, terrazzo, esterno.
C4 = {
    "stato_edificio": "Normale", "eta_edificio": "20-40 anni",
    "finiture": "Signorili",
    "condizioni": "Nuovo o ristrutturato",
    "degrado": "Ordinaria/sufficiente",
    "piano": "Terzo", "ascensore": True,
    "balconi": "Sì", "giardino": "No", "terrazzo": "Sì",
    "luminosita": "Luminoso",
    "spazi_comuni": "Assenti",
    "parcheggio": "Assente",
    "esposizione": "Esterna",
    "riscaldamento": "Centralizzato",
}


def test_coefficiente_del_soggetto_come_excel():
    esito = coefficiente_merito(SOGGETTO)
    assert esito["edificio"] == pytest.approx(1.0)            # N22
    assert esito["unita"] == pytest.approx(1.04832)           # N57
    assert esito["complementi"] == pytest.approx(1.26126)     # N86
    assert esito["totale"] == pytest.approx(1.322204, abs=1e-6)  # N89
    assert esito["mancanti"] == []


def test_coefficiente_di_c4_come_excel():
    esito = coefficiente_merito(C4)
    assert esito["edificio"] == pytest.approx(1.05)           # G22
    assert esito["unita"] == pytest.approx(1.05)              # G57
    assert esito["complementi"] == pytest.approx(1.2733875)   # G86
    assert esito["totale"] == pytest.approx(1.40390972, abs=1e-6)  # G89


def test_le_voci_lasciate_in_bianco_si_dichiarano():
    """Nel foglio una cella vuota e una cella a 1,00 davano lo stesso
    prodotto: non si vedeva quante voci fossero rimaste da compilare."""
    esito = coefficiente_merito({"finiture": "Civili"})
    assert esito["totale"] == pytest.approx(1.0)
    assert "Vetustà" in esito["mancanti"]
    assert "Condizioni" in esito["mancanti"]
    assert "Finiture" not in esito["mancanti"]


def test_il_numero_a_mano_scavalca_la_griglia():
    """Chi ha visto l'immobile sa cose che la griglia non ha: il soggetto
    del foglio portava 1,12 dove la tabella dice 1,10."""
    da_griglia = coefficiente_merito(
        dict(SOGGETTO, condizioni="Finemente ristrutturato"))
    assert da_griglia["totale"] == pytest.approx(1.298593, abs=1e-6)
    assert coefficiente_merito(SOGGETTO)["totale"] > da_griglia["totale"]


def test_senza_ascensore_il_piano_alto_vale_meno():
    """E' il fattore con l'escursione piu' larga della griglia: l'ultimo
    piano passa da 1,10 a 0,70 se l'ascensore non c'e'."""
    con = coefficiente_merito({"piano": "Ultimo piano", "ascensore": True})
    senza = coefficiente_merito({"piano": "Ultimo piano", "ascensore": False})
    assert con["dettaglio"]["Livello piano"] == PIANO_CON_ASCENSORE["Ultimo piano"]
    assert senza["dettaglio"]["Livello piano"] == PIANO_SENZA_ASCENSORE["Ultimo piano"]
    assert senza["totale"] < con["totale"]


def test_senza_indicazione_l_ascensore_si_da_per_assente():
    """La scelta prudente: dare per scontato l'ascensore avrebbe gonfiato
    la stima proprio sul fattore che pesa di piu'."""
    muto = coefficiente_merito({"piano": "Terzo"})
    assert muto["dettaglio"]["Livello piano"] == pytest.approx(0.8)


def test_i_booleani_valgono_come_si_e_no():
    assert (coefficiente_merito({"balconi": True})["dettaglio"]["Balconi"]
            == BALCONI["Sì"])
    assert (coefficiente_merito({"balconi": False})["dettaglio"]["Balconi"]
            == BALCONI["No"])


def test_una_voce_che_non_esiste_e_una_voce_mancante():
    esito = coefficiente_merito({"finiture": "Lussuosissime"})
    assert "Finiture" in esito["mancanti"]
    assert esito["totale"] == pytest.approx(1.0)


def test_la_griglia_e_quella_del_foglio():
    assert FINITURE == {"Signorili": 1.05, "Civili": 1.0, "Economiche": 0.9}
    assert CONDIZIONI["Nuova costruzione"] == 1.15
    assert CONDIZIONI["Da ristrutturare oltre 50 anni"] == 0.8
