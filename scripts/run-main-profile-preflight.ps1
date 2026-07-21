param(
    [Parameter(Mandatory = $true)]
    [string]$ProfileName,
    [ValidateRange(1, 5)]
    [int]$Count = 1
)

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$tool = Join-Path $projectRoot "research\tools\main_profile_preflight.py"

& $python $tool --profile-name $ProfileName --count $Count
exit $LASTEXITCODE
