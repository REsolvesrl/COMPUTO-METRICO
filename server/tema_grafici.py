"""Il tema che Streamlit mette sui grafici Plotly, rifatto uguale.

Streamlit non disegna le figure come arrivano: prima ci stende un suo tema
(il «template» streamlit, completato nel browser coi colori del tema
dell'app). La pagina nuova le riceveva col tema predefinito di Plotly, e le
differenze si vedevano: il riquadro che compare passando il mouse era
pieno del colore della barra, le scritte dell'asse toccavano le barre.

I valori qui sotto sono letti dal programma vecchio acceso
(`el.layout.template.layout` del grafico del riepilogo costi), non
ricordati: fondo e riquadro in ardesia, bordo travertino al 20%, 8 px di
distanza fra le scritte e il grafico (`margin.pad`).
"""
import plotly.graph_objects as go

# Il carattere delle tabelle e dei riquadri di Streamlit; se non c'è,
# ripiega su quello del programma.
CARATTERE = '"Source Sans", "Segoe UI", system-ui, sans-serif'

TEMA = go.layout.Template(layout={
    "font": {"color": "#e6eaf1", "family": CARATTERE, "size": 12,
             "weight": 400},
    "title": {"font": {"family": CARATTERE, "size": 16, "color": "#ECE7DA"},
              "pad": {"l": 4}, "xanchor": "left", "x": 0},
    "legend": {"title": {"font": {"size": 12, "color": "#e6eaf1"},
                         "side": "top"},
               "valign": "top", "bordercolor": "rgba(0,0,0,0)",
               "borderwidth": 0, "font": {"size": 12, "color": "#fafafa"}},
    "paper_bgcolor": "#1A2744",
    "plot_bgcolor": "#1A2744",
    "yaxis": {"ticklabelposition": "outside", "zerolinecolor": "#31333F",
              "title": {"font": {"color": "#e6eaf1", "size": 14},
                        "standoff": 24},
              "tickcolor": "#31333F",
              "tickfont": {"color": "#e6eaf1", "size": 12},
              "gridcolor": "#31333F", "minor": {"gridcolor": "#31333F"},
              "automargin": True},
    "xaxis": {"zerolinecolor": "#31333F", "gridcolor": "#31333F",
              "showgrid": False,
              "tickfont": {"color": "#e6eaf1", "size": 12},
              "tickcolor": "#31333F",
              "title": {"font": {"color": "#e6eaf1", "size": 14},
                        "standoff": 20},
              "minor": {"gridcolor": "#31333F"}, "zeroline": False,
              "automargin": True},
    "margin": {"pad": 8, "r": 0, "l": 0},
    "hoverlabel": {"bgcolor": "#1A2744",
                   "bordercolor": "rgba(236, 231, 218, 0.2)",
                   "font": {"color": "#e6eaf1", "family": CARATTERE,
                            "size": 12}},
    "colorway": ["#83c9ff", "#0068c9", "#ffabab", "#ff2b2b", "#7defa1",
                 "#29b09d", "#ffd16a", "#ff8700", "#6d3fc0", "#d5dae5"],
})


def con_tema(fig):
    """La figura col tema di Streamlit al posto di quello di Plotly."""
    fig.update_layout(template=TEMA)
    return fig
