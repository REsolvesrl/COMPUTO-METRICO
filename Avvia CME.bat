@echo off
rem ===================================================================
rem  CME - Computo Metrico Estimativo
rem  Doppio clic per aprire il programma nella sua finestra.
rem  Questa finestra nera compare per un istante e si chiude da sola.
rem ===================================================================

cd /d "%~dp0"

rem Al primo avvio Streamlit chiede un indirizzo email per la sua newsletter e
rem resta li' ad aspettare, con l'app ferma. Questo file di configurazione
rem risponde "nessuna email" una volta per tutte.
if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
    if not exist "%USERPROFILE%\.streamlit" mkdir "%USERPROFILE%\.streamlit"
    > "%USERPROFILE%\.streamlit\credentials.toml" echo [general]
    >> "%USERPROFILE%\.streamlit\credentials.toml" echo email = ""
)

rem pythonw (invece di python) esegue senza terminale: niente finestra nera
rem che resta aperta accanto al programma.
start "" pythonw "avvia_finestra.py"
