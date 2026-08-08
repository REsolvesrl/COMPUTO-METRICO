@echo off
rem ===================================================================
rem  Ricostruisce il pacchetto CME.exe da consegnare ad altri computer.
rem  Serve solo dopo aver cambiato il programma: per usarlo qui basta
rem  "Avvia CME.bat".
rem  Ci vogliono circa 5 minuti. Il risultato finisce in dist\CME\
rem ===================================================================

title CME - costruzione del pacchetto
cd /d "%~dp0"

echo.
echo   Costruzione in corso: circa 5 minuti.
echo   Alla fine trovi tutto in dist\CME\
echo.

python -m PyInstaller CME.spec --noconfirm --distpath dist --workpath build

if errorlevel 1 (
    echo.
    echo   ================================================
    echo   La costruzione non e' riuscita. Copia il
    echo   messaggio qui sopra e mandalo a Claude.
    echo   ================================================
) else (
    copy /Y LEGGIMI-pacchetto.txt "dist\CME\LEGGIMI.txt" >nul 2>&1
    echo.
    echo   Fatto: dist\CME\CME.exe
    echo   Per consegnarlo, copia tutta la cartella dist\CME
)

echo.
pause
