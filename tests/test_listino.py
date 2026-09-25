import listino


def test_categorie_attese():
    assert listino.CATEGORIE == [
        "Pratiche e oneri",
        "Demolizioni",
        "Ricostruzioni e ripristini",
        "Idraulico",
        "Elettricista",
        "Serramenti",
        "Aree esterne",
        "Tetto",
        "Facciata",
    ]


def test_tetto_e_facciata_sono_facoltativi_e_in_coda():
    """In coda: sono lavori che non tutti i cantieri hanno."""
    assert listino.CATEGORIE_FACOLTATIVE == ["Tetto", "Facciata"]
    assert listino.CATEGORIE[-2:] == listino.CATEGORIE_FACOLTATIVE
    assert listino.voce_per_codice("8.1")["categoria"] == "Tetto"
    assert listino.voce_per_codice("9.1")["categoria"] == "Facciata"


def test_ogni_voce_e_completa():
    for voce in listino.VOCI:
        assert voce["codice"], voce
        assert voce["descrizione"], voce
        assert voce["categoria"] in listino.CATEGORIE, voce
        # «ml» e non «m»: il battiscopa e le velette si misurano a metri
        # LINEARI, ed e' la sigla che si legge su un computo vero.
        assert voce["um"] in {"ml", "m²", "m³", "kg", "t", "cad", "h",
                              "a corpo", "punto", "punto luce",
                              "punto acqua", "utenza"}, voce
        # Un prezzo a zero è ammesso solo se la nota dice perché: due voci
        # del tetto di ENI non l'avevano, e inventarlo sarebbe peggio.
        assert voce["prezzo"] > 0 or "prezzo non c'era" in voce.get(
            "nota", ""), voce


def test_codici_unici():
    codici = [v["codice"] for v in listino.VOCI]
    assert len(codici) == len(set(codici))


def test_tutte_le_categorie_hanno_voci():
    for categoria in listino.CATEGORIE:
        assert listino.voci_della_categoria(categoria), categoria


def test_dimensione_listino():
    assert len(listino.VOCI) >= 45


def test_prezzi_chiave_del_listino():
    """Il listino nuovo (25/09/2026): testi dei cantieri, il prezzo più alto
    fra ENI e Migliarina, le generiche in coda coi loro prezzi."""
    per_codice = {v["codice"]: v for v in listino.VOCI}
    assert per_codice["2.1"]["prezzo"] == 25.0       # demolizione pavimento
    assert per_codice["2.4"]["prezzo"] == 5000.0     # allestimento (ENI)
    assert per_codice["2.5"]["prezzo"] == 1500.0     # bagno (Migliarina)
    assert per_codice["1.3"]["prezzo"] == 450.0      # DOCFA: non i 60.000
    assert per_codice["3.10"]["prezzo"] == 250.0     # balconi, demolendo
    assert per_codice["4.1"]["um"] == "punto acqua"
    assert per_codice["6.9"]["prezzo"] == 1450.0     # porta blindata, generica


def test_prima_le_voci_dei_cantieri_poi_le_generiche():
    """In ogni categoria le nostre in testa, e le generiche in coda."""
    for categoria in listino.CATEGORIE:
        nostre = [bool(v.get("cantieri"))
                  for v in listino.voci_della_categoria(categoria)]
        assert nostre == sorted(nostre, reverse=True), categoria
    assert len([v for v in listino.VOCI if v.get("cantieri")]) == 84


def test_i_codici_seguono_l_ordine_senza_buchi():
    for categoria in listino.CATEGORIE:
        serie = listino.CATEGORIE.index(categoria) + 1
        codici = [v["codice"] for v in listino.voci_della_categoria(categoria)]
        assert codici == [f"{serie}.{n}" for n in range(1, len(codici) + 1)]


def test_voci_della_categoria_filtra():
    demolizioni = listino.voci_della_categoria("Demolizioni")
    assert all(v["categoria"] == "Demolizioni" for v in demolizioni)
    assert len(demolizioni) == 17
