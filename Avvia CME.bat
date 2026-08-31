@echo off
rem ===================================================================
rem  CME - Computo Metrico Estimativo
rem  Doppio clic per aprire il programma nel browser.
rem
rem  Si apre una finestra nera: e' il motore del programma, va lasciata
rem  aperta mentre lavori. E' anche il posto dove compaiono i messaggi
rem  quando qualcosa non va: se vedi un errore, copialo e mandalo.
rem  Per chiudere CME: chiudi questa finestra.
rem ===================================================================

title CME - motore in funzione (non chiudere questa finestra)
cd /d "%~dp0"

rem Al primo avvio Streamlit chiede un indirizzo email per la sua newsletter e
rem resta li' ad aspettare, con l'app ferma. Questo file di configurazione
rem risponde "nessuna email" una volta per tutte.
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
    if not exist "%USERPROFILE%\.streamlit" mkdir "%USERPROFILE%\.streamlit"
    > "%USERPROFILE%\.streamlit\credentials.toml" echo [general]
    >> "%USERPROFILE%\.streamlit\credentials.toml" echo email = ""
)

rem ===================================================================
rem  AGGIORNAMENTO AUTOMATICO
rem  Prima si scarica l'ultima versione, poi si parte.
rem
rem  Prima c'era un "Aggiorna CME.bat" da lanciare a mano: ma un
rem  aggiornamento che dipende da chi si ricorda di premerlo non e' un
rem  aggiornamento. Si finisce a lavorare per giorni sulla versione
rem  vecchia convinti di avere l'ultima, e a segnalare difetti gia'
rem  corretti - che e' esattamente quello che e' successo.
rem
rem  ATTENZIONE: se l'aggiornamento non riesce (niente rete, modifiche locali non
rem  salvate, git assente) il programma parte LO STESSO con la versione
rem  che c'e'. Un aggiornamento fallito non deve mai lasciarti senza
rem  programma; e "--ff-only" fa in modo che non venga mai toccato del
rem  lavoro non ancora inviato.
rem  I tuoi progetti non c'entrano: vivono in un'altra cartella e questo
rem  comando non li sfiora.
rem ===================================================================
where git >nul 2>&1
if errorlevel 1 (
    echo.
    echo   Git non e' installato: salto l'aggiornamento e parto.
    goto avvia
)

echo.
echo   Cerco aggiornamenti...
git pull --ff-only
if errorlevel 1 (
    echo.
    echo   ------------------------------------------------
    echo   Non sono riuscito ad aggiornare: parto con la
    echo   versione che hai adesso. Il messaggio qui sopra
    echo   dice perche' - se non e' chiaro, copialo e mandalo.
    echo   ------------------------------------------------
)

:avvia
echo.
echo   Avvio di CME. Tra pochi secondi si apre il browser da solo.
echo.
echo   NON CHIUDERE questa finestra mentre lavori: e' il motore.
echo   Per uscire, chiudila.
echo.

rem Streamlit su questa macchina si lancia con "python -m": la cartella degli
rem eseguibili installati da pip non e' nel PATH.
rem
rem Porta fissa 8501: senza, CME e CATASTO (altro programma sulla stessa
rem macchina) finiscono a contendersi la stessa porta di default, e chi
rem parte per secondo si becca la scheda del browser gia' aperta sull'altro.
python -m streamlit run streamlit_app.py --server.port=8501 --browser.gatherUsageStats=false

if errorlevel 1 (
    echo.
    echo   ================================================
    echo   L'avvio non e' riuscito. Copia il messaggio qui
    echo   sopra e mandalo a Claude.
    echo   ================================================
    echo.
    pause
)
