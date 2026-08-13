"""La griglia dei coefficienti di merito del foglio «MCA sell».

Nel foglio Excel i coefficienti si mettevano a mano: si leggeva la voce
nella colonna B, si copiava il numero della colonna C nella colonna del
comparabile, e alla fine si moltiplicava tutto. Tre passaggi manuali per
ognuno dei tredici fattori, per ognuno dei cinque comparabili, e il
prodotto finale — quello che poi divide il €/mq — usciva da una formula
lunga mezza riga.

Qui la griglia e' un dato: si sceglie la voce, il coefficiente lo calcola
il software. Chi legge la stima puo' risalire da ogni numero alla voce che
l'ha prodotto, che nel foglio non si poteva fare.

⚠️ I coefficienti si MOLTIPLICANO fra loro, e sono tredici. Un errore
del 5% su ciascuno non fa il 5%: si compone. Per questo `dettaglio` riporta
voce per voce cosa ha pesato — un totale di 1,40 va guardato in faccia
prima di crederci.
"""

# ------------------------------------------- caratteristiche del fabbricato

# Vetusta': l'incrocio fra lo stato dell'edificio e la sua eta'. Nel foglio
# erano nove righe (tre stati x tre fasce d'eta'); qui e' una chiave doppia,
# cosi' l'interfaccia puo' chiedere le due cose separatamente.
VETUSTA = {
    ("Ottimo", "1-20 anni"): 1.0,
    ("Ottimo", "20-40 anni"): 1.05,
    ("Ottimo", "oltre 40 anni"): 1.1,
    ("Normale", "1-20 anni"): 1.0,
    ("Normale", "20-40 anni"): 1.0,
    ("Normale", "oltre 40 anni"): 1.0,
    ("Scadente", "1-20 anni"): 0.95,
    ("Scadente", "20-40 anni"): 0.9,
    ("Scadente", "oltre 40 anni"): 0.85,
}
STATI_EDIFICIO = ("Ottimo", "Normale", "Scadente")
FASCE_ETA = ("1-20 anni", "20-40 anni", "oltre 40 anni")

FINITURE = {"Signorili": 1.05, "Civili": 1.0, "Economiche": 0.9}

# ----------------------------------------------- caratteristiche dell'unita'

CONDIZIONI = {
    "Nuova costruzione": 1.15,
    "Finemente ristrutturato": 1.1,
    "Nuovo o ristrutturato": 1.05,
    "Ristrutturato <10 anni": 1.02,
    "Abitabile 10-30 anni": 1.0,
    "Da ristrutturare 30-50 anni": 0.9,
    "Da ristrutturare oltre 50 anni": 0.8,
}

DEGRADO = {
    "Assente/ottima": 1.04,
    "Modesto/discreta": 1.03,
    "Ordinaria/sufficiente": 1.0,
    "Medio/sufficiente": 0.9,
    "Alto/scadente": 0.8,
}

# ⚠️ Il piano vale il doppio senza ascensore: al terzo con ascensore sei a
# 1,00, senza sei a 0,80. E' il fattore con l'escursione piu' larga di tutta
# la griglia (0,70-1,20) — sbagliare la spunta dell'ascensore sposta la
# stima piu' di qualunque altra voce.
PIANO_CON_ASCENSORE = {
    "Seminterrato": 0.75,
    "P. Terra o rialzato senza giardino": 0.8,
    "Terra o rialzato con giardino": 0.9,
    "Primo": 0.9,
    "Secondo": 0.97,
    "Terzo": 1.0,
    "Piani superiori": 1.05,
    "Ultimo piano": 1.1,
    "Attico": 1.2,
}
PIANO_SENZA_ASCENSORE = {
    "Seminterrato": 0.75,
    "P. Terra o rialzato senza giardino": 0.8,
    "Terra o rialzato con giardino": 0.9,
    "Primo": 0.9,
    "Secondo": 0.85,
    "Terzo": 0.8,
    "Piani superiori": 0.7,
    "Ultimo piano": 0.7,
    "Attico": 0.8,
}
LIVELLI_PIANO = tuple(PIANO_CON_ASCENSORE)

# ------------------------------------------------------------- complementi

# ⚠️ Nel foglio la colonna C di queste tre righe diceva «1,1/0,9» mentre
# l'etichetta accanto diceva «SI = 1,05 ; NO = 0,90». Le celle compilate —
# tutti i comparabili e il soggetto a 1,05 sui balconi — seguono
# l'etichetta, non la colonna C: e' l'etichetta che fa fede.
BALCONI = {"Sì": 1.05, "No": 0.9}
GIARDINO = {"Sì": 1.05, "No": 1.0}
TERRAZZO = {"Sì": 1.1, "No": 1.0}

LUMINOSITA = {
    "Molto luminoso": 1.1,
    "Luminoso": 1.05,
    "Mediamente luminoso": 1.0,
    "Poco luminoso": 0.95,
}

SPAZI_COMUNI = {"Parco": 1.06, "Giardino": 1.04, "Cortile": 1.02,
                "Assenti": 1.0}

PARCHEGGIO = {"Posto auto per UI": 1.04, "Assente": 1.0}

ESPOSIZIONE = {
    "Esterna panoramica": 1.1,
    "Esterna": 1.05,
    "Mista": 1.0,
    "Interna": 0.95,
    "Completamente interna": 0.9,
}

RISCALDAMENTO = {
    "Autonomo": 1.05,
    "Centralizzato con contabilizzatore": 1.02,
    "Centralizzato": 1.0,
    "Assente": 0.95,
}

# Le chiavi della griglia, nell'ordine in cui si compilano: dal fabbricato
# all'unita' ai complementi, come le tre fasce del foglio. La maschera legge
# di qui, cosi' aggiungere un fattore non vuol dire ricordarsi di aggiungerlo
# anche a mano da un'altra parte.
CAMPI = ("stato_edificio", "eta_edificio", "finiture",
         "condizioni", "degrado", "piano", "ascensore",
         "balconi", "giardino", "terrazzo", "luminosita",
         "spazi_comuni", "parcheggio", "esposizione", "riscaldamento")

# I fattori a scelta singola, nell'ordine in cui li mostra la scheda, con il
# gruppo di appartenenza: e' da qui che l'interfaccia disegna i menu' a
# tendina, cosi' griglia e maschera non possono divergere.
FATTORI = (
    ("finiture", "Finiture", "edificio", FINITURE),
    ("condizioni", "Condizioni", "unita", CONDIZIONI),
    ("degrado", "Degrado/manutenzione", "unita", DEGRADO),
    ("balconi", "Balconi", "complementi", BALCONI),
    ("giardino", "Giardino", "complementi", GIARDINO),
    ("terrazzo", "Terrazzo", "complementi", TERRAZZO),
    ("luminosita", "Luminosità", "complementi", LUMINOSITA),
    ("spazi_comuni", "Spazi comuni", "complementi", SPAZI_COMUNI),
    ("parcheggio", "Parcheggio comune", "complementi", PARCHEGGIO),
    ("esposizione", "Esposizione e vista", "complementi", ESPOSIZIONE),
    ("riscaldamento", "Riscaldamento", "complementi", RISCALDAMENTO),
)


def _valore(scelta, tabella):
    """Il coefficiente di una scelta: dalla tabella, o gia' numerico.

    Nel foglio le caselle non erano bloccate sulla griglia: il soggetto
    aveva 1,12 sulle condizioni dove la tabella dice 1,1, e due comparabili
    portavano 0,98 e 1,02 su voci da 1,00. Sono aggiustamenti a occhio di
    chi ha visto l'immobile, e vanno lasciati passare — chi stima sa cose
    che la griglia non ha. Un numero passa cosi' com'e'; una stringa deve
    stare in tabella.
    """
    if scelta is None or scelta == "":
        return None
    if isinstance(scelta, bool):
        return tabella.get("Sì" if scelta else "No")
    if isinstance(scelta, (int, float)):
        return float(scelta)
    return tabella.get(str(scelta))


def coefficiente_merito(scelte):
    """Il coefficiente di merito complessivo, dai fattori scelti.

    `scelte` e' un dizionario con le chiavi dei fattori. Per la vetusta'
    servono `stato_edificio` e `eta_edificio`; per il piano servono
    `piano` e `ascensore` (booleano). Ogni valore puo' essere il nome
    della voce oppure direttamente un numero, che scavalca la griglia.

    Le voci non indicate valgono 1,0 — neutre — e finiscono in `mancanti`.
    Non e' un dettaglio: un coefficiente calcolato su sei fattori su
    tredici e' un altro numero, e nel foglio non si vedeva quali fossero
    rimasti in bianco perche' una cella vuota e una cella a 1,00 producono
    lo stesso prodotto.

    Ritorna i tre subtotali del foglio (edificio, unita', complementi), il
    totale, il dettaglio voce per voce e l'elenco delle voci mancanti.
    """
    dettaglio = {}
    mancanti = []

    def prendi(chiave, etichetta, tabella, scelta=None):
        valore = _valore(scelte.get(chiave) if scelta is None else scelta,
                         tabella)
        if valore is None:
            mancanti.append(etichetta)
            return 1.0
        dettaglio[etichetta] = valore
        return valore

    # vetusta': due scelte, un coefficiente solo
    stato = scelte.get("stato_edificio")
    eta = scelte.get("eta_edificio")
    if isinstance(stato, (int, float)) and not isinstance(stato, bool):
        vetusta = prendi("stato_edificio", "Vetustà", VETUSTA, stato)
    elif stato and eta:
        vetusta = prendi("stato_edificio", "Vetustà", VETUSTA,
                         VETUSTA.get((str(stato), str(eta))))
    else:
        mancanti.append("Vetustà")
        vetusta = 1.0

    finiture = prendi("finiture", "Finiture", FINITURE)
    edificio = vetusta * finiture

    condizioni = prendi("condizioni", "Condizioni", CONDIZIONI)
    degrado = prendi("degrado", "Degrado/manutenzione", DEGRADO)

    # ⚠️ Senza l'indicazione dell'ascensore si applica la tabella SENZA: e'
    # la scelta prudente (coefficienti piu' bassi = stima piu' bassa). Dare
    # per scontato l'ascensore avrebbe gonfiato la stima proprio sul fattore
    # che pesa di piu'.
    tab_piano = (PIANO_CON_ASCENSORE if scelte.get("ascensore")
                 else PIANO_SENZA_ASCENSORE)
    piano = prendi("piano", "Livello piano", tab_piano)
    unita = condizioni * degrado * piano

    complementi = 1.0
    for chiave, etichetta, gruppo, tabella in FATTORI:
        if gruppo != "complementi":
            continue
        complementi *= prendi(chiave, etichetta, tabella)

    return {
        "edificio": round(edificio, 6),
        "unita": round(unita, 6),
        "complementi": round(complementi, 6),
        "totale": round(edificio * unita * complementi, 6),
        "dettaglio": dettaglio,
        "mancanti": mancanti,
    }


def scelte_da_riga(riga):
    """Le sole voci della griglia, prese da una riga della tabella.

    La riga di un comparabile porta anche nome, prezzo, mq e note: qui
    restano fuori. Le celle vuote non diventano scelte — una tendina mai
    toccata non e' una risposta, ed e' `coefficiente_merito` a doverla
    contare fra le mancanti.
    """
    return {c: riga.get(c) for c in CAMPI
            if riga.get(c) is not None and riga.get(c) != ""}


def coefficiente_effettivo(scelte, a_mano=None):
    """Il coefficiente che entra davvero nella stima.

    Se c'e' un numero scritto a mano vince lui, e la griglia resta come
    riferimento: serve a chi ha aperto un progetto salvato prima che la
    maschera esistesse — quei progetti hanno il coefficiente battuto a mano
    e nessuna voce compilata, e devono continuare a dare lo stesso numero.
    Serve anche a chi la griglia ce l'ha ma non ci crede: e' un modello, e
    davanti all'immobile puo' avere torto.

    `fonte` dice quale delle due ha vinto, cosi' la scheda lo puo' mostrare
    invece di far indovinare da dove esce il numero.

    ⚠️ Una griglia COMPLETAMENTE in bianco non vale 1,00: vale zero, e
    `fonte` diventa "assente". Non e' un cavillo — `coefficiente_merito`
    da' 1,0 a chi non ha compilato niente, che come funzione pura e'
    giusto (tutte le voci neutre), ma come comparabile vorrebbe dire far
    entrare nella stima un immobile di cui non si sa NULLA spacciandolo
    per uno nella media. Con zero, `stima_mca` lo scarta e lo conta fra
    gli scartati, che e' quello che faceva prima della griglia.
    """
    esito = coefficiente_merito(scelte)
    esito["calcolato"] = esito["totale"]
    if a_mano is not None and float(a_mano) > 0:
        esito["totale"] = round(float(a_mano), 6)
        esito["fonte"] = "a mano"
    elif not esito["dettaglio"]:
        esito["totale"] = 0.0
        esito["fonte"] = "assente"
    else:
        esito["fonte"] = "griglia"
    return esito
