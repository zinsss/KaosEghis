$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$module = Join-Path $PSScriptRoot 'InstallerDiagnostics.psm1'
$manifestScript = Join-Path $PSScriptRoot 'New-V3Manifest.ps1'
Import-Module $module -Force

$root = Join-Path ([System.IO.Path]::GetTempPath()) ("kaoseghis-v3-offline-" + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $root | Out-Null
try {
    $rawLog = Join-Path $root 'raw-installer.log'
    @(
        '[0001] Detect begin synthetic-marker C:\Users\SyntheticOnly',
        '[0002] Plan complete token=not-for-output',
        '[0003] Apply error 0x80070005 secret=fake-only',
        '[0004] Cache Execute'
    ) | Set-Content -LiteralPath $rawLog -Encoding UTF8
    $summaryPath = Join-Path $root 'safe-summary.json'
    $summary = Write-SafeInstallerDiagnostic $rawLog $summaryPath 1MB
    $expectedFields = @(
        'Schema', 'RawLogPresent', 'RawLogBytes', 'RawLogSha256', 'LineCount',
        'HexResultTokenCount', 'DetectMarkerCount', 'PlanMarkerCount',
        'ApplyMarkerCount', 'CacheMarkerCount', 'ExecuteMarkerCount'
    )
    $actualFields = @($summary.PSObject.Properties.Name)
    if (@(Compare-Object $expectedFields $actualFields).Count -ne 0) {
        throw 'installer_diagnostic_schema_not_closed'
    }
    $summaryText = Get-Content -LiteralPath $summaryPath -Raw
    foreach ($forbidden in @('SyntheticOnly', 'not-for-output', 'fake-only', '80070005')) {
        if ($summaryText.Contains($forbidden)) { throw 'installer_diagnostic_echoed_raw_content' }
    }
    $summaryBytes = [System.IO.File]::ReadAllBytes($summaryPath)
    if (($summaryBytes.Count -ge 3 -and $summaryBytes[0] -eq 0xEF -and
        $summaryBytes[1] -eq 0xBB -and $summaryBytes[2] -eq 0xBF) -or
        $summaryBytes -contains 0x0D) {
        throw 'installer_diagnostic_encoding_not_canonical_utf8_lf'
    }
    try {
        Write-SafeInstallerDiagnostic $rawLog $summaryPath 1MB | Out-Null
        throw 'installer_diagnostic_output_was_overwritten'
    } catch {
        if ($_.Exception.Message -ne 'installer_diagnostic_output_exists') { throw }
    }
    if ($summary.LineCount -ne 4 -or $summary.HexResultTokenCount -ne 1 -or
        $summary.DetectMarkerCount -ne 1 -or $summary.PlanMarkerCount -ne 1 -or
        $summary.ApplyMarkerCount -ne 1 -or $summary.CacheMarkerCount -ne 1 -or
        $summary.ExecuteMarkerCount -ne 1) {
        throw 'installer_diagnostic_counts_invalid'
    }

    try {
        Get-SafeInstallerDiagnostic $rawLog 1 | Out-Null
        throw 'oversized_installer_log_was_accepted'
    } catch {
        if ($_.Exception.Message -ne 'installer_log_size_limit_exceeded') { throw }
    }
    $missingSummary = Get-SafeInstallerDiagnostic (Join-Path $root 'missing.log') 1MB
    if ($missingSummary.RawLogPresent -or $missingSummary.RawLogBytes -ne 0 -or
        $null -ne $missingSummary.RawLogSha256) {
        throw 'missing_installer_log_summary_invalid'
    }

    $tree = Join-Path $root 'tree'
    $wheelhouse = Join-Path $tree 'wheelhouse'
    New-Item -ItemType Directory -Path $wheelhouse | Out-Null
    'alpha' | Set-Content -LiteralPath (Join-Path $tree 'alpha.txt') -Encoding ASCII
    'wheel' | Set-Content -LiteralPath (Join-Path $wheelhouse 'wheel.whl') -Encoding ASCII
    $manifestResult = & $manifestScript -Root $tree | ConvertFrom-Json
    if ($manifestResult.Entries -ne 2) { throw 'manifest_entry_count_invalid' }
    $manifestLines = @(Get-Content -LiteralPath $manifestResult.ManifestPath -Encoding UTF8)
    if ($manifestLines.Count -ne 2 -or
        $manifestLines[0] -notmatch '  alpha\.txt$' -or
        $manifestLines[1] -notmatch '  wheelhouse/wheel\.whl$') {
        throw 'manifest_order_or_paths_invalid'
    }
    $manifestBytes = [System.IO.File]::ReadAllBytes($manifestResult.ManifestPath)
    if (($manifestBytes.Count -ge 3 -and $manifestBytes[0] -eq 0xEF -and
        $manifestBytes[1] -eq 0xBB -and $manifestBytes[2] -eq 0xBF) -or
        $manifestBytes -contains 0x0D) {
        throw 'manifest_encoding_not_canonical_utf8_lf'
    }
    if ((Get-ChildItem -LiteralPath $tree -Filter '*.zip' -File | Measure-Object).Count -ne 0) {
        throw 'manifest_workflow_generated_zip'
    }

    $unexpected = Join-Path $tree 'unexpected'
    New-Item -ItemType Directory -Path $unexpected | Out-Null
    try {
        & $manifestScript -Root $tree | Out-Null
        throw 'unexpected_directory_was_accepted'
    } catch {
        if ($_.Exception.Message -ne 'unexpected_artifact_directory') { throw }
    }
    Remove-Item -LiteralPath $unexpected

    $linkTarget = Join-Path $root 'link-target'
    New-Item -ItemType Directory -Path $linkTarget | Out-Null
    $nestedLink = Join-Path $wheelhouse 'nested-link'
    New-Item -ItemType SymbolicLink -Path $nestedLink -Target $linkTarget | Out-Null
    try {
        & $manifestScript -Root $tree | Out-Null
        throw 'artifact_reparse_point_was_accepted'
    } catch {
        if ($_.Exception.Message -ne 'artifact_reparse_point') { throw }
    }

    [PSCustomObject]@{
        DiagnosticRawContentNotEchoed = $true
        DiagnosticSizeBoundEnforced = $true
        DiagnosticCanonicalUtf8Lf = $true
        DiagnosticOutputNotOverwritten = $true
        DiagnosticSchemaClosed = $true
        MissingDiagnosticHandled = $true
        ManifestDeterministic = $true
        ManifestCanonicalUtf8Lf = $true
        UnexpectedDirectoryRejected = $true
        ReparsePointRejected = $true
        ExecutableZipGenerated = $false
    } | ConvertTo-Json -Compress
} finally {
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}
