"""Il punto di partenza di ogni computo nuovo: il cantiere di La Spezia Migliarina.

«Nuovo progetto» non apre più un foglio bianco: apre queste voci, con i
testi e i prezzi che su Migliarina sono stati scritti a mano. Il listino
guida resta com'è — è il catalogo, generico per definizione — mentre qui
sta il modo in cui RESolve descrive e paga davvero le lavorazioni, che
altrimenti andrebbe riscritto da capo a ogni cantiere.

Le quantità partono tutte da zero: sono del cantiere, non del modello.
Una voce a zero resta a video («da quantificare») ma fuori da totali e
stampa, quindi il modello non mette mai un euro nel computo da solo.
"""
import copy

# Le voci nel computo, nell'ordine di Migliarina.
VOCI_SCELTE = [
    "2.11", "3.1", "1.2", "1.4", "1.9", "2.1", "2.2", "3.8", "3.10", "2.3",
    "4.1", "4.14", "5.6", "4.16", "3.12", "6.6", "6.5", "6.7", "6.8", "2.12",
    "3.11", "3.15", "7.3", "7.4", "3.7", "3.18", "2.14", "3.19", "3.26",
    "6.9", "2.15", "3.28",
]

# Voci del listino guida: il prezzo usato su Migliarina.
PREZZI = {
    "2.1": 35.0,
    "2.2": 35.0,
    "2.3": 400.0,
    "3.1": 120.0,
    "3.7": 85.0,
    "3.8": 80.0,
    "3.10": 48.0,
    "3.11": 48.0,
    "3.12": 55.0,
    "3.15": 10.0,
    "3.18": 25.0,
    "3.19": 10.0,
    "4.1": 330.0,
    "6.5": 350.0,
}

# Voci del listino guida: la descrizione (e l'unità) riscritte su Migliarina.
TESTI = {
    "2.1": {
        "d": "Demolizione pavimento compreso il trasporto dei materiali di risulta e ogni altro onere, discarica compresa",
        "u": "",
    },
    "2.2": {
        "d": "Demolizione tramezze interne, compreso il trasporto dei materiali di risulta e ogni altro onere, discarica compresa",
        "u": "",
    },
    "2.3": {
        "d": "Demolizione rivestimenti cucina, compreso il trasporto dei materiali di risulta e ogni altro onere, discarica compresa",
        "u": "a corpo",
    },
    "3.1": {
        "d": "Creazione tramezze divisorie in laterizio 10 cm con creazione intonaco e applicazione pannello fonoassorbente (no fornitura), compreso il materiale necessario all'opera finita",
        "u": "m²",
    },
    "3.7": {
        "d": "Realizzazione controsoffitti in cartongesso",
        "u": "m²",
    },
    "3.8": {
        "d": "Creazione tramezze interne in cartongesso normale/idro  10 cm finiti con lana di roccia, compreso il materiale necessario all'opera finita",
        "u": "",
    },
    "3.10": {
        "d": "Posa in opera della pavimentazione anche medio/grandi formati,  con spessoratura e stuccatura finale compreso colle, stucchi e se necessario massetto autolivellante.",
        "u": "m²",
    },
    "3.11": {
        "d": "Posa pavimentazione esterna (balconi e terrazzi) con spessoratura",
        "u": "m²",
    },
    "3.12": {
        "d": "Posa in opera dei rivestimenti anche medio/grandi formati, con spessoratura e stuccatura finale",
        "u": "m²",
    },
    "3.15": {
        "d": "Posa in opera del battiscopa perimetrale altezze e materiali vari",
        "u": "ml",
    },
    "3.18": {
        "d": "Rasatura a civile muri compresa carteggiatura (2 mani, compresi materiali)",
        "u": "m²",
    },
    "3.19": {
        "d": "Tinteggiatura muri e soffitti (2 mani, compresi materiali)",
        "u": "m²",
    },
    "4.1": {
        "d": "Installazione impianto idrico e di scarico completo di clarinetto con tubi multistrato in bagno, compreso montaggio dei sanitari, lavabo, termoarredo, box doccia e boiler (no fornitura) - 4,5 punti acqua per bagno + lavatrice",
        "u": "punto acqua",
    },
    "6.5": {
        "d": "Posa in quota porta blindata e controtelaio",
        "u": "cad",
    },
}

# Le voci scritte a mano su Migliarina. Quelle che non stanno in
# VOCI_SCELTE finiscono nel pool, pronte da ripescare.
VOCI_TUE = [
    {
        "codice": "2.11",
        "categoria": "Demolizioni",
        "um": "a corpo",
        "prezzo": 2500.0,
        "descrizione": "Allestimento cantiere",
    },
    {
        "codice": "3.25",
        "categoria": "Ricostruzioni e ripristini",
        "um": "m²",
        "prezzo": 48.0,
        "descrizione": "Posa pavimentazione terrazza con spessoratura e stuccatura finale compreso colle, stucchi.",
    },
    {
        "codice": "2.12",
        "categoria": "Demolizioni",
        "um": "a corpo",
        "prezzo": 1500.0,
        "descrizione": "Demolizione completa bagno",
    },
    {
        "codice": "4.14",
        "categoria": "Idraulico",
        "um": "utenza",
        "prezzo": 330.0,
        "descrizione": "Installazione impianto idrico completo di clarinetto con tubi in multistrato per cucina (lavabo)",
    },
    {
        "codice": "4.15",
        "categoria": "Idraulico",
        "um": "a corpo",
        "prezzo": 330.0,
        "descrizione": "Installazione ventilazione bagno cieco",
    },
    {
        "codice": "5.6",
        "categoria": "Elettricista",
        "um": "punto",
        "prezzo": 60.0,
        "descrizione": "Realizzazione nr. 1 impianti elettrici, fibra, TV (2 punti), citofono, interruttori normali e deviati, prese bipasso, conforme alla Norma CEI 64-8 Livello 1 con potenza fino a 6 kW, a partire dal centralino domestico con tubazioni di distribuzione antifiamma, realizzato sotto traccia con conduttori di adeguata sezione per impianto full electric. NO fornitura frutti, supporti, placche e quadro elettrico",
    },
    {
        "codice": "4.16",
        "categoria": "Idraulico",
        "um": "a corpo",
        "prezzo": 800.0,
        "descrizione": "Realizzazione di impianti di riscaldamento e raffrescamento in pompa di calore canalizzata a soffitto (nr.1 unità interna), incluso montaggio griglie/mascherine, sifoni, scarichi condensa e quanto altro occorre per dare l'opera finita a regola d'arte compreso di certificazione (no fornitura materiali)",
    },
    {
        "codice": "6.6",
        "categoria": "Serramenti",
        "um": "cad",
        "prezzo": 150.0,
        "descrizione": "Installazione solo infissi a filo interno muro (modalità aperture da definire) compresa riquadratura a dimensioni standard o come da progetto - sigillatura con schiuma elastica/acustica a bassa espansione - nastro sigillante autoespandente - profili e registrazione maniglieria (no fornitura)",
    },
    {
        "codice": "6.7",
        "categoria": "Serramenti",
        "um": "cad",
        "prezzo": 50.0,
        "descrizione": "Sostituzione pannello interno porta blindata",
    },
    {
        "codice": "6.8",
        "categoria": "Serramenti",
        "um": "cad",
        "prezzo": 120.0,
        "descrizione": "Posa in opera di porte interne e controtelai (no fornitura)",
    },
    {
        "codice": "3.26",
        "categoria": "Ricostruzioni e ripristini",
        "um": "m²",
        "prezzo": 5.0,
        "descrizione": "Tinteggiatura vano scale (1 mano, compresi materiali)",
    },
    {
        "codice": "7.3",
        "categoria": "Aree esterne",
        "um": "punto",
        "prezzo": 323.33,
        "descrizione": "Installazione linea elettrica completa dal vano contatori al quadro elettrico compreso di opere murarie e quanto altro occorre per dare l'opera finita a regola d'arte",
    },
    {
        "codice": "7.4",
        "categoria": "Aree esterne",
        "um": "punto",
        "prezzo": 400.0,
        "descrizione": "Installazione linea idraulica completa dal vano contatori all'appartamento compreso di opere murarie e quanto altro occorre per dare l'opera finita a regola d'arte",
    },
    {
        "codice": "2.13",
        "categoria": "Demolizioni",
        "um": "a corpo",
        "prezzo": 500.0,
        "descrizione": "Bucatura solaio per installazione botola per installazione unità esterna climatizzatore",
    },
    {
        "codice": "3.27",
        "categoria": "Ricostruzioni e ripristini",
        "um": "m²",
        "prezzo": 80.0,
        "descrizione": "Creazione tramezze interne in cartongesso con lana di roccia 5 cm, compreso il materiale necessario all'opera finita",
    },
    {
        "codice": "2.14",
        "categoria": "Demolizioni",
        "um": "a corpo",
        "prezzo": 7000.0,
        "descrizione": "Assistenza muraria impianto elettrico, riscaldamento canalizzato, idraulico",
    },
    {
        "codice": "6.9",
        "categoria": "Serramenti",
        "um": "a corpo",
        "prezzo": 60.0,
        "descrizione": "Posa in opera di porte interne senza controtelaio (no fornitura)",
    },
    {
        "codice": "2.15",
        "categoria": "Demolizioni",
        "um": "a corpo",
        "prezzo": 1000.0,
        "descrizione": "Apertura bucatura soffitto e installazione botola ispezionabile per accesso sottotetto",
    },
    {
        "codice": "3.28",
        "categoria": "Ricostruzioni e ripristini",
        "um": "a corpo",
        "prezzo": 300.0,
        "descrizione": "Pitturazione ringhiera balcone",
    },
]


def progetto_nuovo():
    """Il modello nel formato di un progetto salvato, pronto da caricare."""
    return copy.deepcopy({
        "voci_scelte": VOCI_SCELTE,
        "listino_stato": {c: {"q": 0.0, "p": p} for c, p in PREZZI.items()},
        "testi_voci": TESTI,
        "voci": [dict(v, quantita_manuale=0.0) for v in VOCI_TUE],
    })
