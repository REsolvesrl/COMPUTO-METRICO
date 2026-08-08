@echo off
rem ===================================================================
rem  Scarica l'ultima versione del programma da GitHub.
rem  Da usare quando Claude ti dice che c'e' un aggiornamento pronto.
rem  Non tocca i tuoi progetti: quelli stanno in un'altra cartella.
rem ===================================================================

title CME - aggiornamento
cd /d "%~dp0"

echo.
echo   Scarico l'ultima versione...
echo.

git pull

if errorlevel 1 (
    echo.
    echo   ================================================
    echo   L'aggiornamento non e' riuscito. Copia il
    echo   messaggio qui sopra e mandalo a Claude.
    echo   ================================================
) else (
    echo.
    echo   Aggiornamento completato.
    echo   Se il programma era aperto, chiudilo e riavvialo.
)

echo.
pause
