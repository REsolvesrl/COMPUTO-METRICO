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

echo.
echo   Avvio di CME. Tra pochi secondi si apre il browser da solo.
echo.
echo   NON CHIUDERE questa finestra mentre lavori: e' il motore.
echo   Per uscire, chiudila.
echo.

rem Streamlit su questa macchina si lancia con "python -m": la cartella degli
rem eseguibili installati da pip non e' nel PATH.
python -m streamlit run streamlit_app.py --browser.gatherUsageStats=false

if errorlevel 1 (
    echo.
    echo   ================================================
    echo   L'avvio non e' riuscito. Copia il messaggio qui
    echo   sopra e mandalo a Claude.
    echo   ================================================
    echo.
    pause
)
