"""Come si scrivono numeri, importi e colori. Niente Streamlit, niente pandas.

Vivevano dentro streamlit_app.py, ma non hanno niente a che fare con
l'interfaccia: servono anche a chi stampa il PDF e a chiunque debba mettere
una cifra sotto gli occhi di qualcuno. Qui sono pure e sotto test.

Convenzione italiana: punto per le migliaia, virgola per i decimali —
1.234,56 €. È il formato che l'utente legge su ogni documento di cantiere,
e sbagliarlo su un computo significa leggere mille volte tanto.
"""


def _vuoto(valore):
    """True per i valori che non sono un numero da scrivere.

    Accetta anche i «non-numero» di pandas (NaN) senza importarlo: NaN è
    l'unico valore che non è uguale a sé stesso.
    """
    if valore is None:
        return True
    return valore != valore          # NaN


def numero_it(valore, decimali=3):
    """Il numero all'italiana: 1.234,568 (vuoto se non c'è)."""
    if _vuoto(valore):
        return ""
    testo = f"{valore:,.{decimali}f}"
    # si passa da un segnaposto perché virgola e punto vanno scambiati fra
    # loro: sostituirli uno dopo l'altro li farebbe collassare entrambi
    return testo.replace(",", "X").replace(".", ",").replace("X", ".")


def euro(valore):
    """L'importo all'italiana con la sua unità: 1.234,56 €."""
    if _vuoto(valore):
        return ""
    return f"{numero_it(valore, 2)} €"


def numero_da_it(testo):
    """Rilegge un numero scritto all'italiana. None se non è un numero.

    Serve ai campi in cui l'utente scrive: `st.number_input` non sa
    raggruppare le migliaia (accetta solo formati printf), quindi i campi
    degli importi sono caselle di testo — e questa funzione è ciò che le
    rende dei numeri.

    Accetta come lo scriverebbe una persona: `1.234,56`, `1234,56`,
    `1.234`, `1234`, con o senza `€`, con o senza spazi.

    ⚠️ Il punto è ambiguo: in `1.234` separa le migliaia, in `1234.56`
    separa i decimali. La regola, quando manca la virgola: **è separatore
    di migliaia solo se raggruppa a tre a tre** (`1.234`, `1.234.567`);
    altrimenti vale come virgola decimale, così anche chi digita
    all'inglese ottiene il numero che intendeva.
    """
    if testo is None:
        return None
    ripulito = (str(testo).replace("€", "").replace("%", "")
                .replace(" ", "").replace(" ", "").strip())
    if not ripulito:
        return None
    if "," in ripulito:
        ripulito = ripulito.replace(".", "").replace(",", ".")
    elif "." in ripulito:
        pezzi = ripulito.lstrip("+-").split(".")
        migliaia = (len(pezzi) > 1 and pezzi[0] != ""
                    and all(len(p) == 3 for p in pezzi[1:]))
        if migliaia:
            ripulito = ripulito.replace(".", "")
    try:
        return float(ripulito)
    except ValueError:
        return None


def colore_testo_su(colore_hex):
    """Colore di testo leggibile su uno sfondo dato.

    ⚠️ Si chiamava `testo_su`: pytest raccoglie come test qualunque funzione
    il cui nome cominci per «test», quindi provava a eseguirla chiedendo un
    argomento che nessuno le passava. Il nome nuovo dice la stessa cosa e
    non fa inciampare nessuno.

    Fra ardesia scura e travertino vince chi stacca di più dal fondo, col
    contrasto vero delle linee guida WCAG. Serve dove il fondo lo sceglie
    l'utente — le categorie di spesa — e un testo fisso finirebbe prima o
    poi illeggibile. Prima si guardava la luminosità percepita con una soglia
    fissa, e sul viola dei Serramenti usciva il travertino a 2,98:1.
    """
    def luce(esadecimale):
        h = esadecimale.lstrip("#")
        canali = [int(h[i:i + 2], 16) / 255 for i in (0, 2, 4)]
        r, g, b = [c / 12.92 if c <= 0.03928 else ((c + 0.055) / 1.055) ** 2.4
                   for c in canali]
        return 0.2126 * r + 0.7152 * g + 0.0722 * b

    fondo = luce(colore_hex)

    def contrasto(testo):
        chiaro, scuro = sorted((luce(testo), fondo), reverse=True)
        return (chiaro + 0.05) / (scuro + 0.05)

    return max(("#1A2744", "#ECE7DA"), key=contrasto)
