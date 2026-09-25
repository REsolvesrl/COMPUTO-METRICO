"""Dai numeri di prima ai numeri del listino nuovo (25 settembre 2026).

Il listino è stato rifatto unendo le voci di ENI e di La Spezia Migliarina,
e rinumerato categoria per categoria (vedi `listino.py`). Un progetto
salvato prima parla coi numeri di prima: il 2.1 di ieri e il 2.1 di oggi
possono essere due voci diverse. Qui lo si traduce, all'apertura.

Si riconosce dalla chiave «listino» del file: manca, o vale meno di
`listino.VERSIONE`, nei file di prima; c'è in quelli salvati dopo. Un file
già tradotto non si traduce una seconda volta — è il difetto che la
rinumerazione di agosto aveva rischiato, e il motivo della chiave.

⚠️ Tradurre non deve cambiare niente di quello che il progetto mostrava:
ogni voce del computo resta con la sua quantità, il suo prezzo, il suo
testo e la sua unità. Dove il progetto usava il valore del listino di
prima (non l'aveva riscritto), quel valore si scrive nel progetto, perché
nel listino nuovo la stessa voce può avere un altro prezzo o un altro
testo. Le voci scritte a mano (le «voci tue») che nel frattempo sono
entrate nel listino si riconoscono dalla descrizione e diventano quella
voce; le altre restano voci tue, e se il loro codice ora è di una voce del
listino ne prendono uno libero.
"""
import re

import listino
import listino_di_prima

# Il codice di ogni voce del listino di prima nel listino nuovo.
NUOVO_CODICE = {
    "1.1": "1.4",
    "1.2": "1.1",
    "1.3": "1.5",
    "1.4": "1.2",
    "1.5": "1.6",
    "1.6": "1.7",
    "1.7": "1.8",
    "1.8": "1.9",
    "1.9": "1.3",
    "1.10": "1.10",
    "1.11": "1.11",
    "2.1": "2.1",
    "2.2": "2.2",
    "2.3": "2.3",
    "2.4": "2.11",
    "2.5": "2.12",
    "2.6": "2.13",
    "2.7": "2.14",
    "2.8": "2.15",
    "2.9": "2.16",
    "2.10": "2.17",
    "3.1": "3.1",
    "3.2": "3.16",
    "3.3": "3.17",
    "3.4": "3.18",
    "3.5": "3.19",
    "3.6": "3.20",
    "3.7": "3.2",
    "3.8": "3.3",
    "3.9": "3.21",
    "3.10": "3.4",
    "3.11": "3.5",
    "3.12": "3.6",
    "3.13": "3.22",
    "3.14": "3.23",
    "3.15": "3.7",
    "3.16": "3.24",
    "3.17": "3.25",
    "3.18": "3.8",
    "3.19": "3.9",
    "3.20": "3.26",
    "3.21": "3.27",
    "3.22": "3.28",
    "3.23": "3.29",
    "3.24": "3.30",
    "3.30": "3.10",
    "4.1": "4.1",
    "4.2": "4.6",
    "4.3": "4.7",
    "4.4": "4.8",
    "4.5": "4.9",
    "4.6": "4.10",
    "4.7": "4.11",
    "4.8": "4.12",
    "4.9": "4.13",
    "4.10": "4.14",
    "4.11": "4.15",
    "4.12": "4.16",
    "4.13": "4.17",
    "5.1": "5.3",
    "5.2": "5.4",
    "5.3": "5.5",
    "5.4": "5.6",
    "5.5": "5.7",
    "6.1": "6.6",
    "6.2": "6.7",
    "6.3": "6.8",
    "6.4": "6.9",
    "6.5": "6.1",
    "7.1": "7.9",
    "7.2": "7.10",
    "8.1": "8.1",
    "8.2": "8.2",
    "8.3": "8.3",
    "8.4": "8.4",
    "8.5": "8.5",
    "8.6": "8.6",
    "8.7": "8.7",
    "8.8": "8.8",
    "8.9": "8.9",
    "8.10": "8.10",
    "8.11": "8.11",
    "8.12": "8.12",
    "8.13": "8.13",
    "9.1": "9.1",
    "9.2": "9.2",
    "9.3": "9.3",
    "9.4": "9.4",
    "9.5": "9.5",
    "9.6": "9.6",
    "9.7": "9.7",
    "9.8": "9.8",
    "9.9": "9.9",
    "9.10": "9.10",
    "9.11": "9.11",
}

# Le voci del listino nuovo nate da voci tue, con le descrizioni (ridotte a
# minuscole e spazi singoli) che avevano nei due cantieri: una voce tua di
# un file di prima con una di queste descrizioni, nella stessa categoria, è
# quella voce. La 3.5 si porta dietro anche la «posa pavimentazione
# terrazza», la 3.25 di prima, che era la stessa lavorazione.
VOCI_TUE_DIVENTATE_DEL_LISTINO = {'2.4': ('allestimento cantiere',),
 '2.5': ('demolizione completa bagno',),
 '2.6': ('bucatura solaio per installazione botola per installazione unità '
         'esterna climatizzatore',),
 '2.7': ('assistenza muraria impianto elettrico, riscaldamento canalizzato, '
         'idraulico',),
 '2.8': ('apertura bucatura soffitto e installazione botola ispezionabile per '
         'accesso sottotetto',),
 '2.9': ('svuotamento e tombamento vasca imhoff',),
 '2.10': ('demolizione scala interna pt-1° piano',),
 '3.5': ('posa pavimentazione terrazza con spessoratura e stuccatura finale '
         'compreso colle, stucchi.',),
 '3.11': ('tinteggiatura vano scale (1 mano, compresi materiali)',),
 '3.12': ('creazione tramezze interne in cartongesso con lana di roccia 5 cm, '
          "compreso il materiale necessario all'opera finita",),
 '3.13': ('pitturazione ringhiera balcone',),
 '3.14': ('ripristino scalini con sostituzione supporto in legno ammalorato, '
          'fissaggio marmo e applicazione resina riparativa',),
 '3.15': ('costruzione scala interna pt-1° piano',),
 '4.2': ('installazione impianto idrico completo di clarinetto con tubi in '
         'multistrato per cucina (lavabo)',),
 '4.3': ('installazione ventilazione bagno cieco',),
 '4.4': ('realizzazione di impianti di riscaldamento e raffrescamento in '
         'pompa di calore canalizzata a soffitto (nr.1 unità interna), '
         'incluso montaggio griglie/mascherine, sifoni, scarichi condensa e '
         "quanto altro occorre per dare l'opera finita a regola d'arte "
         'compreso di certificazione (no fornitura materiali)',),
 '4.5': ('scavo e allaccio fognatura pubblico con pozzetti di ispezione',),
 '5.1': ('realizzazione nr. 1 impianti elettrici, fibra, tv (2 punti), '
         'citofono, interruttori normali e deviati, prese bipasso, conforme '
         'alla norma cei 64-8 livello 1 con potenza fino a 6 kw, a partire '
         'dal centralino domestico con tubazioni di distribuzione antifiamma, '
         'realizzato sotto traccia con conduttori di adeguata sezione per '
         'impianto full electric. no fornitura frutti, supporti, placche e '
         'quadro elettrico',),
 '5.2': ('illuminazione aree esterne',),
 '6.2': ('installazione infissi e avvolgibili a filo interno muro (modalità '
         'aperture da definire) compresa riquadratura a dimensioni standard o '
         'come da progetto - sigillatura con schiuma elastica/acustica a '
         'bassa espansione - nastro sigillante autoespandente - profili e '
         'registrazione maniglieria (no fornitura)',
         'installazione solo infissi a filo interno muro (modalità aperture '
         'da definire) compresa riquadratura a dimensioni standard o come da '
         'progetto - sigillatura con schiuma elastica/acustica a bassa '
         'espansione - nastro sigillante autoespandente - profili e '
         'registrazione maniglieria (no fornitura)'),
 '6.3': ('sostituzione pannello interno porta blindata',),
 '6.4': ('posa in opera di porte interne e controtelai (no fornitura)',),
 '6.5': ('posa in opera di porte interne senza controtelaio (no fornitura)',),
 '7.1': ('installazione linea elettrica completa dal vano contatori al quadro '
         'elettrico compreso di opere murarie e quanto altro occorre per dare '
         "l'opera finita a regola d'arte",),
 '7.2': ('installazione linea idraulica completa dal vano contatori '
         "all'appartamento compreso di opere murarie e quanto altro occorre "
         "per dare l'opera finita a regola d'arte",),
 '7.3': ('installazione ascensore 3 piani',),
 '7.4': ('installazione ascensore esterno 3 piani',),
 '7.5': ('taglio alberi e sistemazione giardino',),
 '7.6': ('posa e fornitura recinzione esterna in alluminio alta 150cm',),
 '7.7': ('installazione e fornitura porta garage elettrica',),
 '7.8': ('installazione e fornitura cancello elettrico',),
 '8.14': ('rimozione di guaina bituminosa esistente compreso smaltimento in '
          'discarica',),
 '8.15': ('preparazione barriera al vapore - posa primer bituminoso',),
 '8.16': ('barriera al vapore bitume-alluminio saldata a fiamma',),
 '8.17': ('fornitura e posa pannelli pir sp.10 cm',),
 '8.18': ('impermeabilizzazione - primo strato in membrana di 4mm in '
          'poliestere',),
 '8.19': ('impermeabilizzazione - secondo strato in membrana ardesiata 4,5 '
          'kg/mq',),
 '9.12': ('rimozione del rivestimento lapideo e della malta di allettamento '
          'compresa discarica',),
 '9.13': ('rimozione dei davanzali esistenti',),
 '9.14': ('fornitura e posa zoccolatura con pannelli ad alta densità, h 80 '
          'cm',),
 '9.15': ('isolamento di spalle e architravi con pannelli da 2–3 cm',),
 '9.16': ('paraspigoli e gocciolatoi con rete',),
 '9.17': ('posa e fornitura nuovi davanzali in alluminio preverniciato, con '
          'testate',)}


def norma(testo):
    """Il testo senza differenze di spazi e maiuscole."""
    return re.sub(r"\s+", " ", (testo or "").strip()).casefold()


def da_tradurre(dati):
    """True se il file parla coi numeri di prima."""
    dati = dati or {}
    if int(dati.get("listino") or 0) >= listino.VERSIONE:
        return False
    return any(dati.get(chiave) for chiave in (
        "listino_stato", "testi_voci", "voci", "voci_scelte",
        "voci_scartate", "voci_a_mano"))


def _serie(categoria):
    if categoria in listino.CATEGORIE:
        return listino.CATEGORIE.index(categoria) + 1
    return len(listino.CATEGORIE) + 1


def traduci(dati):
    """Il progetto coi numeri del listino nuovo. Una copia: `dati` non si
    tocca. Un file che non va tradotto torna com'è."""
    if not da_tradurre(dati):
        return dati
    prima = {v["codice"]: v for v in listino_di_prima.VOCI}
    stato = dati.get("listino_stato") or {}
    testi = dati.get("testi_voci") or {}
    elenchi = {k: list(dati.get(k) or []) for k in
               ("voci_scelte", "voci_scartate", "voci_a_mano")}
    nuovo_stato, nuovi_testi = {}, {}
    mappa = {}          # codice di prima -> codice nuovo
    via = set()         # voci tue che non esistono più (doppioni vuoti)

    def scrivi(codice, q, p, descrizione, um):
        guida = listino.voce_per_codice(codice)
        nuovo_stato[codice] = {"q": q, "p": p}
        testo = {"d": None if norma(descrizione) == norma(guida["descrizione"])
                 else descrizione,
                 "u": None if (um or "") == guida["um"] else um}
        if testo["d"] or testo["u"]:
            nuovi_testi[codice] = testo

    # 1. le voci del listino di prima che il progetto tocca: col valore che
    # avevano — il suo, se l'aveva riscritto, se no quello del listino di
    # prima (un prezzo a zero valeva «quello del listino», come aprendo)
    toccate = set(stato) | set(testi)
    for elenco in elenchi.values():
        toccate |= set(elenco)
    for codice in toccate:
        voce = prima.get(codice)
        if voce is None:
            continue
        e, t = stato.get(codice) or {}, testi.get(codice) or {}
        mappa[codice] = NUOVO_CODICE[codice]
        scrivi(NUOVO_CODICE[codice], float(e.get("q") or 0.0),
               float(e.get("p", voce["prezzo"]) or voce["prezzo"]),
               t.get("d") or voce["descrizione"], t.get("u") or voce["um"])

    # 2. le voci tue
    restano = []
    for riga in dati.get("voci") or []:
        codice, categoria = riga.get("codice"), riga.get("categoria")
        valori = (float(riga.get("quantita_manuale") or 0.0),
                  float(riga.get("prezzo") or 0.0),
                  (riga.get("descrizione") or "").strip(), riga.get("um") or "")
        voce = prima.get(codice)
        if voce is not None and voce["categoria"] == categoria:
            # una voce tua passata al listino col suo codice (la 3.30 di ENI)
            mappa[codice] = NUOVO_CODICE[codice]
            scrivi(NUOVO_CODICE[codice], *valori)
            continue
        uguali = [n for n, descrizioni in VOCI_TUE_DIVENTATE_DEL_LISTINO.items()
                  if listino.voce_per_codice(n)["categoria"] == categoria
                  and norma(riga.get("descrizione")) in descrizioni]
        if uguali and uguali[0] not in nuovo_stato:
            mappa[codice] = uguali[0]
            scrivi(uguali[0], *valori)
            continue
        if (uguali and not valori[0]
                and codice not in elenchi["voci_scelte"]):
            via.add(codice)     # un doppione vuoto, fuori dal computo
            continue
        restano.append(dict(riga))

    # 3. le voci tue che restano: un codice che ora è del listino si cambia
    presi = {v["codice"] for v in listino.VOCI}
    for riga in restano:
        codice = riga.get("codice")
        if not codice:
            continue            # prenderà un codice caricando, come sempre
        if codice in presi:
            serie, n = _serie(riga.get("categoria")), 1
            while f"{serie}.{n}" in presi:
                n += 1
            mappa[codice] = riga["codice"] = f"{serie}.{n}"
        presi.add(riga["codice"])

    def traduci_elenco(elenco):
        fuori = []
        for codice in elenco:
            if codice in via:
                continue
            nuovo = mappa.get(codice, codice)
            if nuovo not in fuori:
                fuori.append(nuovo)
        return fuori

    tradotto = dict(dati)
    tradotto["listino_stato"] = nuovo_stato
    tradotto["testi_voci"] = nuovi_testi
    tradotto["voci"] = restano
    for chiave, elenco in elenchi.items():
        if dati.get(chiave) is not None:
            tradotto[chiave] = traduci_elenco(elenco)
    tradotto["listino"] = listino.VERSIONE
    return tradotto
