"""La scheda planimetria nel banco: piante, gesti della tela, scala, annulla."""
import io
import json

import pytest
from PIL import Image

import banco
from banco_disegno import ErroreDisegno


def _png(larg=800, alt=600):
    buffer = io.BytesIO()
    Image.new("RGB", (larg, alt), "white").save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture
def b():
    b = banco.Banco()
    b.nuovo()
    b.aggiungi_planimetrie(_png(), "piano terra.png")
    b.giro()
    return b


def _gesto(b, **ev):
    ev.setdefault("seq", id(ev))
    b.evento_tela(ev)
    b.giro()


def test_una_planimetria_caricata_prende_il_nome_del_file(b):
    assert [p["nome"] for p in b.dati["piante"]] == ["piano terra"]
    assert b.dati["piante"][0]["mpp"] is None


def test_un_immagine_troppo_larga_si_riduce_alla_misura_canonica():
    b = banco.Banco()
    b.aggiungi_planimetrie(_png(3000, 1500), "grande.png")
    assert b.immagine(0).size == (2000, 1000)


def test_un_file_illeggibile_lo_dice(b):
    with pytest.raises(ErroreDisegno):
        b.aggiungi_planimetrie(b"non sono un'immagine", "rotto.png")


def test_la_scala_si_imposta_dal_segmento(b):
    _gesto(b, tipo="scala", p1=[0, 0], p2=[100, 0])
    b.imposta_scala(5)
    assert b.dati["piante"][0]["mpp"] == pytest.approx(0.05)
    assert b.scala_temp is None


def test_le_misure_note_restano_e_la_scala_e_la_media_pesata(b):
    _gesto(b, tipo="scala", p1=[0, 0], p2=[100, 0])
    b.imposta_scala(1)                               # 1 cm al pixel
    _gesto(b, tipo="scala", p1=[0, 0], p2=[0, 300])
    b.imposta_scala(3.03)                            # 1,01 cm al pixel
    pianta = b.dati["piante"][0]
    assert [s["metri"] for s in pianta["scale"]] == [1, 3.03]
    # 4,03 m su 400 px: il segmento lungo pesa tre volte il corto
    assert pianta["mpp"] == pytest.approx(4.03 / 400)
    # i segmenti nascono NASCOSTI (1/10/2026): si accendono per guardarli
    assert b.argomenti_tela()["scale"] == []
    b.mostra_le_scale(True)
    segni = b.argomenti_tela()["scale"]
    assert [s["etichetta"] for s in segni] == ["① 1,00 m", "② 3,03 m"]


def test_una_misura_che_non_torna_con_le_altre_si_segna(b):
    _gesto(b, tipo="scala", p1=[0, 0], p2=[100, 0])
    b.imposta_scala(1)
    _gesto(b, tipo="scala", p1=[0, 0], p2=[0, 100])
    b.imposta_scala(1.2)                             # 20% in piu'
    segni = b.argomenti_tela()["scale"]
    assert [s["non_torna"] for s in segni] == [True, True]
    assert segni[0]["etichetta"] == "① 1,00 m ⚠"


def test_togliere_una_misura_rifa_la_scala_con_le_altre(b):
    _gesto(b, tipo="scala", p1=[0, 0], p2=[100, 0])
    b.imposta_scala(1)
    _gesto(b, tipo="scala", p1=[0, 0], p2=[0, 200])
    b.imposta_scala(4)
    prima, seconda = b.dati["piante"][0]["scale"]
    b.togli_misura_scala(prima["id"])
    assert b.dati["piante"][0]["mpp"] == pytest.approx(0.02)
    b.togli_misura_scala(seconda["id"])
    assert b.dati["piante"][0]["mpp"] is None
    assert b.annulla_disegno() == "eliminazione di una misura della scala"
    assert b.dati["piante"][0]["mpp"] == pytest.approx(0.02)
    assert [s["id"] for s in b.dati["piante"][0]["scale"]] == [seconda["id"]]


def test_la_scala_di_un_file_di_prima_si_sostituisce_con_la_prima_misura(b):
    pianta = b.dati["piante"][0]
    pianta["mpp"] = 0.5                              # senza segmento
    _gesto(b, tipo="scala", p1=[0, 0], p2=[100, 0])
    b.imposta_scala(2)
    assert pianta["mpp"] == pytest.approx(0.02) and len(pianta["scale"]) == 1


def test_la_scala_di_un_file_di_prima_si_puo_togliere(b):
    b.dati["piante"][0]["mpp"] = 0.5
    b.togli_scala_senza_misure()
    assert b.dati["piante"][0]["mpp"] is None


def test_una_scala_a_zero_non_si_imposta(b):
    _gesto(b, tipo="scala", p1=[0, 0], p2=[100, 0])
    with pytest.raises(ErroreDisegno):
        b.imposta_scala(0)


def test_un_area_disegnata_prende_la_categoria_scelta(b):
    b.scegli_categoria_nuove("Balcone")
    _gesto(b, tipo="zona_chiusa", punti=[[0, 0], [10, 0], [10, 10]])
    zona = b.dati["piante"][0]["zone"][0]
    assert zona["categoria"] == "Balcone" and zona["id"] == 1


def test_lo_stesso_evento_due_volte_vale_una(b):
    ev = {"tipo": "parete", "p1": [0, 0], "p2": [10, 0], "seq": 42}
    b.evento_tela(dict(ev))
    b.evento_tela(dict(ev))
    assert len(b.dati["piante"][0]["pareti"]) == 1


def test_l_annulla_riporta_indietro_anche_la_scala_e_lo_dice(b):
    _gesto(b, tipo="scala", p1=[0, 0], p2=[100, 0])
    b.imposta_scala(5)
    assert b.annulla_disegno() == "impostazione della scala"
    assert b.dati["piante"][0]["mpp"] is None and b.scala_persa


def test_i_muri_disegnati_arrivano_nel_computo_agganciato(b):
    _gesto(b, tipo="scala", p1=[0, 0], p2=[100, 0])
    b.imposta_scala(1)                      # 1 px = 1 cm
    b.scegli_tipo_parete("demolire")
    _gesto(b, tipo="parete", p1=[0, 0], p2=[500, 0])     # 5 m
    b.giro()
    assert "2.2" in b.dati["voci_scelte"]
    assert b.quantita("2.2") == pytest.approx(5 * 2.70, abs=0.01)
    # scritta a mano, il disegno non la tocca più
    b.scrivi_quantita("2.2", 20)
    _gesto(b, tipo="parete", p1=[0, 0], p2=[0, 300])
    assert b.quantita("2.2") == 20


def test_la_lunghezza_scritta_allunga_il_muro(b):
    _gesto(b, tipo="scala", p1=[0, 0], p2=[100, 0])
    b.imposta_scala(1)
    _gesto(b, tipo="parete", p1=[0, 0], p2=[300, 0])
    b.sel_parete = b.dati["piante"][0]["pareti"][0]["id"]
    b.lunghezza_parete(4)
    assert b.dati["piante"][0]["pareti"][0]["p2"] == pytest.approx([400, 0])


def test_una_zona_va_al_computo_nella_categoria_superfici(b):
    _gesto(b, tipo="scala", p1=[0, 0], p2=[100, 0])
    b.imposta_scala(1)
    b.scegli_categoria_nuove("Superficie interna")
    _gesto(b, tipo="zona_chiusa", punti=[[0, 0], [200, 0], [200, 100], [0, 100]])
    b.sel_zona = 1
    b.nome_zona("Cucina")
    b.zona_al_computo()
    voce = b.dati["voci"][-1]
    assert voce["categoria"] == "Superfici" and voce["quantita_manuale"] == 2.0
    assert voce["descrizione"] == "Cucina — piano terra"


def test_togliere_una_pianta_non_lascia_la_selezione_fuori_misura(b):
    b.aggiungi_planimetrie(_png(), "piano primo.png")
    assert b.pianta_idx == 1
    b.togli_pianta(1)
    assert b.pianta_idx == 0 and len(b.dati["piante"]) == 1


def test_il_pdf_delle_planimetrie_si_stampa(b):
    assert b.pdf_planimetrie()[:4] == b"%PDF"
    assert b.pdf_planimetrie(orizzontale=True)[:4] == b"%PDF"


def test_il_ritaglio_sposta_il_disegno_e_non_cambia_le_misure(b):
    _gesto(b, tipo="scala", p1=[0, 0], p2=[100, 0])
    b.imposta_scala(1)
    b.scegli_categoria_nuove("Superficie interna")
    _gesto(b, tipo="zona_chiusa",
           punti=[[200, 100], [500, 100], [500, 400], [200, 400]])
    _gesto(b, tipo="parete", p1=[200, 100], p2=[500, 100])
    prima = b.grandezze()
    b.ritaglia(150, 50, 700, 550)
    pianta = b.dati["piante"][0]
    assert pianta["scale"][0]["p1"] == [-150, -50]
    assert b.immagine(0).size == (550, 500)
    assert pianta["zone"][0]["punti"][0] == [50.0, 50.0]
    assert pianta["pareti"][0]["p2"] == [350.0, 50.0]
    assert pianta["mpp"] == pytest.approx(0.01)
    assert b.grandezze() == prima
    b.annulla_ritaglio()
    assert b.immagine(0).size == (800, 600)
    assert pianta["zone"][0]["punti"][0] == [200.0, 100.0]


def test_un_ritaglio_troppo_piccolo_o_di_tutto_il_foglio_non_si_fa(b):
    with pytest.raises(ErroreDisegno):
        b.ritaglia(0, 0, 20, 20)
    with pytest.raises(ErroreDisegno):
        b.ritaglia(0, 0, 800, 600)
    with pytest.raises(ErroreDisegno):
        b.annulla_ritaglio()


def test_dopo_il_ritaglio_la_pulizia_si_annulla_sul_foglio_ritagliato(b):
    b.prova_pulizia(1.0)
    b.usa_pulizia()
    b.ritaglia(100, 100, 500, 400)
    b.ripristina_originale()
    assert b.immagine(0).size == (400, 300)


def test_la_superficie_reale_e_calpestabile_piu_pertinenze(b):
    """Stanze e pertinenze per intero; il perimetro commerciale e i
    giardini — anche coi nomi di prima — no."""
    from server.vista_disegno import vista_planimetria
    _gesto(b, tipo="scala", p1=[0, 0], p2=[100, 0])
    b.imposta_scala(1)                                  # 1 px = 1 cm
    for categoria, lato in (("Superficie interna", 500),   # 25 m²
                            ("Balcone", 200),               # 4 m²
                            ("Garage / Box", 300),          # 9 m²
                            ("Giardino", 700),              # 49 m², fuori
                            ("Giardino di appartamento", 400),  # fuori
                            ("Superficie commerciale", 600)):  # 36 m²
        b.scegli_categoria_nuove(categoria)
        _gesto(b, tipo="zona_chiusa",
               punti=[[0, 0], [lato, 0], [lato, lato], [0, lato]])
    b.giro()
    s = vista_planimetria(b)["superfici"]
    assert s["totale"] == pytest.approx(25 + 4 + 9)
    assert s["commerciale"] > 36 + 4 * 0.30      # i giardini qui contano


def test_le_misure_note_si_ritrovano_riaprendo_il_progetto(b):
    _gesto(b, tipo="scala", p1=[0, 0], p2=[100, 0])
    b.imposta_scala(1)
    dati, _ = banco.normalizza(json.loads(json.dumps(b.dati)))
    assert dati["piante"][0]["scale"] == b.dati["piante"][0]["scale"]
    assert dati["piante"][0]["mpp"] == pytest.approx(0.01)


# Un punto nuovo su un lato arriva dalla tela in due pezzi: appena nasce a
# metà lato e poi dove la mano lo lascia. Fino all'1/10/2026 arrivava solo
# alla fine, e un trascinamento che non si chiudeva come si deve — il
# rilascio fuori dalla finestra, Esc, un tasto che cambia strumento — lo
# faceva sparire senza che nessuno se ne accorgesse: la risposta successiva
# del server riportava l'area com'era prima. Il secondo pezzo porta
# «seguito», così da annullare resta un gesto solo.

def _area_quadrata(b):
    _gesto(b, tipo="zona_chiusa",
           punti=[[0, 0], [100, 0], [100, 100], [0, 100]])
    return b.dati["piante"][0]["zone"][0]


def test_il_punto_nuovo_resta_anche_se_il_trascinamento_si_perde(b):
    zona = _area_quadrata(b)
    # solo la nascita: la mano non ha mai lasciato il mouse
    _gesto(b, tipo="zona_modificata", id=zona["id"],
           punti=[[0, 0], [50, 0], [100, 0], [100, 100], [0, 100]])
    assert len(b.dati["piante"][0]["zone"][0]["punti"]) == 5


def test_nascita_e_arrivo_del_punto_sono_un_solo_annulla(b):
    zona = _area_quadrata(b)
    passi = len(b.storia)
    _gesto(b, tipo="zona_modificata", id=zona["id"],
           punti=[[0, 0], [50, 0], [100, 0], [100, 100], [0, 100]])
    _gesto(b, tipo="zona_modificata", id=zona["id"], seguito=True,
           punti=[[0, 0], [50, -40], [100, 0], [100, 100], [0, 100]])
    assert len(b.storia) == passi + 1
    assert b.dati["piante"][0]["zone"][0]["punti"][1] == [50, -40]
    # un solo Annulla e il punto non c'è più: l'area torna quadrata
    assert b.annulla_disegno() == "modifica dell'area"
    assert len(b.dati["piante"][0]["zone"][0]["punti"]) == 4


def test_una_modifica_qualunque_resta_da_annullare(b):
    zona = _area_quadrata(b)
    passi = len(b.storia)
    _gesto(b, tipo="zona_modificata", id=zona["id"],
           punti=[[0, 0], [120, 0], [100, 100], [0, 100]])
    assert len(b.storia) == passi + 1
