"""Le costanti del motore nuovo sono quelle del programma vecchio, una per una.

`streamlit_app.py` non si puo' importare (farebbe partire la pagina), quindi
lo si legge come testo: ogni costante che `costanti.py` copia si ricalcola
dal sorgente vecchio e deve venire identica.
"""
import ast
from pathlib import Path

import merito

import costanti

SORGENTE = Path(__file__).resolve().parent.parent / "streamlit_app.py"


def _costanti_del_vecchio():
    testo = SORGENTE.read_text(encoding="utf-8-sig")
    albero = ast.parse(testo)
    spazio = {"merito": merito}
    trovate = {}
    for nodo in albero.body:
        if (isinstance(nodo, ast.Assign) and len(nodo.targets) == 1
                and isinstance(nodo.targets[0], ast.Name)
                and hasattr(costanti, nodo.targets[0].id)):
            nome = nodo.targets[0].id
            exec(compile(ast.Module([nodo], []), "vecchio", "exec"), spazio)
            trovate[nome] = spazio[nome]
    return trovate


def test_ogni_costante_e_identica_a_quella_del_programma_vecchio():
    vecchie = _costanti_del_vecchio()
    nuove = {n: v for n, v in vars(costanti).items()
             if n.isupper() and not n.startswith("_")}
    assert set(nuove) == set(vecchie)
    for nome, valore in nuove.items():
        assert valore == vecchie[nome], nome
