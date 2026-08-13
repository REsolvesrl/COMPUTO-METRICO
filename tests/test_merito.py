"""La griglia dei coefficienti deve dare gli stessi numeri del foglio.

I casi qui sotto sono ricalcati sulle colonne di «MCA sell»: se un giorno
un coefficiente della griglia cambia, questi test dicono di quanto si e'
spostata la stima rispetto al modello di partenza.
"""

import pytest

from merito import (BALCONI, CONDIZIONI, FATTORI, FINITURE,
                    PIANO_CON_ASCENSORE, PIANO_SENZA_ASCENSORE,
                    coefficiente_effettivo, coefficiente_merito,
                    coefficiente_taglio, scelte_da_riga)


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


def test_le_scelte_si_estraggono_da_una_riga_della_tabella():
    """La riga di un comparabile porta anche nome, prezzo, mq e note."""
    riga = dict(SOGGETTO, nome="C1", prezzo=300000.0, mq=80.0,
                coeff=None, note="via Roma 10")
    scelte = scelte_da_riga(riga)
    assert "nome" not in scelte and "prezzo" not in scelte
    assert scelte["piano"] == "Primo"
    assert coefficiente_merito(scelte)["totale"] == pytest.approx(
        1.322204, abs=1e-6)


def test_le_celle_vuote_non_diventano_scelte():
    riga = {"stato_edificio": "Normale", "eta_edificio": "20-40 anni",
            "finiture": None, "condizioni": ""}
    scelte = scelte_da_riga(riga)
    assert "finiture" not in scelte and "condizioni" not in scelte
    assert "Finiture" in coefficiente_merito(scelte)["mancanti"]


def test_il_coefficiente_a_mano_vince_sulla_griglia():
    """E' quello che tiene in piedi i progetti salvati prima della griglia:
    hanno il coefficiente battuto a mano e nessuna voce compilata."""
    esito = coefficiente_effettivo(scelte_da_riga(SOGGETTO), a_mano=1.475)
    assert esito["totale"] == pytest.approx(1.475)
    assert esito["fonte"] == "a mano"
    # la griglia resta visibile accanto, per il confronto
    assert esito["calcolato"] == pytest.approx(1.322204, abs=1e-6)


@pytest.mark.parametrize("a_mano", [None, 0, 0.0])
def test_senza_numero_a_mano_comanda_la_griglia(a_mano):
    esito = coefficiente_effettivo(scelte_da_riga(SOGGETTO), a_mano=a_mano)
    assert esito["fonte"] == "griglia"
    assert esito["totale"] == pytest.approx(1.322204, abs=1e-6)


def test_una_griglia_in_bianco_non_e_un_immobile_nella_media():
    """`coefficiente_merito` dà 1,0 a chi non ha compilato niente — tutte
    le voci neutre — ma come comparabile vorrebbe dire farne entrare uno di
    cui non si sa nulla spacciandolo per medio. A zero viene scartato."""
    esito = coefficiente_effettivo({})
    assert esito["totale"] == 0.0
    assert esito["fonte"] == "assente"
    assert esito["calcolato"] == pytest.approx(1.0)
    # 13 coefficienti da 15 caselle: stato ed età fanno la vetustà, e
    # l'ascensore non è un fattore a sé — sceglie quale tabella dei piani
    # si applica.
    assert len(esito["mancanti"]) == len(FATTORI) + 2
    assert len(esito["mancanti"]) == 13


def test_basta_una_voce_perche_la_griglia_conti():
    """Non serve compilarle tutte: una sola voce dice già qualcosa, e le
    altre restano dichiarate fra le mancanti."""
    esito = coefficiente_effettivo({"finiture": "Signorili"})
    assert esito["fonte"] == "griglia"
    assert esito["totale"] == pytest.approx(1.05)
    assert len(esito["mancanti"]) == 12


# --------------------------------------------------------------- taglio

def test_il_taglio_premia_il_piccolo_e_sconta_il_grande():
    assert coefficiente_taglio(100) == pytest.approx(1.0)
    assert coefficiente_taglio(50) > 1.0
    assert coefficiente_taglio(200) < 1.0
    # 0,15 di elasticità: +11% a 50 m², −10% a 200 m²
    assert coefficiente_taglio(50) == pytest.approx(1.1096, abs=0.001)
    assert coefficiente_taglio(200) == pytest.approx(0.9013, abs=0.001)


def test_il_taglio_e_continuo_e_non_a_fasce():
    """Con le fasce un 79 m² e un 81 m² finirebbero in due mondi diversi
    per un metro quadro."""
    salto = abs(coefficiente_taglio(81) - coefficiente_taglio(79))
    assert salto < 0.01


def test_elasticita_zero_spegne_il_taglio():
    assert coefficiente_taglio(50, elasticita=0) == 1.0
    assert coefficiente_taglio(200, elasticita=0) == 1.0


def test_senza_superficie_non_c_e_taglio_da_correggere():
    """Meglio dirlo che restituire un 1,0 che sembra una misura."""
    for niente in (None, 0, "", "abc", -10):
        assert coefficiente_taglio(niente) is None


def test_la_griglia_e_quella_del_foglio():
    assert FINITURE == {"Signorili": 1.05, "Civili": 1.0, "Economiche": 0.9}
    assert CONDIZIONI["Nuova costruzione"] == 1.15
    assert CONDIZIONI["Da ristrutturare oltre 50 anni"] == 0.8
