"""Il registro d'uso non si corregge: le righe che non sono lavorazioni si
elencano a parte, e i conteggi le tolgono senza toccare la catena."""
import json

import uso


def _registro(cartella, monkeypatch, quante=5):
    monkeypatch.setattr(uso, "BASE", cartella)
    for n in range(quante):
        uso.registra("CME", "operazione_valutata", riferimento=f"progetto {n}")
    return uso._leggi(uso.datetime.now().year, cartella,
                      con_escluse=True)


def _escludi(cartella, anno, righe, motivo="scritta da un test"):
    (cartella / f"esclusioni_{anno}.json").write_text(json.dumps(
        {"esclusioni": [{"h": r["h"], "motivo": motivo} for r in righe]}),
        encoding="utf-8")


def test_le_righe_escluse_non_si_contano_ma_la_catena_resta(tmp_path,
                                                            monkeypatch):
    anno = uso.datetime.now().year
    righe = _registro(tmp_path, monkeypatch)
    prima = uso.verifica(anno, tmp_path)
    _escludi(tmp_path, anno, righe[:3])
    assert "| Operazioni immobiliari valutate con CME | 2 |" in \
        uso.allegato(anno, tmp_path)
    assert "Righe escluse dal conteggio: 3 (CME 3)" in uso.report(anno, tmp_path)
    dopo = uso.verifica(anno, tmp_path)
    # la catena è la stessa di prima, riga per riga
    assert prima.splitlines()[0] == dopo.splitlines()[0]
    assert "integra, 5 registrazioni" in dopo
    assert "Esclusioni: 3 righe, tutte presenti nel registro." in dopo
    assert f"esclusioni_{anno}.json: impronta " in dopo


def test_un_esclusione_che_non_esiste_nel_registro_si_segnala(tmp_path,
                                                             monkeypatch):
    anno = uso.datetime.now().year
    _registro(tmp_path, monkeypatch, quante=2)
    _escludi(tmp_path, anno, [{"h": "0" * 64}])
    assert "1 NON TROVATE nel registro" in uso.verifica(anno, tmp_path)


def test_senza_esclusioni_tutto_come_prima(tmp_path, monkeypatch):
    anno = uso.datetime.now().year
    _registro(tmp_path, monkeypatch, quante=2)
    assert "escluse" not in uso.report(anno, tmp_path)
    assert "Esclusioni" not in uso.verifica(anno, tmp_path)
