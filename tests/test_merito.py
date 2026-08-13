"""La griglia dei coefficienti di merito.

Fino a ieri questi test controllavano la fedelta' al foglio «MCA sell».
Adesso la griglia se ne DISCOSTA di proposito — lo stato era contato tre
volte e la luce due — quindi i numeri attesi sono quelli nuovi, e c'e' un
test apposta che misura di quanto ci si e' spostati dal foglio.
"""

import pytest

import merito
from merito import (BALCONI, FATTORI, FINITURE, LUCE_VISTA,
                    PIANO_CON_ASCENSORE, PIANO_SENZA_ASCENSORE, STATO_UNITA,
                    coefficiente_effettivo, coefficiente_merito,
                    coefficiente_taglio, migra_scelte, scelte_da_riga)


# Il soggetto del foglio, ridetto nella griglia nuova: palazzina normale di
# 20-40 anni, finiture civili, finemente ristrutturato, primo piano con
# ascensore, balconi e terrazzo, posto auto, riscaldamento autonomo.
SOGGETTO = {
    "stato_edificio": "Normale", "eta_edificio": "20-40 anni",
    "stato_unita": "Finemente ristrutturato",
    "finiture": "Civili",
    "piano": "Primo", "ascensore": True,
    "balconi": "Sì", "giardino": "No", "terrazzo": "Sì",
    "luce_vista": "Nella media",
    "spazi_comuni": "Assenti",
    "parcheggio": "Posto auto per UI",
    "riscaldamento": "Autonomo",
}


def test_coefficiente_del_soggetto():
    esito = coefficiente_merito(SOGGETTO)
    assert esito["edificio"] == pytest.approx(1.0)      # vetustà × finiture
    assert esito["unita"] == pytest.approx(1.017)       # 1,13 × 0,90
    assert esito["complementi"] == pytest.approx(1.26126)
    assert esito["totale"] == pytest.approx(1.282701, abs=1e-6)
    assert esito["mancanti"] == []


def test_quanto_ci_si_e_spostati_dal_foglio():
    """Sul caso tipico l'accorpamento vale il 3%: non e' una ritaratura,
    e' l'aver smesso di chiedere due volte la stessa cosa. La differenza
    vera sta agli ESTREMI, che e' dove il difetto mordeva."""
    assert coefficiente_merito(SOGGETTO)["totale"] == pytest.approx(
        1.322204 * 0.970, abs=0.002)      # 1,322204 era il valore del foglio


def test_l_esterno_e_l_interno_restano_due_domande():
    """Si puo' ristrutturare benissimo dentro un palazzo che cade, e
    viceversa: sono due informazioni, non una. Ognuna conta da sola."""
    solo_edificio = coefficiente_merito({"stato_edificio": "Scadente",
                                         "eta_edificio": "oltre 40 anni"})
    solo_unita = coefficiente_merito({"stato_unita": "Finemente ristrutturato"})
    assert solo_edificio["totale"] == pytest.approx(0.90)
    assert solo_unita["totale"] == pytest.approx(1.13)
    # e insieme si moltiplicano, ma partendo da due range tenuti stretti
    insieme = coefficiente_merito({"stato_edificio": "Scadente",
                                   "eta_edificio": "oltre 40 anni",
                                   "stato_unita": "Finemente ristrutturato"})
    assert insieme["totale"] == pytest.approx(0.90 * 1.13)


def test_l_interno_non_si_conta_piu_due_volte():
    """«Condizioni» × «degrado» erano la stessa domanda fatta due volte: un
    appartamento da ristrutturare con manutenzione scadente non e' due
    notizie. Con la vetusta' in fila davano 0,544-1,316; adesso 0,738-1,298."""
    peggiore = coefficiente_merito({
        "stato_unita": "Da ristrutturare integralmente",
        "stato_edificio": "Scadente", "eta_edificio": "oltre 40 anni"})
    migliore = coefficiente_merito({
        "stato_unita": "Nuova costruzione",
        "stato_edificio": "Ottimo", "eta_edificio": "oltre 40 anni"})
    assert peggiore["totale"] == pytest.approx(0.738, abs=1e-3)
    assert migliore["totale"] == pytest.approx(1.298, abs=1e-3)
    # il rudere non vale piu' 0,544: era il prodotto di tre voci gemelle
    assert peggiore["totale"] > 0.544


def test_un_palazzo_d_epoca_tenuto_bene_vale_di_piu_di_uno_nuovo():
    """Non e' una svista ereditata dal foglio: e' un'interazione. Un
    edificio d'epoca in ottimo stato e' un pregio, lo stesso malandato e'
    una spesa."""
    epoca = coefficiente_merito({"stato_edificio": "Ottimo",
                                 "eta_edificio": "oltre 40 anni"})
    recente = coefficiente_merito({"stato_edificio": "Ottimo",
                                   "eta_edificio": "1-20 anni"})
    scadente = coefficiente_merito({"stato_edificio": "Scadente",
                                    "eta_edificio": "oltre 40 anni"})
    assert (epoca["dettaglio"]["Stato edificio"]
            > recente["dettaglio"]["Stato edificio"]
            > scadente["dettaglio"]["Stato edificio"])


# ------------------------- lo stato tarato sul costo dei lavori

def test_la_tabella_base_vale_per_una_zona_da_2500():
    """0,82-1,18 non e' campato in aria: corrisponde a ~800 €/m² di lavori
    riconosciuti all'85% su una zona da 2.500 €/m². E' giusta li', e solo
    li' — che e' il motivo per cui altrove va riscalata."""
    assert merito.costo_implicito(STATO_UNITA, 2500) == pytest.approx(
        807, abs=2)


def test_lo_stesso_costo_pesa_diversamente_secondo_la_zona():
    """900 €/m² sono il 60% del valore in una zona da 1.500 e il 18% in una
    da 5.000: la stessa casa da rifare vale, in proporzione, molto meno
    dove il finito costa poco."""
    povera = merito.scala_stato_unita(1500)
    ricca = merito.scala_stato_unita(5000)
    assert (povera["Da ristrutturare integralmente"]
            < STATO_UNITA["Da ristrutturare integralmente"]
            < ricca["Da ristrutturare integralmente"])
    assert povera["Da ristrutturare integralmente"] == pytest.approx(
        0.623, abs=0.002)
    assert ricca["Da ristrutturare integralmente"] == pytest.approx(
        0.905, abs=0.002)


@pytest.mark.parametrize("zona", [1500, 2000, 2500, 3000, 4000, 5000])
def test_la_scala_riporta_sempre_il_costo_che_le_hai_dato(zona):
    """Il giro si chiude: qualunque sia il livello di prezzo, il salto fra
    finito e da-rifare vale i 900 €/m² di partenza."""
    scala = merito.scala_stato_unita(zona, 900.0, 0.85)
    assert merito.costo_implicito(scala, zona, 0.85) == pytest.approx(
        900, abs=1)


def test_abitabile_resta_l_ancora():
    """E' il punto rispetto a cui i comparabili sono normalizzati: se si
    muovesse, si muoverebbe tutta la stima insieme a lui."""
    for zona in (1500, 2500, 5000):
        assert merito.scala_stato_unita(zona)["Abitabile"] == 1.0


def test_senza_il_livello_di_prezzo_resta_la_tabella():
    assert merito.scala_stato_unita() == STATO_UNITA
    assert merito.scala_stato_unita(0) == STATO_UNITA
    assert merito.scala_stato_unita(2500, costo_mq=0) == STATO_UNITA
    assert merito.scala_stato_unita(2500, quota=0) == STATO_UNITA


def test_la_scala_non_esplode_sulle_zone_economiche():
    """Sotto un certo prezzo l'obiettivo tende a 1 e il ventaglio si
    aprirebbe all'infinito: un coefficiente negativo non vuol dire niente."""
    estrema = merito.scala_stato_unita(400, 1000.0, 1.0)
    assert estrema["Da ristrutturare integralmente"] > 0.5
    assert estrema["Nuova costruzione"] < 1.6


def test_la_scala_entra_nel_coefficiente():
    scelte = {"stato_unita": "Da ristrutturare integralmente"}
    base = coefficiente_merito(scelte)["totale"]
    povera = coefficiente_merito(
        scelte, merito.scala_stato_unita(1500))["totale"]
    assert povera < base
    assert coefficiente_effettivo(
        scelte, scala_stato=merito.scala_stato_unita(1500))["totale"] == \
        pytest.approx(povera)


def test_la_luce_non_si_chiede_piu_due_volte():
    """Un appartamento e' luminoso PERCHE' e' esterno e ben esposto:
    luminosita' × esposizione davano 0,855-1,21 sulla stessa informazione."""
    assert min(LUCE_VISTA.values()) == pytest.approx(0.90)
    assert max(LUCE_VISTA.values()) == pytest.approx(1.10)


def test_undici_coefficienti_da_tredici_caselle():
    """Erano tredici da quindici. Le due caselle in piu' dei coefficienti
    sono l'eta' dell'edificio, che con lo stato fa un coefficiente solo, e
    l'ascensore, che sceglie quale tabella dei piani si applica."""
    assert len(merito.CAMPI) == 13
    esito = coefficiente_effettivo({})
    assert len(esito["mancanti"]) == 11
    assert len(FATTORI) + 3 == 11


def test_le_voci_lasciate_in_bianco_si_dichiarano():
    esito = coefficiente_merito({"finiture": "Civili"})
    assert esito["totale"] == pytest.approx(1.0)
    assert "Stato dell'unità" in esito["mancanti"]
    assert "Stato edificio" in esito["mancanti"]
    assert "Finiture" not in esito["mancanti"]


def test_lo_stato_dell_edificio_vuole_tutt_e_due_le_tendine():
    """Due tendine, un coefficiente solo: con una sola non c'e' la casella
    da cercare nella tabella a doppia entrata."""
    esito = coefficiente_merito({"stato_edificio": "Ottimo"})
    assert "Stato edificio" in esito["mancanti"]
    assert esito["totale"] == pytest.approx(1.0)


def test_il_numero_a_mano_scavalca_la_griglia():
    da_griglia = coefficiente_merito(SOGGETTO)
    esito = coefficiente_effettivo(scelte_da_riga(SOGGETTO), a_mano=1.475)
    assert esito["totale"] == pytest.approx(1.475)
    assert esito["fonte"] == "a mano"
    assert esito["calcolato"] == pytest.approx(da_griglia["totale"])


@pytest.mark.parametrize("a_mano", [None, 0, 0.0])
def test_senza_numero_a_mano_comanda_la_griglia(a_mano):
    esito = coefficiente_effettivo(scelte_da_riga(SOGGETTO), a_mano=a_mano)
    assert esito["fonte"] == "griglia"
    assert esito["totale"] == pytest.approx(1.282701, abs=1e-6)


def test_una_griglia_in_bianco_non_e_un_immobile_nella_media():
    esito = coefficiente_effettivo({})
    assert esito["totale"] == 0.0
    assert esito["fonte"] == "assente"
    assert esito["calcolato"] == pytest.approx(1.0)


def test_basta_una_voce_perche_la_griglia_conti():
    esito = coefficiente_effettivo({"finiture": "Signorili"})
    assert esito["fonte"] == "griglia"
    assert esito["totale"] == pytest.approx(1.05)
    assert len(esito["mancanti"]) == 10


def test_senza_ascensore_il_piano_alto_vale_meno():
    con = coefficiente_merito({"piano": "Ultimo piano", "ascensore": True})
    senza = coefficiente_merito({"piano": "Ultimo piano", "ascensore": False})
    assert con["dettaglio"]["Livello piano"] == PIANO_CON_ASCENSORE["Ultimo piano"]
    assert senza["dettaglio"]["Livello piano"] == PIANO_SENZA_ASCENSORE["Ultimo piano"]
    assert senza["totale"] < con["totale"]


def test_senza_indicazione_l_ascensore_si_da_per_assente():
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
    riga = dict(SOGGETTO, nome="C1", prezzo=300000.0, mq=80.0,
                coeff=None, note="via Roma 10")
    scelte = scelte_da_riga(riga)
    assert "nome" not in scelte and "prezzo" not in scelte
    assert scelte["piano"] == "Primo"
    assert coefficiente_merito(scelte)["totale"] == pytest.approx(
        1.282701, abs=1e-6)


def test_le_celle_vuote_non_diventano_scelte():
    riga = {"stato_edificio": "Normale", "finiture": None, "stato_unita": ""}
    scelte = scelte_da_riga(riga)
    assert "finiture" not in scelte and "stato_unita" not in scelte
    assert "Finiture" in coefficiente_merito(scelte)["mancanti"]


# ------------------------------------------------ dalla griglia di prima

def test_le_condizioni_vecchie_diventano_lo_stato_dell_unita():
    """Tre voci cambiano nome, quattro no. Chi aveva compilato la griglia
    di prima non deve ritrovarsi le tendine vuote — e le tendine vuote non
    sono un errore visibile: la stima uscirebbe lo stesso, solo piu' bassa."""
    assert migra_scelte({"condizioni": "Finemente ristrutturato"})[
        "stato_unita"] == "Finemente ristrutturato"
    assert migra_scelte({"condizioni": "Abitabile 10-30 anni"})[
        "stato_unita"] == "Abitabile"
    assert migra_scelte({"condizioni": "Da ristrutturare oltre 50 anni"})[
        "stato_unita"] == "Da ristrutturare integralmente"


def test_luminosita_ed_esposizione_si_fondono_nella_media():
    """Meccanico e spiegabile: media dei due coefficienti di prima, voce
    nuova piu' vicina."""
    # 1,05 (luminoso) e 1,05 (esterna) -> 1,05
    assert migra_scelte({"luminosita": "Luminoso",
                         "esposizione": "Esterna"})["luce_vista"] == \
        "Esterna e luminosa"
    # 1,10 (molto luminoso) e 0,90 (completamente interna) -> 1,00
    assert migra_scelte({"luminosita": "Molto luminoso",
                         "esposizione": "Completamente interna"})[
        "luce_vista"] == "Nella media"
    # una sola delle due basta
    assert migra_scelte({"esposizione": "Esterna panoramica"})[
        "luce_vista"] == "Panoramica e molto luminosa"


def test_la_migrazione_butta_via_le_voci_sparite():
    fuori = migra_scelte({"condizioni": "Abitabile 10-30 anni",
                          "degrado": "Alto/scadente",
                          "luminosita": "Poco luminoso",
                          "esposizione": "Interna"})
    for sparita in ("condizioni", "degrado", "luminosita", "esposizione"):
        assert sparita not in fuori


def test_la_migrazione_non_tocca_chi_ha_gia_i_campi_nuovi():
    gia_nuovo = {"stato_unita": "Nuova costruzione",
                 "luce_vista": "Interna e buia",
                 "condizioni": "Abitabile 10-30 anni"}
    fuori = migra_scelte(gia_nuovo)
    assert fuori["stato_unita"] == "Nuova costruzione"
    assert fuori["luce_vista"] == "Interna e buia"


def test_la_migrazione_non_modifica_l_originale():
    dentro = {"condizioni": "Abitabile 10-30 anni"}
    migra_scelte(dentro)
    assert dentro == {"condizioni": "Abitabile 10-30 anni"}


# --------------------------------------------------------------- taglio

def test_il_taglio_premia_il_piccolo_e_sconta_il_grande():
    assert coefficiente_taglio(100) == pytest.approx(1.0)
    assert coefficiente_taglio(50) == pytest.approx(1.1096, abs=0.001)
    assert coefficiente_taglio(200) == pytest.approx(0.9013, abs=0.001)


def test_il_taglio_e_continuo_e_non_a_fasce():
    assert abs(coefficiente_taglio(81) - coefficiente_taglio(79)) < 0.01


def test_elasticita_zero_spegne_il_taglio():
    assert coefficiente_taglio(50, elasticita=0) == 1.0


def test_senza_superficie_non_c_e_taglio_da_correggere():
    for niente in (None, 0, "", "abc", -10):
        assert coefficiente_taglio(niente) is None


def test_la_griglia_resta_quella_delle_tabelle_di_mercato():
    """Le voci che NON sono state accorpate coincidono con quelle
    pubblicate da idealista e RockAgent, ed e' il motivo per cui non si
    toccano."""
    assert FINITURE == {"Signorili": 1.05, "Civili": 1.0, "Economiche": 0.9}
    assert PIANO_CON_ASCENSORE["Attico"] == 1.2          # +20%, come loro
    assert PIANO_SENZA_ASCENSORE["Piani superiori"] == 0.7   # -30%
    assert STATO_UNITA["Nuova costruzione"] == 1.18
    assert STATO_UNITA["Da ristrutturare integralmente"] == 0.82
