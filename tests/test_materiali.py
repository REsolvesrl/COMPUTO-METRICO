"""L'elenco dei materiali a cura del committente.

Le regole che qui si controllano vengono da un foglio vero — l'ALLEGATO 1
firmato con l'impresa — e non sono formali: un prezzo mancante che diventa
zero fa sembrare gratis quello che non è ancora stato quotato, e un totale
che non dichiara di essere parziale è un totale che mente verso il basso,
proprio finché mancano i pezzi più cari.
"""
import materiali


ELENCO = [
    {"capitolo": "BAGNO", "descrizione": "PIATTO DOCCIA", "um": "cad",
     "quantita": 1.0, "prezzo": 320.0, "stato": "Ordinato", "note": ""},
    {"capitolo": "BAGNO", "descrizione": "BOX DOCCIA", "um": "cad",
     "quantita": None, "prezzo": None, "stato": "Da ordinare", "note": ""},
    {"capitolo": "PAVIMENTI", "descrizione": "PAVIMENTO/RIVESTIMENTO GRES",
     "um": "m²", "quantita": 94.71, "prezzo": 22.0, "stato": "Consegnato",
     "note": ""},
    {"capitolo": "IMPIANTO RISCALDAMENTO",
     "descrizione": "UNITÀ INTERNA + ESTERNA CLIMA CANALIZZATO", "um": "cad",
     "quantita": 1.0, "prezzo": 2400.0, "stato": "Da ordinare",
     "note": "Si fornisce inoltre: plenum coibentato, collarini."},
]


# ------------------------------------------------------------- il calcolo

def test_importo_e_quantita_per_prezzo():
    riga = materiali.calcola_riga(
        {"descrizione": "GRES", "quantita": 94.71, "prezzo": 22.0})
    assert riga["importo"] == 2083.62


def test_la_quantita_che_manca_vale_uno():
    """«BOX DOCCIA 450 €» ha gia' detto tutto: il box doccia e' uno."""
    riga = materiali.calcola_riga(
        {"descrizione": "BOX DOCCIA", "quantita": None, "prezzo": 450.0})
    assert riga["importo"] == 450.0
    # ma la quantita' resta VUOTA: l'1 e' una convenzione di calcolo, non
    # una misura presa, e sull'allegato non va stampato
    assert riga["quantita"] is None


def test_senza_prezzo_l_importo_e_None_non_zero():
    """Uno zero direbbe «gratis» e finirebbe nel totale."""
    riga = materiali.calcola_riga(
        {"descrizione": "BOX DOCCIA", "quantita": 1.0, "prezzo": None})
    assert riga["importo"] is None


def test_totale_somma_solo_quello_che_ha_un_prezzo():
    calcolate = materiali.calcola_elenco(ELENCO)
    assert materiali.totale(calcolate) == 320.0 + 2083.62 + 2400.0


def test_da_quotare_conta_le_righe_senza_prezzo():
    calcolate = materiali.calcola_elenco(ELENCO)
    assert materiali.da_quotare(calcolate) == 1


def test_totale_di_un_elenco_vuoto_e_zero():
    assert materiali.totale([]) == 0.0
    assert materiali.da_quotare([]) == 0


# ---------------------------------------------------------- le aggregazioni

def test_totali_per_capitolo_seguono_l_ordine_dei_capitoli():
    """L'ordine e' quello del foglio, non quello di comparsa."""
    totali = materiali.totali_per_capitolo(materiali.calcola_elenco(ELENCO))
    assert list(totali) == ["BAGNO", "PAVIMENTI", "IMPIANTO RISCALDAMENTO"]


def test_un_capitolo_senza_prezzi_esiste_lo_stesso():
    """Tre cose e nessun prezzo sono un capitolo, non il nulla."""
    totali = materiali.totali_per_capitolo(materiali.calcola_elenco([
        {"capitolo": "CUCINA", "descrizione": "CUCINA SU MISURA",
         "prezzo": None, "quantita": None},
    ]))
    assert totali["CUCINA"] == {"importo": 0.0, "voci": 1, "da_quotare": 1}


def test_capitolo_mancante_finisce_in_altro():
    totali = materiali.totali_per_capitolo(materiali.calcola_elenco([
        {"descrizione": "ROBA VARIA", "prezzo": 100.0},
    ]))
    assert list(totali) == [materiali.CAPITOLO_PREDEFINITO]


def test_un_capitolo_inventato_va_in_coda():
    """Un progetto vecchio puo' portare un capitolo che non e' in elenco."""
    totali = materiali.totali_per_capitolo(materiali.calcola_elenco([
        {"capitolo": "GIARDINO ZEN", "descrizione": "GHIAIA", "prezzo": 50.0},
        {"capitolo": "BAGNO", "descrizione": "LAVABO", "prezzo": 200.0},
    ]))
    assert list(totali) == ["BAGNO", "GIARDINO ZEN"]


def test_totali_per_stato_dicono_a_che_punto_e_la_spesa():
    per_stato = materiali.totali_per_stato(materiali.calcola_elenco(ELENCO))
    assert per_stato["Da ordinare"]["importo"] == 2400.0
    assert per_stato["Da ordinare"]["voci"] == 2       # il box doccia c'e'
    assert per_stato["Da ordinare"]["da_quotare"] == 1
    assert per_stato["Ordinato"]["importo"] == 320.0
    assert per_stato["Consegnato"]["importo"] == 2083.62


def test_stato_mancante_e_da_ordinare():
    per_stato = materiali.totali_per_stato(materiali.calcola_elenco([
        {"descrizione": "PORTE", "prezzo": 280.0},
    ]))
    assert list(per_stato) == [materiali.STATO_PREDEFINITO]


# ------------------------------------------------- raggruppamento e note

def test_raggruppa_per_capitolo_tiene_le_righe_nel_loro_ordine():
    gruppi = materiali.raggruppa_per_capitolo(ELENCO)
    assert list(gruppi) == ["BAGNO", "PAVIMENTI", "IMPIANTO RISCALDAMENTO"]
    assert [r["descrizione"] for r in gruppi["BAGNO"]] == [
        "PIATTO DOCCIA", "BOX DOCCIA"]


def test_note_numerate_con_gli_asterischi():
    """Uno, due, tre asterischi nell'ordine in cui le note compaiono."""
    note = materiali.note_numerate([
        {"descrizione": "A", "note": "prima"},
        {"descrizione": "B", "note": ""},
        {"descrizione": "C", "note": "seconda"},
    ])
    assert [n["marcatore"] for n in note] == ["*", "**"]
    assert note[0]["riga"]["descrizione"] == "A"
    assert note[1]["testo"] == "seconda"


def test_senza_note_non_c_e_nessun_marcatore():
    assert materiali.note_numerate(
        [{"descrizione": "A", "note": "   "}]) == []


# --------------------------------------------------------- i capitoli veri

def test_i_capitoli_del_foglio_firmato_ci_sono_tutti():
    """Vengono dall'allegato reale del cantiere di Migliarina, in quell'ordine."""
    assert materiali.CAPITOLI[:6] == [
        "BAGNO", "PORTE E INFISSI", "IMPIANTO ELETTRICO", "MURATURA",
        "PAVIMENTI", "IMPIANTO RISCALDAMENTO"]
