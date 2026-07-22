param(
    [Parameter(Mandatory = $true)]
    [string]$ProfileName
)

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $python)) {
    Write-Error "FleetFill virtual environment not found at $python"
    exit 1
}

& $python -m fleetfill --main-profile-five-validation $ProfileName
exit $LASTEXITCODE
