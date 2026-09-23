"""Le misure della planimetria: il nuovo deve dire esattamente quello che
dice il vecchio, campione per campione.

Sono i numeri che finiscono nel computo — pavimenti, battiscopa, pareti,
soffitti, rivestimenti, muri — con le detrazioni di porte, finestre, porte
finestra, locali rivestiti e aperture. Qui il programma vecchio gira davvero
(AppTest): se ne leggono i campioni (st.metric, con etichetta, valore e
detrazione) e le voci proposte al computo, e si confrontano con quello che
il nuovo manda alla pagina.

Si prova sui progetti veri della copia di prova e su varianti che accendono
ogni detrazione: se una formula agganciata al disegno cambia di un
centesimo fra i due programmi, qui si vede.
"""
import copy
import json
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import banco
from formato import numero_it
from server import vista

SORGENTE = Path(__file__).resolve().parent.parent / "streamlit_app.py"
PROVA_VERA = Path.home() / "CME" / "prova" / "progetti"

FISSE = {"Superficie commerciale", "Pavimento", "Battiscopa", "Tinteggiatura",
         "Muri da demolire", "Muri da costruire", "Superficie reale totale",
         "Superficie commerciale totale", "Pavimento (interni)", "Soffitti",
         "Pavimento esterno (balconi, terrazzi)", "→ superficie"}
PREFISSI = ("Pareti (h ", "Rivestimenti (fascia h ", "🔴 ", "🟡 ", "🟢 ")


def _della_planimetria(etichetta):
    return etichetta in FISSE or etichetta.startswith(PREFISSI)


def _dal_vecchio(dati, monkeypatch, cartella):
    monkeypatch.setenv("CME_ARCHIVIO", str(cartella))
    at = AppTest.from_file(str(SORGENTE), default_timeout=300)
    at.run()
    at.session_state["da_caricare"] = copy.deepcopy(dati)
    at.run()
    assert not at.exception, at.exception
    metriche = [(m.label, m.value, m.delta or "") for m in at.metric
                if _della_planimetria(m.label)]
    voci = [c.label for c in at.checkbox if " → **" in c.label]
    conti = [m.value for m in at.markdown if "| Come si calcola | Quanto |"
             in m.value]
    return metriche, voci, conti


def _dal_nuovo(dati):
    """Gli stessi campioni, costruiti come li costruisce web/planimetria.js."""
    b = banco.Banco()
    b.carica(copy.deepcopy(dati))
    p = vista.vista(b)["planimetria"]
    n2 = lambda v: numero_it(v, 2)                         # noqa: E731
    m = []
    for x in p.get("vicino", []):
        m.append((x["nome"], f"{n2(x['valore'])} {x['um']}", ""))
    s = p.get("superfici")
    if s and s["righe"]:
        m.append(("Superficie reale totale", f"{n2(s['totale'])} m²", ""))
        m.append(("Superficie commerciale totale",
                  f"{n2(s['commerciale'])} m²", ""))
    q = p.get("quantita")
    if q:
        f = p["finiture"]
        m += [("Pavimento (interni)", f"{n2(q['pavimento'])} m²", ""),
              ("Battiscopa", f"{n2(q['battiscopa'])} m",
               f"−{n2(q['detr_ml'])} m vani" if q["detr_ml"] else ""),
              (f"Pareti (h {n2(p['altezza'])} m)", f"{n2(q['pareti'])} m²",
               f"−{n2(q['detr_m2'])} m² vani e rivestimenti"
               if q["detr_m2"] else ""),
              ("Soffitti", f"{n2(q['soffitti'])} m²", ""),
              ("Pavimento esterno (balconi, terrazzi)",
               f"{n2(q['pavimento_esterno'])} m²", ""),
              (f"Rivestimenti (fascia h {n2(f['riv_alt'])} m)",
               f"{n2(q['rivestimenti'])} m²",
               f"−{n2(q['detr_riv'])} m² vani" if q["detr_riv"] else "")]
    muri = p.get("muri")
    if muri:
        for tipo, segno, nome in (("demolire", "🔴", "Da demolire"),
                                  ("costruire", "🟡", "Da costruire"),
                                  ("cartongesso", "🟢", "In cartongesso")):
            w = muri[tipo]
            m.append((f"{segno} {nome} ({w['n']})", f"{n2(w['ml'])} m", ""))
            m.append(("→ superficie", f"{n2(w['netto'])} m²",
                      f"−{n2(w['aperture'])} m² aperture"
                      if w["aperture"] else ""))
    voci = []
    for v in p.get("dal_disegno", {}).get("voci", []):
        etichetta = (f"**{v['codice']}** · {v['descrizione']} → "
                     f"**{n2(v['quantita'])} {v['um']}**")
        if v["attuale"] and abs(v["attuale"] - v["quantita"]) > 0.005:
            etichetta += f" :orange[(sostituisce {n2(v['attuale'])})]"
        voci.append(etichetta)
    # «Il conto in chiaro», scritto come lo scrive _scaletta nel vecchio
    conti = []
    for sez in (p.get("conto") or {}).get("sezioni", []):
        righe = [f"| {sez['intestazione']} | Come si calcola | Quanto |",
                 "|---|---|---:|"]
        righe += [f"| {a} | {b} | {c} |" for a, b, c in sez["righe"]]
        righe.append(f"| **Totale** | | **{sez['totale']}** |")
        conti.append("\n".join(righe))
    return m, voci, conti


def _confronta(dati, monkeypatch, tmp_path):
    vecchie, voci_vecchie, conti_vecchi = _dal_vecchio(dati, monkeypatch,
                                                       tmp_path)
    nuove, voci_nuove, conti_nuovi = _dal_nuovo(dati)
    assert vecchie, "il vecchio non ha misure: il progetto non ha disegni?"
    assert sorted(nuove) == sorted(vecchie)
    assert voci_nuove == voci_vecchie
    assert conti_vecchi and conti_nuovi == conti_vecchi


def _progetti():
    return sorted(PROVA_VERA.glob("*.json")) if PROVA_VERA.is_dir() else []


def _con_disegni(file):
    dati = json.loads(file.read_text(encoding="utf-8"))
    if not any(p.get("zone") or p.get("pareti")
               for p in dati.get("piante") or []):
        pytest.skip("progetto senza disegni")
    return dati


# Ogni detrazione accesa, e un bagno rivestito: le varianti toccano tutti i
# rami di quantita_finiture e dei muri.
VARIANTI = {
    "porte_e_finestre": {"porta_n": 5, "porta_n_est": 1, "fin_n": 4,
                         "pf_n": 2, "porta_larg": 0.9, "porta_alt": 2.2},
    "rivestiti": {"riv_porte_n": 2, "riv_finestre_n": 1, "riv_alt": 2.4,
                  "porta_n": 3},
    "aperture_nei_muri": {"apert_dem_n": 2, "apert_cos_n": 1,
                          "apert_car_n": 1, "apert_larg": 1.0,
                          "apert_alt": 2.3},
}


@pytest.mark.parametrize("file", _progetti(), ids=lambda f: f.stem)
def test_le_misure_sono_quelle_del_vecchio(file, monkeypatch, tmp_path):
    _confronta(_con_disegni(file), monkeypatch, tmp_path)


@pytest.mark.parametrize("variante", sorted(VARIANTI))
@pytest.mark.parametrize("file", _progetti(), ids=lambda f: f.stem)
def test_le_detrazioni_sono_quelle_del_vecchio(file, variante, monkeypatch,
                                               tmp_path):
    dati = _con_disegni(file)
    dati.setdefault("finiture", {}).update(VARIANTI[variante])
    dati["altezza_locali"] = 2.85
    if variante == "rivestiti":
        # il primo locale interno diventa un bagno rivestito, col battiscopa
        for p in dati["piante"]:
            for z in p["zone"]:
                if z.get("categoria") == "Superficie interna":
                    z.update(rivestito=True, battiscopa=True)
                    break
    _confronta(dati, monkeypatch, tmp_path)
