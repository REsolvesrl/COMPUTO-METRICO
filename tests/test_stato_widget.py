"""Guardia contro il difetto che ha piantato «Svuota tutto» (2026-08-08).

Streamlit vieta di riscrivere lo stato di un widget DOPO che il widget è
stato creato: solleva «cannot be modified after the widget is instantiated»
e l'app muore davanti all'utente. È un errore che non si vede leggendo il
codice — la riga incriminata sembra innocua — e che i test funzionali
scoprono solo se qualcuno preme proprio quel bottone.

Questo controllo legge il sorgente e cerca il motivo, non il sintomo.
Rimedio quando scatta: spostare la riscrittura dentro una funzione usata
come `on_click`, dove Streamlit la consente.
"""
import re
from pathlib import Path

SORGENTE = Path(__file__).resolve().parent.parent / "streamlit_app.py"


def _righe():
    return SORGENTE.read_text(encoding="utf-8").splitlines()


def _chiavi_widget(righe):
    """{chiave: prima riga in cui nasce il widget con quella chiave}."""
    chiavi = {}
    for n, riga in enumerate(righe, 1):
        for m in re.finditer(r'key\s*=\s*f?["\']([^"\'{}]+)["\']', riga):
            chiavi.setdefault(m.group(1), n)
    return chiavi


def _dentro_funzione(righe, n):
    """True se la riga n sta dentro un def (lì la riscrittura è lecita)."""
    for i in range(n - 1, 0, -1):
        riga = righe[i - 1]
        if riga.startswith(("def ", "@")):
            return True
        if riga and not riga[0].isspace() and not riga.startswith(
                ("#", ")", "]", "}")):
            return False
    return False


def test_nessuna_riscrittura_di_widget_dopo_la_creazione():
    righe = _righe()
    chiavi = _chiavi_widget(righe)
    colpevoli = []
    for n, riga in enumerate(righe, 1):
        for m in re.finditer(
                r'st\.session_state(?:\.(\w+)|\[["\'](\w+)["\']\])\s*=(?!=)',
                riga):
            chiave = m.group(1) or m.group(2)
            if chiave not in chiavi:
                continue
            if n > chiavi[chiave] and not _dentro_funzione(righe, n):
                colpevoli.append(
                    f"riga {n}: scrive «{chiave}», widget creato alla riga "
                    f"{chiavi[chiave]} — {riga.strip()[:70]}")
    assert not colpevoli, (
        "Riscrittura di stato di widget dopo la loro creazione: Streamlit "
        "solleva un'eccezione e l'app si pianta. Spostala in una callback "
        "on_click.\n" + "\n".join(colpevoli))


def test_la_guardia_riconosce_il_difetto():
    """La guardia serve solo se sa accorgersi del caso che deve impedire."""
    finto = [
        'x = st.checkbox("conferma", key="conf_prova")',
        'if st.button("vai"):',
        '    st.session_state.conf_prova = False',
    ]
    chiavi = _chiavi_widget(finto)
    assert chiavi == {"conf_prova": 1}
    assert not _dentro_funzione(finto, 3)
