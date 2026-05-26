# Erstellt .venv, aktiviert es und installiert die Abhaengigkeiten.
#
# Aufruf in PowerShell (dot-sourcen, damit das venv aktiv bleibt):
#     . .\setup.ps1
#
# Falls die Execution Policy das Ausfuehren von Scripts verbietet, entweder
# einmalig fuer den Benutzer freischalten:
#     Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
# ... oder einmalig fuer diesen Aufruf umgehen:
#     powershell -ExecutionPolicy Bypass -File .\setup.ps1

$ErrorActionPreference = "Stop"

# --- 1. Python pruefen --------------------------------------------------
$python = Get-Command python -ErrorAction SilentlyContinue
if (-not $python) {
    Write-Host "[Fehler] Python wurde nicht gefunden im PATH." -ForegroundColor Red
    Write-Host "Bitte Python 3.10 oder neuer von https://www.python.org/downloads/ installieren."
    exit 1
}

# --- 2. venv anlegen, falls noch nicht vorhanden -----------------------
if (-not (Test-Path ".venv\Scripts\Activate.ps1")) {
    Write-Host "[1/3] Erstelle virtuelle Umgebung in .venv ..." -ForegroundColor Cyan
    python -m venv .venv
} else {
    Write-Host "[1/3] Virtuelle Umgebung .venv existiert bereits - ueberspringe." -ForegroundColor Cyan
}

# --- 3. Aktivieren ------------------------------------------------------
Write-Host "[2/3] Aktiviere .venv ..." -ForegroundColor Cyan
. .\.venv\Scripts\Activate.ps1

# --- 4. Abhaengigkeiten installieren -----------------------------------
Write-Host "[3/3] Installiere Abhaengigkeiten ..." -ForegroundColor Cyan
python -m pip install --upgrade pip
pip install -r requirements.txt

Write-Host ""
Write-Host "============================================================" -ForegroundColor Green
Write-Host " Fertig. Die virtuelle Umgebung ist aktiviert." -ForegroundColor Green
Write-Host ""
Write-Host " Web-App starten:  python -m camt54_converter.web"
Write-Host " CLI verwenden:    python -m camt54_converter.cli datei.xml -o out.csv"
Write-Host ""
Write-Host " Hinweis: Wurde dieses Script mit '& .\setup.ps1' statt"
Write-Host " '. .\setup.ps1' (dot-sourced) gestartet, ist das venv nach"
Write-Host " dem Script wieder weg. Beim naechsten Mal mit Punkt-Leerzeichen"
Write-Host " davor aufrufen."
Write-Host "============================================================" -ForegroundColor Green
