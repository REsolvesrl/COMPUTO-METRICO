import listino


def test_categorie_attese():
    assert listino.CATEGORIE == [
        "Demolizioni",
        "Ricostruzioni e ripristini",
        "Idraulico",
        "Elettricista",
        "Serramenti",
        "Aree esterne",
    ]


def test_ogni_voce_e_completa():
    for voce in listino.VOCI:
        assert voce["codice"], voce
        assert voce["descrizione"], voce
        assert voce["categoria"] in listino.CATEGORIE, voce
        assert voce["um"] in {"m", "m²", "m³", "kg", "t", "cad", "h",
                              "a corpo", "punto", "utenza"}, voce
        assert voce["prezzo"] > 0, voce


def test_codici_unici():
    codici = [v["codice"] for v in listino.VOCI]
    assert len(codici) == len(set(codici))


def test_tutte_le_categorie_hanno_voci():
    for categoria in listino.CATEGORIE:
        assert listino.voci_della_categoria(categoria), categoria


def test_dimensione_listino():
    assert len(listino.VOCI) >= 45


def test_prezzi_chiave_del_listino():
    """Prezzi di riferimento presi dal computo d'esempio."""
    per_codice = {v["codice"]: v for v in listino.VOCI}
    assert per_codice["1.01"]["prezzo"] == 100.0      # demolizione pavimenti
    assert per_codice["4.02"]["prezzo"] == 73.0       # punto elettrico
    assert per_codice["5.01"]["prezzo"] == 450.0      # serramenti al m²
    assert per_codice["5.04"]["prezzo"] == 1450.0     # porta blindata
    assert per_codice["3.01"]["um"] == "utenza"


def test_voci_della_categoria_filtra():
    demolizioni = listino.voci_della_categoria("Demolizioni")
    assert all(v["categoria"] == "Demolizioni" for v in demolizioni)
    assert len(demolizioni) == 10
