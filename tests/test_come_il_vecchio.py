"""Il nuovo dice ancora quello che diceva il programma vecchio.

Finché i due programmi convivevano, il vecchio (Streamlit) girava nei test
e ogni progetto aperto e salvato dall'uno doveva uscire uguale dall'altro,
campione per campione anche sulla planimetria. Il 25/09/2026 il vecchio se
n'è andato; prima, i progetti di prova qui sotto li ha calcolati un'ultima
volta, e quello che ha detto sta in `dati/riferimento_vecchio.json`:

- il file salvato (senza le immagini, che il vecchio ricodificava in JPEG a
  ogni apertura);
- i campioni della planimetria: pavimenti, battiscopa, pareti, soffitti,
  rivestimenti, muri, con le loro detrazioni;
- le voci che il disegno propone al computo, con le quantità;
- «il conto in chiaro», riga per riga.

I progetti sono inventati — nessun file vero finisce nel repository: un
progetto dei formati di prima, il modello di un progetto nuovo, e un
appartamento con ogni categoria di zona, i muri dei quattro tipi, porte,
finestre, porte finestra, un bagno rivestito, nelle varianti che accendono
ogni detrazione; più lo stesso appartamento con la 3.30 al posto della 3.11.

⚠️ Se una regola cambia APPOSTA, questo test si rompe: è giusto. Si
corregge il riferimento a mano, per la sola voce cambiata, e il messaggio
del commit dice perché il nuovo ora dice un'altra cosa.
"""
import copy
import json
from pathlib import Path

import pytest

import banco
import banco_disegno
import listino
import listino_di_prima
import rinumerazione
from formato import numero_it
from server import vista

RIFERIMENTO = json.loads(
    (Path(__file__).resolve().parent / "dati" / "riferimento_vecchio.json")
    .read_text(encoding="utf-8"))
CON_DISEGNO = sorted(n for n, r in RIFERIMENTO.items() if "metriche" in r)


@pytest.fixture(autouse=True)
def _il_listino_di_allora(monkeypatch):
    """Il vecchio faceva i conti col listino di prima del 25/09/2026, e i
    progetti di prova parlano coi suoi numeri: qui il motore li rifà con
    quello, senza tradurli. Si prova la logica, non il listino."""
    monkeypatch.setattr(listino, "VOCI", listino_di_prima.VOCI)
    for modulo in (banco, banco_disegno):
        monkeypatch.setattr(modulo, "VOCI_DA_SUPERFICI",
                            listino_di_prima.VOCI_DA_SUPERFICI)
    monkeypatch.setattr(banco, "ALTERNATIVE_DAL_DISEGNO",
                        listino_di_prima.ALTERNATIVE_DAL_DISEGNO)
    monkeypatch.setattr(rinumerazione, "traduci", lambda dati: dati)


# Campi del business plan nati dopo il vecchio (i materiali, 26/09/2026):
# nel file ci sono, nel riferimento no.
CAMPI_NUOVI_BP = ("bp_materiali", "bp_iva_materiali")


def _senza_immagini(dati):
    dati = json.loads(json.dumps(dati))
    for p in dati.get("piante") or []:
        p.pop("immagine", None)
    dati.pop("listino", None)       # la numerazione: il vecchio non l'aveva
    for campo in CAMPI_NUOVI_BP:
        (dati.get("business_plan") or {}).pop(campo, None)
    return dati


def _salvato_dal_nuovo(dati, cartella, monkeypatch):
    monkeypatch.setenv("CME_ARCHIVIO", str(cartella))
    b = banco.Banco()
    b.carica(copy.deepcopy(dati))
    nome = b.salva()
    return json.loads((cartella / f"{nome}.json").read_text(encoding="utf-8"))


def _campioni_del_nuovo(dati):
    """I campioni della planimetria, scritti come li scriveva il vecchio
    (st.metric: etichetta, valore, detrazione) e come li costruisce
    web/planimetria.js."""
    b = banco.Banco()
    b.carica(copy.deepcopy(dati))
    p = vista.vista(b)["planimetria"]
    n2 = lambda v: numero_it(v, 2)                         # noqa: E731
    m = []
    for x in p.get("vicino", []):
        m.append((x["nome"], f"{n2(x['valore'])} {x['um']}", ""))
    s = p.get("superfici")
    if s and s["righe"]:
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
    conti = []
    for sez in (p.get("conto") or {}).get("sezioni", []):
        righe = [f"| {sez['intestazione']} | Come si calcola | Quanto |",
                 "|---|---|---:|"]
        righe += [f"| {a} | {b} | {c} |" for a, b, c in sez["righe"]]
        righe.append(f"| **Totale** | | **{sez['totale']}** |")
        conti.append("\n".join(righe))
    return m, voci, conti


@pytest.mark.parametrize("nome", sorted(RIFERIMENTO))
def test_il_file_salvato_e_quello_del_vecchio(nome, tmp_path, monkeypatch):
    r = RIFERIMENTO[nome]
    nuovo = _senza_immagini(_salvato_dal_nuovo(r["dati"], tmp_path,
                                               monkeypatch))
    assert set(nuovo) == set(r["salvato"])
    for chiave, valore in r["salvato"].items():
        assert nuovo[chiave] == valore, chiave


@pytest.mark.parametrize("nome", CON_DISEGNO)
def test_le_misure_della_planimetria_sono_quelle_del_vecchio(nome):
    r = RIFERIMENTO[nome]
    metriche, voci, conti = _campioni_del_nuovo(r["dati"])
    assert sorted(metriche) == sorted(tuple(m) for m in r["metriche"])
    assert voci == r["voci"]
    assert conti == r["conti"]
