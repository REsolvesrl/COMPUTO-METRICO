"""I progetti salvati coi numeri di prima del 25/09/2026 si riaprono uguali.

Il listino è stato rifatto dalle voci di ENI e Migliarina e rinumerato:
il 3.10 di ieri (posa pavimenti) oggi è il 3.4, e il 3.10 di oggi è la
demolizione e posa dei balconi. Un file di prima si traduce all'apertura,
e tradurlo non deve cambiare niente di quello che mostrava: quantità,
prezzi, testi, unità, ordine, scarti.
"""
import copy

import banco
import listino
import listino_di_prima
import rinumerazione

PRIMA = {v["codice"]: v for v in listino_di_prima.VOCI}


def _aperto(dati):
    b = banco.Banco()
    b.carica(copy.deepcopy(dati))
    return b


def test_un_file_gia_tradotto_non_si_traduce_due_volte():
    dati = {"listino": listino.VERSIONE, "voci_scelte": ["3.10"],
            "listino_stato": {"3.10": {"q": 5.0, "p": 250.0}}}
    assert rinumerazione.traduci(dati) is dati
    b = _aperto(dati)
    assert b.quantita("3.10") == 5.0
    assert b.dati["listino"] == listino.VERSIONE      # e si salva così


def test_la_voce_del_listino_di_prima_tiene_prezzo_e_testo_che_aveva():
    """La 3.10 di prima non era riscritta: valeva il prezzo e il testo del
    listino di allora, e li deve valere ancora — nella voce nuova."""
    b = _aperto({"voci_scelte": ["3.10"],
                 "listino_stato": {"3.10": {"q": 40.0,
                                            "p": PRIMA["3.10"]["prezzo"]}}})
    nuovo = rinumerazione.NUOVO_CODICE["3.10"]
    assert b.scelte() == [nuovo]
    assert b.quantita(nuovo) == 40.0
    assert b.prezzo(nuovo) == PRIMA["3.10"]["prezzo"]
    assert b.testi(nuovo) == (PRIMA["3.10"]["descrizione"], PRIMA["3.10"]["um"])
    assert b.totali()["totale"] == 40.0 * PRIMA["3.10"]["prezzo"]


def test_la_voce_tua_entrata_nel_listino_si_riconosce_dalla_descrizione():
    b = _aperto({"voci": [{"categoria": "Demolizioni", "codice": "2.11",
                           "descrizione": "Allestimento cantiere",
                           "um": "a corpo", "quantita_manuale": 1,
                           "prezzo": 3000}],
                 "voci_scelte": ["2.11"]})
    assert b.dati["voci"] == []
    assert b.scelte() == ["2.4"]
    assert (b.quantita("2.4"), b.prezzo("2.4")) == (1.0, 3000.0)
    assert not b.e_tua("2.4")


def test_le_due_3_29_diventano_due_voci():
    """Stesso codice, voci diverse: la scala di ENI e gli scalini di
    Migliarina."""
    scala = rinumerazione.traduci({"voci": [{
        "categoria": "Ricostruzioni e ripristini", "codice": "3.29",
        "descrizione": "Costruzione scala interna PT-1° piano",
        "um": "a corpo", "quantita_manuale": 1, "prezzo": 10000}],
        "voci_scelte": ["3.29"]})
    scalini = rinumerazione.traduci({"voci": [{
        "categoria": "Ricostruzioni e ripristini", "codice": "3.29",
        "descrizione": "Ripristino scalini con sostituzione supporto in "
                       "legno ammalorato, fissaggio marmo e applicazione "
                       "resina riparativa",
        "um": "a corpo", "quantita_manuale": 0, "prezzo": 0}],
        "voci_scelte": ["3.29"]})
    assert scala["voci"] == scalini["voci"] == []    # tutte e due nel listino
    assert scala["voci_scelte"] != scalini["voci_scelte"]
    assert listino.voce_per_codice(scala["voci_scelte"][0])["descrizione"] \
        == "Costruzione scala interna PT-1° piano"
    assert listino.voce_per_codice(scalini["voci_scelte"][0])["descrizione"] \
        .startswith("Ripristino scalini")


def test_la_posa_terrazza_vuota_sparisce_nella_posa_esterna():
    posa = rinumerazione.NUOVO_CODICE["3.11"]
    terrazza = {"categoria": "Ricostruzioni e ripristini", "codice": "3.25",
                "descrizione": "Posa pavimentazione terrazza con spessoratura"
                               " e stuccatura finale compreso colle, stucchi.",
                "um": "m²", "quantita_manuale": 0, "prezzo": 48}
    # nel pool e vuota, con la 3.11 nel computo: era un doppione
    dati = rinumerazione.traduci({"voci": [terrazza], "voci_scelte": ["3.11"],
                                  "voci_scartate": ["3.25"]})
    assert dati["voci"] == [] and dati["voci_scartate"] == []
    assert dati["voci_scelte"] == [posa]
    # nel computo con dei metri, da sola: diventa la posa esterna
    dati = rinumerazione.traduci({"voci": [dict(terrazza, quantita_manuale=12)],
                                  "voci_scelte": ["3.25"]})
    assert dati["voci_scelte"] == [posa]
    assert dati["listino_stato"][posa]["q"] == 12


def test_una_voce_tua_sconosciuta_prende_un_codice_libero():
    """Il suo codice di prima ora è di una voce del listino: ne prende uno
    libero, e il computo, gli scarti e le quantità scritte a mano la
    seguono."""
    riga = {"categoria": "Demolizioni", "codice": "2.12",
            "descrizione": "Rimozione caldaia", "um": "cad",
            "quantita_manuale": 2, "prezzo": 150}
    b = _aperto({"voci": [riga], "voci_scelte": ["2.12"],
                 "voci_a_mano": ["2.12"]})
    [tua] = b.dati["voci"]
    assert tua["codice"] not in {v["codice"] for v in listino.VOCI}
    assert b.scelte() == [tua["codice"]] and b.e_tua(tua["codice"])
    assert b.dati["voci_a_mano"] == [tua["codice"]]
    assert b.totali()["totale"] == 300


def test_scarti_scritte_a_mano_e_ordine_si_traducono():
    b = _aperto({"voci_scelte": ["3.19", "2.1", "3.10"],
                 "voci_scartate": ["2.10"], "voci_a_mano": ["3.19"],
                 "listino_stato": {"3.19": {"q": 300.0, "p": 12.0}}})
    n = rinumerazione.NUOVO_CODICE
    assert b.dati["voci_scelte"] == [n["3.19"], n["2.1"], n["3.10"]]
    assert b.dati["voci_scartate"] == [n["2.10"]]
    assert b.dati["voci_a_mano"] == [n["3.19"]]
    assert b.quantita(n["3.19"]) == 300.0


def test_ogni_voce_di_prima_ha_il_suo_posto():
    nuovi = list(rinumerazione.NUOVO_CODICE.values())
    assert set(rinumerazione.NUOVO_CODICE) == set(PRIMA)
    assert len(nuovi) == len(set(nuovi))
    for vecchio, nuovo in rinumerazione.NUOVO_CODICE.items():
        assert listino.voce_per_codice(nuovo)["categoria"] == \
            PRIMA[vecchio]["categoria"], vecchio
