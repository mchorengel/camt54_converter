@echo off
REM Erstellt .venv, aktiviert es und installiert die Abhaengigkeiten.
REM
REM Aufruf in cmd.exe:
REM     call setup.bat
REM (das "call" sorgt dafuer, dass das venv in der aktuellen Shell aktiv bleibt)

setlocal enabledelayedexpansion

REM --- 1. Python pruefen ---------------------------------------------------
where python >nul 2>&1
if errorlevel 1 (
    echo [Fehler] Python wurde nicht gefunden im PATH.
    echo Bitte Python 3.10 oder neuer von https://www.python.org/downloads/ installieren.
    exit /b 1
)

REM --- 2. venv anlegen, falls noch nicht vorhanden ------------------------
if not exist ".venv\Scripts\activate.bat" (
    echo [1/3] Erstelle virtuelle Umgebung in .venv ...
    python -m venv .venv
    if errorlevel 1 (
        echo [Fehler] Konnte virtuelle Umgebung nicht erstellen.
        exit /b 1
    )
) else (
    echo [1/3] Virtuelle Umgebung .venv existiert bereits - ueberspringe.
)

REM --- 3. Aktivieren ------------------------------------------------------
echo [2/3] Aktiviere .venv ...
call ".venv\Scripts\activate.bat"
if errorlevel 1 (
    echo [Fehler] Aktivierung fehlgeschlagen.
    exit /b 1
)

REM --- 4. Abhaengigkeiten installieren ------------------------------------
echo [3/3] Installiere Abhaengigkeiten ...
python -m pip install --upgrade pip
pip install -r requirements.txt
if errorlevel 1 (
    echo [Fehler] pip install ist fehlgeschlagen.
    exit /b 1
)

echo.
echo ============================================================
echo  Fertig. Die virtuelle Umgebung ist aktiviert.
echo.
echo  Web-App starten:  python -m camt54_converter.web
echo  CLI verwenden:    python -m camt54_converter.cli datei.xml -o out.csv
echo.
echo  Hinweis: Wurde dieses Script per Doppelklick gestartet,
echo  schliesst sich das Fenster gleich und das venv ist weg.
echo  Stattdessen in cmd mit "call setup.bat" aufrufen.
echo ============================================================

endlocal & call ".venv\Scripts\activate.bat"
