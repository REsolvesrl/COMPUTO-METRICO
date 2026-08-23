"""L'elenco dei materiali a cura del committente.

Le regole che qui si controllano vengono da un foglio vero — l'ALLEGATO 1
firmato con l'impresa — e la prima è la più facile da disfare per distrazione:
**qui dentro non ci sono soldi**. Il foglio elenca forniture, non importi, e
i prezzi dei materiali vivono nel registro delle spese, dove arrivano dalle
fatture. Una colonna di euro rimessa qui vorrebbe dire due numeri per la
stessa cosa, e prima o poi due numeri diversi.
"""
import materiali


ELENCO = [
    {"capitolo": "BAGNO", "descrizione": "PIATTO DOCCIA", "um": "cad",
     "quantita": 1.0, "stato": "Ordinato", "note": ""},
    {"capitolo": "BAGNO", "descrizione": "BOX DOCCIA", "um": "cad",
     "quantita": None, "stato": "Da ordinare", "note": ""},
    {"capitolo": "PAVIMENTI", "descrizione": "PAVIMENTO/RIVESTIMENTO GRES",
     "um": "m²", "quantita": 94.71, "stato": "Consegnato", "note": ""},
    {"capitolo": "IMPIANTO RISCALDAMENTO",
     "descrizione": "UNITÀ INTERNA + ESTERNA CLIMA CANALIZZATO", "um": "cad",
     "quantita": 1.0, "stato": "Da ordinare",
     "note": "Si fornisce inoltre: plenum coibentato, collarini."},
]


# ------------------------------------------------------- niente soldi qui

def test_una_riga_non_ha_nessun_campo_di_soldi():
    """Il prezzo sta nel registro spese, dove arriva dalla fattura."""
    riga = materiali.riga_vuota()
    assert "prezzo" not in riga
    assert "importo" not in riga


def test_la_riga_vuota_ha_tutti_i_campi_che_servono():
    riga = materiali.riga_vuota()
    assert set(riga) == {"capitolo", "descrizione", "um", "quantita",
                         "fornitore", "link", "stato", "note"}
    assert riga["stato"] == materiali.STATO_PREDEFINITO
    assert riga["quantita"] is None


# ------------------------------------------------------- l'elenco standard

def test_l_elenco_standard_ha_le_voci_del_foglio_firmato():
    descrizioni = [r["descrizione"] for r in materiali.elenco_standard()]
    # una per capitolo, prese dall'allegato del cantiere di Migliarina
    for attesa in ("PIATTO DOCCIA", "PORTE A BATTENTE / SCRIGNO", "FRUTTI",
                   "LANA DI ROCCIA", "PAVIMENTO/RIVESTIMENTO GRES",
                   "CLIMATIZZATORE MOD. UNICO TWIN"):
        assert attesa in descrizioni, attesa
    assert len(descrizioni) == len(materiali.ELENCO_STANDARD)


def test_l_elenco_standard_copre_i_sei_capitoli_del_foglio():
    capitoli = {r["capitolo"] for r in materiali.elenco_standard()}
    assert capitoli == set(materiali.CAPITOLI[:6])


def test_l_elenco_standard_porta_la_nota_del_clima():
    """Sul foglio vero quella riga ha l'asterisco e la nota in fondo."""
    clima = [r for r in materiali.elenco_standard()
             if r["descrizione"].startswith("UNITÀ INTERNA")]
    assert clima and clima[0]["note"].startswith("Si fornisce inoltre")


def test_ogni_chiamata_da_righe_nuove():
    """Se restituisse i dizionari del modulo, modificarne uno in un
    progetto lo cambierebbe per tutti i successivi."""
    primo = materiali.elenco_standard()
    primo[0]["fornitore"] = "Ceramiche Rossi"
    assert materiali.elenco_standard()[0]["fornitore"] == ""


def test_l_elenco_standard_nasce_tutto_da_ordinare():
    assert all(r["stato"] == materiali.STATO_PREDEFINITO
               for r in materiali.elenco_standard())


# ------------------------------------------------------------- i conteggi

def test_conteggi_per_capitolo_seguono_l_ordine_dei_capitoli():
    """L'ordine è quello del foglio, non quello di comparsa."""
    conti = materiali.conteggi_per_capitolo(ELENCO)
    assert list(conti) == ["BAGNO", "PAVIMENTI", "IMPIANTO RISCALDAMENTO"]
    assert conti["BAGNO"] == 2


def test_capitolo_mancante_finisce_in_altro():
    conti = materiali.conteggi_per_capitolo([{"descrizione": "ROBA VARIA"}])
    assert list(conti) == [materiali.CAPITOLO_PREDEFINITO]


def test_un_capitolo_inventato_va_in_coda():
    """Un progetto vecchio può portare un capitolo che non è in elenco."""
    conti = materiali.conteggi_per_capitolo([
        {"capitolo": "GIARDINO ZEN", "descrizione": "GHIAIA"},
        {"capitolo": "BAGNO", "descrizione": "LAVABO"},
    ])
    assert list(conti) == ["BAGNO", "GIARDINO ZEN"]


def test_conteggi_per_stato_dicono_a_che_punto_e_la_spesa():
    per_stato = materiali.conteggi_per_stato(ELENCO)
    assert per_stato == {"Da ordinare": 2, "Ordinato": 1, "Consegnato": 1}


def test_quante_da_ordinare_e_il_numero_che_conta():
    assert materiali.quante_da_ordinare(ELENCO) == 2
    assert materiali.quante_da_ordinare([]) == 0


def test_stato_mancante_e_da_ordinare():
    per_stato = materiali.conteggi_per_stato([{"descrizione": "PORTE"}])
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
    """Vengono dall'allegato reale del cantiere, in quell'ordine."""
    assert materiali.CAPITOLI[:6] == [
        "BAGNO", "PORTE E INFISSI", "IMPIANTO ELETTRICO", "MURATURA",
        "PAVIMENTI", "IMPIANTO RISCALDAMENTO"]
