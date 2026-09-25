"""Il business plan nel banco: le regole dei campi, le spese, il cantiere, l'MCA."""
import pytest

import banco
import storico
from server.vista_bp import vista_bp


@pytest.fixture
def b():
    b = banco.Banco()
    b.nuovo()
    return b


def test_scrivendo_l_importo_la_percentuale_torna_al_centesimo(b):
    """6.000 € su 145.000: la percentuale ha sei decimali, e l'importo
    rifatto è 6.000,00, non 6.000,10."""
    b.imposta_bp("bp_acquisto", 145000)
    b.imposta_bp("bp_ag_in_eur", 6000)
    assert b.dati["business_plan"]["bp_ag_in"] == pytest.approx(4.137931)
    assert b.euro_derivati()["bp_ag_in_eur"] == 6000.0


def test_gli_importi_derivati_non_finiscono_nel_file(b):
    b.imposta_bp("bp_acquisto", 100000)
    assert "bp_imposta_eur" not in b.dati["business_plan"]
    assert b.euro_derivati()["bp_imposta_eur"] == 9000.0


def test_gli_imprevisti_seguono_i_lavori(b):
    b.scrivi_quantita("2.1", 100)            # 100 m² a 35 €
    b.giro()
    assert b.dati["business_plan"]["bp_imprevisti"] == pytest.approx(
        b.totali()["totale"] * 0.10)


def test_gli_imprevisti_scritti_a_mano_restano_e_la_percentuale_si_adegua(b):
    b.scrivi_quantita("2.1", 100)
    b.giro()
    base = b.totali()["totale"]
    b.imposta_bp("bp_imprevisti", 700)
    b.giro()
    bp = b.dati["business_plan"]
    assert bp["bp_imprevisti"] == 700
    assert bp["bp_imprevisti_pct"] == pytest.approx(700 / base * 100)


def test_i_campi_stanno_nei_loro_confini(b):
    b.imposta_bp("bp_imposta", 99)
    b.imposta_bp("bp_durata", 0)
    b.imposta_bp("bp_passo", 10)
    bp = b.dati["business_plan"]
    assert (bp["bp_imposta"], bp["bp_durata"], bp["bp_passo"]) == (30.0, 1, 1000.0)


def test_un_campo_sconosciuto_non_passa(b):
    with pytest.raises(banco.ErroreBanco):
        b.imposta_bp("bp_inventato", 1)


def test_le_spese_si_normalizzano_come_nel_vecchio(b):
    b.scrivi_spese("spese", [
        {"importo": 1220, "aliquota_iva": 22, "categoria": "🟡 LAVORI"},
        {"importo": None, "oggetto": "riga vuota"}])
    assert b.dati["spese"] == [{
        "importo": 1220.0, "aliquota_iva": 22.0, "data": "", "nr_fattura": "",
        "fornitore": "", "oggetto": "", "categoria": "LAVORI", "note": ""}]
    v = vista_bp(b)["spese"]
    assert v["sostenute"][0]["iva_eur"] == pytest.approx(220.0)
    assert v["quota_cantiere"] == 1220.0


def test_i_costi_reali_del_cantiere_sostituiscono_la_stima(b):
    b.scrivi_spese("spese", [{"importo": 50000, "categoria": "LAVORI"}])
    b.imposta_bp("bp_usa_consuntivo", True)
    assert b.ristrutturazione() == (50000.0, True)
    assert b.base_imprevisti() == 0.0


def test_un_file_che_non_e_una_fattura_finisce_fra_i_non_letti(b):
    b.leggi_fatture([("scontrino.pdf", b"niente")])
    assert b.fatture_lette == {"righe": [], "non_letti": ["scontrino.pdf"]}


def test_il_cantiere_si_chiude_nello_storico(b):
    b.dati["progetto"]["nome"] = "Via Roma"
    b.imposta_cantiere("contratto", 100000)
    b.imposta_cantiere("extra", 8000)
    b.scrivi_sal([{"percento": 50, "pagato": True}, {"percento": 50}])
    stato = b.stato_cantiere()
    assert stato["pagato"] == 50000 and stato["totale_finale"] == 108000
    b.chiudi_operazione()
    assert storico.carica()[0]["nome"] == "Via Roma"
    storico.elimina("Via Roma")


def test_senza_contratto_non_si_chiude(b):
    with pytest.raises(banco.ErroreBanco):
        b.chiudi_operazione()


def test_l_mca_stima_e_manda_il_prezzo_allo_studio(b):
    b.imposta_bp("bp_mq", 100)
    b.scrivi_comparabili([
        {"nome": "C1", "prezzo": 250000, "mq": 100, "coeff": 1.0},
        {"nome": "C2", "prezzo": 270000, "mq": 100, "coeff": 1.0},
        {"nome": "", "prezzo": None}])
    b.imposta_bp("bp_coeff_sogg", 1.0)
    esito = vista_bp(b)["mca"]["esito"]
    assert esito["usati"] == 2
    assert esito["eur_mq_media"] == pytest.approx(2600, rel=0.01)
    b.usa_come_vendita(esito["valore"])
    assert b.dati["business_plan"]["bp_vendita"] == round(esito["valore"])


def test_il_soggetto_si_sceglie_dalle_tendine(b):
    b.scegli_soggetto("finiture", "Signorili")
    b.scegli_soggetto("giardino", "—")
    b.scegli_soggetto("ascensore", True)
    s = b.dati["mca_soggetto"]
    assert (s["finiture"], s["giardino"], s["ascensore"]) == \
        ("Signorili", None, True)


# ------------------------------------ i netti sono sempre la percentuale
# (dal programma vecchio: test_percentuali_business_plan e
# test_valori_forzati, che provavano le stesse regole sulla sua pagina)

@pytest.mark.parametrize("chiave, atteso", [
    ("bp_imposta_eur", 13050.0),          # 9% di 145.000
    # le provvigioni sono IMPONIBILI: l'IVA sta nella sua colonna
    ("bp_ag_in_eur", 5800.0),             # 4% di 145.000
    ("bp_ag_out_eur", 9000.0),            # 3% di 300.000
])
def test_il_netto_e_sempre_la_percentuale_del_suo_prezzo(b, chiave, atteso):
    """Nel file ci sono solo le percentuali: un netto non può restare
    storto, perché non c'è un netto da lasciare storto."""
    b.imposta_bp("bp_acquisto", 145000)
    b.imposta_bp("bp_vendita", 300000)
    b.imposta_bp("bp_ag_in", 4)
    b.imposta_bp("bp_ag_out", 3)
    assert b.euro_derivati()[chiave] == atteso


def test_cambiare_percentuale_o_prezzo_rifa_il_netto(b):
    b.imposta_bp("bp_acquisto", 145000)
    b.imposta_bp("bp_imposta", 4)
    assert b.euro_derivati()["bp_imposta_eur"] == 5800.0
    b.imposta_bp("bp_imposta", 9)
    b.imposta_bp("bp_acquisto", 200000)
    assert b.euro_derivati()["bp_imposta_eur"] == 18000.0


def test_scrivere_il_netto_a_mano_aggiusta_la_percentuale(b):
    b.imposta_bp("bp_acquisto", 145000)
    b.imposta_bp("bp_imposta_eur", 14500)
    assert b.dati["business_plan"]["bp_imposta"] == 10.0
    assert b.euro_derivati()["bp_imposta_eur"] == 14500.0


def test_senza_prezzo_il_netto_e_zero(b):
    b.imposta_bp("bp_imposta_eur", 5000)            # niente su cui ricavarlo
    assert b.dati["business_plan"]["bp_imposta"] == 9.0
    assert b.euro_derivati()["bp_imposta_eur"] == 0.0


def test_l_iva_delle_provvigioni_sta_a_parte(b):
    import fattibilita
    b.imposta_bp("bp_acquisto", 145000)
    netto = b.euro_derivati()["bp_ag_in_eur"]
    assert netto == 4350.0                           # 3% imponibile
    assert b.dati["business_plan"]["bp_iva_ag_in"] == 22.0
    assert fattibilita.iva_su(netto, 22.0) == 957.0


def test_un_progetto_nuovo_riporta_i_predefiniti(b):
    from costanti import IMPOSTAZIONI_BP
    b.imposta_bp("bp_durata", 30)
    b.imposta_bp("bp_iva_imprevisti", 22)
    b.nuovo()
    bp = b.dati["business_plan"]
    for chiave, valore in IMPOSTAZIONI_BP.items():
        assert bp[chiave] == valore, chiave
    # una riserva non è una fattura: niente IVA da scorporare
    assert bp["bp_iva_imprevisti"] == 0.0


def test_cambiare_l_aliquota_iva_muove_il_totale(b):
    b.scrivi_quantita("2.1", 100)
    imponibile = b.totali()["totale"]
    b.imposta_progetto("aliquota_iva", 22)
    t = b.totali()
    assert t["iva"] == pytest.approx(imponibile * 0.22)
    assert t["totale_con_iva"] == pytest.approx(imponibile * 1.22)
