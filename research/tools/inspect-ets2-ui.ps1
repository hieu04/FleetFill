[CmdletBinding()]
param(
    [ValidateSet("List", "Extract")]
    [string] $Mode = "Extract",

    [Parameter(Mandatory = $true)]
    [string] $GameRoot,

    [string] $OutputRoot = "",

    [switch] $VerifyArchive
)

Set-StrictMode -Version Latest
$ErrorActionPreference = "Stop"

$extractor = Join-Path $PSScriptRoot "skzk-extractor\extractor.exe"
$archive = Join-Path $GameRoot "base_share.scs"

if ([string]::IsNullOrWhiteSpace($OutputRoot)) {
    $OutputRoot = Join-Path $PSScriptRoot "..\output\ets2-ui"
}

if (-not (Test-Path -LiteralPath $extractor -PathType Leaf)) {
    throw "Extractor not found at: $extractor"
}

if (-not (Test-Path -LiteralPath $archive -PathType Leaf)) {
    throw "ETS2 base_share.scs not found at: $archive"
}

$allowedUiPaths = @(
    "/ui/company_manager",
    "/ui/layout/company_driver_widget.sii",
    "/ui/layout/company_driver_widget_small.sii",
    "/ui/layout/company_garage_widget.sii",
    "/ui/layout/company_garage_widget_small.sii",
    "/ui/layout/company_vehicle_widget.sii",
    "/ui/layout/company_vehicle_widget_small.sii",
    "/ui/layout/garage_detail_slot.sii",
    "/ui/copy_truck_table.sii",
    "/ui/driver_view.sii",
    "/ui/garage_selection.sii",
    "/ui/garage_selection_map.sii",
    "/ui/recruit.sii",
    "/ui/recruitment_map.sii",
    "/ui/recruitment_overview.sii",
    "/ui/truck_browser_center.sii",
    "/ui/truck_browser_left.sii",
    "/ui/truck_browser_right.sii",
    "/ui/truck_configuration_bcg.sii",
    "/ui/truck_configuration_center.sii",
    "/ui/truck_configuration_left.sii",
    "/ui/truck_configuration_right.sii",
    "/ui/truck_dealer_bcg.sii",
    "/ui/truck_dealer_left.sii",
    "/ui/truck_dealer_map.sii",
    "/ui/truck_dealer_offer.sii",
    "/ui/truck_dealer_online.sii",
    "/ui/truck_dealer_overview.sii",
    "/ui/truck_dealer_right.sii",
    "/ui/truck_view.sii"
)

Write-Host "Archive: $archive"
Write-Host "Archive size: $((Get-Item -LiteralPath $archive).Length) bytes"
if ($VerifyArchive) {
    Write-Host "Archive SHA256: $((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash)"
}
Write-Host "Extractor SHA256: $((Get-FileHash -LiteralPath $extractor -Algorithm SHA256).Hash)"

if ($Mode -eq "List") {
    & $extractor $archive --list |
        Select-String -Pattern '^/ui/.*(company|dealer|recruit|garage|truck|driver|purchase|shop)'
    if ($LASTEXITCODE -ne 0) {
        throw "Extractor exited with code $LASTEXITCODE"
    }
    exit 0
}

$workspaceRoot = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\.."))
$resolvedOutput = [System.IO.Path]::GetFullPath($OutputRoot)
$workspacePrefix = $workspaceRoot.TrimEnd([System.IO.Path]::DirectorySeparatorChar) + [System.IO.Path]::DirectorySeparatorChar

if (-not $resolvedOutput.StartsWith($workspacePrefix, [System.StringComparison]::OrdinalIgnoreCase)) {
    throw "Output must stay inside the ETS2 research workspace: $workspaceRoot"
}

New-Item -ItemType Directory -Path $resolvedOutput -Force | Out-Null
$partial = $allowedUiPaths -join ','

& $extractor $archive --dest $resolvedOutput --partial=$partial --skip-existing
if ($LASTEXITCODE -ne 0) {
    throw "Extractor exited with code $LASTEXITCODE"
}

Write-Host "Targeted UI files are available under: $resolvedOutput"
