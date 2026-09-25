"""Il computo nel banco: il pool, le voci tue, gli scarti, l'ordine, i lavori
facoltativi, il modello di un progetto nuovo.

Queste regole le provavano i test del programma vecchio (Streamlit) facendo
i gesti sulla sua pagina — test_voci_scelte, test_lavori_facoltativi,
test_modello_computo, test_progetti_indipendenti. Col vecchio se ne sono
andati; le regole restano, e qui si provano sul banco, che è dove vivono
adesso. Gli stessi casi, gli stessi numeri.
"""
import json

import pytest

import archivio_locale
import banco
import listino
import modello_computo
from server.vista import computo

NON_FACOLTATIVE = [v["codice"] for v in listino.VOCI
                   if v["categoria"] not in listino.CATEGORIE_FACOLTATIVE]
VOCI_TETTO = [v["codice"] for v in listino.voci_della_categoria("Tetto")]


def _pool(b):
    return [v["codice"] for cat in computo(b)["pool"] for v in cat["voci"]]


def _riaperto(b):
    """Salvato e riaperto, come chi chiude e torna domani."""
    nome = b.salva()
    nuovo = banco.Banco()
    nuovo.apri(nome)
    return nuovo


@pytest.fixture
def b():
    return banco.Banco()


# ------------------------------------------------- il computo nasce vuoto

def test_il_computo_nasce_senza_voci(b):
    assert b.dati["voci_scelte"] == []
    assert b.totali()["totale"] == 0


def test_il_pool_offre_tutte_le_voci_tranne_tetto_e_facciata(b):
    assert sorted(_pool(b)) == sorted(NON_FACOLTATIVE)


# --------------------------------------------------- prendere e rimettere

def test_una_voce_presa_e_nel_computo_e_non_piu_nel_pool(b):
    b.porta_nel_computo("2.2")
    assert b.dati["voci_scelte"] == ["2.2"]
    assert "2.2" not in _pool(b)


def test_prendere_tutto_porta_il_listino_ma_non_tocca_le_decisioni(b):
    b.porta_nel_computo("2.2")
    b.scarta("2.3")
    b.prendi_tutte()
    assert "2.3" not in b.dati["voci_scelte"]
    assert set(b.dati["voci_scelte"]) == set(NON_FACOLTATIVE) - {"2.3"}
    assert b.dati["voci_scelte"].count("2.2") == 1


def test_togliere_una_voce_non_ne_cancella_la_quantita(b):
    b.porta_nel_computo("2.2")
    b.scrivi_quantita("2.2", 10)
    b.togli_dal_computo("2.2")
    assert b.totali()["totale"] == 0             # contano solo le scelte
    b.porta_nel_computo("2.2")
    assert b.quantita("2.2") == 10


def test_la_descrizione_riscritta_vale_e_vuota_torna_al_listino(b):
    b.porta_nel_computo("2.2")
    b.scrivi_descrizione("2.2", "Demolizione tramezze del bagno")
    assert b.testi("2.2")[0] == "Demolizione tramezze del bagno"
    assert _riaperto(b).testi("2.2")[0] == "Demolizione tramezze del bagno"
    b.scrivi_descrizione("2.2", "")
    assert b.testi("2.2")[0] == listino.voce_per_codice("2.2")["descrizione"]
    assert "2.2" not in b.dati["testi_voci"]     # niente chiavi vuote


# ------------------------------------------------- i progetti di prima

PROGETTO_VECCHIO = {
    "progetto": {"nome": "Via Roma 12", "data": "2026-08-09"},
    "voci": [],
    "listino_stato": {"2.2": {"q": 120.0, "p": 115.0},
                      "3.1": {"q": 30.0, "p": 80.0},
                      "3.10": {"q": 0.0, "p": 60.0},
                      "9.99": {"q": 5.0, "p": 10.0}},     # sparita
}


def test_un_progetto_senza_elenco_riapre_le_voci_con_una_quantita(b):
    b.carica(json.loads(json.dumps(PROGETTO_VECCHIO)))
    assert b.dati["voci_scelte"] == ["2.2", "3.1"]
    assert b.totali()["totale"] == 120 * 115 + 30 * 80


def test_le_voci_libere_di_prima_diventano_voci_del_computo(b):
    b.carica({"voci": [{"categoria": "Idraulico", "descrizione": "Pompa",
                        "um": "cad", "quantita_manuale": 2,
                        "prezzo": 150}]})
    codice = b.dati["voci"][0]["codice"]
    assert codice.startswith("4.") and listino.voce_per_codice(codice) is None
    assert codice in b.scelte() and b.totali()["totale"] == 300


# ------------------------------------------------------ le voci tue

def test_la_voce_tua_nasce_nel_computo_col_codice_della_serie(b):
    codice = b.crea_voce_a_mano("Idraulico", "Pompa di sollevamento", "cad",
                                2, 450)
    assert codice.startswith("4.") and listino.voce_per_codice(codice) is None
    assert codice in b.dati["voci_scelte"] and codice not in _pool(b)
    assert b.totali()["totale"] == 900


def test_una_voce_senza_descrizione_non_si_crea(b):
    with pytest.raises(banco.ErroreBanco):
        b.crea_voce_a_mano("Idraulico", "  ", "cad", 1, 10)


def test_a_corpo_propone_uno_senza_chiederlo(b):
    codice = b.crea_voce_a_mano("Demolizioni", "Allestimento cantiere",
                                banco.UM_A_CORPO, 0, 2500)
    assert b.quantita(codice) == 1


def test_a_corpo_nel_computo_propone_uno_solo_se_manca(b):
    b.porta_nel_computo("2.2")
    b.scrivi_unita("2.2", banco.UM_A_CORPO)
    assert b.quantita("2.2") == 1
    b.scrivi_quantita("2.2", 3)
    b.scrivi_unita("2.2", banco.UM_A_CORPO)
    assert b.quantita("2.2") == 3


def test_la_voce_tua_tolta_torna_nel_pool_e_si_ritrova_com_era(b):
    codice = b.crea_voce_a_mano("Idraulico", "Pompa", "cad", 2, 450)
    b.togli_dal_computo(codice)
    assert codice in _pool(b)
    b.porta_nel_computo(codice)
    assert (b.quantita(codice), b.prezzo(codice)) == (2, 450)


def test_quantita_e_prezzo_di_una_voce_tua_si_modificano(b):
    codice = b.crea_voce_a_mano("Idraulico", "Pompa", "cad", 2, 450)
    b.scrivi_quantita(codice, 3)
    b.scrivi_prezzo(codice, 500)
    assert b.totali()["totale"] == 1500


# ------------------------------------------------------------ gli scarti

def test_scartare_toglie_dal_pool_e_non_tocca_il_listino(b):
    b.scarta("2.3")
    assert "2.3" not in _pool(b)
    assert listino.voce_per_codice("2.3") is not None


def test_si_scarta_anche_una_voce_tua_e_riaprendo_resta_da_parte(b):
    codice = b.crea_voce_a_mano("Idraulico", "Pompa", "cad", 2, 450)
    b.scarta(codice)
    riaperto = _riaperto(b)
    assert codice not in riaperto.dati["voci_scelte"]
    assert codice in riaperto.dati["voci_scartate"]
    assert codice not in _pool(riaperto)


def test_gli_scarti_si_rimettono_tutti_insieme(b):
    b.scarta("2.3")
    b.scarta("2.4")
    b.ripristina_scarti()
    assert {"2.3", "2.4"} <= set(_pool(b))


def test_riprendere_una_voce_scartata_la_toglie_dagli_scarti(b):
    b.scarta("2.3")
    b.porta_nel_computo("2.3")
    assert "2.3" not in b.dati["voci_scartate"]


# ------------------------------------------- spostare e mettere in ordine

def test_una_voce_tua_cambia_categoria_e_codice_con_quantita_e_prezzo(b):
    b.porta_nel_computo("4.1")
    codice = b.crea_voce_a_mano("Idraulico", "Pompa", "cad", 2, 450)
    b.porta_nel_computo("4.2")
    nuovo = b.sposta_voce_tua(codice, "Elettricista")
    assert nuovo.startswith("5.") and codice not in b.dati["voci_scelte"]
    assert (b.quantita(nuovo), b.prezzo(nuovo)) == (2, 450)
    assert b.dati["voci_scelte"] == ["4.1", nuovo, "4.2"]


def test_le_voci_del_listino_non_cambiano_categoria(b):
    b.porta_nel_computo("4.1")
    assert b.sposta_voce_tua("4.1", "Elettricista") == "4.1"
    assert b.voce("4.1")["categoria"] == "Idraulico"


def test_l_ordine_si_muove_solo_fra_le_vicine_e_si_salva(b):
    for codice in ("2.2", "4.1", "2.3", "2.4"):
        b.porta_nel_computo(codice)
    b.scambia_con_vicina("2.3", -1)
    assert b.dati["voci_scelte"] == ["2.3", "4.1", "2.2", "2.4"]
    b.scambia_con_vicina("2.3", -1)              # la prima non scappa
    b.scambia_con_vicina("2.4", +1)              # l'ultima nemmeno
    assert b.dati["voci_scelte"] == ["2.3", "4.1", "2.2", "2.4"]
    assert _riaperto(b).dati["voci_scelte"] == ["2.3", "4.1", "2.2", "2.4"]


# --------------------------------------------------- lavori facoltativi

def test_in_un_progetto_nuovo_tetto_e_facciata_sono_spenti(b):
    b.nuovo()
    assert b.dati["lavori_facoltativi"] == []
    nomi = b.categorie_del_computo()
    assert "Demolizioni" in nomi
    assert "Tetto" not in nomi and "Facciata" not in nomi
    assert not any(c.startswith(("8.", "9.")) for c in _pool(b))


def test_accendere_il_tetto_porta_le_sue_voci_tranne_le_scartate(b):
    b.scarta("8.6")
    b.cambia_lavoro_facoltativo("Tetto", True)
    assert b.dati["lavori_facoltativi"] == ["Tetto"]
    assert b.dati["voci_scelte"] == [c for c in VOCI_TETTO if c != "8.6"]
    assert "Tetto" in b.categorie_del_computo()
    assert "Facciata" not in b.categorie_del_computo()


def test_accendere_una_categoria_che_ha_gia_voci_non_ne_aggiunge(b):
    b.dati["voci_scelte"] = ["8.3"]
    b.cambia_lavoro_facoltativo("Tetto", True)
    assert b.dati["voci_scelte"] == ["8.3"]


def test_spenta_non_conta_e_riaccesa_si_ritrova_uguale(b):
    b.cambia_lavoro_facoltativo("Facciata", True)
    b.scrivi_quantita("9.8", 100)
    b.scrivi_prezzo("9.8", 18)
    assert b.totali()["totale"] == 1800
    b.cambia_lavoro_facoltativo("Facciata", False)
    assert b.totali()["totale"] == 0
    assert "9.8" in b.dati["voci_scelte"] and b.quantita("9.8") == 100
    b.cambia_lavoro_facoltativo("Facciata", True)
    assert b.totali()["totale"] == 1800
    assert b.dati["voci_scelte"].count("9.8") == 1


def test_una_voce_tua_nel_tetto_si_spegne_col_tetto(b):
    b.cambia_lavoro_facoltativo("Tetto", True)
    b.crea_voce_a_mano("Tetto", "Lucernario", "cad", 1, 900)
    totale_acceso = b.totali()["totale"]
    b.cambia_lavoro_facoltativo("Tetto", False)
    assert totale_acceso >= 900 and b.totali()["totale"] == 0


def test_il_numero_della_facciata_resta_nove_col_tetto_spento(b):
    b.cambia_lavoro_facoltativo("Facciata", True)
    righe = [r["nome"] for r in computo(b)["riepilogo"]["righe"]]
    assert "9. Facciata" in righe


def test_i_lavori_facoltativi_si_salvano_e_tornano(b):
    b.dati["progetto"]["nome"] = "Con facciata"
    b.cambia_lavoro_facoltativo("Facciata", True)
    b.scrivi_quantita("9.8", 100)
    riaperto = _riaperto(b)
    assert riaperto.dati["lavori_facoltativi"] == ["Facciata"]
    assert riaperto.totali()["totale"] == 2200


def test_un_progetto_di_prima_o_sconosciuto_li_apre_spenti(b):
    b.cambia_lavoro_facoltativo("Tetto", True)
    b.carica({"voci_scelte": ["2.2"], "listino_stato": {"2.2": {"q": 10.0}}})
    assert b.dati["lavori_facoltativi"] == []
    b.carica({"lavori_facoltativi": ["Piscina"]})
    assert b.dati["lavori_facoltativi"] == []


def test_una_categoria_non_facoltativa_non_si_accende(b):
    with pytest.raises(banco.ErroreBanco):
        b.cambia_lavoro_facoltativo("Idraulico", True)


# ------------------------------------------ il modello di un progetto nuovo

def test_il_banco_appena_acceso_non_carica_il_modello(b):
    assert b.dati["voci_scelte"] == [] and b.dati["voci"] == []


def test_il_progetto_nuovo_porta_le_voci_dei_nostri_cantieri(b):
    """Tutte quelle che vengono da ENI o da Migliarina, coi testi e i prezzi
    del listino: niente voci tue, niente riscritture."""
    b.nuovo()
    nostre = [v["codice"] for v in listino.VOCI if v.get("cantieri")]
    assert b.dati["voci_scelte"] == nostre == modello_computo.VOCI_SCELTE
    assert b.dati["voci"] == [] and b.dati["testi_voci"] == {}
    for codice in nostre:
        assert b.prezzo(codice) == listino.voce_per_codice(codice)["prezzo"]
    assert b.dati["lavori_facoltativi"] == []       # tetto e facciata spenti


def test_le_voci_generiche_restano_nel_pool(b):
    b.nuovo()
    generiche = [v["codice"] for v in listino.VOCI if not v.get("cantieri")
                 and v["categoria"] not in listino.CATEGORIE_FACOLTATIVE]
    assert generiche and set(generiche) == set(_pool(b))


def test_il_computo_nuovo_non_vale_niente_finche_non_lo_quantifichi(b):
    b.nuovo()
    assert all(b.quantita(c) == 0 for c in b.dati["voci_scelte"])
    assert b.totali()["totale"] == 0


def test_ogni_progetto_nuovo_ha_la_sua_copia(b):
    b.nuovo()
    b.scrivi_quantita("2.1", 50)
    b.scrivi_descrizione("2.1", "Toccata")
    altro = banco.Banco()
    altro.nuovo()
    assert altro.quantita("2.1") == 0
    assert altro.testi("2.1")[0] == listino.voce_per_codice("2.1")["descrizione"]


# ---------------------------------------------- un progetto alla volta

def test_aprire_un_altro_progetto_non_lascia_tracce(b):
    b.nuovo()
    b.scrivi_quantita("2.1", 50)
    b.scrivi_prezzo("2.1", 99)
    b.scrivi_descrizione("2.2", "Riscritta")
    b.cambia_lavoro_facoltativo("Tetto", True)
    b.imposta_bp("bp_acquisto", 150000)
    b.carica({"progetto": {"nome": "Altro"}, "voci_scelte": ["2.1"],
              "listino": listino.VERSIONE})
    assert b.quantita("2.1") == 0
    assert b.prezzo("2.1") == listino.voce_per_codice("2.1")["prezzo"]
    assert b.testi("2.2")[0] == listino.voce_per_codice("2.2")["descrizione"]
    assert b.dati["lavori_facoltativi"] == []
    assert b.dati["business_plan"]["bp_acquisto"] == 0


def test_un_progetto_rovinato_non_si_carica_a_meta(b):
    b.dati["progetto"]["nome"] = "Buono"
    b.porta_nel_computo("2.2")
    b.scrivi_quantita("2.2", 10)
    b.salva()
    cartella = archivio_locale.cartella()
    (cartella / "Rovinato.json").write_text("{ non è json", encoding="utf-8")
    with pytest.raises(banco.ErroreBanco):
        b.apri("Rovinato")
    assert b.dati["progetto"]["nome"] == "Buono" and b.quantita("2.2") == 10


# --------------------------------------------------------- i materiali

def test_l_elenco_dei_materiali_svuotato_resta_svuotato(b):
    b.carica({"progetto": {"nome": "Senza materiali"}, "materiali": []})
    assert _riaperto(b).dati["materiali"] == []
