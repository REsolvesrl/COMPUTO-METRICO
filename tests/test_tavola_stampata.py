"""Che cosa va, e che cosa NON va, sulla planimetria che si stampa.

La tavola stampata non è lo schermo su carta: va in cantiere, e chi la
guarda ha in mano un metro, non un listino. Le targhette delle aree si
compongono in `etichetta_zona`, ma quale riga ci finisca lo decide chi
chiama — a video le impostazioni dell'utente, in stampa le decide
`pdf_planimetrie_bytes`.

La percentuale è il caso che conta: dice quanto di quella superficie fa
mercato, serve a valutare un immobile e non a costruirlo. Su una tavola dei
lavori è un numero senza mestiere — e per giunta il perimetro commerciale,
che è quello a cui la percentuale si riferisce, da quel foglio è già
escluso. Finisce dentro l'immagine PNG, quindi dal PDF non si rilegge: la
si controlla dove viene decisa, cioè nel sorgente.
"""
import ast
from pathlib import Path

SORGENTE = Path(__file__).resolve().parent.parent / "streamlit_app.py"


def _funzione(nome):
    albero = ast.parse(SORGENTE.read_text(encoding="utf-8-sig"))
    for nodo in ast.walk(albero):
        if isinstance(nodo, ast.FunctionDef) and nodo.name == nome:
            return nodo
    raise AssertionError(f"{nome} non c'è più in streamlit_app.py")


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
    percento = _impostazioni_etichette("pdf_planimetrie_bytes")["percento"]
    assert isinstance(percento, ast.Constant) and percento.value is False


def test_nome_e_metri_sulla_tavola_restano_a_scelta():
    """Quelli sì che servono in cantiere, e li comanda l'utente: se
    diventassero costanti anche loro, le spunte sopra la tela non
    varrebbero più niente per la stampa."""
    impostazioni = _impostazioni_etichette("pdf_planimetrie_bytes")
    for chiave in ("nome", "m2", "perimetro"):
        assert isinstance(impostazioni[chiave], ast.Attribute), (
            f"«{chiave}» non arriva più dalle impostazioni dell'utente")
