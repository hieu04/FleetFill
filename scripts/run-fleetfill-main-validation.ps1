param(
    [Parameter(Mandatory = $true)]
    [string]$ProfileName
)

$ErrorActionPreference = "Stop"
$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path -LiteralPath $python)) {
    throw "FleetFill virtual environment was not found at $python"
}

& $python -m fleetfill --main-profile-validation $ProfileName
