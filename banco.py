"""Il banco di lavoro: il progetto aperto, e tutto quello che gli si fa.

È quello che nel programma vecchio (Streamlit, tolto il 25/09/2026) stava
sparso nello stato di sessione e nelle callback dei bottoni, rimesso in un
posto solo: un dizionario nel formato del file (`dati`) e i gesti che lo
cambiano. Il motore (`server/`) ne tiene uno aperto, come la sessione di
Streamlit teneva il suo; la pagina chiede `vista()` e manda gesti.

⚠️ `dati` è SEMPRE nel formato del file, già normalizzato come lo lasciava
il caricamento del programma vecchio: salvarlo vuol dire scriverlo così
com'è. Niente traduzioni fra un formato «di lavoro» e uno «di file». Che
esca ancora uguale a come l'avrebbe scritto il vecchio lo prova
tests/test_come_il_vecchio.py.

Qui non c'è niente dell'interfaccia: nessun colore, nessuna parola da
mostrare che non sia un dato. La pagina decide come si vede.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import io
import json
from datetime import date, datetime

import pandas as pd

import archivio_locale
from banco_bp import BusinessPlanMixin
from banco_disegno import DisegnoMixin, ErroreDisegno
import calcoli
import cantiere
import listino
import listino_personale
import materiali
import merito
import modello_computo
import planimetria
import fattibilita
import rinumerazione
from costanti import (
    ALTERNATIVE_DAL_DISEGNO,
    CAMPI_NUMERO_IT,
    CATEGORIE_ESTERNE,
    CATEGORIE_INVOLUCRO,
    CATEGORIE_SOLO_COMPUTO,
    VOCI_DA_SUPERFICI,
    CATEGORIE_DEFAULT,
    IMPOSTAZIONI_BP,
    PASSI_STORIA_COMPUTO,
    PERCENTUALI_STORICHE,
    SOGGETTO_MCA,
    UM_A_CORPO,
    UNITA_DELLA_CATEGORIA,
    UNITA_MISURA,
)
from tabelle import (
    COLONNE_MCA,
    COLONNE_SPESE,
    COLONNE_SPESE_PREV,
    df_materiali_da_righe,
    df_mca_normalizzato,
    df_spese_da_righe,
    materiali_da_df,
    mca_da_df,
    spese_da_df,
)

try:
    from uso import registra as _registra_uso
except Exception:                                            # noqa: BLE001
    def _registra_uso(*_a, **_k):
        pass


# Le misure delle detrazioni: come le lascia il caricamento del vecchio.
FINITURE_PREDEFINITE = {
    "porta_larg": 0.80, "porta_alt": 2.10, "porta_n": 0, "porta_n_est": 0,
    "riv_alt": 1.20, "riv_porte_n": 1, "riv_finestre_n": 0,
    "fin_n": 0, "fin_larg": 1.20, "fin_alt": 1.40,
    "pf_n": 0, "pf_larg": 1.20, "pf_alt": 2.30,
    "apert_dem_n": 0, "apert_cos_n": 0, "apert_car_n": 0,
    "apert_larg": 0.80, "apert_alt": 2.10,
}
ETICHETTE_PREDEFINITE = {"font": 14, "nome": True, "m2": True,
                         "percento": True, "perimetro": True}


class ErroreBanco(ErroreDisegno):
    """Un gesto che non si può fare, con la frase da dire a chi l'ha fatto."""


# ---------------------------------------------------------------- utilità


def serie_della_categoria(categoria):
    """Il numero di serie di una categoria (stampato sulla pastiglia)."""
    if categoria in listino.CATEGORIE:
        return listino.CATEGORIE.index(categoria) + 1
    return len(listino.CATEGORIE) + 1        # le categorie inventate, in coda


def unita_per_categoria(categoria):
    """Le unità proposte in quella categoria, con la sua in testa."""
    propria = UNITA_DELLA_CATEGORIA.get(categoria)
    if not propria:
        return list(UNITA_MISURA)
    return [propria] + [u for u in UNITA_MISURA if u != propria]


def unita_della_voce(categoria, um):
    """Quelle di casa più la sua: un computo vecchio può portare «m»."""
    elenco = unita_per_categoria(categoria)
    return elenco if um in elenco else [um] + elenco


def categorie_per_progetto(piante):
    """Le categorie di superficie: le predefinite, più quelle di un progetto
    salvato che nel frattempo sono state tolte (con il loro peso storico)."""
    categorie = [dict(c) for c in CATEGORIE_DEFAULT]
    noti = {c["nome"] for c in categorie}
    usate = {z.get("categoria") for p in piante for z in (p.get("zone") or [])}
    for nome in sorted(n for n in usate if n and n not in noti):
        regola = PERCENTUALI_STORICHE.get(nome, 100.0)
        if isinstance(regola, dict):
            categorie.append({"nome": nome, **regola})
        else:
            categorie.append({"nome": nome, "percento": float(regola)})
    return categorie


def mappa_percentuali(categorie):
    """{categoria: percento} o, con lo scaglione, {percento, soglia, oltre}."""
    regole = {}
    for c in categorie:
        if c.get("soglia") and c.get("oltre") is not None:
            regole[c["nome"]] = {"percento": float(c["percento"]),
                                 "soglia": float(c["soglia"]),
                                 "oltre": float(c["oltre"])}
        else:
            regole[c["nome"]] = float(c["percento"])
    return regole


def percento_di(regole, categoria):
    """L'incidenza piena di una categoria, scaglione o no."""
    valore = regole.get(categoria, 100.0)
    if isinstance(valore, dict):
        return float(valore.get("percento", 100.0))
    return float(valore)


def _immagine_leggibile(testo_b64):
    """True se la planimetria si lascia aprire (il vecchio la scartava)."""
    from PIL import Image
    try:
        Image.open(io.BytesIO(base64.b64decode(testo_b64))).verify()
        return True
    except Exception:                                        # noqa: BLE001
        return False


# ---------------------------------------------------------- normalizzare


def normalizza(dati):
    """Il file di un progetto come lo lascia il caricamento del vecchio.

    Ritorna (dati_normalizzati, piante_scartate). È la traduzione, passo
    per passo, del caricamento del programma vecchio («if "da_caricare" in
    st.session_state») e poi del suo `_payload_progetto`: un progetto
    aperto qui e salvato subito esce uguale a come lo salvava il vecchio.
    """
    # un file coi numeri del listino di prima si traduce (rinumerazione.py);
    # poi le voci tue passate al listino col loro codice diventano sue
    dati = listino.assorbi_voci_tue(rinumerazione.traduci(dati or {}))
    progetto = dati.get("progetto") or {}
    try:
        data_prg = date.fromisoformat(progetto.get("data", "")).isoformat()
    except (TypeError, ValueError):
        data_prg = date.today().isoformat()
    fuori = {
        # la numerazione del listino in cui il file è scritto
        "listino": listino.VERSIONE,
        "progetto": {
            "nome": progetto.get("nome", "") or "",
            "committente": progetto.get("committente", "") or "",
            "oggetto": progetto.get("oggetto", "") or "",
            "luogo": progetto.get("luogo", "") or "",
            "data": data_prg,
            "aliquota_iva": float(progetto.get("aliquota_iva", 10.0)),
        },
    }

    # Le voci scritte a mano. Quelle dei computi più vecchi non avevano un
    # codice, e lo prendono adesso — il primo libero della loro categoria.
    righe_extra = [r for r in (dati.get("voci") or [])
                   if (r.get("descrizione") or "").strip()]
    presi = {v["codice"] for v in listino.VOCI}
    voci = []
    for riga in righe_extra:
        codice = riga.get("codice")
        if not codice:
            serie = serie_della_categoria(
                riga.get("categoria") or calcoli.SENZA_CATEGORIA)
            n = 1
            while f"{serie}.{n}" in presi:
                n += 1
            codice = f"{serie}.{n}"
        presi.add(codice)
        voci.append({
            "categoria": riga.get("categoria") or calcoli.SENZA_CATEGORIA,
            "codice": codice,
            "descrizione": riga["descrizione"].strip(),
            "um": riga.get("um") or "",
            "parti": None, "lunghezza": None, "larghezza": None,
            "altezza": None,
            "quantita_manuale": float(riga.get("quantita_manuale") or 0.0),
            "prezzo": float(riga.get("prezzo") or 0.0),
        })
    fuori["voci"] = voci
    extra = {v["codice"] for v in voci}

    stato_listino = dati.get("listino_stato") or {}
    fuori["listino_stato"] = {}
    for voce in listino.VOCI:
        elemento = stato_listino.get(voce["codice"]) or {}
        q = float(elemento.get("q", 0.0) or 0.0)
        p = float(elemento.get("p", voce["prezzo"]) or voce["prezzo"])
        if q > 0 or p != voce["prezzo"]:
            fuori["listino_stato"][voce["codice"]] = {"q": q, "p": p}

    scelte = dati.get("voci_scelte")
    vecchio = scelte is None
    if vecchio:
        scelte = sorted(c for c, e in stato_listino.items()
                        if float((e or {}).get("q") or 0.0) > 0)
    scelte = [c for c in scelte if listino.voce_per_codice(c) or c in extra]
    if vecchio:
        scelte += [c for c in extra if c not in scelte]
    fuori["voci_scelte"] = scelte
    fuori["voci_scartate"] = [c for c in (dati.get("voci_scartate") or [])
                              if c not in scelte]
    fuori["voci_a_mano"] = list(dati.get("voci_a_mano") or [])
    fuori["lavori_facoltativi"] = [
        c for c in (dati.get("lavori_facoltativi") or [])
        if c in listino.CATEGORIE_FACOLTATIVE]

    # ASSENTE e VUOTO sono due cose diverse: senza la chiave l'elenco
    # standard, con [] l'elenco svuotato da chi ci lavora.
    salvati = dati.get("materiali")
    if salvati is None:
        salvati = materiali.elenco_standard()
    fuori["materiali"] = materiali_da_df(df_materiali_da_righe(salvati))

    testi = dati.get("testi_voci") or {}
    fuori["testi_voci"] = {}
    for voce in listino.VOCI:
        t = testi.get(voce["codice"]) or {}
        if t.get("d") or t.get("u"):
            fuori["testi_voci"][voce["codice"]] = {
                "d": t.get("d") or None, "u": t.get("u") or None}

    bp = dati.get("business_plan") or {}
    fuori["business_plan"] = {
        chiave: (int(bp.get(chiave, valore)) if isinstance(valore, int)
                 else float(bp.get(chiave, valore)))
        for chiave, valore in IMPOSTAZIONI_BP.items()}
    fuori["business_plan"]["bp_usa_consuntivo"] = bool(
        bp.get("bp_usa_consuntivo", False))

    spese = dati.get("spese") or []
    spese_prev = dati.get("spese_prev")
    if spese_prev is None:
        # vecchio formato: un registro solo, separato per stato
        spese_prev = [s for s in spese if s.get("stato") == "Da sostenere"]
        spese = [s for s in spese
                 if s.get("stato", "Sostenuta") != "Da sostenere"]
    fuori["spese"] = spese_da_df(df_spese_da_righe(spese, COLONNE_SPESE))
    fuori["spese_prev"] = spese_da_df(
        df_spese_da_righe(spese_prev, COLONNE_SPESE_PREV))

    # ⚠️ normalizzato come nel vecchio: un comparabile salvato prima che
    # l'ascensore entrasse nella griglia ha la spunta a False, non vuota
    df_mc = df_mca_normalizzato(pd.DataFrame(
        [merito.migra_scelte(r) for r in (dati.get("mca_comparabili") or [])]
    ).reindex(columns=COLONNE_MCA))
    fuori["mca_comparabili"] = mca_da_df(df_mc)

    sog = dati.get("mca_soggetto")
    if sog is not None:
        sog = merito.migra_scelte(sog)
    soggetto = {}
    for campo in merito.CAMPI:
        if sog is None:
            valore = SOGGETTO_MCA[f"sog_{campo}"]
        else:
            valore = sog.get(campo)
        if campo == "ascensore":
            soggetto[campo] = bool(valore)
        else:
            soggetto[campo] = None if valore in (None, "", "—") else str(valore)
    fuori["mca_soggetto"] = soggetto
    # nel vecchio la tendina riportava a «media» qualunque altro valore
    fuori["mca_statistica"] = (dati.get("mca_statistica")
                               if dati.get("mca_statistica") == "mediana"
                               else "media")

    piante, scartate = [], []
    for p in dati.get("piante") or []:
        if p.get("immagine") and _immagine_leggibile(p["immagine"]):
            piante.append({"nome": p.get("nome") or "Planimetria",
                           "mpp": p.get("mpp"),
                           "zone": p.get("zone") or [],
                           "pareti": p.get("pareti") or [],
                           "immagine": p["immagine"]})
        else:
            scartate.append(p.get("nome") or "planimetria senza nome")
    fuori["categorie"] = categorie_per_progetto(piante)

    et = dati.get("etichette") or {}
    fuori["etichette"] = {
        "font": int(et.get("font", 14)), "nome": bool(et.get("nome", True)),
        "m2": bool(et.get("m2", True)),
        "percento": bool(et.get("percento", True)),
        "perimetro": bool(et.get("perimetro", True))}
    fuori["altezza_locali"] = float(dati.get("altezza_locali", 2.70))
    fin = dati.get("finiture") or {}
    fuori["finiture"] = {
        k: (int(fin.get(k, v)) if isinstance(v, int) else float(fin.get(k, v)))
        for k, v in FINITURE_PREDEFINITE.items()}
    fuori["auto_computo"] = bool(dati.get("auto_computo", True))
    cant = dati.get("cantiere") or {}
    # ⚠️ Le quote vuote diventano quelle predefinite: nel vecchio la tabella
    # dei SAL le mostra e le riscrive nel progetto a ogni giro, quindi ogni
    # progetto che salva le porta.
    sal = [{"percento": float(q.get("percento") or 0.0),
            "pagato": bool(q.get("pagato"))}
           for q in (cant.get("sal") or [])] or [
        {"percento": float(p), "pagato": False}
        for p in cantiere.SAL_PREDEFINITI]
    fuori["cantiere"] = {"contratto": float(cant.get("contratto", 0.0)),
                         "extra": float(cant.get("extra", 0.0)),
                         "sal": sal}
    fuori["piante"] = piante
    return fuori, scartate


def firma(dati):
    """Firma del progetto SENZA le immagini: dice se qualcosa è cambiato."""
    leggero = dict(dati)
    leggero["piante"] = [{**p, "immagine": len(p.get("immagine") or "")}
                         for p in dati.get("piante") or []]
    return hashlib.md5(json.dumps(leggero, ensure_ascii=False, default=str,
                                  separators=(",", ":"), sort_keys=True)
                       .encode("utf-8")).hexdigest()


def json_bytes(dati):
    """Il progetto come lo scrive il vecchio (`progetto_json_bytes`)."""
    return json.dumps(dati, ensure_ascii=False,
                      separators=(",", ":")).encode("utf-8")


# ------------------------------------------------------------------ banco


class Banco(DisegnoMixin, BusinessPlanMixin):
    """Il progetto aperto. Uno per motore, come una sessione di Streamlit."""

    def __init__(self):
        self.dati, _ = normalizza({})
        # un banco appena acceso non ha niente: nemmeno il modello
        self.dati["voci_scelte"] = []
        self.storia_computo = []
        self.ultimo_salvataggio = None
        self.firma_salvata = None
        self.ripristino_valutato = False
        self.ripreso = None
        self.piante_scartate = []
        self._uso_contati = set()
        self.carica_disegno()
        self.carica_bp()
        self.carica_giro()

    # ------------------------------------------------------ progetto intero

    def carica(self, dati):
        """Mette sul banco un progetto (letto da file o dall'archivio)."""
        self.dati, self.piante_scartate = normalizza(dati)
        self.storia_computo = []
        self.ultimo_salvataggio = None
        self.firma_salvata = None
        self.carica_disegno()
        self.carica_bp()
        self.carica_giro()
        self.giro()

    def nuovo(self):
        """«Svuota tutto»: il computo riparte dalle voci di Migliarina."""
        self.carica(modello_computo.progetto_nuovo())

    def apri(self, nome):
        try:
            self.carica(archivio_locale.carica_progetto(nome))
        except RuntimeError as errore:
            raise ErroreBanco(str(errore)) from errore
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as errore:
            raise ErroreBanco(f"Non riesco ad aprire «{nome}»: {errore}") \
                from errore

    def apri_versione(self, file):
        try:
            self.carica(archivio_locale.carica_versione(file))
        except (OSError, json.JSONDecodeError, UnicodeDecodeError) as errore:
            raise ErroreBanco("Questa versione non è leggibile.") from errore

    def vuoto(self):
        """True se non c'è ancora niente da perdere (`progetto_e_vuoto`)."""
        d = self.dati
        if d["piante"] or d["voci_scelte"]:
            return False
        bp = d["business_plan"]
        if bp.get("bp_acquisto") or bp.get("bp_vendita"):
            return False
        if d["spese"]:
            return False
        if d["materiali"] and d["materiali"] != materiali.elenco_standard():
            return False
        return True

    def riapri_ultimo(self):
        """All'avvio, una volta sola e solo a banco vuoto: l'ultimo salvato."""
        if self.ripristino_valutato:
            return
        self.ripristino_valutato = True
        if not self.vuoto():
            return
        nome, quando = archivio_locale.ultimo_progetto()
        if not nome:
            return
        try:
            self.carica(archivio_locale.carica_progetto(nome))
        except Exception:                                    # noqa: BLE001
            return            # file illeggibile: si parte puliti
        self.ripreso = {"nome": nome, "quando": quando.isoformat()}

    def nome_archivio(self):
        """Il nome con cui salvare al volo. Mai vuoto."""
        return (self.dati["progetto"]["nome"] or "").strip() \
            or "Progetto senza nome"

    def nome_file(self, estensione):
        base = (self.dati["progetto"]["nome"] or "computo").strip() \
            .replace(" ", "_")
        base = "".join(c for c in base if c.isalnum() or c in "_-") \
            or "computo"
        return f"{base}.{estensione}"

    def firma(self):
        return firma(self.dati)

    def stato_salvataggio(self):
        """'vuoto' · 'mai' · 'modificato' · 'pari' (la testata lo dice)."""
        if self.vuoto():
            return "vuoto"
        if self.ultimo_salvataggio is None:
            return "mai"
        if self.firma() != self.firma_salvata:
            return "modificato"
        return "pari"

    def _segna_salvato(self):
        self.ultimo_salvataggio = datetime.now()
        self.firma_salvata = self.firma()

    def _conta_uso(self, nome):
        """Una lavorazione per progetto e per sessione, non per salvataggio."""
        if nome in self._uso_contati:
            return
        self._uso_contati.add(nome)
        try:
            _registra_uso("CME", "operazione_valutata", riferimento=nome)
        except Exception:                                    # noqa: BLE001
            pass       # il registro è un testimone, non ferma il lavoro

    def salva(self):
        """Il tasto «Salva»: in archivio, col nome del progetto, subito."""
        nome = self.nome_archivio()
        try:
            archivio_locale.salva_progetto(nome, json_bytes(self.dati))
        except OSError as errore:
            raise ErroreBanco(f"Non sono riuscito a salvare: {errore}") \
                from errore
        self._segna_salvato()
        self._conta_uso(nome)
        return nome

    def archivia(self, nome, sovrascrivi=False):
        """«Archivia» con un nome scelto: chiede conferma per sovrascrivere."""
        nome = (nome or "").strip()
        if not nome:
            raise ErroreBanco("Dai un nome al progetto prima di archiviarlo.")
        if nome in archivio_locale.elenco_progetti() and not sovrascrivi:
            raise ErroreBanco(f"«{nome}» esiste già in archivio: spunta la "
                              "conferma, oppure cambia nome.")
        try:
            archivio_locale.salva_progetto(nome, json_bytes(self.dati))
        except OSError as errore:
            raise ErroreBanco(f"Errore nel salvataggio: {errore}") from errore
        self._segna_salvato()
        self._conta_uso(nome)
        return nome

    def elimina_dallarchivio(self, nome):
        try:
            archivio_locale.elimina_progetto(nome)
        except Exception as errore:                          # noqa: BLE001
            raise ErroreBanco(f"Non riesco a eliminarlo: {errore}") \
                from errore

    def scarica_json(self):
        """Il .json da portarsi altrove: conta come messa al sicuro."""
        contenuto = json_bytes(self.dati)
        self._segna_salvato()
        return contenuto

    def imposta_progetto(self, campo, valore):
        """I dati del progetto: nome, committente, oggetto, luogo, data, IVA."""
        prg = self.dati["progetto"]
        if campo == "data":
            try:
                prg["data"] = date.fromisoformat(str(valore)).isoformat()
            except ValueError as errore:
                raise ErroreBanco("Data non valida.") from errore
        elif campo == "aliquota_iva":
            prg["aliquota_iva"] = min(100.0, max(0.0, float(valore or 0.0)))
        elif campo in ("nome", "committente", "oggetto", "luogo"):
            prg[campo] = str(valore or "")
        else:
            raise ErroreBanco(f"Campo sconosciuto: {campo}")

    # --------------------------------------------------------- le voci

    def _extra(self):
        return {v["codice"]: v for v in self.dati["voci"]}

    def voce(self, codice):
        """La voce con quel codice: prima nel listino, poi fra le tue."""
        return listino.voce_per_codice(codice) or self._extra().get(codice)

    def e_tua(self, codice):
        return listino.voce_per_codice(codice) is None \
            and codice in self._extra()

    def quantita(self, codice):
        extra = self._extra().get(codice)
        if extra is not None and listino.voce_per_codice(codice) is None:
            return float(extra.get("quantita_manuale") or 0.0)
        return float((self.dati["listino_stato"].get(codice) or {})
                     .get("q", 0.0))

    def prezzo(self, codice):
        extra = self._extra().get(codice)
        if extra is not None and listino.voce_per_codice(codice) is None:
            return float(extra.get("prezzo") or 0.0)
        guida = listino.voce_per_codice(codice)
        stato = self.dati["listino_stato"].get(codice)
        if stato is not None:
            return float(stato.get("p", guida["prezzo"]))
        return float(guida["prezzo"]) if guida else 0.0

    def testi(self, codice):
        """Descrizione e unità correnti: riscritte, o quelle del listino."""
        voce = self.voce(codice)
        if voce is None:
            return "", ""
        if self.e_tua(codice):
            return voce["descrizione"], voce["um"]
        t = self.dati["testi_voci"].get(codice) or {}
        return (t.get("d") or voce["descrizione"], t.get("u") or voce["um"])

    def _scrivi_listino(self, codice, q=None, p=None):
        """listino_stato tiene solo quello che si discosta dalla guida."""
        guida = listino.voce_per_codice(codice)
        stato = self.dati["listino_stato"]
        elemento = dict(stato.get(codice) or {"q": 0.0, "p": guida["prezzo"]})
        if q is not None:
            elemento["q"] = float(q)
        if p is not None:
            elemento["p"] = float(p)
        if elemento["q"] > 0 or elemento["p"] != guida["prezzo"]:
            stato[codice] = elemento
        else:
            stato.pop(codice, None)

    def _voce_nota(self, codice):
        if self.voce(codice) is None:
            raise ErroreBanco(f"La voce {codice} non esiste.")

    def scrivi_quantita(self, codice, valore, a_mano=True):
        """Una quantità scritta da una persona: da lì il disegno non la tocca.

        `a_mano=False` è il disegno che scrive (la quantità segue lui).
        """
        self._voce_nota(codice)
        valore = max(0.0, float(valore or 0.0))
        if a_mano and abs(valore - self.quantita(codice)) > 0.005:
            if codice not in self.dati["voci_a_mano"]:
                self.dati["voci_a_mano"].append(codice)
        if self.e_tua(codice):
            self._extra()[codice]["quantita_manuale"] = valore
        else:
            self._scrivi_listino(codice, q=valore)

    def scrivi_prezzo(self, codice, valore):
        self._voce_nota(codice)
        valore = max(0.0, float(valore or 0.0))
        if self.e_tua(codice):
            self._extra()[codice]["prezzo"] = valore
        else:
            self._scrivi_listino(codice, p=valore)

    def scrivi_descrizione(self, codice, testo):
        """Vuota vuol dire «quella del listino». Per una voce tua, invece,
        una descrizione vuota non c'è: resta quella di prima.

        ⚠️ Le voci tue si riscrivono DENTRO la voce: nel vecchio la
        riscrittura finiva in una chiave che il salvataggio non portava
        nel file, e riaprendo tornava il testo di prima.
        """
        self._voce_nota(codice)
        testo = (testo or "").strip()
        if self.e_tua(codice):
            if testo:
                self._extra()[codice]["descrizione"] = testo
            return
        self._scrivi_testo(codice, "d", testo)

    def scrivi_unita(self, codice, um):
        """L'unità, con la proposta del «a corpo»: 1 se la quantità è vuota."""
        self._voce_nota(codice)
        um = (um or "").strip()
        if self.e_tua(codice):
            if um:
                self._extra()[codice]["um"] = um
        else:
            guida = listino.voce_per_codice(codice)
            self._scrivi_testo(codice, "u", "" if um == guida["um"] else um)
        if self.testi(codice)[1] == UM_A_CORPO and not self.quantita(codice):
            if self.e_tua(codice):
                self._extra()[codice]["quantita_manuale"] = 1.0
            else:
                self._scrivi_listino(codice, q=1.0)

    def _scrivi_testo(self, codice, chiave, testo):
        testi = self.dati["testi_voci"]
        elemento = dict(testi.get(codice) or {"d": None, "u": None})
        elemento[chiave] = testo or None
        if elemento.get("d") or elemento.get("u"):
            testi[codice] = elemento
        else:
            testi.pop(codice, None)

    # ------------------------------------------------ scelte e categorie

    def categoria_accesa(self, categoria):
        return (categoria not in listino.CATEGORIE_FACOLTATIVE
                or categoria in self.dati["lavori_facoltativi"])

    def categorie_accese(self):
        return [c for c in listino.CATEGORIE if self.categoria_accesa(c)]

    def categorie_del_computo(self):
        """Quelle del listino accese, più le inventate («Superfici»)."""
        extra = [v["categoria"] for v in self.dati["voci"]
                 if v["categoria"] not in listino.CATEGORIE]
        return self.categorie_accese() + list(dict.fromkeys(extra))

    def scelte(self):
        """Le voci del computo, senza quelle dei lavori spenti."""
        return [c for c in self.dati["voci_scelte"]
                if (v := self.voce(c)) is None
                or self.categoria_accesa(v["categoria"])]

    def scelte_della_categoria(self, categoria):
        return [c for c in self.scelte()
                if (v := self.voce(c)) and v["categoria"] == categoria]

    def porta_nel_computo(self, codice):
        self._voce_nota(codice)
        if codice in self.dati["voci_scartate"]:
            self.dati["voci_scartate"].remove(codice)
        if codice not in self.dati["voci_scelte"]:
            self.dati["voci_scelte"].append(codice)

    def togli_dal_computo(self, codice):
        """Quantità, prezzo e testi restano: ripescata, si ritrova com'era."""
        if codice in self.dati["voci_scelte"]:
            self.dati["voci_scelte"].remove(codice)

    def scarta(self, codice):
        """Fuori dal pool di QUESTO progetto. Il listino non si tocca."""
        self.togli_dal_computo(codice)
        if codice not in self.dati["voci_scartate"]:
            self.dati["voci_scartate"].append(codice)

    def ripristina_scarti(self):
        self.dati["voci_scartate"] = []

    def prendi_tutte(self):
        """Tutto il listino non ancora deciso (scelte e scarti restano)."""
        for voce in listino.VOCI:
            c = voce["codice"]
            if (self.categoria_accesa(voce["categoria"])
                    and c not in self.dati["voci_scelte"]
                    and c not in self.dati["voci_scartate"]):
                self.dati["voci_scelte"].append(c)

    def scambia_con_vicina(self, codice, verso):
        """Su (−1) o giù (+1), ma solo fra le vicine di casa."""
        scelte = self.dati["voci_scelte"]
        voce = self.voce(codice)
        if voce is None or codice not in scelte:
            return
        sorelle = [c for c in scelte if (v := self.voce(c))
                   and v["categoria"] == voce["categoria"]]
        posto = sorelle.index(codice) + int(verso)
        if not 0 <= posto < len(sorelle):
            return
        qui, la = scelte.index(codice), scelte.index(sorelle[posto])
        scelte[qui], scelte[la] = scelte[la], scelte[qui]

    def codice_nuovo(self, categoria):
        """Il prossimo codice libero della categoria: l'ultimo, più uno."""
        serie = serie_della_categoria(categoria)
        presi = {v["codice"] for v in listino.voci_della_categoria(categoria)}
        presi |= set(self._extra())
        n = 1
        while f"{serie}.{n}" in presi:
            n += 1
        return f"{serie}.{n}"

    def aggiungi_voce(self, categoria, descrizione, um, quantita, prezzo,
                      codice=None):
        """Una voce che il listino non ha: nasce NEL computo, non nel pool."""
        codice = codice or self.codice_nuovo(categoria)
        self.dati["voci"].append({
            "categoria": categoria, "codice": codice,
            "descrizione": descrizione or "Voce senza descrizione",
            "um": um or "", "parti": None, "lunghezza": None,
            "larghezza": None, "altezza": None,
            "quantita_manuale": float(quantita or 0.0),
            "prezzo": float(prezzo or 0.0)})
        if codice not in self.dati["voci_scelte"]:
            self.dati["voci_scelte"].append(codice)
        return codice

    def crea_voce_a_mano(self, categoria, descrizione, um, quantita, prezzo):
        """Il pannello «Aggiungi una voce tua»."""
        descrizione = (descrizione or "").strip()
        if not descrizione:
            raise ErroreBanco("Dai una descrizione alla voce: nel computo si "
                              "legge quella, non il codice.")
        categoria = categoria or listino.CATEGORIE[0]
        if um == UM_A_CORPO and not quantita:
            quantita = 1.0
        return self.aggiungi_voce(categoria, descrizione, um, quantita,
                                  prezzo)

    def sposta_voce_tua(self, codice, categoria):
        """Una voce tua cambia casa, e il codice cambia con lei."""
        voce = self._extra().get(codice)
        if (voce is None or listino.voce_per_codice(codice) is not None
                or not categoria or categoria == voce["categoria"]):
            return codice
        nuovo = self.codice_nuovo(categoria)
        voce["codice"] = nuovo
        voce["categoria"] = categoria
        scelte = self.dati["voci_scelte"]
        if codice in scelte:
            scelte[scelte.index(codice)] = nuovo
        else:
            scelte.append(nuovo)
        if codice in self.dati["voci_scartate"]:
            self.dati["voci_scartate"].remove(codice)
        mano = self.dati["voci_a_mano"]
        if codice in mano:
            mano[mano.index(codice)] = nuovo
        return nuovo

    def cambia_lavoro_facoltativo(self, categoria, acceso):
        """Tetto e facciata: spenti non contano, riaccesi si ritrovano."""
        if categoria not in listino.CATEGORIE_FACOLTATIVE:
            raise ErroreBanco(f"{categoria} non è un lavoro facoltativo.")
        accese = self.dati["lavori_facoltativi"]
        if not acceso:
            if categoria in accese:
                accese.remove(categoria)
            return
        if categoria not in accese:
            accese.append(categoria)
        if not self.scelte_della_categoria(categoria):
            for voce in listino.voci_della_categoria(categoria):
                if voce["codice"] not in self.dati["voci_scartate"]:
                    self.porta_nel_computo(voce["codice"])

    def riaggancia_al_disegno(self, codice=None):
        if codice is None:
            self.dati["voci_a_mano"] = []
        elif codice in self.dati["voci_a_mano"]:
            self.dati["voci_a_mano"].remove(codice)

    # ------------------------------------------------------- l'annulla

    def registra_storia_computo(self, descrizione):
        """Prima di un'azione che cambia tutto in un colpo."""
        self.storia_computo.append({
            "descrizione": descrizione,
            "stato": copy.deepcopy({k: self.dati[k] for k in (
                "listino_stato", "voci", "voci_scelte", "voci_scartate")})})
        del self.storia_computo[:-PASSI_STORIA_COMPUTO]

    def annulla_computo(self):
        if not self.storia_computo:
            return None
        passo = self.storia_computo.pop()
        self.dati.update(copy.deepcopy(passo["stato"]))
        return passo["descrizione"]

    # ---------------------------------------------------- il mio listino

    def _prezzi_correnti(self):
        return {v["codice"]: self.prezzo(v["codice"]) for v in listino.VOCI}

    def listino_personale(self):
        """Com'è messo il listino personale rispetto a questo progetto."""
        salvati, quando = listino_personale.carica()
        correnti = self._prezzi_correnti()
        return {
            "salvati": len(salvati or {}),
            "quando": quando,
            "miei": len(listino_personale.scostamenti(listino.VOCI,
                                                      correnti)),
            "da_applicare": len(listino_personale.da_applicare(
                salvati, listino.VOCI, correnti)),
            "file": str(listino_personale.percorso()),
        }

    def salva_listino_personale(self):
        miei = listino_personale.scostamenti(listino.VOCI,
                                             self._prezzi_correnti())
        if not miei:
            raise ErroreBanco("Nessun prezzo diverso dalla guida da salvare.")
        try:
            listino_personale.salva(miei)
        except OSError as errore:
            raise ErroreBanco(f"Non sono riuscito a salvare il listino: "
                              f"{errore}") from errore
        return len(miei)

    def applica_listino_personale(self):
        salvati, _ = listino_personale.carica()
        da_scrivere = listino_personale.da_applicare(
            salvati, listino.VOCI, self._prezzi_correnti())
        if not da_scrivere:
            return 0
        self.registra_storia_computo("applicazione del listino personale")
        for codice, prezzo in da_scrivere.items():
            self._scrivi_listino(codice, p=prezzo)
        return len(da_scrivere)

    def elimina_listino_personale(self):
        listino_personale.elimina()

    # --------------------------------------------------- i conti del computo

    def voci_calcolate(self):
        """Le voci scelte con quantità > 0, calcolate (`voci_dal_listino`)."""
        voci = []
        for codice in self.scelte():
            voce = self.voce(codice)
            if voce is None:
                continue
            q = self.quantita(codice)
            if q <= 0:
                continue
            descrizione, um = self.testi(codice)
            voci.append({"categoria": voce["categoria"], "codice": codice,
                         "descrizione": descrizione, "um": um,
                         "parti": None, "lunghezza": None, "larghezza": None,
                         "altezza": None, "quantita_manuale": q,
                         "prezzo": self.prezzo(codice)})
        return calcoli.calcola_computo(voci)

    def totale_categoria(self, categoria):
        return round(sum(self.quantita(c) * self.prezzo(c)
                         for c in self.scelte_della_categoria(categoria)), 2)

    def totali(self):
        calcolate = self.voci_calcolate()
        totale = calcoli.totale_generale(calcolate)
        aliquota = self.dati["progetto"]["aliquota_iva"]
        iva, con_iva = calcoli.totale_con_iva(totale, aliquota)
        per_cat = calcoli.totali_per_categoria(calcolate)
        return {"voci": calcolate, "totale": totale, "aliquota_iva": aliquota,
                "iva": iva, "totale_con_iva": con_iva,
                "per_categoria": per_cat,
                "incidenze": calcoli.incidenze_percentuali(per_cat, totale)}

    # ------------------------------------------------ il giro della pagina

    def carica_giro(self):
        """Dopo un caricamento: quello che il vecchio azzera aprendo."""
        self._mq_automatici = 0.0
        self._importo_scritto = None
        self.supvoce = {c: acceso for c, _g, acceso in VOCI_DA_SUPERFICI}

    def giro(self):
        """Quello che il vecchio rifà a ogni giro di pagina, e che finisce
        nel file: le categorie di superficie, le spunte dei locali, le
        quantità agganciate al disegno, i mq e gli imprevisti del business
        plan. Si chiama dopo ogni gesto, come Streamlit rifaceva la pagina.
        """
        d = self.dati
        d["categorie"] = categorie_per_progetto(d["piante"])
        self._spunte_dei_locali()
        grandezze = self.grandezze()
        if d["auto_computo"] and any(v > 0 for v in grandezze.values()):
            for codice, valore in self.proposte_dal_disegno(
                    grandezze).items():
                self.scrivi_quantita(codice, valore, a_mano=False)
                if codice not in d["voci_scelte"]:
                    d["voci_scelte"].append(codice)
        self._giro_business_plan()
        self._importo_scritto = None

    def piante_calcolo(self):
        """Le piante come le vogliono le funzioni di planimetria.py."""
        return [dict(p, uid=i) for i, p in enumerate(self.dati["piante"])]

    def percentuali(self):
        return mappa_percentuali(self.dati["categorie"])

    def _zona(self, uid, zid):
        return next((z for z in self.dati["piante"][uid]["zone"]
                     if z.get("id") == zid), None)

    def _spunte_dei_locali(self):
        """Le spunte che la tabella dei locali scrive nelle zone.

        Nel vecchio la tabella le riempie coi valori di norma appena la
        disegna, e da lì finiscono nel file: una stanza interna si
        pavimenta, si tinteggia e ha il battiscopa; un bagno è rivestito e
        lo zoccolino di norma non ce l'ha.
        """
        perc = self.percentuali()
        righe, _ = planimetria.riepilogo_locali(
            self.piante_calcolo(), escludi=CATEGORIE_INVOLUCRO)
        for r in righe:
            zona = self._zona(r["uid"], r["id"])
            if zona is None:
                continue
            interna = percento_di(perc, r["categoria"]) >= 100.0
            bagno = any(parola in (r["nome"] + " " + r["categoria"]).lower()
                        for parola in ("bagno", "wc", "w.c"))
            for chiave, predefinito in (("pavimento", interna),
                                        ("battiscopa", interna and not bagno),
                                        ("pittura", interna),
                                        ("rivestito", bagno)):
                zona[chiave] = bool(predefinito if zona.get(chiave) is None
                                    else zona[chiave])

    def locali(self):
        """I locali con le loro spunte, per la tabella e per i conti."""
        righe, senza_scala = planimetria.riepilogo_locali(
            self.piante_calcolo(), escludi=CATEGORIE_INVOLUCRO)
        fuori = []
        for r in righe:
            zona = self._zona(r["uid"], r["id"])
            if zona is None:
                continue
            fuori.append({**r, "m2": round(r["m2"], 2),
                          "perimetro": round(r["perimetro"], 2),
                          "pavimento": bool(zona.get("pavimento")),
                          "battiscopa": bool(zona.get("battiscopa")),
                          "pittura": bool(zona.get("pittura")),
                          "rivestito": bool(zona.get("rivestito")),
                          "esterno": (zona.get("categoria") or "")
                          in CATEGORIE_ESTERNE})
        return fuori, senza_scala

    def aperture(self):
        f = self.dati["finiture"]
        return [
            {"nome": "Finestre", "n": f["fin_n"], "larghezza": f["fin_larg"],
             "altezza": f["fin_alt"], "battiscopa": False},
            {"nome": "Porte finestra", "n": f["pf_n"],
             "larghezza": f["pf_larg"], "altezza": f["pf_alt"],
             "battiscopa": True},
        ]

    def finiture(self):
        """`quantita_finiture` coi locali e le detrazioni del progetto."""
        locali, _ = self.locali()
        if not locali:
            return None
        f = self.dati["finiture"]
        return planimetria.quantita_finiture(
            locali, self.dati["altezza_locali"],
            larghezza_porta=f["porta_larg"], altezza_porta=f["porta_alt"],
            n_porte=f["porta_n"], altezza_rivestimento=f["riv_alt"],
            n_porte_esterne=f["porta_n_est"], aperture=self.aperture(),
            n_porte_rivestiti=f["riv_porte_n"],
            n_finestre_rivestiti=f["riv_finestre_n"],
            larghezza_finestra=f["fin_larg"],
            altezza_finestra=f["fin_alt"])

    def muri(self):
        """I muri per tipo, al netto delle aperture dichiarate."""
        riep, senza_scala = planimetria.riepilogo_pareti(
            self.piante_calcolo(), self.dati["altezza_locali"])
        if not riep:
            return None, senza_scala
        f = self.dati["finiture"]
        vuoto = {"n": 0, "ml": 0.0, "m2": 0.0}
        fuori = {}
        for tipo, chiave_n in (("demolire", "apert_dem_n"),
                               ("costruire", "apert_cos_n"),
                               ("cartongesso", "apert_car_n")):
            muro = riep.get(tipo, vuoto)
            aperture = planimetria.superficie_aperture(
                f[chiave_n], f["apert_larg"], f["apert_alt"])
            fuori[tipo] = {**muro, "aperture": aperture,
                           "netto": planimetria.muri_al_netto(muro["m2"],
                                                              aperture)}
        fuori["esistente"] = riep.get("esistente", vuoto)
        return fuori, senza_scala

    def grandezze(self):
        """Le misure del disegno che possono andare nel computo."""
        grandezze = {}
        q = self.finiture()
        if q is not None:
            grandezze.update({
                "pavimento": q["pavimento"],
                "pavimento_esterno": q["pavimento_esterno"],
                "rivestimenti": q["rivestimenti"],
                "battiscopa": q["battiscopa"],
                "tinteggiatura": q["pareti"] + q["soffitti"],
                "tinteggiatura_pareti": q["pareti"],
                "soffitti": q["soffitti"],
            })
        muri, _ = self.muri()
        if muri is not None:
            grandezze["muri_demolire"] = muri["demolire"]["netto"]
            grandezze["muri_costruire"] = muri["costruire"]["netto"]
            grandezze["muri_cartongesso"] = muri["cartongesso"]["netto"]
            grandezze["rasatura"] = round(2 * muri["costruire"]["netto"], 2)
        return grandezze

    def voci_dal_disegno(self, grandezze):
        """Le voci che il disegno può alimentare, con la loro spunta.

        Non le scartate, e di due alternative una sola
        (`planimetria.voci_alimentate`).
        """
        alimentate = planimetria.voci_alimentate(
            [c for c, g, _a in VOCI_DA_SUPERFICI
             if listino.voce_per_codice(c) is not None
             and round(grandezze.get(g, 0.0), 2) > 0],
            self.dati["voci_scelte"], self.dati["voci_scartate"],
            ALTERNATIVE_DAL_DISEGNO)
        fuori = []
        for codice, grandezza, _acceso in VOCI_DA_SUPERFICI:
            voce = listino.voce_per_codice(codice)
            quantita = round(grandezze.get(grandezza, 0.0), 2)
            if voce is None or quantita <= 0 or codice not in alimentate:
                continue
            fuori.append({"codice": codice, "grandezza": grandezza,
                          "descrizione": voce["descrizione"],
                          "um": voce["um"], "quantita": quantita,
                          "attuale": self.quantita(codice),
                          "spuntata": bool(self.supvoce.get(codice)),
                          "a_mano": codice in self.dati["voci_a_mano"]})
        return fuori

    def proposte_dal_disegno(self, grandezze):
        selezionate = [(v["codice"], v["grandezza"])
                       for v in self.voci_dal_disegno(grandezze)
                       if v["spuntata"]]
        a_mano = [c for c, _ in selezionate if c in self.dati["voci_a_mano"]]
        return planimetria.voci_da_riscrivere(
            selezionate, grandezze,
            {c: self.quantita(c) for c, _ in selezionate}, escluse=a_mano)

    def mq_da_planimetria(self):
        _, _, mq, _ = planimetria.riepilogo_superfici(
            self.piante_calcolo(), self.percentuali(),
            escludi=CATEGORIE_SOLO_COMPUTO)
        return mq

    def mq_calpestabili(self):
        mq, _ = planimetria.superficie_calpestabile(
            self.piante_calcolo(), self.percentuali(),
            escludi=CATEGORIE_INVOLUCRO)
        return mq

    def cantiere_consuntivo(self):
        """Lavori, materiale e architetto: sostenute più da sostenere."""
        return round(sum(
            r["importo"] for r in self.dati["spese"] + self.dati["spese_prev"]
            if r["categoria"] in fattibilita.CATEGORIE_CANTIERE), 2)

    def ristrutturazione(self):
        """(importo dei lavori usato dal business plan, usa_consuntivo)."""
        bp = self.dati["business_plan"]
        consuntivo = self.cantiere_consuntivo()
        if bool(bp.get("bp_usa_consuntivo")) and consuntivo > 0:
            return consuntivo, True
        return (bp["bp_ristr"] or self.totali()["totale"]), False

    def _giro_business_plan(self):
        """I mq dalla planimetria (finché nessuno li scrive a mano) e gli
        imprevisti, che sono una percentuale dei lavori."""
        bp = self.dati["business_plan"]
        mq = self.mq_da_planimetria()
        if mq and bp["bp_mq"] == self._mq_automatici:
            bp["bp_mq"] = mq
            self._mq_automatici = mq
        ristr, usa = self.ristrutturazione()
        base = 0.0 if usa else ristr
        if base and self._importo_scritto != "bp_imprevisti":
            bp["bp_imprevisti"] = round(
                base * bp["bp_imprevisti_pct"] / 100, 2)

    # -------------------------------------------------------- i materiali

    def scrivi_materiali(self, righe):
        """L'elenco intero, come lo rimanda la tabella (una riga, una
        descrizione: le altre non esistono ancora)."""
        self.dati["materiali"] = materiali_da_df(df_materiali_da_righe(
            righe or []))

    def riordina_materiali(self, criterio):
        """Riordina i DATI, stabile, su una chiave sola."""
        righe = list(self.dati["materiali"])
        if criterio == "Stato":
            pos = {s: i for i, s in enumerate(materiali.STATI)}
            righe.sort(key=lambda r: pos.get(r["stato"], len(pos)))
        elif criterio == "Fornitore":
            righe.sort(key=lambda r: (r["fornitore"] or "").strip().upper()
                       or "￿")
        else:
            pos = {c: i for i, c in enumerate(materiali.CAPITOLI)}
            righe.sort(key=lambda r: pos.get(r["capitolo"], len(pos)))
        self.dati["materiali"] = righe


# I campi numerici del business plan scritti all'italiana: qui per chi
# legge le chiavi dal banco (vedi server). Lo stesso elenco del vecchio.
CAMPI_IMPORTO = dict(CAMPI_NUMERO_IT)
