@echo off
rem ===================================================================
rem  Avvio di riserva: apre CME nel browser invece che nella sua
rem  finestra, e lascia visibile la finestra nera con i messaggi.
rem  Da usare solo se "Avvia CME.bat" non funziona: qui si vedono gli
rem  errori, che nell'altra modalita' restano nascosti.
rem ===================================================================

title CME - avvio di riserva (non chiudere questa finestra)
cd /d "%~dp0"

if not exist "%USERPROFILE%\.streamlit\credentials.toml" (
    if not exist "%USERPROFILE%\.streamlit" mkdir "%USERPROFILE%\.streamlit"
    > "%USERPROFILE%\.streamlit\credentials.toml" echo [general]
    >> "%USERPROFILE%\.streamlit\credentials.toml" echo email = ""
)

echo.
echo   Avvio nel browser. Lascia aperta questa finestra mentre lavori.
echo.

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
