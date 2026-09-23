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
<http://127.0.0.1:8504>.

Porte diverse — 8501 il vecchio, 8504 questo — quindi **possono stare
aperti nello stesso momento**. (8502/8503 sono di CATASTO.)

## L'archivio è sigillato

Il cantiere lavora su una **copia** dei progetti, in `~/CME/progetti-prova`.
Non può toccare quelli veri, e non perché il .bat si ricordi di dirglielo:
la copia è decisa in [`server/principale.py`](server/principale.py), in un
blocco che si toglie in una riga sola quando il cantiere avrà finito.

⚠️ Il rovescio: **quello che scrivi qui resta nella copia.** Nel cantiere si
prova, non si lavora.

⚠️ Il listino personale (`~/CME/listino_personale.json`) **non** è
sigillato: sta accanto alla cartella dei progetti, e la copia è accanto
all'originale. Per ora il cantiere non lo legge né lo scrive; quando ci
arriverà, andrà sigillato anche lui.

## Il salvataggio: col tasto, come prima

Al contrario di CATASTO, qui **non** si salva a ogni modifica. Ogni
salvataggio di CME mette da parte una versione, e se ne tengono tre:
salvare a ogni cifra le brucerebbe in tre battute. La pagina ricalcola
mentre scrivi (rotta `/prova`, che non scrive niente) e salva quando premi
«Salva». Uscire con modifiche in sospeso chiede conferma.

## Cosa c'è e cosa non c'è ancora

| | |
|---|---|
| ✅ | elenco dei progetti, si riapre l'ultimo |
| ✅ | il computo: voci per categoria, testi riscritti, voci a mano, Tetto/Facciata solo se accesi |
| ✅ | quantità e prezzo si scrivono in tabella, importi e totali ricalcolati da `calcoli.py` |
| ✅ | totale lavori, IVA, totale IVA inclusa |
| ✅ | salvataggio negli stessi file del programma vecchio, con le versioni |
| ⬜ | dati del progetto (committente, oggetto, IVA…), progetto nuovo, elimina |
| ⬜ | aggiungere, togliere, spostare voci; riscrivere testi; voci a mano |
| ⬜ | la planimetria e le superfici |
| ⬜ | materiali, business plan, spese, SAL e cantiere |
| ⬜ | stampa PDF, fattura, export |
| ⬜ | listino personale, registro d'uso, ripristino automatico |

## Com'è fatto

```
*.py         il motore di sempre (calcoli, listino, archivio_locale…),
             identico a quello di sviluppo.
computo.py   le righe del computo lette e scritte sul file del progetto,
             senza stato di sessione. Nuovo, puro, testato.
server/      FastAPI. Traduce fra una richiesta del browser e una
             chiamata ai moduli. Nessuna logica di computo qui dentro.
web/         la pagina: Vue 3 come modulo del browser, senza assemblatore.
```

⚠️ **Niente `npm`, per ora.** Vue è un file in `web/vendor/`, il browser lo
carica e basta, come in CATASTO.

⚠️ `streamlit_app.py` in questo ramo **non si tocca** oltre lo stretto
necessario: finché i due convivono, le correzioni al programma vecchio si
fanno su `sviluppo` e arrivano qui con un merge.

## Se qualcosa non torna

Prima cosa da guardare: <http://127.0.0.1:8504/api/salute>. Dice su quale
archivio si sta lavorando davvero.
