"""La parte del banco che riguarda il disegno: la scheda «Misura da planimetria».

È la traduzione di `scheda_planimetria()` e delle sue funzioni di contorno
in streamlit_app.py (gestisci_evento, registra_storia, annulla_ultima,
carica_immagini, pdf_planimetrie_bytes…), senza Streamlit. Le piante
stanno in `dati["piante"]` nel formato del file — nome, mpp, zone, pareti,
immagine in base64 — e tutto il resto (la zona selezionata, la scala in
attesa, l'annulla, l'anteprima della pulizia) vive solo finché il banco è
aperto, come nella sessione del vecchio.
"""
from __future__ import annotations

import base64
import copy
import hashlib
import io

from PIL import Image

import planimetria
import stampa
import tavola
from costanti import (
    CANON_MAX,
    CATEGORIA_STANZE,
    CATEGORIE_INVOLUCRO,
    CATEGORIE_SOLO_COMPUTO,
    COLORE_CATEGORIA_SUP,
    DA_ANNULLARE,
    PALETTE_ZONE,
    PASSI_STORIA,
    TIPI_PARETE,
    TIPI_PARETE_SCELTA,
    VOCI_DA_SUPERFICI,
)
from formato import numero_it


class ErroreDisegno(Exception):
    pass


def immagine_b64(img, qualita=85):
    """L'immagine come la salva il vecchio (`pil_a_src`): JPEG, qualità 85."""
    buffer = io.BytesIO()
    img.save(buffer, format="JPEG", quality=qualita)
    return base64.b64encode(buffer.getvalue()).decode()


def carica_immagini(contenuto, nome_file):
    """Le pagine del file caricato come immagini RGB (dieci al massimo per
    un PDF, a 200 dpi), ridotte alla misura canonica."""
    immagini = []
    if nome_file.lower().endswith(".pdf") or contenuto[:4] == b"%PDF":
        import fitz
        documento = fitz.open(stream=contenuto, filetype="pdf")
        for pagina in list(documento)[:10]:
            pix = pagina.get_pixmap(dpi=200)
            immagini.append(Image.frombytes("RGB", (pix.width, pix.height),
                                            pix.samples))
    else:
        immagini.append(Image.open(io.BytesIO(contenuto)).convert("RGB"))
    pronte = []
    for img in immagini:
        if img.width > CANON_MAX:
            img = img.resize((CANON_MAX, round(img.height * CANON_MAX
                                               / img.width)))
        pronte.append(img)
    return pronte


def etichetta_zona(zona, mpp, perc_map, impostazioni, percento_di):
    righe = []
    if impostazioni["nome"]:
        righe.append(zona.get("nome") or zona["categoria"])
    if impostazioni["m2"] and mpp:
        righe.append(f"{numero_it(planimetria.area_reale_m2(zona['punti'], mpp), 2)} m²")
    if impostazioni.get("perimetro") and mpp:
        righe.append(
            f"per. {numero_it(planimetria.perimetro_reale_m(zona['punti'], mpp), 2)} m")
    if impostazioni["percento"]:
        righe.append(f"{numero_it(percento_di(perc_map, zona['categoria']), 0)} %")
    return "\n".join(righe)


def etichetta_parete(parete, mpp):
    if not mpp:
        return "— m"
    metri = planimetria.distanza_pixel(parete["p1"], parete["p2"]) * mpp
    return f"{numero_it(metri, 2)} m"


class DisegnoMixin:
    """I gesti della scheda planimetria. Il Banco la eredita."""

    def carica_disegno(self):
        """Quello che il vecchio azzera aprendo un progetto."""
        self.pianta_idx = 0
        self.sel_zona = None
        self.sel_parete = None
        self.scala_temp = None
        self.ultimo_seq = None
        self.ultimo_rilevamento = None
        self.storia = []
        self.cat_attiva = None
        self.tipo_parete = "demolire"
        self.anteprima_pulizia = None
        self.originali = {}          # indice della pianta → immagine di prima
        self.ritagli = {}            # indice della pianta → ritagli da annullare
        self.scala_persa = False
        self._immagini = {}          # cache: impronta → PIL

    # ------------------------------------------------------------ immagini

    def immagine(self, i):
        """L'immagine PIL di una pianta (decodificata una volta sola)."""
        b64 = self.dati["piante"][i]["immagine"]
        chiave = hashlib.md5(b64[:4096].encode() + str(len(b64)).encode()) \
            .hexdigest()
        if chiave not in self._immagini:
            self._immagini[chiave] = Image.open(
                io.BytesIO(base64.b64decode(b64))).convert("RGB")
        return self._immagini[chiave]

    def impronta_immagine(self, i):
        b64 = self.dati["piante"][i]["immagine"]
        return hashlib.md5(b64.encode()).hexdigest()[:12]

    def _pianta(self, i=None):
        piante = self.dati["piante"]
        if not piante:
            raise ErroreDisegno("Nessuna planimetria caricata.")
        i = self.pianta_idx if i is None else int(i)
        if not 0 <= i < len(piante):
            raise ErroreDisegno("Questa planimetria non c'è più.")
        return piante[i]

    def _nuovo_id(self, pianta):
        ids = [z.get("id", 0) for z in pianta["zone"]] + \
              [p.get("id", 0) for p in pianta["pareti"]]
        return (max(ids) + 1) if ids else 1

    # ---------------------------------------------------- piante: il banco

    def aggiungi_planimetrie(self, contenuto, nome_file):
        """Le pagine del file diventano planimetrie, e si apre la prima."""
        try:
            immagini = carica_immagini(contenuto, nome_file)
        except Exception as errore:                          # noqa: BLE001
            raise ErroreDisegno(f"Non riesco a leggere questo file: "
                                f"{errore}") from errore
        base = nome_file.rsplit(".", 1)[0]
        primo = len(self.dati["piante"])
        for n, img in enumerate(immagini):
            nome = base if len(immagini) == 1 else f"{base} · pag. {n + 1}"
            self.dati["piante"].append({"nome": nome, "mpp": None, "zone": [],
                                        "pareti": [],
                                        "immagine": immagine_b64(img)})
        self.pianta_idx = primo
        self.sel_zona = self.sel_parete = self.scala_temp = None
        return len(immagini)

    def scegli_pianta(self, i):
        self._pianta(i)
        self.pianta_idx = int(i)
        self.sel_zona = self.sel_parete = self.scala_temp = None

    def togli_pianta(self, i):
        self._pianta(i)
        self.dati["piante"].pop(int(i))
        self.originali = {}
        self.ritagli = {}
        self.pianta_idx = max(0, min(self.pianta_idx,
                                     len(self.dati["piante"]) - 1))
        self.sel_zona = self.sel_parete = self.scala_temp = None

    def rinomina_pianta(self, nome):
        pianta = self._pianta()
        pianta["nome"] = (nome or "").strip() or pianta["nome"]

    def scegli_categoria_nuove(self, nome):
        self.cat_attiva = nome

    def scegli_tipo_parete(self, codice):
        if codice not in TIPI_PARETE_SCELTA:
            raise ErroreDisegno(f"Tipo di muro sconosciuto: {codice}")
        self.tipo_parete = codice

    # ---------------------------------------------------------- l'annulla

    def registra_storia(self, descrizione):
        """Da chiamare PRIMA di modificare zone, muri o scala."""
        self.storia.append({"descrizione": descrizione, "piante": [
            {"mpp": p["mpp"], "zone": copy.deepcopy(p["zone"]),
             "pareti": copy.deepcopy(p["pareti"])}
            for p in self.dati["piante"]]})
        del self.storia[:-PASSI_STORIA]

    def annulla_disegno(self):
        """Zone, muri e scala com'erano prima dell'ultima operazione.

        Se tornando indietro la pianta perde la scala, lo si dice: da lì le
        misure non sono più in metri, e in silenzio sembrerebbe un guasto.
        """
        if not self.storia:
            return None
        passo = self.storia.pop()
        self.scala_persa = False
        for pianta, salvata in zip(self.dati["piante"], passo["piante"]):
            if pianta["mpp"] and not salvata["mpp"]:
                self.scala_persa = True
            pianta["mpp"] = salvata["mpp"]
            pianta["zone"] = copy.deepcopy(salvata["zone"])
            pianta["pareti"] = copy.deepcopy(salvata["pareti"])
        self.sel_zona = self.sel_parete = self.scala_temp = None
        self.ultimo_rilevamento = None
        return passo["descrizione"]

    # ------------------------------------------------- i gesti sulla tela

    def evento_tela(self, ev):
        """Un gesto del visualizzatore (gestisci_evento del vecchio)."""
        seq = ev.get("seq")
        if seq is not None and seq == self.ultimo_seq:
            return                          # già applicato
        self.ultimo_seq = seq
        pianta = self._pianta()
        tipo = ev.get("tipo")
        if tipo in DA_ANNULLARE:
            self.registra_storia(DA_ANNULLARE[tipo])
        if tipo == "zona_chiusa":
            punti = [[float(x), float(y)] for x, y in ev.get("punti", [])]
            if len(punti) >= 3:
                nomi = [c["nome"] for c in self.dati["categorie"]]
                categoria = self.cat_attiva or (nomi[0] if nomi
                                                else "Superficie interna")
                pianta["zone"].append({"id": self._nuovo_id(pianta),
                                       "categoria": categoria, "nome": None,
                                       "punti": punti})
        elif tipo == "zona_modificata":
            for zona in pianta["zone"]:
                if zona["id"] == ev.get("id"):
                    zona["punti"] = [[float(x), float(y)]
                                     for x, y in ev.get("punti", [])]
        elif tipo == "zona_eliminata":
            pianta["zone"] = [z for z in pianta["zone"]
                              if z["id"] != ev.get("id")]
            if self.sel_zona == ev.get("id"):
                self.sel_zona = None
        elif tipo == "selezione":
            self.sel_zona = ev.get("zona")
            self.sel_parete = ev.get("parete")
        elif tipo == "etichetta_spostata":
            elenco = pianta["zone"] if ev.get("elemento") == "zona" \
                else pianta["pareti"]
            for elemento in elenco:
                if elemento["id"] == ev.get("id"):
                    elemento["etichetta_pos"] = [float(ev["pos"][0]),
                                                 float(ev["pos"][1])]
        elif tipo == "parete":
            pianta["pareti"].append({"id": self._nuovo_id(pianta),
                                     "p1": list(ev["p1"]),
                                     "p2": list(ev["p2"]),
                                     "tipo": self.tipo_parete})
        elif tipo == "parete_modificata":
            for parete in pianta["pareti"]:
                if parete["id"] == ev.get("id"):
                    parete["p1"] = [float(ev["p1"][0]), float(ev["p1"][1])]
                    parete["p2"] = [float(ev["p2"][0]), float(ev["p2"][1])]
        elif tipo == "parete_eliminata":
            pianta["pareti"] = [p for p in pianta["pareti"]
                                if p["id"] != ev.get("id")]
            if self.sel_parete == ev.get("id"):
                self.sel_parete = None
        elif tipo == "scala":
            self.scala_temp = {"p1": list(ev["p1"]), "p2": list(ev["p2"])}
        elif tipo == "rinomina":
            for zona in pianta["zone"]:
                if zona["id"] == ev.get("id"):
                    zona["nome"] = (ev.get("nome") or "").strip() or None

    # --------------------------------------------------------------- scala

    def imposta_scala(self, metri):
        pianta = self._pianta()
        if not self.scala_temp:
            raise ErroreDisegno("Traccia prima il segmento della scala.")
        metri = float(metri or 0.0)
        if metri <= 0:
            raise ErroreDisegno("Scrivi la misura reale in metri (> 0).")
        dist = planimetria.distanza_pixel(tuple(self.scala_temp["p1"]),
                                          tuple(self.scala_temp["p2"]))
        self.registra_storia("impostazione della scala")
        pianta["mpp"] = planimetria.metri_per_pixel(dist, metri)
        self.scala_temp = None

    def annulla_scala(self):
        self.scala_temp = None

    # ----------------------------------------- zona e parete selezionate

    def _zona_sel(self):
        pianta = self._pianta()
        zona = next((z for z in pianta["zone"] if z["id"] == self.sel_zona),
                    None)
        if zona is None:
            raise ErroreDisegno("Nessuna zona selezionata.")
        return pianta, zona

    def _parete_sel(self):
        pianta = self._pianta()
        parete = next((p for p in pianta["pareti"]
                       if p["id"] == self.sel_parete), None)
        if parete is None:
            raise ErroreDisegno("Nessun muro selezionato.")
        return pianta, parete

    def nome_zona(self, nome):
        _, zona = self._zona_sel()
        zona["nome"] = (nome or "").strip() or None

    def categoria_zona(self, categoria):
        _, zona = self._zona_sel()
        if categoria and categoria != zona["categoria"]:
            self.registra_storia("cambio di categoria")
            zona["categoria"] = categoria

    def zona_al_computo(self):
        pianta, zona = self._zona_sel()
        if zona["categoria"] in CATEGORIE_INVOLUCRO:
            raise ErroreDisegno("Il perimetro commerciale non è una voce del "
                                "computo: serve solo a misurare la "
                                "superficie vendibile.")
        if not pianta["mpp"]:
            raise ErroreDisegno("Imposta prima la scala.")
        area = planimetria.area_reale_m2(zona["punti"], pianta["mpp"])
        self.aggiungi_voce(
            "Superfici",
            f"{zona.get('nome') or zona['categoria']} — {pianta['nome']}",
            "m²", round(area, 2), None)

    def elimina_zona(self):
        pianta, zona = self._zona_sel()
        self.registra_storia("eliminazione dell'area")
        pianta["zone"] = [z for z in pianta["zone"] if z["id"] != zona["id"]]
        self.sel_zona = None

    def tipo_parete_sel(self, codice):
        _, parete = self._parete_sel()
        if codice != parete.get("tipo", "demolire"):
            self.registra_storia("cambio di tipo del muro")
            parete["tipo"] = codice

    def lunghezza_parete(self, metri):
        """Il muro si allunga o si accorcia dal capo di arrivo."""
        pianta, parete = self._parete_sel()
        metri = float(metri or 0.0)
        if not pianta["mpp"] or metri <= 0:
            return
        nuovo = planimetria.allunga_segmento(parete["p1"], parete["p2"],
                                             metri / pianta["mpp"])
        if nuovo is None:
            return
        self.registra_storia("modifica del muro")
        parete["p2"] = nuovo

    def elimina_parete(self):
        pianta, parete = self._parete_sel()
        self.registra_storia("eliminazione del muro")
        pianta["pareti"] = [p for p in pianta["pareti"]
                            if p["id"] != parete["id"]]
        self.sel_parete = None

    # ------------------------------------------- pulizia e rilevamento

    def prova_pulizia(self, forza):
        import rilevamento
        pianta = self._pianta()
        ripulita, rimossi = rilevamento.pulisci_planimetria(
            self.immagine(self.pianta_idx), pianta["mpp"], float(forza))
        self.anteprima_pulizia = {"indice": self.pianta_idx,
                                  "img": ripulita, "rimossi": rimossi,
                                  "forza": float(forza)}

    def usa_pulizia(self):
        a = self.anteprima_pulizia
        if not a or a["indice"] != self.pianta_idx:
            raise ErroreDisegno("Nessuna anteprima da usare.")
        pianta = self._pianta()
        self.originali.setdefault(self.pianta_idx, pianta["immagine"])
        pianta["immagine"] = immagine_b64(a["img"])
        self.anteprima_pulizia = None

    def scarta_pulizia(self):
        self.anteprima_pulizia = None

    def ripristina_originale(self):
        if self.pianta_idx not in self.originali:
            raise ErroreDisegno("Questa planimetria non è stata pulita.")
        self._pianta()["immagine"] = self.originali.pop(self.pianta_idx)
        self.anteprima_pulizia = None

    # ------------------------------------------------------------ ritaglio

    def _sposta_disegno(self, pianta, dx, dy):
        """Zone, muri ed etichette seguono il foglio quando lo si ritaglia."""
        def sposta(p):
            return [float(p[0]) + dx, float(p[1]) + dy]
        for zona in pianta["zone"]:
            zona["punti"] = [sposta(p) for p in zona["punti"]]
            if zona.get("etichetta_pos"):
                zona["etichetta_pos"] = sposta(zona["etichetta_pos"])
        for parete in pianta["pareti"]:
            parete["p1"], parete["p2"] = sposta(parete["p1"]), sposta(parete["p2"])
            if parete.get("etichetta_pos"):
                parete["etichetta_pos"] = sposta(parete["etichetta_pos"])

    def ritaglia(self, x0, y0, x1, y1):
        """Taglia via i margini del foglio (cartiglio, bordi, quote fuori).

        Si ritaglia l'immagine e basta: i pixel restano della stessa misura,
        quindi la scala resta valida; zone, muri ed etichette già disegnati
        si spostano col foglio. Si può annullare, un ritaglio alla volta.
        """
        pianta = self._pianta()
        i = self.pianta_idx
        img = self.immagine(i)
        x0, x1 = sorted((int(round(float(x0))), int(round(float(x1)))))
        y0, y1 = sorted((int(round(float(y0))), int(round(float(y1)))))
        x0, y0 = max(0, x0), max(0, y0)
        x1, y1 = min(img.width, x1), min(img.height, y1)
        if x1 - x0 < 50 or y1 - y0 < 50:
            raise ErroreDisegno("Il riquadro è troppo piccolo: almeno 50 × 50 "
                                "pixel del disegno.")
        if (x0, y0, x1, y1) == (0, 0, img.width, img.height):
            raise ErroreDisegno("Il riquadro prende tutto il foglio: non c'è "
                                "niente da ritagliare.")
        self.ritagli.setdefault(i, []).append(
            {"immagine": pianta["immagine"], "dx": x0, "dy": y0,
             "originale": self.originali.get(i)})
        pianta["immagine"] = immagine_b64(img.crop((x0, y0, x1, y1)))
        # l'originale della pulizia si ritaglia uguale, o ripristinarlo
        # rimetterebbe un foglio intero sotto un disegno spostato
        if i in self.originali:
            vecchia = Image.open(io.BytesIO(base64.b64decode(
                self.originali[i]))).convert("RGB")
            self.originali[i] = immagine_b64(vecchia.crop((x0, y0, x1, y1)))
        self._sposta_disegno(pianta, -x0, -y0)
        self.scala_temp = None
        self.anteprima_pulizia = None

    def annulla_ritaglio(self):
        passi = self.ritagli.get(self.pianta_idx)
        if not passi:
            raise ErroreDisegno("Questa planimetria non è stata ritagliata.")
        passo = passi.pop()
        pianta = self._pianta()
        pianta["immagine"] = passo["immagine"]
        if passo["originale"] is not None:
            self.originali[self.pianta_idx] = passo["originale"]
        else:
            self.originali.pop(self.pianta_idx, None)
        self._sposta_disegno(pianta, passo["dx"], passo["dy"])
        self.scala_temp = None
        self.anteprima_pulizia = None

    def rileva_stanze(self):
        import rilevamento
        pianta = self._pianta()
        proposte = rilevamento.rileva_stanze(
            self.immagine(self.pianta_idx), pianta["mpp"],
            zone_esistenti=[z["punti"] for z in pianta["zone"]
                            if z["categoria"] not in CATEGORIE_INVOLUCRO])
        if not proposte:
            raise ErroreDisegno("Non ho riconosciuto stanze chiuse su questo "
                                "disegno. Prova a impostare prima la scala, o "
                                "disegna le aree a mano.")
        self.registra_storia("rilevamento automatico delle stanze")
        nuovi = []
        for punti in proposte:
            zid = self._nuovo_id(pianta)
            pianta["zone"].append({"id": zid, "categoria": CATEGORIA_STANZE,
                                   "nome": None, "punti": punti})
            nuovi.append(zid)
        self.ultimo_rilevamento = {"indice": self.pianta_idx, "ids": nuovi}
        return len(proposte)

    def annulla_rilevamento(self):
        r = self.ultimo_rilevamento
        if not r or r["indice"] != self.pianta_idx:
            return
        pianta = self._pianta()
        pianta["zone"] = [z for z in pianta["zone"] if z["id"] not in r["ids"]]
        self.ultimo_rilevamento = None
        self.sel_zona = None

    # --------------------------------------------------------- etichette

    def imposta_etichette(self, campo, valore):
        if campo == "font":
            self.dati["etichette"]["font"] = max(10, min(24, int(valore)))
        elif campo in ("nome", "m2", "percento", "perimetro"):
            self.dati["etichette"][campo] = bool(valore)
        else:
            raise ErroreDisegno(f"Etichetta sconosciuta: {campo}")

    def riporta_etichette(self):
        for p in self.dati["piante"]:
            for elenco in (p["zone"], p["pareti"]):
                for elemento in elenco:
                    elemento.pop("etichetta_pos", None)

    # ------------------------------------- dalle superfici al computo

    def superficie_commerciale_al_computo(self):
        _, _, tot_comm, _ = planimetria.riepilogo_superfici(
            self.piante_calcolo(), self.percentuali(),
            escludi=CATEGORIE_SOLO_COMPUTO)
        self.aggiungi_voce(
            "Superfici", "Superficie commerciale — "
            + (self.dati["progetto"]["nome"] or "fabbricato"),
            "m²", round(tot_comm, 2), None)

    def imposta_altezza(self, metri):
        self.dati["altezza_locali"] = max(1.0, min(6.0, float(metri)))

    def spunta_locale(self, pianta, zona, campo, valore):
        if campo not in ("pavimento", "battiscopa", "pittura", "rivestito"):
            raise ErroreDisegno(f"Spunta sconosciuta: {campo}")
        z = self._zona(int(pianta), zona)
        if z is None:
            raise ErroreDisegno("Questo locale non c'è più.")
        z[campo] = bool(valore)

    def imposta_finitura(self, campo, valore):
        f = self.dati["finiture"]
        if campo not in f:
            raise ErroreDisegno(f"Misura sconosciuta: {campo}")
        f[campo] = max(0, int(valore)) if isinstance(f[campo], int) \
            else max(0.0, float(valore))

    def aggancia_al_disegno(self, acceso):
        self.dati["auto_computo"] = bool(acceso)

    def spunta_voce_dal_disegno(self, codice, acceso):
        if codice not in {c for c, _g, _a in VOCI_DA_SUPERFICI}:
            raise ErroreDisegno(f"La voce {codice} non viene dal disegno.")
        self.supvoce[codice] = bool(acceso)

    def scrivi_quantita_dal_disegno(self):
        """Il bottone, quando il computo non è agganciato."""
        proposte = self.proposte_dal_disegno(self.grandezze())
        if not proposte:
            return 0
        self.registra_storia_computo("quantità portate dalla planimetria")
        for codice, valore in proposte.items():
            self.scrivi_quantita(codice, valore, a_mano=False)
            if codice not in self.dati["voci_scelte"]:
                self.dati["voci_scelte"].append(codice)
        return len(proposte)

    # ---------------------------------------------------------- per la vista

    def mappa_colori(self):
        return {c["nome"]: COLORE_CATEGORIA_SUP.get(
            c["nome"], PALETTE_ZONE[i % len(PALETTE_ZONE)])
            for i, c in enumerate(self.dati["categorie"])}

    def argomenti_tela(self, impostazioni=None):
        """Quello che il visualizzatore riceve (gli argomenti di image_viewer)."""
        from banco import percento_di
        pianta = self._pianta()
        et = self.dati["etichette"]
        impostazioni = impostazioni or {"nome": et["nome"], "m2": et["m2"],
                                        "percento": et["percento"],
                                        "perimetro": et["perimetro"]}
        perc, colori = self.percentuali(), self.mappa_colori()
        img = self.immagine(self.pianta_idx)
        pos = planimetria.posiziona_etichette(
            pianta["zone"], img.width, img.height,
            trasparenti=CATEGORIE_INVOLUCRO)
        nomi = [c["nome"] for c in self.dati["categorie"]]
        attiva = self.cat_attiva if self.cat_attiva in nomi else \
            (nomi[0] if nomi else "Superficie interna")
        return {
            "zone": [{
                "id": z["id"], "punti": z["punti"],
                "colore": colori.get(z["categoria"], "#9E9E9E"),
                "senza_sfondo": z["categoria"] in CATEGORIE_INVOLUCRO,
                "etichetta": etichetta_zona(z, pianta["mpp"], perc,
                                            impostazioni, percento_di),
                "etichetta_pos": z.get("etichetta_pos") or pos.get(z["id"]),
                "nome": z.get("nome") or "",
            } for z in pianta["zone"]],
            "pareti": [{
                "id": p["id"], "p1": p["p1"], "p2": p["p2"],
                "tipo": p.get("tipo", "esistente"),
                "colore": TIPI_PARETE.get(p.get("tipo", "esistente"),
                                          TIPI_PARETE["esistente"])["colore"],
                "etichetta": etichetta_parete(p, pianta["mpp"]),
                "etichetta_pos": p.get("etichetta_pos"),
            } for p in pianta["pareti"]],
            "scala_temp": self.scala_temp,
            "colore_attivo": colori.get(attiva, PALETTE_ZONE[0]),
            "mpp": float(pianta["mpp"] or 0.0),
            "font_px": int(et["font"]),
            "tipo_parete": self.tipo_parete,
            "seq_applicato": self.ultimo_seq,
        }

    def pdf_planimetrie(self, orizzontale=False):
        """Le piante disegnate, con le misure principali sulla prima.

        Il perimetro commerciale resta FUORI: su una tavola che va in
        cantiere sarebbe una linea che gira attorno a tutto senza dire niente.
        """
        from banco import percento_di
        perc, colori = self.percentuali(), self.mappa_colori()
        et = self.dati["etichette"]
        impostazioni = {"nome": et["nome"], "m2": et["m2"], "percento": False,
                        "perimetro": et["perimetro"]}
        tavole = []
        for i, pianta in enumerate(self.dati["piante"]):
            zone = [{"punti": z["punti"],
                     "colore": colori.get(z["categoria"], "#9E9E9E"),
                     "etichetta": etichetta_zona(z, pianta["mpp"], perc,
                                                 impostazioni, percento_di),
                     "etichetta_pos": z.get("etichetta_pos")}
                    for z in pianta["zone"]
                    if z.get("categoria") not in CATEGORIE_INVOLUCRO]
            pareti = [{"p1": p["p1"], "p2": p["p2"],
                       "colore": TIPI_PARETE.get(
                           p.get("tipo", "esistente"),
                           TIPI_PARETE["esistente"])["colore"],
                       "etichetta": etichetta_parete(p, pianta["mpp"]),
                       "etichetta_pos": p.get("etichetta_pos")}
                      for p in pianta["pareti"]]
            disegnata = tavola.disegna(self.immagine(i), zone, pareti,
                                       mpp=pianta["mpp"])
            buffer = io.BytesIO()
            disegnata.save(buffer, format="PNG")
            tipi = {m.get("tipo") or "esistente" for m in pianta["pareti"]}
            tavole.append({"nome": pianta["nome"], "png": buffer.getvalue(),
                           "legenda": [(TIPI_PARETE[t]["nome"],
                                        TIPI_PARETE[t]["colore"])
                                       for t in TIPI_PARETE if t in tipi]})
        grandezze = self.grandezze()
        etichette = (("Pavimento (interni)", "pavimento", "m²"),
                     ("Pavimento esterno", "pavimento_esterno", "m²"),
                     ("Battiscopa", "battiscopa", "ml"),
                     ("Pareti", "tinteggiatura_pareti", "m²"),
                     ("Soffitti", "soffitti", "m²"),
                     ("Rivestimenti", "rivestimenti", "m²"),
                     ("Muri da demolire", "muri_demolire", "m²"),
                     ("Muri da costruire", "muri_costruire", "m²"),
                     ("Cartongesso", "muri_cartongesso", "m²"))
        misure = [(nome, f"{numero_it(grandezze[k], 2)} {um}")
                  for nome, k, um in etichette if grandezze.get(k)]
        prg = self.dati["progetto"]
        return stampa.pdf_planimetrie(
            {"nome": prg["nome"], "committente": prg["committente"],
             "oggetto": prg["oggetto"], "data": prg["data"]},
            tavole, misure, orizzontale=orizzontale)
