"""La parte del banco che riguarda il Business plan e le sue quattro linguette:
studio di fattibilità, spese a consuntivo, cantiere (contratto e SAL), MCA.

Traduce le callback e i campi di streamlit_app.py senza Streamlit. Le
regole che contavano restano quelle:

- gli importi di imposte e agenzie NON si salvano: sono la percentuale del
  loro prezzo, sempre (bp_ricalcola_euro). Scrivendo l'importo, si ricava
  la percentuale con SEI decimali, così l'importo rifatto torna al
  centesimo;
- gli imprevisti invece si salvano in euro, e seguono i lavori a ogni giro
  (il giro è nel banco);
- i mq commerciali si compilano dalla planimetria finché nessuno ci
  scrive sopra.
"""
from __future__ import annotations

import pandas as pd

import archivio_fatture
import cantiere
import fattibilita
import fattura
import merito
import storico
from costanti import CAMPI_NUMERO_IT, IMPOSTAZIONI_BP
from tabelle import (COLONNE_MCA, COLONNE_SPESE, COLONNE_SPESE_PREV,
                     cat_pulita, df_spese_da_righe, mca_da_df, spese_da_df)

# I confini dei campi numerici, come i number_input del vecchio.
LIMITI_BP = {
    "bp_imposta": (0.0, 30.0), "bp_ag_in": (0.0, 10.0),
    "bp_ag_out": (0.0, 10.0), "bp_imprevisti_pct": (0.0, 50.0),
    "bp_durata": (1, 120), "bp_coeff_sogg": (0.0, 3.0),
    "bp_taglio": (0.0, 0.60), "bp_sconto": (0.0, 30.0),
    "bp_costo_ristr_mq": (0.0, 3000.0), "bp_quota_mercato": (0.0, 130.0),
    **{k: (0.0, 50.0) for k in IMPOSTAZIONI_BP if k.startswith("bp_iva_")},
}
# gli importi che non si salvano: la percentuale del loro prezzo
DERIVATI = {"bp_imposta_eur": ("bp_imposta", "bp_acquisto"),
            "bp_ag_in_eur": ("bp_ag_in", "bp_acquisto"),
            "bp_ag_out_eur": ("bp_ag_out", "bp_vendita")}


def dati_fattura(nome, contenuto):
    """I dati di una spesa da un file fattura (PDF o XML). Non solleva mai:
    un file illeggibile torna None e finisce fra i «non letti»."""
    try:
        nome = (nome or "").lower()
        if nome.endswith((".xml", ".p7m")):
            dati = fattura.dati_da_xml(contenuto)
            if dati:
                return dati
        if nome.endswith(".pdf") or contenuto[:4] == b"%PDF":
            import fitz
            with fitz.open(stream=contenuto, filetype="pdf") as doc:
                testo = "\n".join(doc[i].get_text()
                                  for i in range(doc.page_count))
            return fattura.dati_da_pdf_testo(testo)
    except Exception:                                        # noqa: BLE001
        return None
    return None


class BusinessPlanMixin:

    def carica_bp(self):
        self.fatture_lette = None
        # I byte delle fatture appena lette, in attesa di una risposta: si
        # scrivono sul disco solo quando le righe vengono aggiunte alle
        # spese. Chi scarta non lascia niente in archivio.
        self.fatture_in_attesa = {}

    # --------------------------------------------------- fattibilità

    def euro_derivati(self):
        """Imposte e agenzie in euro: la percentuale del loro prezzo."""
        bp = self.dati["business_plan"]
        return {chiave: round(bp[prezzo] * bp[pct] / 100, 2)
                for chiave, (pct, prezzo) in DERIVATI.items()}

    def base_imprevisti(self):
        ristr, usa = self.ristrutturazione()
        return 0.0 if usa else ristr

    def imposta_bp(self, chiave, valore):
        """Un campo del business plan, con le sue regole."""
        bp = self.dati["business_plan"]
        if chiave in DERIVATI:
            pct, prezzo = DERIVATI[chiave]
            if bp[prezzo] > 0:
                bp[pct] = round(max(0.0, float(valore or 0.0))
                                / bp[prezzo] * 100, 6)
            return
        if chiave == "bp_usa_consuntivo":
            bp[chiave] = bool(valore)
            return
        if chiave not in IMPOSTAZIONI_BP:
            raise self._errore(f"Campo sconosciuto: {chiave}")
        if isinstance(IMPOSTAZIONI_BP[chiave], int):
            minimo, massimo = LIMITI_BP.get(chiave, (0, 10 ** 9))
            bp[chiave] = int(min(massimo, max(minimo, round(float(valore)))))
            return
        minimo = CAMPI_NUMERO_IT.get(chiave, (0, None, 0.0))[2]
        minimo, massimo = LIMITI_BP.get(chiave, (minimo, float("inf")))
        valore = min(massimo, max(minimo, float(valore or 0.0)))
        bp[chiave] = valore
        if chiave == "bp_imprevisti":
            # l'ha scritto una persona: la percentuale si adegua, e per
            # questo giro l'importo non si tocca di un centesimo
            base = self.base_imprevisti()
            if base > 0:
                bp["bp_imprevisti_pct"] = round(valore / base * 100, 6)
            self._importo_scritto = "bp_imprevisti"

    def _errore(self, testo):
        from banco import ErroreBanco
        return ErroreBanco(testo)

    def riprendi_mq_planimetria(self):
        mq = self.mq_da_planimetria()
        self.dati["business_plan"]["bp_mq"] = mq
        self._mq_automatici = mq

    def usa_come_vendita(self, valore):
        """«Usa come prezzo di vendita» dall'MCA."""
        self.dati["business_plan"]["bp_vendita"] = float(round(valore, 0))

    def applica_imprevisti(self, percentuale):
        """Tara la riserva sui cantieri già chiusi."""
        self.dati["business_plan"]["bp_imprevisti_pct"] = float(percentuale)

    # ------------------------------------------------------ le spese

    def scrivi_spese(self, registro, righe):
        colonne = {"spese": COLONNE_SPESE, "spese_prev": COLONNE_SPESE_PREV}
        if registro not in colonne:
            raise self._errore(f"Registro sconosciuto: {registro}")
        self.dati[registro] = spese_da_df(df_spese_da_righe(
            righe or [], colonne[registro]))

    def leggi_fatture(self, file):
        """[(nome, byte)] → le righe lette, da controllare prima di
        aggiungerle, e i file che non si sono lasciati leggere.

        Il documento viaggia con la riga: ogni riga porta il nome del suo
        file, e i byte restano qui in attesa. In archivio ci vanno dopo, se
        le righe vengono aggiunte davvero (aggiungi_fatture).
        """
        righe, non_letti = [], []
        self.fatture_in_attesa = {}
        for nome, contenuto in file:
            dati = dati_fattura(nome, contenuto)
            numero = (dati or {}).get("nr_fattura")
            if dati and (dati.get("importo") is not None
                         or (numero and numero != fattura.NUMERO_MANCANTE)):
                riga = {col: dati.get(col) for col in COLONNE_SPESE}
                # due file con lo stesso nome nella stessa infornata: la
                # chiave deve restare distinta anche prima dell'archivio
                chiave = archivio_fatture.nome_distinto(
                    nome, self.fatture_in_attesa)
                self.fatture_in_attesa[chiave] = contenuto
                riga["file"] = chiave
                righe.append(riga)
            else:
                non_letti.append(nome)
        # le righe senza importo restano: sono da completare a mano
        lette = []
        for r in righe:
            riga = {c: ("" if r.get(c) is None else str(r.get(c)))
                    for c in COLONNE_SPESE}
            for c in ("importo", "aliquota_iva"):
                riga[c] = None if r.get(c) is None else float(r[c])
            riga["categoria"] = cat_pulita(riga["categoria"]) or None
            lette.append(riga)
        self.fatture_lette = {"righe": lette, "non_letti": non_letti}
        return len(lette)

    def aggiungi_fatture(self, righe):
        """Le righe controllate entrano nelle spese, e i loro file in
        archivio — nella cartella di QUESTO cantiere.

        Si archivia qui e non alla lettura perché fino a questo momento la
        fattura si poteva ancora scartare, e una cartella che si riempie di
        documenti che nessuno ha voluto non è un archivio.

        Se il file non si lascia scrivere (disco pieno, cartella in sola
        lettura) la spesa entra lo stesso, senza allegato: i numeri del
        business plan valgono più del collegamento al documento.
        """
        righe = [dict(r) for r in (righe or [])]
        for riga in righe:
            contenuto = self.fatture_in_attesa.get(riga.get("file"))
            if contenuto is None:
                riga.pop("file", None)
                continue
            try:
                riga["file"] = archivio_fatture.salva(
                    self.nome_archivio(), riga["file"], contenuto)
            except OSError:
                riga.pop("file", None)
        self.dati["spese"] = spese_da_df(df_spese_da_righe(
            list(self.dati["spese"]) + righe, COLONNE_SPESE))
        self.fatture_lette = None
        self.fatture_in_attesa = {}

    def scarta_fatture(self):
        self.fatture_lette = None
        self.fatture_in_attesa = {}

    def fatture_del_cantiere(self):
        """I documenti messi da parte per il progetto aperto."""
        return archivio_fatture.elenco(self.nome_archivio())

    # ---------------------------------------------------- il cantiere

    def imposta_cantiere(self, campo, valore):
        if campo not in ("contratto", "extra"):
            raise self._errore(f"Campo sconosciuto: {campo}")
        self.dati["cantiere"][campo] = max(0.0, float(valore or 0.0))

    def scrivi_sal(self, righe):
        self.dati["cantiere"]["sal"] = [
            {"percento": min(100.0, max(0.0, float(r.get("percento") or 0.0))),
             "pagato": bool(r.get("pagato"))} for r in (righe or [])]

    def contratto_dal_computo(self):
        self.dati["cantiere"]["contratto"] = self.totali()["totale"]

    def stato_cantiere(self):
        c = self.dati["cantiere"]
        percentuali = [q["percento"] for q in c["sal"]]
        return cantiere.stato_cantiere(
            c["contratto"], percentuali,
            pagati=[i for i, q in enumerate(c["sal"], start=1)
                    if q["pagato"]],
            extra=c["extra"])

    def chiudi_operazione(self):
        """L'operazione entra nello storico, che vive fuori dai progetti."""
        stato = self.stato_cantiere()
        if not stato["contratto"]:
            raise self._errore("Serve l'importo di contratto per chiudere "
                               "l'operazione.")
        nome = self.dati["progetto"]["nome"] or "Progetto senza nome"
        mq = self.mq_calpestabili()
        try:
            storico.registra({
                "nome": nome, "contratto": stato["contratto"],
                "extra": stato["extra"], "scostamento": stato["scostamento"],
                "mq_calpestabili": mq or None,
                "eur_mq": (round(stato["totale_finale"] / mq, 2)
                           if mq and stato["totale_finale"] else None),
            })
        except OSError as errore:
            raise self._errore(f"Non sono riuscito a scrivere lo storico: "
                               f"{errore}") from errore
        return nome

    # ------------------------------------------------------------ MCA

    def scrivi_comparabili(self, righe):
        df = pd.DataFrame([merito.migra_scelte(r) for r in (righe or [])]) \
            .reindex(columns=COLONNE_MCA)
        for col in ("prezzo", "mq", "coeff"):
            df[col] = pd.to_numeric(df[col], errors="coerce")
        # l'ascensore è una spunta: una cella vuota vuol dire «assente»
        df["ascensore"] = df["ascensore"].map(lambda v: bool(v)
                                              if v == v else False)
        self.dati["mca_comparabili"] = mca_da_df(df)

    def scegli_soggetto(self, campo, valore):
        if campo not in merito.CAMPI:
            raise self._errore(f"Voce sconosciuta: {campo}")
        if campo == "ascensore":
            self.dati["mca_soggetto"][campo] = bool(valore)
        else:
            self.dati["mca_soggetto"][campo] = \
                None if valore in (None, "", "—") else str(valore)

    def scegli_statistica(self, valore):
        if valore not in ("media", "mediana"):
            raise self._errore("Si riassume con la media o la mediana.")
        self.dati["mca_statistica"] = valore
