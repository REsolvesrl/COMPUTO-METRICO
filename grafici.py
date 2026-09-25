"""I grafici del programma, fuori da Streamlit.

Sono le stesse funzioni di `streamlit_app.py` (barre del riepilogo costi,
torta delle spese, matrici di sensitivita'), copiate senza cambiare una
riga: costruiscono una figura Plotly, e la pagina nuova la disegna con lo
stesso Plotly. Stessi colori, stessi margini, stessa scala del pareggio.
"""
import plotly.graph_objects as go

from costanti import (COLORE_CATEGORIA_SPESA, COLORI_CATEGORIE, ETICHETTE,
                      GRIGLIA, OTTONE, TRAVERTINO)
from formato import colore_testo_su, euro, numero_it

ORO = OTTONE
CREMA = TRAVERTINO


def grafico_totali(totali):
    """Barre orizzontali: una barra, la tinta della sua categoria.

    Le stesse tinte delle schede e delle pastiglie del riepilogo: il colore
    qui non decora, è il modo in cui si riconosce una categoria in tutta la
    pagina. Con un solo oro per tutte, questo grafico era l'unico posto in
    cui bisognava rileggere l'etichetta per sapere di che si parla.
    """
    categorie = sorted(totali, key=totali.get)
    valori = [totali[c] for c in categorie]
    fig = go.Figure(go.Bar(
        x=valori,
        y=categorie,
        orientation="h",
        marker_color=[COLORI_CATEGORIE.get(c, (OTTONE, ""))[0]
                      for c in categorie],
        text=[euro(v) for v in valori],
        textposition="outside",
        textfont=dict(color=CREMA),
        cliponaxis=False,
        hovertemplate="%{y}: %{text}<extra></extra>",
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=80, t=10, b=10),
        height=max(200, 60 + 40 * len(categorie)),
        showlegend=False,
        font=dict(family='system-ui, -apple-system, "Segoe UI", sans-serif',
                  color=CREMA),
        xaxis=dict(showgrid=True, gridcolor=GRIGLIA, zeroline=False,
                   tickfont=dict(color=ETICHETTE)),
        yaxis=dict(showgrid=False, tickfont=dict(color=CREMA)),
    )
    return fig


def grafico_torta_spese(riepilogo):
    """Torta delle spese sostenute per categoria (importi lordi)."""
    categorie = list(riepilogo)
    valori = [riepilogo[c]["importo"] for c in categorie]
    colori = [COLORE_CATEGORIA_SPESA.get(c, ORO) for c in categorie]
    fig = go.Figure(go.Pie(
        labels=categorie,
        values=valori,
        marker=dict(colors=colori, line=dict(color="#1A2744", width=1)),
        textinfo="percent",
        # testo della % leggibile su ogni fetta (scuro sui chiari, crema sugli scuri)
        textfont=dict(color=[colore_testo_su(c) for c in colori], size=11),
        hovertemplate="%{label}: %{value:.2f} € (%{percent})<extra></extra>",
        sort=False,
    ))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=0, r=0, t=10, b=10),
        height=320,
        showlegend=True,
        legend=dict(font=dict(color=CREMA, size=10), orientation="v",
                    yanchor="middle", y=0.5, xanchor="left", x=1.0),
        font=dict(family='system-ui, -apple-system, "Segoe UI", sans-serif',
                  color=CREMA),
    )
    return fig


# Sotto questo money multiple la cella è rossa (26/09/2026: 1,10x, per
# tutti i progetti; prima era il pareggio, 1,00x).
SOGLIA_MULTIPLO = 1.10

# rosso → arancio → giallo alla soglia → verde (26/09/2026: prima il
# bianco stava alla soglia, e una matrice tutta sopra era solo verde)
ARANCIO = "#FFA84C"
GIALLO = "#FFEB84"


def grafico_sensitivita(prezzi_acquisto, prezzi_vendita, matrice, metrica,
                        base_acquisto=None, base_vendita=None, altezza=330):
    """Matrice di sensitività come mappa di calore stile Excel.

    Colori come la formattazione condizionale del foglio — minimo → rosso,
    massimo → verde — ma con il BIANCO sul PAREGGIO, non sulla mediana.
    L'Excel ancora il bianco al 50° percentile: è un rango relativo, e su
    una matrice tutta in utile finisce per dipingere di rosso salmone uno
    scenario da +25.900 € solo perché è il peggiore dei buoni. Su una
    schermata compra/non-compra il colore dev'essere un verdetto: sotto il
    pareggio si perde, sopra si guadagna. Il prezzo base di
    acquisto/vendita è evidenziato in
    **grassetto sull'etichetta nativa** dell'asse (non su una copia
    posizionata a mano): così l'allineamento con le altre etichette è
    garantito dal disegno stesso del grafico — uno spostamento in pixel
    stimato a occhio si è rivelato inaffidabile da un browser all'altro.
    Lo sfondo colorato del chip è un rettangolo agganciato alle coordinate
    dei DATI (colonna/riga esatta), non a coordinate di pagina che
    dipendono dalla larghezza della finestra.
    """
    if metrica == "multiplo":
        testo = [[numero_it(v, 2) + "x" for v in riga] for riga in matrice]
    else:
        testo = [[numero_it(v / 1000, 1) + "k" for v in riga]
                 for riga in matrice]
    piatti = sorted(v for riga in matrice for v in riga)
    minimo, massimo = piatti[0], piatti[-1]
    if minimo == massimo:
        minimo, massimo = minimo - 1, massimo + 1
    # la soglia del bianco: per il money multiple non il pareggio (1,00x) ma
    # SOGLIA_MULTIPLO — un'operazione che rende meno del 10% non vale il
    # rischio, e deve già dirlo in rosso; per il guadagno, 0 €
    pareggio = SOGLIA_MULTIPLO if metrica == "multiplo" else 0.0
    if pareggio <= minimo:
        # ogni scenario della matrice è in utile: dal pareggio in su
        scala = [[0.0, GIALLO], [1.0, "#63BE7B"]]
    elif pareggio >= massimo:
        # ogni scenario è in perdita: nessun verde da mostrare
        scala = [[0.0, "#F8696B"], [0.5, ARANCIO], [1.0, GIALLO]]
    else:
        frazione_bianco = (pareggio - minimo) / (massimo - minimo)
        scala = [[0.0, "#F8696B"], [frazione_bianco / 2, ARANCIO],
                 [frazione_bianco, GIALLO], [1.0, "#63BE7B"]]

    etichette_v = [numero_it(p / 1000, 0) + "k" for p in prezzi_vendita]
    etichette_a = [numero_it(p / 1000, 0) + "k" for p in prezzi_acquisto]

    def indice_base(prezzi, base):
        if base is None or not prezzi:
            return None
        return min(range(len(prezzi)), key=lambda i: abs(prezzi[i] - base))

    idx_a = indice_base(prezzi_acquisto, base_acquisto)
    idx_v = indice_base(prezzi_vendita, base_vendita)
    # grassetto sull'etichetta VERA (pseudo-html nativo di Plotly): stessa
    # posizione delle altre etichette per costruzione, zero rischio.
    if idx_v is not None:
        etichette_v[idx_v] = f"<b>{etichette_v[idx_v]}</b>"
    if idx_a is not None:
        etichette_a[idx_a] = f"<b>{etichette_a[idx_a]}</b>"

    fig = go.Figure(go.Heatmap(
        z=matrice, x=etichette_v, y=etichette_a,
        text=testo, texttemplate="%{text}",
        textfont=dict(size=11, color="#1A2744"),
        colorscale=scala, zmin=minimo, zmax=massimo, showscale=False,
        xgap=1, ygap=1,
        hovertemplate=("Acquisto %{y} · Vendita %{x}: %{text}"
                       "<extra></extra>"),
    ))
    # Margini in pixel (uguali a quelli di update_layout più sotto). In
    # coordinate "paper" y=1.0 è il bordo ALTO dell'area dati e x=0 il bordo
    # SINISTRO: le etichette vivono appena FUORI da lì, nei margini
    # (y>1.0 in alto, x<0 a sinistra). Il margine superiore va da y=1.0 a
    # y=1.0 + margine/area_dati; restarci dentro (2 px di sicurezza) evita
    # che il riquadro ad altezza fissa di Streamlit lo ritagli.
    margine_alto_px, margine_sx_px = 26, 48
    area_alto = altezza - margine_alto_px
    frazione_alto = (margine_alto_px - 2) / area_alto
    # sfondo azzurro DIETRO l'etichetta della colonna base (nel margine
    # superiore): xref="x" segue il dato (giusto a qualunque larghezza).
    if idx_v is not None:
        fig.add_shape(type="rect", xref="x", x0=idx_v - 0.5, x1=idx_v + 0.5,
                      yref="paper", y0=1.0, y1=1.0 + frazione_alto,
                      fillcolor="#DDEBF7", line=dict(width=0),
                      layer="below")
    # sfondo giallo dietro l'etichetta della riga base (margine sinistro):
    # yref="y" segue il dato; xref="paper" x<0 sta nel margine. Confermato
    # visivamente dall'utente che funziona.
    if idx_a is not None:
        fig.add_shape(type="rect", yref="y", y0=idx_a - 0.5, y1=idx_a + 0.5,
                      xref="paper", x0=-0.075, x1=0.005,
                      fillcolor="#FFF2CC", line=dict(width=0),
                      layer="below")
    # riquadro spesso sulla cella base (punto di riferimento della matrice):
    # solo coordinate dati, già robusto.
    if idx_a is not None and idx_v is not None:
        fig.add_shape(type="rect",
                      x0=idx_v - 0.5, x1=idx_v + 0.5,
                      y0=idx_a - 0.5, y1=idx_a + 0.5,
                      line=dict(color="#111111", width=3))
    fig.update_layout(
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        margin=dict(l=margine_sx_px, r=0, t=margine_alto_px, b=0),
        height=altezza,
        font=dict(family='system-ui, -apple-system, "Segoe UI", sans-serif',
                  color=CREMA),
        xaxis=dict(title=None, side="top", ticks="",
                   tickfont=dict(color=ETICHETTE)),
        yaxis=dict(title=None, autorange="reversed", ticks="",
                   tickfont=dict(color=ETICHETTE)),
    )
    return fig
