"""Le fatture messe da parte, una cartella per cantiere.

Caricare una fattura serviva solo a riempire la riga di spesa: del documento
non restava niente. Adesso il file resta accanto al progetto che l'ha
ricevuto, e la riga lo sa riaprire (2/10/2026).

⚠️ I test scrivono SOLO dentro la cartella temporanea: CME_ARCHIVIO viene
spostato lì, e l'archivio vero di chi lavora non viene mai sfiorato.
"""
import pytest

import archivio_fatture
import banco


XML = """<?xml version="1.0" encoding="UTF-8"?>
<p:FatturaElettronica xmlns:p="http://ivaservizi.agenziaentrate.gov.it/docs/xsd/fatture/v1.2">
  <FatturaElettronicaHeader>
    <CedentePrestatore><DatiAnagrafici><Anagrafica>
      <Denominazione>ACME Edilizia S.r.l.</Denominazione>
    </Anagrafica></DatiAnagrafici></CedentePrestatore>
  </FatturaElettronicaHeader>
  <FatturaElettronicaBody>
    <DatiGenerali><DatiGeneraliDocumento>
      <TipoDocumento>TD01</TipoDocumento>
      <Data>2026-01-15</Data>
      <Numero>{numero}</Numero>
      <ImportoTotaleDocumento>122.00</ImportoTotaleDocumento>
    </DatiGeneraliDocumento></DatiGenerali>
    <DatiBeniServizi>
      <DettaglioLinee><Descrizione>Materiale edile</Descrizione></DettaglioLinee>
      <DatiRiepilogo>
        <AliquotaIVA>22.00</AliquotaIVA>
        <ImponibileImporto>100.00</ImponibileImporto>
        <Imposta>22.00</Imposta>
      </DatiRiepilogo>
    </DatiBeniServizi>
  </FatturaElettronicaBody>
</p:FatturaElettronica>"""


def _xml(numero="123/2026"):
    return XML.format(numero=numero).encode("utf-8")


@pytest.fixture
def archivio(tmp_path, monkeypatch):
    monkeypatch.setenv("CME_ARCHIVIO", str(tmp_path / "progetti"))
    return tmp_path / "progetti"


@pytest.fixture
def b(archivio):
    b = banco.Banco()
    b.nuovo()
    b.dati["progetto"]["nome"] = "Via Roma 12"
    return b


def _carica(b, *file):
    b.leggi_fatture(list(file))
    return b.fatture_lette["righe"]


# ------------------------------------------------- dove finiscono i file

def test_ogni_cantiere_ha_la_sua_cartella(archivio):
    una = archivio_fatture.cartella("Via Roma 12")
    altra = archivio_fatture.cartella("Migliarina")
    assert una != altra
    assert una.parent == altra.parent == archivio / "fatture"


def test_un_nome_di_progetto_impossibile_non_rompe_il_percorso(archivio):
    cart = archivio_fatture.cartella('Via "Roma"/12: lotto?')
    assert cart.parent == archivio / "fatture"
    assert "/" not in cart.name and '"' not in cart.name


def test_la_cartella_nasce_solo_quando_arriva_una_fattura(b, archivio):
    assert not (archivio / "fatture").exists()
    _carica(b, ("f1.xml", _xml()))
    assert not (archivio / "fatture").exists()   # letta, non ancora voluta
    b.aggiungi_fatture(b.fatture_lette["righe"])
    assert archivio_fatture.cartella("Via Roma 12").is_dir()


# -------------------------------------------------- dalla riga al file

def test_la_riga_di_spesa_porta_il_nome_del_documento(b):
    righe = _carica(b, ("fattura ACME.xml", _xml()))
    b.aggiungi_fatture(righe)
    spesa = b.dati["spese"][-1]
    assert spesa["importo"] == 122.0
    assert spesa["file"] == "fattura ACME.xml"
    assert archivio_fatture.percorso("Via Roma 12", spesa["file"]).read_bytes() \
        == _xml()


def test_le_fatture_di_un_cantiere_non_entrano_nell_altro(b):
    b.aggiungi_fatture(_carica(b, ("f1.xml", _xml())))
    b.dati["progetto"]["nome"] = "Migliarina"
    b.aggiungi_fatture(_carica(b, ("f2.xml", _xml("456/2026"))))
    assert archivio_fatture.elenco("Via Roma 12") == ["f1.xml"]
    assert archivio_fatture.elenco("Migliarina") == ["f2.xml"]


def test_due_fatture_con_lo_stesso_nome_non_si_cancellano(b):
    b.aggiungi_fatture(_carica(b, ("fattura.xml", _xml())))
    b.aggiungi_fatture(_carica(b, ("fattura.xml", _xml("456/2026"))))
    assert archivio_fatture.elenco("Via Roma 12") == ["fattura (2).xml",
                                                      "fattura.xml"]
    assert [s["file"] for s in b.dati["spese"]] == ["fattura.xml",
                                                    "fattura (2).xml"]


def test_due_file_uguali_nella_stessa_infornata_restano_distinti(b):
    righe = _carica(b, ("fattura.xml", _xml()),
                    ("fattura.xml", _xml("456/2026")))
    assert len({r["file"] for r in righe}) == 2
    b.aggiungi_fatture(righe)
    assert len(archivio_fatture.elenco("Via Roma 12")) == 2


def test_scartare_non_lascia_niente_in_archivio(b, archivio):
    _carica(b, ("f1.xml", _xml()))
    b.scarta_fatture()
    assert archivio_fatture.elenco("Via Roma 12") == []
    assert b.fatture_lette is None


def test_una_riga_tolta_prima_di_confermare_non_si_archivia(b):
    righe = _carica(b, ("tengo.xml", _xml()), ("butto.xml", _xml("456/2026")))
    b.aggiungi_fatture([r for r in righe if r["file"] == "tengo.xml"])
    assert archivio_fatture.elenco("Via Roma 12") == ["tengo.xml"]


def test_una_spesa_scritta_a_mano_non_ha_la_colonna_file(b):
    b.scrivi_spese("spese", [{"importo": 50.0, "categoria": "LAVORI"}])
    assert "file" not in b.dati["spese"][0]


def test_il_documento_resta_attaccato_quando_si_corregge_la_riga(b):
    b.aggiungi_fatture(_carica(b, ("f1.xml", _xml())))
    righe = [dict(r, oggetto="Rifatto a mano") for r in b.dati["spese"]]
    b.scrivi_spese("spese", righe)
    assert b.dati["spese"][0]["file"] == "f1.xml"


# ------------------------------------------------------ aprire il file

def test_si_rilegge_solo_dalla_cartella_del_suo_cantiere(b):
    b.aggiungi_fatture(_carica(b, ("f1.xml", _xml())))
    assert archivio_fatture.percorso("Migliarina", "f1.xml") is None


def test_un_nome_che_esce_dalla_cartella_non_apre_niente(b, archivio):
    b.aggiungi_fatture(_carica(b, ("f1.xml", _xml())))
    (archivio / "fuori.json").write_text("{}", encoding="utf-8")
    assert archivio_fatture.percorso("Via Roma 12", "../../fuori.json") is None
    assert archivio_fatture.percorso("Via Roma 12", "non c'e'.pdf") is None


def test_quante_ne_ha_questo_cantiere(b):
    assert b.fatture_del_cantiere() == []
    b.aggiungi_fatture(_carica(b, ("f1.xml", _xml())))
    assert b.fatture_del_cantiere() == ["f1.xml"]
