[CmdletBinding()]
param(
    [switch]$SkipAppBuild,
    [switch]$SkipTests
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$appBuild = Join-Path $PSScriptRoot "build-personal-beta.ps1"
$installerScript = Join-Path $projectRoot "packaging\FleetFill.iss"
$installerOutput = Join-Path $projectRoot "packaging\dist\installer\FleetFill-Personal-Beta-Setup-0.1.0.exe"
$compilerCandidates = @(
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 7\ISCC.exe"),
    (Join-Path $env:LOCALAPPDATA "Programs\Inno Setup 6\ISCC.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 7\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 7\ISCC.exe"),
    (Join-Path ${env:ProgramFiles(x86)} "Inno Setup 6\ISCC.exe"),
    (Join-Path $env:ProgramFiles "Inno Setup 6\ISCC.exe")
)
$compiler = $compilerCandidates |
    Where-Object { $_ -and (Test-Path -LiteralPath $_ -PathType Leaf) } |
    Select-Object -First 1

if (-not $SkipAppBuild) {
    $arguments = @("-NoProfile", "-ExecutionPolicy", "Bypass", "-File", $appBuild)
    if ($SkipTests) { $arguments += "-SkipTests" }
    & powershell.exe @arguments
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

if (-not $compiler) {
    throw "Inno Setup 6 or 7 is required. Install JRSoftware.InnoSetup with winget, then rerun this script."
}

& $compiler $installerScript
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not (Test-Path -LiteralPath $installerOutput -PathType Leaf)) {
    throw "FleetFill installer was not produced at $installerOutput"
}

Write-Host "FLEETFILL_INSTALLER: $installerOutput"
