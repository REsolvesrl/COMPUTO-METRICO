# Il cantiere

Questa cartella è la **versione nuova** di CME, in costruzione: motore
FastAPI e pagina Vue, al posto di Streamlit. È la stessa strada fatta con
CATASTO. Non sostituisce niente: il programma che usi tutti i giorni è in
`C:\Users\fredr\code\CME` e si avvia col suo `Avvia CME.bat`, come sempre.

I due sono la stessa cartella di git vista da due porte (`git worktree`):
il cantiere sta sul ramo `nuovo`, il programma vero su `sviluppo`/`main`.
Niente di quello che succede qui arriva là finché non lo decidiamo.

## Come si avvia

Doppio clic su **`Avvia CME NUOVO.bat`**: il browser si apre da solo su
<http://127.0.0.1:8504>. Porte diverse — 8501 il vecchio, 8504 questo (8502
e 8503 sono di CATASTO) — quindi **possono stare aperti nello stesso
momento**.

## Lavora in una cartella sua: `~/CME/prova`

Il cantiere non tocca il lavoro vero, e non perché il .bat si ricordi di
dirglielo: è deciso in [`server/principale.py`](server/principale.py).

| | vero | cantiere |
|---|---|---|
| progetti | `~/CME/progetti` | `~/CME/prova/progetti` |
| listino personale | `~/CME/listino_personale.json` | `~/CME/prova/listino_personale.json` |
| storico delle operazioni | `~/CME/storico_operazioni.json` | `~/CME/prova/storico_operazioni.json` |
| registro d'uso | `~/.resolve_uso` | `~/CME/prova/uso` |

⚠️ Listino e storico vivono **accanto** alla cartella dei progetti: è per
questo che la copia sta in `prova/progetti` e non in `progetti-prova` (com'era
nella prima pietra), dove listino e storico sarebbero finiti in quelli veri.

⚠️ Il rovescio: **quello che scrivi qui resta nella copia.** Nel cantiere si
prova, non si lavora. Per riprovare coi progetti di oggi basta ricopiarli
da `~/CME/progetti` a `~/CME/prova/progetti`.

## Il patto fra le due versioni

Lo stesso file, aperto e risalvato da una parte o dall'altra, esce **uguale**.
Non è una promessa: [`tests/test_banco_come_il_vecchio.py`](tests/test_banco_come_il_vecchio.py)
fa girare davvero il programma vecchio (AppTest), gli fa aprire un progetto
e premere Salva, fa lo stesso col nuovo e confronta i due file chiave per
chiave — su un progetto scritto apposta coi formati di prima, sul modello di
un progetto nuovo, e sui progetti veri della copia di prova. L'unica
differenza dichiarata sono le immagini, che il vecchio ricodifica in JPEG a
ogni apertura e il nuovo lascia com'erano.

## Com'è fatto

```
*.py              il motore di sempre (calcoli, listino, planimetria,
                  fattibilita, merito, stampa, archivio_locale…), identico
                  a quello di sviluppo.
costanti.py       le costanti dell'interfaccia (colori, categorie, muri,
                  impostazioni del business plan), copiate da
                  streamlit_app.py: un test le pretende identiche.
grafici.py        le figure Plotly del vecchio, copiate senza toccarle.
esporta.py        PDF, PDF senza prezzi, Excel, CSV, Allegato 1.
banco.py          il banco di lavoro: il progetto aperto nel formato del
banco_disegno.py  file, e tutti i gesti che lo cambiano — computo e
banco_bp.py       materiali, disegno, business plan. Niente Streamlit.
server/           FastAPI: la vista (cosa si mostra) e le rotte (i gesti).
web/              la pagina: Vue 3 come modulo, senza assemblatore.
cme_viewer/frontend/  la tela delle planimetrie del VECCHIO, servita
                  così com'è in /tela: parla il protocollo dei componenti
                  Streamlit e la pagina nuova glielo parla uguale.
```

Il modello è quello di Streamlit senza Streamlit: il motore tiene aperto un
progetto (il banco, come una sessione), la pagina manda un gesto e riceve la
vista intera ricalcolata. Dopo ogni gesto il banco rifà il suo **giro**, come
Streamlit rifaceva la pagina — ed è importante, perché il vecchio scrive nel
file anche cose che nessuno ha toccato: gli imprevisti in euro, i mq dalla
planimetria, le quantità agganciate al disegno, le spunte dei locali, le
quote SAL predefinite.

⚠️ **Niente `npm`.** Vue è un file in `web/vendor/`; Plotly.js arriva dal
pacchetto Python che costruisce le figure, quindi è sempre la versione giusta.

⚠️ `streamlit_app.py` in questo ramo **non si tocca**: finché i due
convivono, le correzioni al programma vecchio si fanno su `sviluppo` e
arrivano qui con un merge. Chi cambia una costante là la cambia anche in
`costanti.py` (il test lo ricorda).

## L'inventario: tutto quello che c'è nel vecchio, e dov'è nel nuovo

✅ passato e provato · 🟡 passato, non ancora provato a mano nel browser ·
⬜ non passato

### Testata e contorno

| | |
|---|---|
| ✅ | cartiglio col nome del progetto, «codice del …», stato del salvataggio (mai salvato / modifiche non salvate / salvato alle) |
| ✅ | 💾 Salva in testata: in archivio, col nome del progetto, subito, con la versione precedente messa da parte |
| ✅ | all'avvio si riapre l'ultimo progetto salvato, e lo si dice («Ripreso …») col suo «Progetto nuovo» |
| ✅ | avviso delle planimetrie che non si sono potute rileggere |
| ✅ | registro d'uso: un'operazione valutata per progetto e per sessione |
| ✅ | tre linguette e sei sottolinguette, con gli stessi nomi, nello stesso ordine; la linguetta aperta si ricorda |
| ⬜ | accesso con password e archivio online su Supabase (vedi «Da decidere») |

### 📝 Computo metrico → 📝 Il computo

| | |
|---|---|
| ✅ | 📋 Dati del progetto: nome, committente, oggetto, luogo, data |
| 🟡 | apri un progetto salvato (.json) dal disco |
| ✅ | progetti in archivio: apri, elimina con spunta, archivia con un nome, sovrascrivi con spunta |
| 🟡 | versioni precedenti (le ultime tre) da riaprire |
| ✅ | nuovo progetto con conferma: riparte dalle voci di Migliarina |
| 🟡 | ↩️ Annulla del computo (listino personale, quantità dal disegno) |
| ✅ | 📓 Il mio listino: salva, applica, cancella |
| ✅ | Tetto e Facciata: accesi entrano, spenti spariscono ma restano da parte |
| ✅ | le schede delle categorie: pastiglia col numero, nome nella tinta, totale; aperta/chiusa |
| ✅ | le righe: descrizione, unità (tendina con quella di casa in testa), quantità (a frecce dove si contano pezzi), prezzo, parziale / «da quantificare», ✕ |
| ✅ | il codice apre il pannellino: su, giù, sposta di categoria (voci tue), riaggancia al disegno, nota del listino; ✎ sulle quantità scritte a mano |
| ✅ | ➕ Aggiungi una voce tua: categoria, descrizione, unità, quantità (1 con «a corpo»), prezzo |
| ✅ | 🧰 Pool: prendi tutte, ricerca su più parole, categorie apribili, ＋, 🗑 scarta, rimetti tutte |
| ✅ | 💰 Riepilogo costi: righe per categoria, totale lavori, aliquota IVA, IVA, totale finale d'ottone, grafico a barre |
| ✅ | 📄 Computo calcolato (tabella completa) |
| ✅ | 💾 Salva ed esporta: stato, .json, PDF, PDF senza prezzi (data di oggi), Excel, CSV |

### 📝 Computo metrico → 🛒 Materiali

| | |
|---|---|
| ✅ | tabella con capitolo, descrizione, quantità, fornitore, link, stato, note; righe nuove e cancellate |
| ✅ | ⇅ Capitolo, ⇅ Stato, ⇅ Fornitore; filtro per stato che non perde le righe nascoste |
| ✅ | conteggi per stato e per capitolo; stato vuoto |
| ✅ | 🖨️ Allegato 1 (da firmare) |

### 📐 Misura da planimetria

| | |
|---|---|
| ✅ | la tela del vecchio (zoom, sposta, area, modifica, scala, parete, misura, etichette trascinabili, scorciatoie) |
| 🟡 | carica PNG/JPG/PDF (una pianta per pagina), miniature, scegli e togli una pianta |
| ✅ | nome della pianta, categoria delle aree nuove, tipo dei muri nuovi |
| ✅ | ↩️ Annulla del disegno, con l'avviso quando si porta via la scala |
| 🟡 | la scala: il segmento e la misura reale |
| 🟡 | zona selezionata: nome, categoria, ➕ al computo, elimina; muro selezionato: tipo, lunghezza, elimina |
| 🟡 | 🧹 Pulisci la planimetria: prova, anteprima affiancata, usa, scarta, ripristina l'originale |
| 🟡 | 🪄 Rileva stanze (beta) e annulla l'ultimo rilevamento |
| ✅ | legenda delle categorie; 🔤 etichette (carattere, cosa mostrare, riporta fuori) |
| ✅ | 🧮 Superfici commerciali: tabella, avvisi, totali, riporta nel computo |
| ✅ | 📏 locale per locale: altezza, spunte dei locali, porte e rivestimenti, finestre e porte finestra, le sei quantità, 🔍 il conto in chiaro |
| ✅ | 🧱 muri: aperture, demolire / costruire / cartongesso, esistenti esclusi, rasatura |
| ✅ | ➕ nel computo: aggancio al disegno, voci da spuntare, «sostituisce», scritte a mano e riaggancia, bottone quando è sganciato |
| 🟡 | 🖨️ stampa planimetrie (PDF), in piedi o steso |

### 📊 Business plan

| | |
|---|---|
| ✅ | 🏦 Studio di fattibilità: mq (dalla planimetria o a mano), passo, durata, ESTIMATED, entry/exit, ROI/ROE/annuo, total cost, EBIT, le due matrici con legenda, dettaglio costi con %, netto, IVA, ristrutturazione dal computo o dai costi reali, €/mq sui calpestabili, IVA a credito |
| 🟡 | 🧾 Spese a consuntivo: 📎 fatture PDF/XML lette e controllate prima di aggiungerle |
| ✅ | 🧾 registro delle sostenute con IVA scorporata, riepilogo per categoria, da sostenere, totale del registro, torta, il computo alla prova del cantiere |
| ✅ | 🏗️ Cantiere: contratto (anche dal computo), extra, SAL, piano, saldato/residuo/finale, scostamento |
| 🟡 | 🏗️ chiudi nello storico, riserva tarata sui cantieri chiusi |
| ✅ | 🏷️ MCA: comparabili con la griglia, soggetto a lavori finiti, coefficienti, taglio, sconto, salto ristrutturato/da ristrutturare, stima, dispersione, media o mediana |
| 🟡 | 📥 usa come prezzo di vendita |

## Dove il nuovo fa diversamente, apposta

- **Si salva col tasto**, come nel vecchio — non a ogni modifica come in
  CATASTO: ogni salvataggio mette da parte una versione e se ne tengono tre.
- Il **.json si scarica con un clic**: niente più «📦 Prepara il file», che
  serviva solo perché Streamlit rimandava i megabyte a ogni giro.
- Le **tabelle** (materiali, spese, SAL, MCA) hanno «＋ riga», «Copia»,
  «Cancella» sempre in vista; un blocco copiato da Excel si incolla in una
  cella e si distribuisce sulle altre.
- **Niente avviso «premi Invio»** sui prezzi del business plan: serviva
  perché Streamlit non applicava il numero finché non lo si confermava;
  qui il numero parte appena si esce dalla casella.
- La **descrizione riscritta di una voce tua** finisce nel file (nel vecchio
  si perdeva riaprendo: vedi il commit del banco).
- Le **immagini** delle planimetrie non si ricodificano a ogni apertura.
- Ricaricare la pagina del browser **non perde niente**: il progetto aperto
  sta nel motore, non nella pagina.

## Da decidere

- **Accesso con password e archivio online (Supabase, Render).** Il vecchio
  li ha per quando girava su internet (computometrico.streamlit.app, e poi
  Render). Oggi CME gira sul computer, e il nuovo ascolta solo su
  127.0.0.1: se il programma online serve ancora, vanno rifatti; se no, si
  lasciano andare con Streamlit.
- **Quando il cantiere diventa il programma**: come per CATASTO — si toglie
  il blocco della cartella di prova in `server/principale.py`, `Avvia
  CME.bat` passa al motore nuovo, e il vecchio resta accanto qualche
  settimana come rete di sicurezza.

## Se qualcosa non torna

Prima cosa da guardare: <http://127.0.0.1:8504/api/salute>. Dice su quale
archivio si sta lavorando davvero, e che progetto è aperto.
