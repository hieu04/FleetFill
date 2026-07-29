[CmdletBinding()]
param(
    [switch]$SkipTests
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$projectRoot = Split-Path -Parent $PSScriptRoot
$python = Join-Path $projectRoot ".venv\Scripts\python.exe"
$pyInstaller = Join-Path $projectRoot ".venv\Scripts\pyinstaller.exe"
$inspector = Join-Path $projectRoot "research\tools\save-inspector"
$spec = Join-Path $projectRoot "packaging\FleetFill.spec"
$work = Join-Path $projectRoot "packaging\build"
$dist = Join-Path $projectRoot "packaging\dist"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "FleetFill environment not found at $python"
}
if (-not (Test-Path -LiteralPath $pyInstaller -PathType Leaf)) {
    throw "PyInstaller is missing. Run: .venv\Scripts\python.exe -m pip install -r requirements-build.txt"
}
if (-not (Get-Command node -ErrorAction SilentlyContinue)) {
    throw "Node.js 20 or newer is required to build the bundled save decoder."
}
if (-not (Get-Command pnpm -ErrorAction SilentlyContinue)) {
    throw "pnpm is required to restore the pinned save-decoder dependency."
}

& pnpm --dir $inspector install --frozen-lockfile --prod
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

if (-not $SkipTests) {
    & $python -m unittest discover -s (Join-Path $projectRoot "tests") -p "test_*.py"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
    & $python -m unittest discover -s (Join-Path $projectRoot "research\tests") -p "test_*.py"
    if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }
}

# Avoid PyInstaller's global --clean pass here. OneDrive marks generated cache
# directories as reparse points and can briefly deny their removal; PyInstaller
# still invalidates individual build stages when the spec or sources change.
& $pyInstaller --noconfirm --workpath $work --distpath $dist $spec
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$app = Join-Path $dist "FleetFill\FleetFill.exe"
$worker = Join-Path $dist "FleetFill\FleetFillWorker.exe"
if (-not (Test-Path -LiteralPath $app -PathType Leaf)) {
    throw "FleetFill.exe was not produced."
}
if (-not (Test-Path -LiteralPath $worker -PathType Leaf)) {
    throw "FleetFillWorker.exe was not produced."
}

& $worker -m fleetfill.simulated_controller --help
if ($LASTEXITCODE -ne 0) { exit $LASTEXITCODE }

$packagedTools = Join-Path $dist "FleetFill\_internal\research\tools"
$probeScripts = @(
    Get-ChildItem -LiteralPath $packagedTools -Filter "ets2_ui_*_probe.py" -File
    Get-Item -LiteralPath (Join-Path $packagedTools "finalize_batch_validation.py")
    Get-Item -LiteralPath (Join-Path $packagedTools "inspect_company_save.py")
    Get-Item -LiteralPath (Join-Path $packagedTools "rehearse_main_profile_restore.py")
    Get-Item -LiteralPath (Join-Path $packagedTools "verify_fill_batch_save.py")
)
foreach ($probeScript in $probeScripts) {
    $probeOutput = & $worker $probeScript.FullName --help 2>&1
    if ($LASTEXITCODE -ne 0) {
        throw "Packaged worker could not load $($probeScript.Name):`n$($probeOutput -join [Environment]::NewLine)"
    }
}

$calibrationCheck = Join-Path $packagedTools "check_packaged_calibration.py"
& $worker $calibrationCheck
if ($LASTEXITCODE -ne 0) {
    throw "Packaged calibration self-check failed."
}

$requiredBundleFiles = @(
    "_internal\assets\fleetfill-app.png",
    "_internal\assets\fleetfill-app.ico",
    "_internal\runtime\node.exe",
    "_internal\research\tools\save-inspector\decrypt-save.mjs",
    "_internal\research\output\video-020357\frames\frame-0010-000005.000s.jpg",
    "_internal\research\output\video-020129\frames\frame-0027-000013.500s.jpg",
    "_internal\research\output\live-wake-home-test\direct-capture-20260721-005704-141212.png",
    "_internal\research\output\live-hover-services-test\direct-capture-20260721-005945-220477.png",
    "_internal\research\output\live-open-recruitment-from-home-test\direct-capture-20260721-010250-822667.png",
    "_internal\licenses\LICENSE",
    "_internal\licenses\THIRD_PARTY_NOTICES.md"
)
foreach ($relativePath in $requiredBundleFiles) {
    $bundledPath = Join-Path (Join-Path $dist "FleetFill") $relativePath
    if (-not (Test-Path -LiteralPath $bundledPath -PathType Leaf)) {
        throw "Required packaged resource is missing: $relativePath"
    }
}

Write-Host "FLEETFILL_PERSONAL_BETA: $app"
