"""Che cosa va, e che cosa NON va, sulla planimetria che si stampa.

La tavola stampata non è lo schermo su carta: va in cantiere, e chi la
guarda ha in mano un metro, non un listino. Le targhette delle aree si
compongono in `etichetta_zona`, ma quale riga ci finisca lo decide chi
chiama — a video le impostazioni dell'utente, in stampa le decide
`pdf_planimetrie` (banco_disegno.py).

La percentuale è il caso che conta: dice quanto di quella superficie fa
mercato, serve a valutare un immobile e non a costruirlo. Su una tavola dei
lavori è un numero senza mestiere — e per giunta il perimetro commerciale,
che è quello a cui la percentuale si riferisce, da quel foglio è già
escluso. Finisce dentro l'immagine PNG, quindi dal PDF non si rilegge: la
si controlla dove viene decisa, cioè nel sorgente.
"""
import ast
from pathlib import Path

import pytest

import stampa
import tavola

SORGENTE = Path(__file__).resolve().parent.parent / "banco_disegno.py"


def _funzione(nome):
    albero = ast.parse(SORGENTE.read_text(encoding="utf-8-sig"))
    for nodo in ast.walk(albero):
        if isinstance(nodo, ast.FunctionDef) and nodo.name == nome:
            return nodo
    raise AssertionError(f"{nome} non c'è più in banco_disegno.py")


def _impostazioni_etichette(nome_funzione):
    """Il dizionario `impostazioni` costruito dentro quella funzione."""
    for nodo in ast.walk(_funzione(nome_funzione)):
        if (isinstance(nodo, ast.Assign)
                and any(getattr(b, "id", None) == "impostazioni"
                        for b in nodo.targets)
                and isinstance(nodo.value, ast.Dict)):
            return {chiave.value: valore
                    for chiave, valore in zip(nodo.value.keys,
                                              nodo.value.values)}
    raise AssertionError(f"in {nome_funzione} non si compone più "
                         "«impostazioni»")


def test_sulla_tavola_stampata_niente_percentuali():
    """Serve a valutare, non a costruire: sul foglio di cantiere non va."""
    percento = _impostazioni_etichette("pdf_planimetrie")["percento"]
    assert isinstance(percento, ast.Constant) and percento.value is False


def test_nome_e_metri_sulla_tavola_restano_a_scelta():
    """Quelli sì che servono in cantiere, e li comanda l'utente: se
    diventassero costanti anche loro, le spunte sopra la tela non
    varrebbero più niente per la stampa."""
    impostazioni = _impostazioni_etichette("pdf_planimetrie")
    for chiave in ("nome", "m2", "perimetro"):
        assert not isinstance(impostazioni[chiave], ast.Constant), (
            f"«{chiave}» non arriva più dalle impostazioni dell'utente")


def test_la_scala_della_pianta_arriva_al_disegno_stampato():
    """Senza mpp la barra di scala non compare, e sparirebbe in silenzio:
    il PDF verrebbe lo stesso, solo senza la cosa che permette di misurare
    con un righello quello che sul foglio non è quotato."""
    chiamate = [n for n in ast.walk(_funzione("pdf_planimetrie"))
                if isinstance(n, ast.Call)
                and isinstance(n.func, ast.Attribute)
                and n.func.attr == "disegna"]
    assert chiamate, "la tavola non si disegna più da pdf_planimetrie"
    passati = {k.arg for k in chiamate[0].keywords}
    assert "mpp" in passati, "la scala non arriva più alla tavola stampata"


# ------------------- il foglio è del disegno (2/10/2026)

def _png_tavola(larg, alt):
    import io
    from PIL import Image
    buffer = io.BytesIO()
    Image.new("RGB", (larg, alt), "white").save(buffer, format="PNG")
    return buffer.getvalue()


def _misura_del_disegno(pdf):
    """Quanto del foglio si prende il disegno, in percentuale."""
    import fitz
    doc = fitz.open(stream=pdf, filetype="pdf")
    pagina = doc[0]
    rettangoli = pagina.get_image_rects(pagina.get_images()[0][0])
    disegno = max(rettangoli, key=lambda r: r.get_area())
    foglio = pagina.rect
    return (disegno.width, disegno.height,
            100 * disegno.get_area() / (foglio.width * foglio.height),
            doc.page_count)


PROGETTO_TAVOLA = {"nome": "Prova", "committente": "Rossi",
                   "oggetto": "Ristrutturazione", "data": "02/10/2026"}
MISURE_TAVOLA = [("Pavimento (interni)", "94,62 m²"),
                 ("Battiscopa", "96,09 m"), ("Pareti (h 2,70 m)", "413,22 m²"),
                 ("Soffitti", "94,62 m²"), ("Muri da demolire", "12,70 m²")]


def test_sul_foglio_steso_il_disegno_prende_quasi_tutta_la_pagina():
    """Era il 43% del foglio: testata alta, colonna larga, margini da
    documento di testo. Adesso sta sopra il 65%."""
    tavole = [{"nome": "Piano secondo", "png": _png_tavola(1600, 1100),
               "legenda": [("Da demolire", "#FFD400")]}]
    _, _, percento, pagine = _misura_del_disegno(stampa.pdf_planimetrie(
        PROGETTO_TAVOLA, tavole, MISURE_TAVOLA, orizzontale=True))
    assert percento > 65
    assert pagine == 1


def test_sul_foglio_in_piedi_il_disegno_arriva_ai_margini():
    """Una pianta larga, in verticale, è limitata dalla LARGHEZZA del
    foglio: il disegno deve arrivarci, meno i cinque millimetri di
    margine."""
    tavole = [{"nome": "Piano secondo", "png": _png_tavola(1600, 1100),
               "legenda": []}]
    larghezza, _, _, pagine = _misura_del_disegno(stampa.pdf_planimetrie(
        PROGETTO_TAVOLA, tavole, MISURE_TAVOLA))
    from reportlab.lib.pagesizes import A4
    from reportlab.lib.units import mm
    assert larghezza == pytest.approx(A4[0] - 2 * 5 * mm, abs=1)
    assert pagine == 1


def test_una_pianta_per_pagina_anche_strette_e_alte():
    """Il disegno non deve scivolare alla pagina dopo: due piante, due
    pagine, non tre o quattro mezze vuote."""
    tavole = [{"nome": f"Piano {n}", "png": _png_tavola(1100, 1600),
               "legenda": [("Da costruire", "#E53935")]} for n in range(2)]
    for orizzontale in (False, True):
        pdf = stampa.pdf_planimetrie(PROGETTO_TAVOLA, tavole, MISURE_TAVOLA,
                                     orizzontale=orizzontale)
        import fitz
        assert fitz.open(stream=pdf, filetype="pdf").page_count == 2


def test_le_targhette_sulla_pianta_sono_piu_piccole_e_lasciano_posto():
    """Le targhette stanno FUORI dal disegno: il margine che si prendono è
    margine tolto alla pianta."""
    from PIL import Image
    pianta = Image.new("RGB", (900, 650), "white")
    zone = [{"punti": [[50, 50], [400, 50], [400, 300], [50, 300]],
             "colore": "#E57373", "etichetta": "Camera matrimoniale\n14,19 m²",
             "etichetta_pos": [-260, 100]}]
    composta = tavola.disegna(pianta, zone)
    # col corpo di prima (20 px su una pianta da 900) il foglio composto era
    # più largo: meno pianta, a parità di foglio stampato
    prima = tavola.disegna(pianta, zone, dimensione_testo=20)
    assert composta.size[0] < prima.size[0]
