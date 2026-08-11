import pytest

from cantiere import (
    SAL_PREDEFINITI,
    imprevisti_consigliati,
    piano_sal,
    scostamento_percentuale,
    somma_percentuali,
    stato_cantiere,
)

# contratto tipico: 60.000 € ripartiti 20-30-30-20
CONTRATTO = 60000.0
QUOTE = [20.0, 30.0, 30.0, 20.0]


def test_piano_sal_ripartisce_il_contratto():
    piano = piano_sal(CONTRATTO, QUOTE)
    assert [s["importo"] for s in piano] == [12000.0, 18000.0, 18000.0,
                                             12000.0]
    assert [s["n"] for s in piano] == [1, 2, 3, 4]


def test_piano_sal_ogni_cantiere_ha_le_sue_quote():
    """20-30-30-20 e' la media, non una regola."""
    piano = piano_sal(100000.0, [40.0, 60.0])
    assert [s["importo"] for s in piano] == [40000.0, 60000.0]


def test_piano_sal_senza_contratto():
    assert [s["importo"] for s in piano_sal(0.0, QUOTE)] == [0.0] * 4


def test_piano_sal_senza_quote():
    assert piano_sal(CONTRATTO, []) == []


def test_le_quote_non_vengono_aggiustate_di_nascosto():
    """Un contratto che non fa 100 e' un errore da vedere, non da correggere."""
    piano = piano_sal(CONTRATTO, [20.0, 30.0, 30.0])
    assert sum(s["importo"] for s in piano) == 48000.0     # non 60.000
    assert somma_percentuali([20.0, 30.0, 30.0]) == 80.0
    assert somma_percentuali(QUOTE) == 100.0


def test_predefiniti_fanno_cento():
    assert somma_percentuali(SAL_PREDEFINITI) == 100.0


# ------------------------------------------------------ stato del cantiere

def test_stato_a_meta_strada():
    stato = stato_cantiere(CONTRATTO, QUOTE, pagati=[1, 2])
    assert stato["pagato"] == 30000.0            # 12.000 + 18.000
    assert stato["residuo"] == 30000.0
    assert stato["totale_finale"] == 60000.0
    assert stato["scostamento"] == 0.0


def test_stato_a_cantiere_aperto_non_conosce_gli_extra():
    """Gli extra si calcolano a cantiere chiuso: prima valgono zero."""
    stato = stato_cantiere(CONTRATTO, QUOTE, pagati=[1])
    assert stato["extra"] == 0.0
    assert stato["totale_finale"] == CONTRATTO


def test_chiusura_con_extra():
    stato = stato_cantiere(CONTRATTO, QUOTE, pagati=[1, 2, 3, 4],
                           extra=7200.0)
    assert stato["pagato"] == 60000.0
    assert stato["residuo"] == 0.0
    assert stato["totale_finale"] == 67200.0
    assert stato["da_pagare"] == 7200.0          # restano solo gli extra
    assert stato["scostamento"] == 12.0          # +12% sul contratto


def test_gli_extra_non_entrano_nel_residuo():
    """Non sono un pagamento in ritardo: sono lavoro che il contratto
    non conosceva."""
    stato = stato_cantiere(CONTRATTO, QUOTE, pagati=[1, 2], extra=5000.0)
    assert stato["residuo"] == 30000.0           # solo il contratto
    assert stato["da_pagare"] == 35000.0         # residuo + extra


def test_il_sovrapagamento_si_vede():
    """Quote che fanno 110 e tutte saldate: il residuo va SOTTO zero.

    C'era un `max(0.0, ...)` che quel caso lo azzerava — la stessa
    correzione di nascosto che `piano_sal` rifiuta di fare sulle
    percentuali, spostata un passo più in là. Aver pagato più del contratto
    è precisamente il genere di cosa per cui si guarda questa schermata.
    """
    stato = stato_cantiere(CONTRATTO, [20.0, 30.0, 30.0, 30.0],
                           pagati=[1, 2, 3, 4])
    assert stato["pagato"] == 66000.0
    assert stato["residuo"] == -6000.0
    assert stato["da_pagare"] == -6000.0


def test_il_sovrapagamento_si_somma_agli_extra():
    """Il credito verso l'impresa e gli extra si compensano: è una cassa."""
    stato = stato_cantiere(CONTRATTO, [20.0, 30.0, 30.0, 30.0],
                           pagati=[1, 2, 3, 4], extra=2000.0)
    assert stato["da_pagare"] == -4000.0     # 6.000 pagati in più − 2.000


def test_stato_senza_niente():
    stato = stato_cantiere(0.0, [], pagati=[], extra=0.0)
    assert stato["contratto"] == 0.0
    assert stato["scostamento"] is None


# ------------------------------------------------ lo scostamento finale

def test_scostamento_in_piu_e_in_meno():
    assert scostamento_percentuale(60000.0, 67200.0) == 12.0
    assert scostamento_percentuale(60000.0, 58200.0) == -3.0


def test_scostamento_senza_contratto_non_e_zero():
    """Zero direbbe «nessuno sforamento», che e' un'altra cosa da «non so»."""
    assert scostamento_percentuale(0.0, 5000.0) is None
    assert scostamento_percentuale(None, None) is None


# --------------------------------- la percentuale di imprevisti consigliata

def test_imprevisti_dalla_media_dei_cantieri_chiusi():
    assert imprevisti_consigliati([9.0, 14.0, 7.0]) == 10.0


def test_imprevisti_contano_anche_i_cantieri_andati_bene():
    """Tenere fuori i risparmi gonfierebbe la media."""
    assert imprevisti_consigliati([12.0, -2.0]) == 5.0


def test_imprevisti_senza_storia_non_si_consigliano():
    assert imprevisti_consigliati([]) is None
    assert imprevisti_consigliati(None) is None
    assert imprevisti_consigliati([None, None]) is None


def test_imprevisti_negativi_restano_negativi():
    """Chi chiude sotto contratto deve leggerlo, non un finto zero.

    Prima un `max(0.0, ...)` riportava la media a zero, e la scheda diceva
    «i tuoi cantieri chiusi dicono 0,00%» a chi risparmia sistematicamente.
    Che una riserva non possa essere negativa è vero, ma è una decisione di
    chi la propone: qui si misura, e basta.
    """
    assert imprevisti_consigliati([-8.0, -6.0]) == -7.0


def test_imprevisti_ignorano_i_buchi():
    assert imprevisti_consigliati([10.0, None, 20.0]) == pytest.approx(15.0)
