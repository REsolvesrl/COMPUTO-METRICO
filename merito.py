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
#
# ⚠️ Questo coefficiente riguarda l'ESTERNO — facciata, coperture, parti
# comuni — e resta separato da quello dell'unita' perche' sono davvero due
# informazioni: si puo' ristrutturare benissimo dentro un palazzo che cade,
# e viceversa. La duplicazione che e' stata tolta era un'altra, fra
# «condizioni» e «degrado», che chiedevano tutt'e due dell'interno.
#
# Rispetto al foglio cambia solo il fondo scala: da 0,85 a 0,90. Due
# coefficienti che si moltiplicano vanno tenuti stretti ognuno, se no
# tornano a comporsi — 0,90-1,10 qui per 0,82-1,18 sull'unita' fa
# 0,74-1,30, che e' l'ordine di grandezza delle tabelle di mercato.
#
# Il segno dell'eta' NON e' quello che verrebbe da pensare, ed e' voluto:
# un edificio in OTTIMO stato vale di piu' se vecchio (1,10 oltre i 40 anni
# contro 1,00 sotto i 20), in stato SCADENTE vale di meno. Non e' una
# svista del foglio: un palazzo d'epoca tenuto bene e' un pregio, lo stesso
# palazzo malandato e' una spesa. E' un'interazione, non un effetto
# dell'eta' da sola.
VETUSTA = {
    ("Ottimo", "1-20 anni"): 1.0,
    ("Ottimo", "20-40 anni"): 1.05,
    ("Ottimo", "oltre 40 anni"): 1.1,
    ("Normale", "1-20 anni"): 1.0,
    ("Normale", "20-40 anni"): 1.0,
    ("Normale", "oltre 40 anni"): 1.0,
    ("Scadente", "1-20 anni"): 0.97,
    ("Scadente", "20-40 anni"): 0.94,
    ("Scadente", "oltre 40 anni"): 0.9,
}
STATI_EDIFICIO = ("Ottimo", "Normale", "Scadente")
FASCE_ETA = ("1-20 anni", "20-40 anni", "oltre 40 anni")

FINITURE = {"Signorili": 1.05, "Civili": 1.0, "Economiche": 0.9}

# --------------------------------------------- stato dell'unita' (interno)

# ⚠️ QUI stava il difetto piu' costoso della griglia, e riguardava
# l'INTERNO. Lo stato dell'unita' viaggiava su DUE voci che si
# moltiplicavano — «condizioni» (0,80-1,15) e «degrado/manutenzione»
# (0,80-1,04) — che sono la stessa domanda fatta due volte: un
# appartamento «da ristrutturare» con manutenzione «alta/scadente» non e'
# due notizie, e' una. Moltiplicate, e messe in fila con la vetusta'
# dell'edificio, davano un'escursione da 0,54 a 1,32: il doppio del range
# piu' largo in circolazione (RealAdvisor si ferma a 0,65-1,25).
#
# Adesso e' una voce sola, 0,82-1,18. Range largo e non stretto: per chi
# compra da ristrutturare e rivende finemente ristrutturato lo stato E' la
# variabile, e schiacciarlo a +/-10% come fanno idealista e RockAgent
# avrebbe tolto il mestiere dalla stima.
#
# Resta DIVISO dalla vetusta' dell'edificio (vedi VETUSTA), che e' l'altra
# meta' del discorso e un'informazione diversa davvero.
STATO_UNITA = {
    "Nuova costruzione": 1.18,
    "Finemente ristrutturato": 1.13,
    "Nuovo o ristrutturato": 1.07,
    "Ristrutturato <10 anni": 1.03,
    "Abitabile": 1.0,
    "Da ristrutturare": 0.89,
    "Da ristrutturare integralmente": 0.82,
}

# Le tabelle di prima, tenute SOLO per rileggere i progetti salvati con la
# griglia vecchia (vedi `migra_scelte`). Non entrano piu' nel calcolo.
CONDIZIONI_STORICHE = {
    "Nuova costruzione": 1.15,
    "Finemente ristrutturato": 1.1,
    "Nuovo o ristrutturato": 1.05,
    "Ristrutturato <10 anni": 1.02,
    "Abitabile 10-30 anni": 1.0,
    "Da ristrutturare 30-50 anni": 0.9,
    "Da ristrutturare oltre 50 anni": 0.8,
}
DEGRADO_STORICO = {
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

# ⚠️ Anche qui c'erano due voci per una cosa sola: luminosita' (0,95-1,10) ed
# esposizione/vista (0,90-1,10), moltiplicate fra loro per un 0,855-1,21. Ma
# un appartamento e' luminoso PERCHE' e' esterno e ben esposto: sono la
# stessa informazione chiesta due volte. Adesso e' una voce sola, 0,90-1,10,
# che e' quello che dicono idealista e RockAgent per la vista.
LUCE_VISTA = {
    "Panoramica e molto luminosa": 1.1,
    "Esterna e luminosa": 1.05,
    "Nella media": 1.0,
    "Poco luminosa o interna": 0.95,
    "Interna e buia": 0.9,
}

SPAZI_COMUNI = {"Parco": 1.06, "Giardino": 1.04, "Cortile": 1.02,
                "Assenti": 1.0}

PARCHEGGIO = {"Posto auto per UI": 1.04, "Assente": 1.0}

# Tenute per rileggere i progetti vecchi, come sopra: fuori dal calcolo.
LUMINOSITA_STORICA = {
    "Molto luminoso": 1.1,
    "Luminoso": 1.05,
    "Mediamente luminoso": 1.0,
    "Poco luminoso": 0.95,
}
ESPOSIZIONE_STORICA = {
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
CAMPI = ("stato_edificio", "eta_edificio", "stato_unita", "finiture",
         "piano", "ascensore",
         "balconi", "giardino", "terrazzo", "luce_vista",
         "spazi_comuni", "parcheggio", "riscaldamento")

# I fattori a scelta singola, nell'ordine in cui li mostra la scheda, con il
# gruppo di appartenenza: e' da qui che l'interfaccia disegna i menu' a
# tendina, cosi' griglia e maschera non possono divergere.
FATTORI = (
    ("finiture", "Finiture", "edificio", FINITURE),
    ("balconi", "Balconi", "complementi", BALCONI),
    ("giardino", "Giardino", "complementi", GIARDINO),
    ("terrazzo", "Terrazzo", "complementi", TERRAZZO),
    ("luce_vista", "Luce e vista", "complementi", LUCE_VISTA),
    ("spazi_comuni", "Spazi comuni", "complementi", SPAZI_COMUNI),
    ("parcheggio", "Parcheggio comune", "complementi", PARCHEGGIO),
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

    `scelte` e' un dizionario con le chiavi dei fattori. Per lo stato
    servono `stato_unita` (la scala) piu' `stato_edificio` e `eta_edificio`
    (lo scostamento, SOMMATO); per il piano servono `piano` e `ascensore`
    (booleano). Ogni valore puo' essere il nome della voce oppure
    direttamente un numero, che scavalca la griglia.

    Le voci non indicate valgono 1,0 — neutre — e finiscono in `mancanti`.
    Non e' un dettaglio: un coefficiente calcolato su cinque voci su dieci
    e' un altro numero, e nel foglio non si vedeva quali fossero rimaste in
    bianco perche' una cella vuota e una cella a 1,00 producono lo stesso
    prodotto.

    Ritorna i tre subtotali (edificio, unita', complementi), il totale, il
    dettaglio voce per voce e l'elenco delle voci mancanti.
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

    finiture = prendi("finiture", "Finiture", FINITURE)

    # L'ESTERNO: due tendine, un coefficiente solo. E' il trucco che il
    # foglio usava gia' per la vetusta', e va bene cosi' — il doppio
    # conteggio non era qui.
    stato_ed = scelte.get("stato_edificio")
    eta = scelte.get("eta_edificio")
    if isinstance(stato_ed, (int, float)) and not isinstance(stato_ed, bool):
        vetusta = prendi("stato_edificio", "Stato edificio", VETUSTA, stato_ed)
    elif stato_ed and eta:
        vetusta = prendi("stato_edificio", "Stato edificio", VETUSTA,
                         VETUSTA.get((str(stato_ed), str(eta))))
    else:
        mancanti.append("Stato edificio")
        vetusta = 1.0
    edificio = vetusta * finiture

    # L'INTERNO: una voce sola dove prima erano condizioni x degrado.
    stato = prendi("stato_unita", "Stato dell'unità", STATO_UNITA)

    # ⚠️ Senza l'indicazione dell'ascensore si applica la tabella SENZA: e'
    # la scelta prudente (coefficienti piu' bassi = stima piu' bassa). Dare
    # per scontato l'ascensore avrebbe gonfiato la stima proprio sul fattore
    # che pesa di piu'.
    tab_piano = (PIANO_CON_ASCENSORE if scelte.get("ascensore")
                 else PIANO_SENZA_ASCENSORE)
    piano = prendi("piano", "Livello piano", tab_piano)
    unita = stato * piano

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


# ------------------------------------------------------- taglio (superficie)

# I tagli piccoli costano di piu' al metro: e' la regolarita' di mercato piu'
# solida che ci sia, e none delle tabelle di coefficienti in circolazione ce
# l'ha — ne' la nostra griglia, ne' quelle pubblicate da idealista, RockAgent
# o Borsino. L'MCA fatto per bene non ne ha bisogno perche' la superficie e'
# una caratteristica come le altre e il suo prezzo marginale si ricava dai
# comparabili (e viene sempre piu' basso del prezzo medio al metro: e'
# esattamente l'effetto taglio). Con la griglia dei coefficienti, invece, va
# messo a mano.
#
# La forma e' una legge di potenza e non una tabella a fasce: con le fasce un
# appartamento di 79 mq e uno di 81 finirebbero in due mondi diversi per un
# metro quadro.
#
#     coefficiente = (superficie_neutra / mq) ** elasticita
#
# `elasticita` a zero spegne tutto. A 0,15 un 50 mq vale l'11% in piu' al
# metro di un 100 mq e un 200 mq il 10% in meno: 23% di escursione fra i due
# estremi, che e' l'ordine di grandezza che si osserva.
#
# ⚠️ Sui comparabili del MCA.xlsx reale l'elasticita' che minimizza la
# dispersione e' 0,415 — e NON va usata: su cinque punti sta inseguendo il
# rumore, e infatti a quel valore C5 diventa un outlier al contrario (da
# 2.187 a 2.916 €/mq normalizzati). A 0,15 la dispersione scende dal 25,5%
# al 21,6%: meglio, ma ancora sopra la soglia. Il taglio spiega una PARTE
# dello scarto di C1, non tutto.
SUPERFICIE_NEUTRA = 100.0
ELASTICITA_TAGLIO = 0.15


def coefficiente_taglio(mq, elasticita=ELASTICITA_TAGLIO,
                        neutra=SUPERFICIE_NEUTRA):
    """Quanto vale di piu' (o di meno) il metro quadro a questa metratura.

    Sopra 1 per i tagli piccoli, sotto 1 per quelli grandi, esattamente 1
    alla superficie neutra. Ritorna None se la superficie non c'e': senza
    metratura non c'e' effetto taglio da correggere, ed e' meglio dirlo che
    restituire un 1,0 che sembra una misura.
    """
    try:
        mq = float(mq or 0.0)
    except (TypeError, ValueError):
        return None
    if mq <= 0:
        return None
    if not elasticita:
        return 1.0
    return round((float(neutra) / mq) ** float(elasticita), 6)


# ------------------------------------------------- dalla griglia di prima

# Le voci di «Condizioni» che si chiamavano diversamente. Le altre quattro
# — nuova costruzione, finemente ristrutturato, nuovo o ristrutturato,
# ristrutturato <10 anni — hanno lo stesso nome e passano da sole.
CONDIZIONI_RINOMINATE = {
    "Abitabile 10-30 anni": "Abitabile",
    "Da ristrutturare 30-50 anni": "Da ristrutturare",
    "Da ristrutturare oltre 50 anni": "Da ristrutturare integralmente",
}


def _piu_vicina(valore, tabella):
    """La voce della tabella col coefficiente piu' vicino a `valore`."""
    return min(tabella, key=lambda voce: abs(tabella[voce] - valore))


def migra_scelte(scelte):
    """Le scelte di un progetto salvato con la griglia di prima, tradotte.

    Serve perche' accorpare le voci ha cambiato i nomi dei campi: chi ha
    compilato la griglia vecchia si ritroverebbe le tendine vuote, e le
    tendine vuote non sono un errore visibile — la stima verrebbe fuori lo
    stesso, solo piu' bassa, senza che nessuno lo dica.

    - `condizioni` diventa `stato_unita` (tre voci cambiano nome, quattro
      no); `degrado` sparisce, perche' era la stessa informazione;
    - `luminosita` ed `esposizione` diventano `luce_vista`: si prende la
      MEDIA dei due coefficienti di prima e si sceglie la voce nuova piu'
      vicina. E' meccanico e si puo' spiegare, che e' meglio di indovinare.

    Chi ha gia' i campi nuovi non viene toccato. Ritorna un dizionario
    nuovo: `scelte` non si modifica.
    """
    fuori = dict(scelte)

    if not fuori.get("stato_unita") and fuori.get("condizioni"):
        vecchia = str(fuori["condizioni"])
        fuori["stato_unita"] = CONDIZIONI_RINOMINATE.get(vecchia, vecchia)

    if not fuori.get("luce_vista"):
        luce = LUMINOSITA_STORICA.get(str(fuori.get("luminosita") or ""))
        vista = ESPOSIZIONE_STORICA.get(str(fuori.get("esposizione") or ""))
        presenti = [v for v in (luce, vista) if v is not None]
        if presenti:
            fuori["luce_vista"] = _piu_vicina(
                sum(presenti) / len(presenti), LUCE_VISTA)

    for sparita in ("condizioni", "degrado", "luminosita", "esposizione"):
        fuori.pop(sparita, None)
    return fuori


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
