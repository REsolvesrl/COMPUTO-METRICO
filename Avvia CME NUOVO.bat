@echo off
rem ===================================================================
rem  CME - la versione NUOVA, in cantiere
rem  Doppio clic per aprirla. Il browser si apre da solo.
rem
rem  ATTENZIONE: lavora su una COPIA dei progetti (~\CME\progetti-prova).
rem  Qui si prova, non si lavora: il lavoro vero si fa ancora con
rem  "Avvia CME.bat", nella cartella C:\Users\fredr\code\CME.
rem
rem  Le due versioni possono stare aperte insieme: porte diverse,
rem  8501 la vecchia, 8504 questa.
rem ===================================================================

title CME NUOVO - motore in funzione (non chiudere questa finestra)
cd /d "%~dp0"

echo.
echo   Avvio di CME (versione nuova). Tra pochi secondi si apre il browser.
echo.
echo   Se non si apre, vai su:  http://127.0.0.1:8504
echo.
echo   NON CHIUDERE questa finestra mentre lavori: e' il motore.
echo.

rem Uvicorn non apre il browser, al contrario di Streamlit: lo apriamo noi,
rem con qualche secondo di ritardo perche' il motore faccia in tempo a
rem rispondere.
start "" /b python -c "import time, webbrowser; time.sleep(4); webbrowser.open('http://127.0.0.1:8504')"

rem --host 127.0.0.1: risponde soltanto a questo computer, mai alla rete.
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
