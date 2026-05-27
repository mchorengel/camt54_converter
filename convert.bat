@echo off
REM Drag und Drop Konverter fuer camt.054 nach CSV.
REM
REM Verwendung: Eine oder mehrere camt.054 XML-Dateien auf diese .bat ziehen.
REM Fuer jede Datei wird daneben eine gleichnamige .csv erzeugt.
REM
REM Voraussetzung: einmalig "call setup.bat" ausfuehren, damit .venv existiert.

setlocal enabledelayedexpansion

REM In das Verzeichnis dieser .bat wechseln, damit das Python-Modul gefunden wird.
cd /d "%~dp0"

if "%~1"=="" (
    echo.
    echo  Keine Datei uebergeben.
    echo.
    echo  So verwendest du dieses Script:
    echo    Ziehe eine oder mehrere camt.054 XML-Dateien per Drag ^& Drop
    echo    auf diese .bat-Datei. Neben jeder XML-Datei wird eine CSV mit
    echo    gleichem Namen erzeugt.
    echo.
    pause
    exit /b 1
)

REM Python aus .venv bevorzugen, sonst System-Python.
if exist ".venv\Scripts\python.exe" (
    set "PYTHON=.venv\Scripts\python.exe"
) else (
    where python >nul 2>&1
    if errorlevel 1 (
        echo [Fehler] Weder .venv noch system Python gefunden.
        echo Bitte zuerst "call setup.bat" ausfuehren.
        pause
        exit /b 1
    )
    set "PYTHON=python"
)

set "HAD_ERROR="

:loop
if "%~1"=="" goto :done
set "INPUT=%~1"
set "OUTPUT=%~dpn1.csv"
echo.
echo Konvertiere  "!INPUT!"
echo        nach  "!OUTPUT!"
"!PYTHON!" -m camt54_converter.cli "!INPUT!" -o "!OUTPUT!"
if errorlevel 1 (
    echo [Fehler] Konvertierung fehlgeschlagen.
    set "HAD_ERROR=1"
)
shift
goto :loop

:done
echo.
if defined HAD_ERROR (
    echo Mit Fehlern abgeschlossen - siehe oben.
) else (
    echo Alle Dateien erfolgreich konvertiert.
)
echo.
pause
endlocal
