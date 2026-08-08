@echo off
rem ===================================================================
rem  CME - Computo Metrico Estimativo
rem  Doppio clic su questo file per aprire il programma.
rem  Si apre una finestra nera (e' il motore: lasciala aperta) e poi
rem  il browser con l'app. Per chiudere tutto: chiudi la finestra nera.
rem ===================================================================

title CME - motore in funzione (non chiudere questa finestra)
cd /d "%~dp0"

echo.
echo   Avvio di CME in corso...
echo   Tra pochi secondi si apre il browser da solo.
echo.
echo   NON CHIUDERE questa finestra mentre lavori:
echo   e' il motore del programma. Per uscire, chiudila.
echo.

rem Al primo avvio Streamlit chiede un indirizzo email per la sua newsletter e
rem resta li' ad aspettare, con l'app ferma. Questo file di configurazione
rem risponde "nessuna email" una volta per tutte.
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
    if not exist "%USERPROFILE%\.streamlit" mkdir "%USERPROFILE%\.streamlit"
    > "%USERPROFILE%\.streamlit\credentials.toml" echo [general]
    >> "%USERPROFILE%\.streamlit\credentials.toml" echo email = ""
)

rem Streamlit su questa macchina si lancia con "python -m": la cartella degli
rem eseguibili installati da pip non e' nel PATH.
python -m streamlit run streamlit_app.py ^
    --server.headless=false ^
    --browser.gatherUsageStats=false

rem Se Python non c'e' o l'avvio fallisce, la finestra resta aperta per
rem far leggere l'errore invece di sparire in un lampo.
if errorlevel 1 (
    echo.
    echo   ================================================
    echo   L'avvio non e' riuscito. Copia il messaggio qui
    echo   sopra e mandalo a Claude per capire cosa manca.
    echo   ================================================
    echo.
    pause
)
