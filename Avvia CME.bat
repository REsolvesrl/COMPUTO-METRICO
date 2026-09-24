@echo off
rem ===================================================================
rem  CME - Computo Metrico Estimativo
rem  Doppio clic per aprire il programma. Il browser si apre da solo.
rem
rem  Si apre una finestra nera: e' il motore del programma, va lasciata
rem  aperta mentre lavori. E' anche il posto dove compaiono i messaggi
rem  quando qualcosa non va: se vedi un errore, copialo e mandalo.
rem  Per chiudere CME: chiudi questa finestra.
rem
rem  ATTENZIONE: La versione vecchia, quella a Streamlit, e' ancora qui e si
rem  avvia con "Avvia CME (vecchio).bat": legge lo stesso archivio. E' la
rem  rete di sicurezza finche' questa non avra' lavorato per qualche
rem  settimana senza sorprese.
rem ===================================================================

title CME - motore in funzione (non chiudere questa finestra)
cd /d "%~dp0"

rem ===================================================================
rem  QUESTO FILE NON SI COPIA: SI COLLEGA
rem  Il .bat parte dalla cartella in cui sta, e il motore e' li'
rem  accanto. Copiato altrove - per esempio sul Desktop - la cartella
rem  e' un'altra e Python risponde con venti righe di traceback e
rem  "No module named 'server'": vero, e illeggibile. Per averlo sul
rem  Desktop si fa un COLLEGAMENTO.
rem ===================================================================
if not exist "%~dp0server\principale.py" (
    echo.
    echo   ================================================
    echo   Questo file e' una COPIA, e da qui non parte:
    echo   il motore non e' in questa cartella.
    echo.
    echo   Apri il collegamento "Avvia CME" sul Desktop,
    echo   oppure il .bat che sta in
    echo   C:\Users\fredr\code\CME
    echo   ================================================
    echo.
    pause
    exit /b 1
)

rem ===================================================================
rem  AGGIORNAMENTO AUTOMATICO
rem  Prima si scarica l'ultima versione, poi si parte. Un aggiornamento
rem  che dipende da chi si ricorda di premerlo non e' un aggiornamento.
rem
rem  ATTENZIONE: se l'aggiornamento non riesce (niente rete, modifiche
rem  locali non salvate, git assente) il programma parte LO STESSO con la
rem  versione che c'e'; e "--ff-only" non tocca mai lavoro non ancora
rem  inviato. I tuoi progetti non c'entrano: vivono in un'altra cartella.
rem ===================================================================
where git >nul 2>&1
if errorlevel 1 (
    echo.
    echo   Git non e' installato: salto l'aggiornamento e parto.
    goto librerie
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

:librerie
rem Il motore nuovo ha bisogno di FastAPI e Uvicorn: se mancano (un
rem computer dove CME girava solo con Streamlit) si installano una volta.
python -c "import fastapi, uvicorn" >nul 2>&1
if errorlevel 1 (
    echo.
    echo   Installo le librerie che mancano, una volta sola...
    python -m pip install -r requirements.txt
)

echo.
echo   Avvio di CME. Tra pochi secondi si apre il browser da solo.
echo.
echo   Se non si apre, vai su:  http://127.0.0.1:8504
echo.
echo   NON CHIUDERE questa finestra mentre lavori: e' il motore.
echo.

rem ===================================================================
rem  IL BROWSER SI APRE DA SOLO
rem  Uvicorn non lo apre, al contrario di Streamlit: lo apriamo noi, con
rem  qualche secondo di ritardo perche' il motore faccia in tempo a
rem  rispondere. Gira di fianco (/b: nessuna finestra in piu') e se non
rem  riesce, pazienza: l'indirizzo e' scritto qui sopra.
rem ===================================================================
start "" /b python -c "import time, webbrowser; time.sleep(4); webbrowser.open('http://127.0.0.1:8504')"

rem --host 127.0.0.1: risponde soltanto a questo computer, mai alla rete.
rem Porta 8504: la vecchia resta sulla 8501, e possono stare aperte insieme.
python -m uvicorn server.principale:app --host 127.0.0.1 --port 8504

if errorlevel 1 (
    echo.
    echo   ================================================
    echo   L'avvio non e' riuscito. Copia il messaggio qui
    echo   sopra e mandalo a Claude.
    echo   ================================================
    echo.
    pause
)
