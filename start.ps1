<#
Landtag-Sim: kleines Start-Skript fuer Windows/PowerShell.

Startet Postgres (Docker), Backend (FastAPI/uvicorn) und Frontend (Vite)
je in einem eigenen Fenster und oeffnet danach den Browser auf
http://localhost:5173.

Voraussetzung: einmaliges Setup nach README.md ("Lokal starten") --
sim-Package installiert (`pip install -e .`), Backend-Requirements
installiert, Frontend-node_modules installiert, Docker Desktop laeuft.
Mit -Setup fuehrt das Skript diese Installationsschritte zusaetzlich
(erneut) aus, bevor es startet -- praktisch nach einem Update von
requirements.txt/package.json oder beim allerersten Lauf.

Aufruf (aus dem Projektordner, z.B.
C:\Users\chris\Claude Code Projekte\landtag-sim):
    .\start.ps1
    .\start.ps1 -Setup

Falls PowerShell das Ausfuehren von Skripten blockiert ("... is not
digitally signed" o.ae.), einmalig ausfuehren:
    powershell -ExecutionPolicy Bypass -File .\start.ps1
#>

param(
    [switch]$Setup
)

$ErrorActionPreference = "Stop"
$root = $PSScriptRoot

function Step($text) {
    Write-Host "-> $text" -ForegroundColor Yellow
}

Write-Host "== Landtag-Sim Start ==" -ForegroundColor Cyan

# Compose-Datei ueber -f explizit ansprechen, damit das Skript unabhaengig
# vom aktuellen Arbeitsverzeichnis funktioniert (z.B. per Doppelklick oder
# aus einem anderen Ordner heraus gestartet).
$composeFile = Join-Path $root "docker-compose.yml"

# 1) Postgres per Docker starten (idempotent -- passiert nichts, falls schon oben)
Step "Starte Postgres (Docker) ..."
docker compose -f "$composeFile" --project-directory "$root" up -d db
if ($LASTEXITCODE -ne 0) {
    Write-Error "Docker-Start fehlgeschlagen. Laeuft Docker Desktop?"
    exit 1
}

# 2) Warten, bis Postgres den eigenen Healthcheck erfuellt (siehe docker-compose.yml)
Step "Warte, bis Postgres bereit ist ..."
$ready = $false
for ($i = 0; $i -lt 30; $i++) {
    docker compose -f "$composeFile" --project-directory "$root" exec -T db pg_isready -U landtag *> $null
    if ($LASTEXITCODE -eq 0) { $ready = $true; break }
    Start-Sleep -Seconds 1
}
if (-not $ready) {
    Write-Warning "Postgres ist nach 30 Sekunden immer noch nicht bereit -- pruefe manuell mit 'docker compose ps' bzw. 'docker compose logs db'."
}

# 3) backend/.env sicherstellen (einmalig aus .env.example kopiert)
$envFile = Join-Path $root "backend\.env"
$envExample = Join-Path $root "backend\.env.example"
if (-not (Test-Path $envFile)) {
    Step "Kopiere backend\.env.example nach backend\.env"
    Copy-Item $envExample $envFile
}

# 4) Optional: Abhaengigkeiten (neu) installieren
if ($Setup) {
    Step "Installiere sim-Package (pip install -e .) ..."
    Push-Location (Join-Path $root "sim")
    pip install -e .
    Pop-Location

    Step "Installiere Backend-Abhaengigkeiten ..."
    Push-Location (Join-Path $root "backend")
    pip install -r requirements.txt
    Pop-Location

    Step "Installiere Frontend-Abhaengigkeiten (npm install) ..."
    Push-Location (Join-Path $root "frontend")
    npm install
    Pop-Location
}

# 5) Backend in eigenem Fenster starten
Step "Starte Backend (uvicorn) ..."
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd `"$root\backend`"; uvicorn app.main:app --reload"
)

# 6) Frontend in eigenem Fenster starten
Step "Starte Frontend (npm run dev) ..."
Start-Process powershell -ArgumentList @(
    "-NoExit", "-Command",
    "cd `"$root\frontend`"; npm run dev"
)

# 7) Kurz warten (Vite-Dev-Server braucht ein paar Sekunden), dann Browser oeffnen
Step "Warte 5 Sekunden, dann oeffne Browser ..."
Start-Sleep -Seconds 5
Start-Process "http://localhost:5173"

Write-Host "== Fertig. Backend- und Frontend-Fenster laufen in separaten Konsolen. ==" -ForegroundColor Green
Write-Host "   Beenden: die beiden geoeffneten Fenster einfach schliessen (Strg+C oder X)." -ForegroundColor Gray
Write-Host "   Postgres stoppen: docker compose down (im Projektordner)" -ForegroundColor Gray
