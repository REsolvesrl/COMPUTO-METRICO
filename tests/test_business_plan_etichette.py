"""Quello che il Business plan DICE dei suoi numeri.

Gli altri test provano che i conti tornano. Questi provano che la scheda
non li nomina male — che è un difetto altrettanto costoso, e più difficile
da vedere: un numero giusto sotto un'etichetta sbagliata non stona, e
finisce lo stesso in una decisione d'acquisto.

Le tre famiglie sorvegliate qui:

- una **stima su tre comparabili** quando in tabella ce ne sono cinque non
  deve sembrare la stessa cosa di una stima su cinque;
- il **confronto col preventivo** non deve comparire prima che esista una
  spesa di cantiere: senza, urlava «−100 %» sul computo intero;
- un **contratto pagato oltre il suo importo** deve vedersi, invece di
  fermarsi a un residuo di zero.

Girano sull'app vera con AppTest: le etichette vivono nell'interfaccia, e
leggere il sorgente qui non basterebbe.
"""
import json
from pathlib import Path

import pandas as pd
import pytest
from streamlit.testing.v1 import AppTest

SORGENTE = Path(__file__).resolve().parent.parent / "streamlit_app.py"


def _avvia(**stato):
    """L'app eseguita una volta, con la sessione preparata."""
    at = AppTest.from_file(str(SORGENTE), default_timeout=300)
    at.run()
    for chiave, valore in stato.items():
        at.session_state[chiave] = valore
    at.run()
    assert not at.exception, [e.value for e in at.exception]
    return at


def _testi(at):
    """Tutto il testo della pagina, in un unico blocco da cercare dentro."""
    pezzi = []
    for elenco in (at.markdown, at.caption, at.warning, at.info, at.error,
                   at.subheader, at.metric):
        for elemento in elenco:
            pezzi.append(str(getattr(elemento, "value", "")))
            pezzi.append(str(getattr(elemento, "label", "")))
    return "\n".join(pezzi)


def _riga_comparabili(at, indice=0):
    """Una riga della tabella dei comparabili, come dizionario."""
    for elemento in at.dataframe:
        tabella = getattr(elemento, "value", None)
        if tabella is not None and "Coeff. merito" in getattr(
                tabella, "columns", []):
            return tabella.iloc[indice].to_dict()
    raise AssertionError("la tabella dei comparabili non c'è")


# --------------------------------------------------------------------- MCA

@pytest.fixture(scope="module")
def mca_con_scarti():
    """Due comparabili buoni e due incompleti nella stessa tabella."""
    return _avvia(df_mca=pd.DataFrame([
        {"nome": "C1", "prezzo": 300000.0, "mq": 100.0, "coeff": 1.0,
         "note": ""},
        {"nome": "C2", "prezzo": 260000.0, "mq": 100.0, "coeff": 1.0,
         "note": ""},
        {"nome": "senza coefficiente", "prezzo": 300000.0, "mq": 100.0,
         "coeff": 0.0, "note": ""},
        {"nome": "senza mq", "prezzo": 300000.0, "mq": 0.0, "coeff": 1.0,
         "note": ""},
    ]), bp_mq=100.0)


def test_i_comparabili_scartati_non_spariscono_in_silenzio(mca_con_scarti):
    testo = _testi(mca_con_scarti)
    assert "2 comparabile/i" in testo
    assert "non entra/entrano" in testo


def test_la_media_dichiara_su_quanti_e_fatta(mca_con_scarti):
    """«€/mq medio» senza il numero di comparabili è mezza informazione."""
    etichette = [m.label for m in mca_con_scarti.metric]
    assert any("normalizzato" in e and "su 2" in e for e in etichette), \
        etichette


def test_la_media_dichiara_di_essere_aritmetica(mca_con_scarti):
    """Un bilocale pesa quanto un quadrilocale: va detto, non dedotto."""
    assert "aritmetica" in _testi(mca_con_scarti)


def test_il_coefficiente_esce_dalla_griglia_senza_scriverlo_a_mano():
    """Il motivo per cui la griglia esiste: si dice com'è fatto l'immobile
    e il coefficiente lo calcola CME. Prima si moltiplicava a mano."""
    at = _avvia(bp_mq=100.0, df_mca=pd.DataFrame([{
        "nome": "C1", "prezzo": 300000.0, "mq": 100.0,
        "finiture": "Signorili", "piano": "Terzo", "ascensore": True,
        "coeff": None, "note": "",
    }]))
    assert not at.exception, [e.value for e in at.exception]
    # ⚠️ Si legge la COLONNA, non `str(dataframe)`: con sette colonne pandas
    # elide quelle di mezzo nella rappresentazione, e il test passava o
    # falliva a seconda di quante colonne aveva la tabella quel giorno.
    riga = _riga_comparabili(at)
    # 1,05 (signorili) × 1,00 (terzo con ascensore) = 1,05
    assert riga["Coeff. merito"] == "1,050"
    # 100 m² è la superficie neutra: il taglio non corregge niente
    assert riga["Coeff. taglio"] == "1,000"


def test_un_comparabile_senza_niente_resta_scartato():
    """Griglia in bianco e nessun coefficiente: non è un immobile «nella
    media», è un immobile di cui non si sa nulla. Come prima della griglia,
    non entra nella stima e si dice che non c'è entrato."""
    at = _avvia(bp_mq=100.0, df_mca=pd.DataFrame([
        {"nome": "C1", "prezzo": 300000.0, "mq": 100.0, "coeff": 1.0,
         "note": ""},
        {"nome": "vuoto", "prezzo": 250000.0, "mq": 100.0, "coeff": None,
         "note": ""},
    ]))
    testo = _testi(at)
    assert "1 comparabile/i" in testo
    assert "non entra/entrano" in testo


def test_i_predefiniti_sono_l_immobile_tipo_a_lavori_finiti():
    """Palazzina normale di 20-40 anni, finiture civili, finemente
    ristrutturato, balconi, esterna e luminosa, riscaldamento autonomo:
    1,13 × 1,157625 = 1,308."""
    at = _avvia(bp_mq=100.0, bp_coeff_sogg=0.0)
    etichette = {m.label: m.value for m in at.metric}
    assert etichette["Coeff. di merito del tuo immobile"] == "1,308"


def test_la_correzione_del_taglio_si_regola_anche_senza_comparabili():
    """Il suo effetto — il coefficiente sotto i mq — si vede sempre. Se il
    comando stesse fra i risultati, che compaiono solo con un comparabile
    buono in tabella, si vedrebbe l'effetto senza la manopola."""
    at = _avvia(bp_mq=132.0)
    assert at.number_input(key="bp_taglio").value == pytest.approx(0.15)
    # (100/132) ** 0,15 = 0,9592
    assert "0,959" in _testi(at)


def test_il_piano_resta_da_indicare():
    """È la voce che cambia a ogni immobile ed è quella che pesa di più:
    un predefinito lì sarebbe un numero deciso da nessuno."""
    at = _avvia(bp_mq=100.0, bp_coeff_sogg=0.0)
    assert at.session_state["sog_piano"] == "—"
    assert at.session_state["sog_ascensore"] is False
    assert "Livello piano" in _testi(at)


def test_il_coefficiente_del_soggetto_segue_le_tendine():
    """Cambiando una voce cambia il numero: attico con ascensore (1,20)
    invece del piano non indicato (1,00) porta 1,308 a 1,570."""
    at = _avvia(bp_mq=100.0, bp_coeff_sogg=0.0, sog_piano="Attico",
                sog_ascensore=True)
    etichette = {m.label: m.value for m in at.metric}
    assert etichette["Coeff. di merito del tuo immobile"] == "1,570"


def test_svuotando_la_griglia_il_soggetto_vale_uno_e_lo_dichiara():
    """Il soggetto è uno solo ed è il motivo per cui si sta stimando:
    scartarlo come si fa coi comparabili vorrebbe dire non dare numeri."""
    import streamlit_app
    vuote = {chiave: "—" for chiave in streamlit_app.SOGGETTO_MCA
             if chiave != "sog_ascensore"}
    at = _avvia(bp_mq=100.0, bp_coeff_sogg=0.0, sog_ascensore=False, **vuote)
    etichette = {m.label: m.value for m in at.metric}
    assert etichette["Coeff. di merito del tuo immobile"] == "1,000"
    assert "non compilata" in _testi(at)


def test_un_progetto_vecchio_riceve_i_predefiniti():
    """Chiave «mca_soggetto» assente = progetto salvato prima della
    griglia, cioè «di questo non si sa niente»: valgono i predefiniti. Se
    no chi riapre il lavoro di sempre trova quattordici tendine vuote e i
    predefiniti non li vede mai."""
    at = _avvia(da_caricare={"progetto": {"nome": "vecchio"},
                             "business_plan": {"bp_coeff_sogg": 1.4}})
    assert at.session_state["sog_stato_unita"] == "Finemente ristrutturato"
    assert at.session_state["sog_riscaldamento"] == "Autonomo"
    # ma il coefficiente battuto a mano resta al comando: i numeri di un
    # progetto vecchio non si muovono da soli
    etichette = {m.label: m.value for m in at.metric}
    assert etichette["Coeff. di merito del tuo immobile"] == "1,400"


def test_una_voce_svuotata_apposta_resta_svuotata():
    """Chiave presente con dentro un None = l'utente ha messo «—» apposta.
    Rimetterci il predefinito sarebbe riempire una casella svuotata."""
    at = _avvia(da_caricare={
        "progetto": {"nome": "nuovo"},
        "mca_soggetto": {"stato_unita": None, "riscaldamento": "Autonomo"},
    })
    assert at.session_state["sog_stato_unita"] == "—"
    assert at.session_state["sog_riscaldamento"] == "Autonomo"


def test_un_progetto_con_la_griglia_di_prima_si_traduce():
    """Chi aveva compilato «condizioni», «degrado», «luminosità» ed
    «esposizione» non deve ritrovarsi le tendine vuote: la stima uscirebbe
    lo stesso, solo più bassa, senza che nessuno lo dica."""
    at = _avvia(da_caricare={
        "progetto": {"nome": "griglia vecchia"},
        "mca_soggetto": {
            "condizioni": "Da ristrutturare oltre 50 anni",
            "degrado": "Alto/scadente",
            "luminosita": "Luminoso", "esposizione": "Esterna",
            "riscaldamento": "Autonomo",
        },
    })
    assert at.session_state["sog_stato_unita"] == "Da ristrutturare integralmente"
    assert at.session_state["sog_luce_vista"] == "Esterna e luminosa"


def test_la_tabella_dei_comparabili_scorre_di_lato():
    """Venti colonne fanno ~2.040 px in un contenitore da ~1.100, e ogni
    antenato ha `overflow-x: visible`: senza questa regola le ultime
    colonne non finiscono sotto una barra di scorrimento, spariscono
    tagliate. È il difetto peggiore di questa scheda — non stona niente,
    semplicemente «Riscaldamento» non esiste per chi guarda.

    Si controlla il foglio di stile perché il taglio è visivo: AppTest non
    disegna, e la tabella vive su canvas.
    """
    sorgente = SORGENTE.read_text(encoding="utf-8")
    assert '[class*="st-key-editor_mca"] {{ overflow-x: auto; }}' in sorgente


def test_i_mq_dei_comparabili_e_del_soggetto_sono_la_stessa_grandezza():
    """Commerciali di qua, commerciali di là: se le basi differiscono
    l'errore non si vede mai, si porta dentro il prezzo di vendita."""
    at = _avvia(bp_mq=120.0)
    etichette = [m.label for m in at.metric]
    assert any("Mq commerciali del soggetto" in e for e in etichette)


# ------------------------------------------ il registro delle spese

def _registro(at):
    """La tabella delle spese sostenute: (configurazione colonne, dati)."""
    for nodo in at.dataframe:
        config = json.loads(nodo.proto.columns or "{}")
        if "Totale fattura" in [c.get("label") for c in config.values()]:
            return config, nodo.value
    raise AssertionError("tabella delle spese sostenute non trovata")


@pytest.fixture(scope="module")
def registro():
    """Le due spese vere del progetto di collaudo: la provvigione
    dell'agenzia con l'IVA dentro, e una caparra che l'IVA non ce l'ha."""
    agenzia = dict(_spesa("🟣 AGENZIA", 7320.0), aliquota_iva=22.0,
                   fornitore="studiokennedy snc")
    caparra = dict(_spesa("🔴 ACQUISTO", 20000.0), aliquota_iva=0.0,
                   oggetto="Caparra confirmatoria")
    return _registro(_avvia(df_spese=pd.DataFrame([agenzia, caparra])))


def test_il_fornitore_ha_una_colonna_sua(registro):
    """Stava dentro «Oggetto», appiccicato alla descrizione."""
    config, dati = registro
    assert config["fornitore"]["label"] == "Fornitore"
    assert "fornitore" in dati.columns


def test_l_iva_in_euro_c_e_e_non_si_scrive_a_mano(registro):
    """È importo − importo/(1+aliquota/100): un valore calcolato non si
    digita, o le due cifre possono raccontare cose diverse."""
    config, _ = registro
    iva = config["iva_eur"]
    assert iva["label"] == "di cui IVA"
    assert iva["disabled"] is True


def test_l_iva_in_euro_e_quella_giusta(registro):
    """7.320 € al 22% ne contengono 1.320; una caparra senza IVA, zero."""
    _, dati = registro
    per_importo = dict(zip(dati["importo"], dati["iva_eur"]))
    assert per_importo[7320.0] == pytest.approx(1320.0, abs=0.01)
    assert per_importo[20000.0] == pytest.approx(0.0)


def test_le_cifre_hanno_il_separatore_delle_migliaia(registro):
    """«20000.00» non si legge a colpo d'occhio: «20.000,00 €» sì.

    Il formato è «euro», NON «localized»: «localized» conserva i decimali
    del numero, e su una colonna di soldi significa perdere i centesimi a
    schermo (20000 scritto «20.000»). «euro» ne tiene sempre due.
    """
    config, _ = registro
    for colonna in ("importo", "iva_eur"):
        assert config[colonna]["type_config"]["format"] == "euro"


def test_i_centesimi_non_si_perdono_per_strada():
    """Il formato è come si SCRIVE il numero, mai quanto vale: i centesimi
    restano nel dato, nei totali e nell'IVA scorporata.

    Vale la pena provarlo e non darlo per buono: se un formato arrotondasse
    davvero il valore, su un registro di fatture l'errore si accumulerebbe
    riga per riga senza che nessuna singola cifra sembri sbagliata.
    """
    at = _avvia(df_spese=pd.DataFrame([
        dict(_spesa("🟡 LAVORI", 1234.56), aliquota_iva=22.0),
        dict(_spesa("🟢 MATERIALE", 99.99), aliquota_iva=10.0),
    ]))
    config, dati = _registro(at)
    # il dato che torna dalla tabella ha ancora i suoi centesimi
    assert sorted(dati["importo"]) == [99.99, 1234.56]
    # e anche l'IVA calcolata, al centesimo
    per_importo = dict(zip(dati["importo"], dati["iva_eur"]))
    assert per_importo[1234.56] == pytest.approx(222.63, abs=0.01)
    assert per_importo[99.99] == pytest.approx(9.09, abs=0.01)
    # il totale li somma tutti e due, centesimi compresi
    metriche = {m.label: m.value for m in at.metric}
    assert metriche["Totale spese sostenute"] == "1.334,55 €"


def test_le_colonne_sono_strette_e_su_misura(registro):
    """Con nove colonne, le taglie di Streamlit sprecano dove non serve.
    Quel che avanza va in scorrimento, non in compressione."""
    config, _ = registro
    larghezze = {c: v["width"] for c, v in config.items() if "width" in v}
    assert larghezze["data"] <= 100          # una data non occupa 200 px
    assert larghezze["aliquota_iva"] <= 80
    assert larghezze["oggetto"] >= larghezze["data"] * 2
    # niente taglie simboliche: pixel, decisi uno per uno
    assert all(isinstance(v, int) for v in larghezze.values()), larghezze


def test_l_iva_calcolata_non_entra_nel_progetto_salvato():
    """Il ritorno della tabella porta anche le colonne calcolate: se una
    rientrasse nei dati, al giro dopo si inserirebbe due volte."""
    at = _avvia(df_spese=pd.DataFrame([_spesa("🟡 LAVORI", 1220.0)]))
    salvato = at.session_state["df_spese"]
    assert "iva_eur" not in salvato.columns


# ------------------------------------------- confronto col preventivo

def _computo_da(totale):
    """Un computo di una riga sola, che vale esattamente `totale`."""
    return pd.DataFrame([{
        "categoria": "1 · Demolizioni", "codice": "X.01",
        "descrizione": "voce di prova", "um": "a corpo",
        "parti": None, "lunghezza": None, "larghezza": None, "altezza": None,
        "quantita_manuale": 1.0, "prezzo": float(totale),
    }])


def _spesa(categoria, importo):
    return {"importo": importo, "aliquota_iva": 22.0, "data": "",
            "nr_fattura": "", "oggetto": "acconto",
            "categoria": categoria, "note": ""}


def test_senza_spese_di_cantiere_non_si_confronta_niente():
    """Bastava la provvigione dell'agenzia e il blocco compariva con
    «−100 %»: il computo intero dato per non speso, a cantiere chiuso."""
    at = _avvia(df_spese=pd.DataFrame(
        [_spesa("🔴 ACQUISTO", 20000.0), _spesa("🟣 AGENZIA", 7320.0)]))
    assert "prova del cantiere" not in _testi(at)


def test_con_una_spesa_di_cantiere_il_confronto_compare():
    at = _avvia(df_spese=pd.DataFrame([_spesa("🟡 LAVORI", 5000.0)]))
    assert "prova del cantiere" in _testi(at)


def test_speso_e_da_sostenere_restano_distinti():
    """«Consuntivo» vuol dire soldi usciti: le previsioni stanno a parte."""
    at = _avvia(df_spese=pd.DataFrame([_spesa("🟡 LAVORI", 5000.0)]),
                df_spese_prev=pd.DataFrame([_spesa("🟢 MATERIALE", 3000.0)]))
    # Le etichette qui sono in tondo: il maiuscoletto lo fa il CSS.
    metriche = {m.label: m.value for m in at.metric}
    assert metriche["Speso davvero (fatture)"] == "5.000,00 €"
    assert metriche["Ancora da sostenere (stime)"] == "3.000,00 €"


def test_lo_scostamento_e_una_percentuale_non_la_stessa_cifra_due_volte():
    """Valore grande e delta erano gli stessi euro; la percentuale — quella
    con cui lo storico tara gli imprevisti — non c'era.

    Serve un computo vero da confrontare: senza preventivo non esiste una
    percentuale, e la scheda scrive «—» (che è la cosa giusta).
    """
    at = _avvia(df_voci=_computo_da(10000.0),
                df_spese=pd.DataFrame([_spesa("🟡 LAVORI", 5000.0)]))
    scostamento = [m for m in at.metric
                   if m.label == "Scostamento sul preventivo"]
    assert scostamento, [m.label for m in at.metric]
    assert "-50,0 %" == scostamento[0].value
    assert "-5.000,00 €" == scostamento[0].delta


def test_senza_preventivo_lo_scostamento_non_inventa_una_percentuale():
    at = _avvia(df_spese=pd.DataFrame([_spesa("🟡 LAVORI", 5000.0)]))
    scostamento = [m for m in at.metric
                   if m.label == "Scostamento sul preventivo"]
    assert scostamento[0].value == "—"


# ------------------------------------------------ contratto e SAL

def test_il_registro_spese_non_si_chiama_costo_delloperazione():
    """ACQUISTO e AGENZIA qui dentro sono già contati nell'entry: due
    totali che si sovrappongono, e quello col nome più grosso era il meno
    vero dei due."""
    at = _avvia(df_spese=pd.DataFrame([_spesa("🔴 ACQUISTO", 20000.0)]))
    testo = _testi(at)
    assert "Totale del registro spese" in testo
    assert "Costi totali dell'operazione" not in testo


def test_ancora_da_pagare_dichiara_di_essere_il_residuo():
    """Senza extra sono lo stesso numero sotto due nomi, e due nomi sullo
    stesso numero si leggono come due conferme indipendenti."""
    at = _avvia(cant_contratto=60000.0, cant_extra=0.0,
                cant_sal=[{"percento": 20.0, "pagato": True},
                          {"percento": 80.0, "pagato": False}])
    etichette = [m.label for m in at.metric]
    assert any("= il residuo" in e for e in etichette), etichette


def test_con_gli_extra_ancora_da_pagare_torna_a_essere_se_stesso():
    at = _avvia(cant_contratto=60000.0, cant_extra=5000.0,
                cant_sal=[{"percento": 20.0, "pagato": True},
                          {"percento": 80.0, "pagato": False}])
    etichette = [m.label for m in at.metric]
    assert "Ancora da pagare" in etichette
    assert not any("= il residuo" in e for e in etichette)


def test_il_totale_a_fine_cantiere_non_si_chiama_totale_finale():
    """Nel computo «TOTALE FINALE» è la card d'ottone dei lavori."""
    at = _avvia(cant_contratto=60000.0,
                cant_sal=[{"percento": 100.0, "pagato": False}])
    etichette = [m.label for m in at.metric]
    assert "Totale a fine cantiere" in etichette
    assert "Totale finale" not in etichette


def test_aver_pagato_oltre_il_contratto_si_vede():
    """Quote che fanno 110 e tutte saldate: prima il residuo si fermava a
    zero e non lo diceva nessuno."""
    at = _avvia(cant_contratto=60000.0,
                cant_sal=[{"percento": 20.0, "pagato": True},
                          {"percento": 30.0, "pagato": True},
                          {"percento": 30.0, "pagato": True},
                          {"percento": 30.0, "pagato": True}])
    avvisi = "\n".join(a.value for a in at.warning)
    assert "6.000,00 € in più" in avvisi
    metriche = {m.label: m.value for m in at.metric}
    assert metriche["Residuo di contratto"] == "-6.000,00 €"
    assert metriche["Saldato"] == "66.000,00 €"
