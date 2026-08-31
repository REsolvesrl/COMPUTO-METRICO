"""Geometria pura per la misura delle superfici da planimetria.

Nessuna dipendenza da Streamlit o da immagini: solo coordinate in pixel
e conversioni in metri. Tutta la logica misurabile vive qui; l'interfaccia
(upload, disegno, overlay) sta in streamlit_app.py.

Convenzioni:
- un punto è una coppia (x, y) in pixel;
- "metri per pixel" (mpp) è il fattore di scala: metri_reali = pixel × mpp;
  di conseguenza le aree si convertono con mpp² (metri quadri = pixel² × mpp²).
"""

import math


def distanza_pixel(p1, p2):
    """Distanza euclidea in pixel tra due punti (x, y)."""
    return math.hypot(p2[0] - p1[0], p2[1] - p1[1])


def metri_per_pixel(lunghezza_pixel, lunghezza_reale_m):
    """Fattore di scala a partire da una misura nota.

    lunghezza_pixel: lunghezza in pixel del segmento tracciato sul disegno.
    lunghezza_reale_m: quanto vale quel segmento nella realtà, in metri.
    """
    if lunghezza_pixel <= 0:
        raise ValueError("La lunghezza in pixel deve essere positiva.")
    if lunghezza_reale_m <= 0:
        raise ValueError("La misura reale deve essere positiva.")
    return lunghezza_reale_m / lunghezza_pixel


def calibra_da_due_punti(p1, p2, lunghezza_reale_m):
    """Metri per pixel calibrando su un segmento noto (due punti cliccati)."""
    return metri_per_pixel(distanza_pixel(p1, p2), lunghezza_reale_m)


def area_poligono_pixel(punti):
    """Area di un poligono in pixel² con la formula di Gauss ("shoelace").

    Il poligono si intende chiuso (l'ultimo punto si ricollega al primo);
    non serve ripetere il primo punto in fondo. Restituisce sempre un valore
    non negativo, indipendentemente dal verso (orario/antiorario) dei punti.
    """
    if len(punti) < 3:
        return 0.0
    somma = 0.0
    for i in range(len(punti)):
        x1, y1 = punti[i]
        x2, y2 = punti[(i + 1) % len(punti)]
        somma += x1 * y2 - x2 * y1
    return abs(somma) / 2.0


def perimetro_poligono_pixel(punti):
    """Perimetro di un poligono chiuso, in pixel."""
    if len(punti) < 2:
        return 0.0
    return sum(
        distanza_pixel(punti[i], punti[(i + 1) % len(punti)])
        for i in range(len(punti))
    )


def area_reale_m2(punti, mpp):
    """Superficie reale in m² del poligono, dato il fattore di scala mpp."""
    return round(area_poligono_pixel(punti) * mpp * mpp, 3)


def perimetro_reale_m(punti, mpp):
    """Perimetro reale in metri del poligono, dato il fattore di scala mpp."""
    return round(perimetro_poligono_pixel(punti) * mpp, 3)


def punto_in_poligono(punto, punti):
    """True se il punto (x, y) cade dentro il poligono (ray casting)."""
    x, y = punto
    dentro = False
    n = len(punti)
    j = n - 1
    for i in range(n):
        xi, yi = punti[i][0], punti[i][1]
        xj, yj = punti[j][0], punti[j][1]
        if (yi > y) != (yj > y) and x < (xj - xi) * (y - yi) / (yj - yi) + xi:
            dentro = not dentro
        j = i
    return dentro


def posiziona_etichette(zone, larghezza, altezza, trasparenti=()):
    """Posizioni predefinite delle etichette: FUORI dalle aree, ma vicine.

    zone: [{"id", "punti", "etichetta_pos" (opzionale)}, ...]. Per ogni zona
    senza posizione personalizzata si prova, in ordine, un punto a destra,
    sinistra, sopra, sotto e agli angoli del suo riquadro: vince il primo
    che non cade dentro NESSUNA zona, resta nell'immagine e non si accavalla
    alle etichette già piazzate. Se nessun candidato va bene si ripiega sul
    baricentro (dentro l'area).

    trasparenti: nomi di categoria che non «occupano» spazio (il perimetro
    commerciale, che spesso copre tutto il disegno): un'etichetta può
    starci sopra, altrimenti non troverebbe più un posto libero.

    Ritorna {id: [x, y]} solo per le zone senza posizione personalizzata.
    """
    trasparenti = set(trasparenti)
    piene = [z for z in zone
             if (z.get("categoria") or "") not in trasparenti]
    piazzate = [tuple(z["etichetta_pos"]) for z in zone
                if z.get("etichetta_pos")]
    distacco_x = larghezza * 0.05
    distacco_y = altezza * 0.055
    dx_min = larghezza * 0.085          # ingombro tipico di un'etichetta
    dy_min = altezza * 0.05
    margine = larghezza * 0.01
    risultato = {}

    for zona in zone:
        if zona.get("etichetta_pos"):
            continue
        punti = zona.get("punti") or []
        if len(punti) < 3:
            continue
        xs = [p[0] for p in punti]
        ys = [p[1] for p in punti]
        x0, x1, y0, y1 = min(xs), max(xs), min(ys), max(ys)
        cx, cy = (x0 + x1) / 2, (y0 + y1) / 2
        candidati = [
            (x1 + distacco_x, cy), (x0 - distacco_x, cy),
            (cx, y0 - distacco_y), (cx, y1 + distacco_y),
            (x1 + distacco_x, y0), (x0 - distacco_x, y0),
            (x1 + distacco_x, y1), (x0 - distacco_x, y1),
        ]

        def valido(px, py, controlla_distanza):
            if not (margine <= px <= larghezza - margine
                    and margine <= py <= altezza - margine):
                return False
            if any(punto_in_poligono((px, py), q.get("punti") or [])
                   for q in piene if len(q.get("punti") or []) >= 3):
                return False
            if controlla_distanza and any(
                    abs(px - ox) < dx_min and abs(py - oy) < dy_min
                    for ox, oy in piazzate):
                return False
            return True

        scelto = None
        for con_distanza in (True, False):
            for px, py in candidati:
                if valido(px, py, con_distanza):
                    scelto = (px, py)
                    break
            if scelto:
                break
        if scelto is None:
            scelto = (cx, cy)
        risultato[zona["id"]] = [round(scelto[0], 1), round(scelto[1], 1)]
        piazzate.append(scelto)
    return risultato


def riepilogo_locali(piante, escludi=()):
    """Elenco per-locale (zona) delle piante con scala: superficie e perimetro.

    Serve per battiscopa (metri lineari) e tinteggiature (perimetro × altezza
    per le pareti, superficie calpestabile per i soffitti).

    escludi: nomi di categoria che NON sono locali da lavorare (es. il
    perimetro commerciale, che serve solo a misurare la superficie vendibile):
    restano fuori da questo elenco e quindi da tutte le quantità del computo.

    Ritorna (righe, senza_scala). Ogni riga: {"pianta", "uid", "id", "nome",
    "categoria", "m2", "perimetro"} — nome = nome della zona o, se assente,
    la categoria. Le piante senza scala finiscono in senza_scala.
    """
    righe = []
    senza_scala = []
    escludi = set(escludi)
    for pianta in piante:
        zone = [z for z in (pianta.get("zone") or [])
                if (z.get("categoria") or "") not in escludi]
        if not zone:
            continue
        mpp = pianta.get("mpp")
        nome_pianta = pianta.get("nome") or "Planimetria"
        if not mpp:
            senza_scala.append(nome_pianta)
            continue
        for zona in zone:
            punti = zona.get("punti") or []
            righe.append({
                "pianta": nome_pianta,
                "uid": pianta.get("uid"),
                "id": zona.get("id"),
                "nome": zona.get("nome") or zona.get("categoria") or "Zona",
                "categoria": zona.get("categoria") or "",
                "m2": area_reale_m2(punti, mpp),
                "perimetro": perimetro_reale_m(punti, mpp),
            })
    return righe, senza_scala


def quantita_finiture(locali, altezza, larghezza_porta=0.0, altezza_porta=0.0,
                      n_porte=0, altezza_rivestimento=0.0, n_porte_esterne=0,
                      aperture=(), n_porte_rivestiti=0,
                      n_finestre_rivestiti=0, larghezza_finestra=0.0,
                      altezza_finestra=0.0):
    """Quantità nette di pavimenti, battiscopa, pareti, soffitti, rivestimenti.

    locali: [{"m2", "perimetro", "pavimento", "battiscopa", "pittura",
    "rivestito", "esterno"}] — le spunte dicono che cosa si rifà in quel
    locale; `esterno` dice se è un balcone, un terrazzo o una loggia.

    Il pavimento esce in DUE quantità, e non è un capriccio: la pavimentazione
    di un balcone non è quella di una camera — vuole la spessoratura, la
    pendenza, spesso un gres diverso — e ha un prezzo suo. Sommandole si
    finiva per computare i metri del balcone al prezzo del gres da interni.

    Quello che sta FUORI resta fuori anche da battiscopa, pareti e soffitti:
    un balcone non ha zoccolino e non lo si tinteggia insieme alle stanze.
    Finché ci entrava, i soffitti risultavano più grandi del pavimento —
    98,42 contro 94,71 su un progetto vero — e la differenza era esattamente
    il balcone: un numero che non si spiegava guardando la pianta.

    I RIVESTIMENTI (la fascia piastrellata di bagni e cucine) escono come
    quantità positiva, non solo come detrazione della tinteggiatura: sono
    perimetro × `altezza_rivestimento` dei locali spuntati «rivestito».

    Detrazioni applicate:
    - i locali RIVESTITI (bagni, fasce di cucina) non hanno battiscopa: il
      loro perimetro non entra nel conteggio;
    - nei locali rivestiti la fascia alta `altezza_rivestimento` non si rasa
      né si tinteggia: si toglie perimetro × altezza_rivestimento;
    - i VANI PORTA non hanno battiscopa e non si tinteggiano. Una porta
      INTERNA affaccia su due locali, quindi interrompe il battiscopa di
      qua e di là e toglie superficie a due pareti: conta per DUE lati.
      Il portoncino d'ingresso (n_porte_esterne) ne ha uno solo, perché
      l'altra faccia è fuori dall'appartamento.

    aperture: le altre bucature del muro, [{"n", "larghezza", "altezza",
    "battiscopa"}, ...] — finestre e porte finestra. Stanno su un muro
    perimetrale, quindi affacciano su UN SOLO locale: contano un lato solo,
    a differenza della porta interna. Tolgono sempre `n × larghezza ×
    altezza` alla parete da rasare e tinteggiare; tolgono anche `n ×
    larghezza` al battiscopa **solo se** `battiscopa` è vero — la finestra
    ha il davanzale in alto e il battiscopa ci passa sotto indisturbato, la
    porta finestra invece arriva a terra e lo interrompe.

    Le detrazioni non possono portare sotto zero. Ritorna anche i valori
    lordi e le detrazioni, per poterli mostrare.
    """
    h = float(altezza or 0.0)
    h_riv = float(altezza_rivestimento or 0.0)
    lati = 2 * max(0, int(n_porte or 0)) + max(0, int(n_porte_esterne or 0))
    larg_p = float(larghezza_porta or 0.0)
    alt_p = float(altezza_porta or 0.0)

    # Della porta e della finestra si toglie solo la parte che cade DENTRO
    # la fascia rivestita: un vano porta alto 2,10 su una fascia da 1,20
    # toglie 0,80 × 1,20, non 0,80 × 2,10. Togliere il vano intero sarebbe
    # una detrazione più grande del muro da cui si detrae.
    detr_riv_porte = (max(0, int(n_porte_rivestiti or 0))
                      * float(larghezza_porta or 0.0)
                      * min(float(altezza_porta or 0.0), h_riv))
    detr_riv_finestre = (max(0, int(n_finestre_rivestiti or 0))
                         * float(larghezza_finestra or 0.0)
                         * min(float(altezza_finestra or 0.0), h_riv))

    detr_aperture_ml = detr_aperture_m2 = 0.0
    for apertura in aperture:
        n = max(0, int(apertura.get("n") or 0))
        larghezza = float(apertura.get("larghezza") or 0.0)
        altezza_ap = float(apertura.get("altezza") or 0.0)
        detr_aperture_m2 += n * larghezza * altezza_ap
        if apertura.get("battiscopa"):
            detr_aperture_ml += n * larghezza

    pavimento = pavimento_esterno = 0.0
    battiscopa_lordo = pareti_lorde = soffitti = 0.0
    detr_rivestimenti = 0.0
    for locale in locali:
        m2 = float(locale.get("m2") or 0.0)
        perimetro = float(locale.get("perimetro") or 0.0)
        rivestito = bool(locale.get("rivestito"))
        esterno = bool(locale.get("esterno"))
        if locale.get("pavimento"):
            if esterno:
                pavimento_esterno += m2
            else:
                pavimento += m2
        if esterno:
            continue          # fuori: niente zoccolino, niente tinteggiatura
        if locale.get("battiscopa") and not rivestito:
            battiscopa_lordo += perimetro
        if locale.get("pittura"):
            pareti_lorde += perimetro * h
            soffitti += m2
            if rivestito:
                detr_rivestimenti += perimetro * h_riv

    detr_porte_ml = larg_p * lati
    detr_porte_m2 = larg_p * alt_p * lati
    return {
        "lati_porta": lati,
        "pavimento": round(pavimento, 3),
        "pavimento_esterno": round(pavimento_esterno, 3),
        "rivestimenti": round(max(0.0, detr_rivestimenti - detr_riv_porte
                                  - detr_riv_finestre), 3),
        "rivestimenti_lordi": round(detr_rivestimenti, 3),
        "detr_riv_porte": round(detr_riv_porte, 3),
        "detr_riv_finestre": round(detr_riv_finestre, 3),
        "battiscopa": round(max(0.0, battiscopa_lordo - detr_porte_ml
                                - detr_aperture_ml), 3),
        "battiscopa_lordo": round(battiscopa_lordo, 3),
        "pareti": round(max(0.0, pareti_lorde - detr_rivestimenti
                            - detr_porte_m2 - detr_aperture_m2), 3),
        "pareti_lorde": round(pareti_lorde, 3),
        "soffitti": round(soffitti, 3),
        "detr_porte_ml": round(detr_porte_ml, 3),
        "detr_porte_m2": round(detr_porte_m2, 3),
        "detr_aperture_ml": round(detr_aperture_ml, 3),
        "detr_aperture_m2": round(detr_aperture_m2, 3),
        "detr_rivestimenti": round(detr_rivestimenti, 3),
    }


def riepilogo_pareti(piante, altezza):
    """Muri tracciati, raggruppati per tipo di intervento (demolire/costruire).

    piante: [{"nome", "mpp", "pareti": [{"tipo", "p1", "p2"}]}].
    altezza: altezza dei muri in metri (la superficie è lunghezza × altezza:
    è così che si computano demolizioni e ricostruzioni murarie).

    Ritorna ({tipo: {"n", "ml", "m2"}}, senza_scala): le planimetrie senza
    scala non sono misurabili e finiscono in senza_scala.
    """
    totali = {}
    senza_scala = []
    h = float(altezza or 0.0)
    for pianta in piante:
        pareti = pianta.get("pareti") or []
        if not pareti:
            continue
        mpp = pianta.get("mpp")
        if not mpp:
            senza_scala.append(pianta.get("nome") or "Planimetria")
            continue
        for parete in pareti:
            tipo = parete.get("tipo") or "esistente"
            metri = distanza_pixel(parete["p1"], parete["p2"]) * mpp
            voce = totali.setdefault(tipo, {"n": 0, "ml": 0.0, "m2": 0.0})
            voce["n"] += 1
            voce["ml"] += metri
            voce["m2"] += metri * h
    return ({tipo: {"n": v["n"], "ml": round(v["ml"], 3),
                    "m2": round(v["m2"], 3)}
             for tipo, v in totali.items()}, senza_scala)


def superficie_aperture(n, larghezza, altezza):
    """Superficie complessiva di n vani uguali, in m².

    Si dichiara QUANTE aperture ci sono e quanto misura la porta tipo
    (0,80 × 2,10 nelle case): i m² li fa l'app. Un numero negativo — che
    non vuol dire niente — vale zero.
    """
    return round(max(0, int(n or 0)) * float(larghezza or 0.0)
                 * float(altezza or 0.0), 3)


def muri_al_netto(m2, aperture_m2):
    """Superficie di muro da demolire (o costruire) tolte le sue bucature.

    Il muro si misura pieno (lunghezza × altezza): dove c'è una porta o una
    finestra non c'è muratura da buttare giù né da tirare su. Qui si toglie
    la superficie dei vani, dichiarata dall'utente in m², senza mai andare
    sotto zero — un'apertura più grande del muro è un errore di battitura,
    non una quantità negativa da portare nel computo.
    """
    return round(max(0.0, float(m2 or 0.0) - float(aperture_m2 or 0.0)), 3)


def voci_da_riscrivere(mappa, grandezze, attuali, escluse=(),
                       tolleranza=0.005):
    """Quali voci del computo la planimetria deve riscrivere, e con quanto.

    È il cuore del collegamento automatico: si confronta quello che il disegno
    misura ORA con quello che c'è già nel computo, e si restituiscono solo le
    voci che cambierebbero davvero. Chiamandola a ogni giro, il computo segue
    il disegno da sé; restituendo un dizionario VUOTO quando non è cambiato
    niente, dice anche quando NON serve rifare il giro.

    mappa: [(codice_voce, nome_grandezza), ...] — quale misura alimenta quale
        voce di listino (es. ("1.02", "muri_demolire")).
    grandezze: {nome_grandezza: quantità misurata sul disegno}.
    attuali: {codice_voce: quantità già nel computo}.
    escluse: codici da non toccare — chi ha scritto una quantità a mano ha
        deciso lui, e il disegno non gliela riscrive sopra.
    tolleranza: sotto questa differenza si considera già a posto (evita di
        rincorrere l'ultimo centesimo all'infinito).

    Le quantità NULLE non si scrivono: una misura che non c'è (nessun muro
    tracciato) non deve cancellare un numero battuto a mano.
    """
    escluse = set(escluse)
    da_scrivere = {}
    for codice, grandezza in mappa:
        if codice in escluse:
            continue
        quantita = round(float(grandezze.get(grandezza) or 0.0), 2)
        if quantita <= 0:
            continue
        attuale = float(attuali.get(codice) or 0.0)
        if abs(attuale - quantita) > tolleranza:
            da_scrivere[codice] = quantita
    return da_scrivere


def superficie_calpestabile(piante, percentuali, escludi=()):
    """I metri quadri che si calpestano davvero: le stanze, e basta.

    È il denominatore giusto del **costo di ristrutturazione al metro**. La
    superficie commerciale non lo è: comprende i balconi al 30%, il vano
    scale al 50% e il perimetro d'ingombro, cioè superfici che si vendono
    ma che non si ristrutturano. Dividere il costo dei lavori per la
    commerciale fa uscire un €/mq **più basso del vero** — e su quel numero
    si decide se comprare.

    Sono calpestabili le zone la cui categoria vale il 100% (le stanze
    interne); le altre pesano meno proprio perché non sono pavimento su cui
    si cammina. `escludi` toglie le categorie d'involucro, che non sono
    locali ma il contorno del fabbricato.

    Ritorna (m2, senza_scala): le planimetrie non calibrate non sono
    misurabili e si segnalano invece di sparire in silenzio.
    """
    totale = 0.0
    senza_scala = []
    escludi = set(escludi)
    for pianta in piante:
        zone = [z for z in (pianta.get("zone") or [])
                if (z.get("categoria") or "") not in escludi
                and _regola(percentuali, z.get("categoria") or "")[0] >= 100.0]
        if not zone:
            continue
        mpp = pianta.get("mpp")
        if not mpp:
            senza_scala.append(pianta.get("nome") or "Planimetria")
            continue
        for zona in zone:
            totale += area_reale_m2(zona.get("punti") or [], mpp)
    return round(totale, 2), senza_scala


def superficie_commerciale(m2, percento, soglia=None, percento_oltre=None):
    """Superficie commerciale di una superficie accessoria, a scaglioni.

    Le superfici di ornamento (balconi, terrazzi, giardini…) valgono la loro
    incidenza piena solo fino a una certa estensione: l'eccedenza pesa molto
    meno. Es. 40 m² di terrazzo al 35% con soglia 25 e eccedenza al 10%:
    25 × 35% + 15 × 10% = 10,25 m².

    Senza soglia (o senza percentuale sull'eccedenza) si applica la sola
    incidenza piena, come per le superfici principali.
    """
    m2 = float(m2 or 0.0)
    piena = float(percento or 0.0) / 100.0
    if not soglia or percento_oltre is None or m2 <= float(soglia):
        return round(m2 * piena, 3)
    soglia = float(soglia)
    eccedenza = m2 - soglia
    return round(soglia * piena
                 + eccedenza * float(percento_oltre) / 100.0, 3)


def _regola(percentuali, categoria):
    """(percento, soglia, percento_oltre) per una categoria.

    percentuali accetta sia {nome: 35.0} sia
    {nome: {"percento": 35, "soglia": 25, "oltre": 10}}.
    """
    valore = percentuali.get(categoria, 100.0)
    if isinstance(valore, dict):
        return (float(valore.get("percento", 100.0)),
                valore.get("soglia"), valore.get("oltre"))
    return float(valore), None, None


def riepilogo_superfici(piante, percentuali, escludi=()):
    """Riepilogo delle superfici di tutte le planimetrie di un progetto.

    piante: elenco di dizionari {"nome", "mpp", "zone": [{"categoria", "punti"}]}.
    percentuali: {nome_categoria: percento} — il peso "commerciale" di ogni
        categoria (es. balcone 30). Le categorie sconosciute valgono 100.
    escludi: categorie che non fanno superficie commerciale (le stanze
        interne, quando la parte vendibile si misura col perimetro esterno:
        contarle entrambe significherebbe contare due volte lo stesso spazio).

    Ritorna (righe, totale_m2, totale_commerciale, senza_scala):
    - righe: aggregate per (pianta, categoria) con numero di zone, m² reali,
      percento e m² commerciali (reali × percento / 100);
    - senza_scala: nomi delle piante con zone ma senza scala impostata,
      escluse dai totali.
    """
    righe = []
    totale_m2 = 0.0
    totale_comm = 0.0
    senza_scala = []
    escludi = set(escludi)
    for pianta in piante:
        nome = pianta.get("nome") or "Planimetria"
        mpp = pianta.get("mpp")
        zone = [z for z in (pianta.get("zone") or [])
                if (z.get("categoria") or "") not in escludi]
        if not zone:
            continue
        if not mpp:
            senza_scala.append(nome)
            continue
        gruppi = {}
        for zona in zone:
            categoria = zona.get("categoria") or "Senza categoria"
            gruppo = gruppi.setdefault(categoria, {"zone": 0, "m2": 0.0})
            gruppo["zone"] += 1
            gruppo["m2"] += area_reale_m2(zona.get("punti") or [], mpp)
        for categoria, gruppo in gruppi.items():
            percento, soglia, oltre = _regola(percentuali, categoria)
            m2 = round(gruppo["m2"], 3)
            # la soglia vale sul totale della categoria in quella pianta:
            # è l'unità immobiliare ad avere diritto ai primi 25 m² pieni,
            # non ogni singolo balcone
            m2_comm = superficie_commerciale(m2, percento, soglia, oltre)
            righe.append({
                "pianta": nome,
                "categoria": categoria,
                "zone": gruppo["zone"],
                "percento": percento,
                "m2": m2,
                "m2_commerciale": m2_comm,
            })
            totale_m2 += m2
            totale_comm += m2_comm
    return righe, round(totale_m2, 2), round(totale_comm, 2), senza_scala
