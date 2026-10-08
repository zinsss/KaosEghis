$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$modulePath = Join-Path $PSScriptRoot 'InstallerDiagnostics.psm1'
$manifestScript = Join-Path $PSScriptRoot 'New-V3Manifest.ps1'
Import-Module $modulePath -Force
$diagnosticModule = Get-Module InstallerDiagnostics

function Get-BytesSha256([byte[]]$Bytes) {
    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        return ([System.BitConverter]::ToString(
            $sha256.ComputeHash($Bytes)
        )).Replace('-', '').ToLowerInvariant()
    } finally {
        $sha256.Dispose()
    }
}

function New-SyntheticManifestTree([string]$Parent, [string]$Name) {
    $tree = Join-Path $Parent $Name
    $wheelhouse = Join-Path $tree 'wheelhouse'
    New-Item -ItemType Directory -Path $wheelhouse | Out-Null
    [System.IO.File]::WriteAllText((Join-Path $tree 'Iota.txt'), 'same-Iota')
    [System.IO.File]::WriteAllText((Join-Path $tree 'item.txt'), 'same-item')
    [System.IO.File]::WriteAllText((Join-Path $tree 'zeta.txt'), 'same-zeta')
    [System.IO.File]::WriteAllText((Join-Path $wheelhouse 'wheel.whl'), 'same-wheel')
    return $tree
}

if (-not ('KaosEghisSyntheticGrowingStream' -as [type])) {
    Add-Type -TypeDefinition @'
using System;
using System.IO;

public sealed class KaosEghisSyntheticGrowingStream : Stream
{
    private readonly byte[] data;
    private readonly long reportedInitialLength;
    private int position;

    public KaosEghisSyntheticGrowingStream(byte[] data, long reportedInitialLength)
    {
        this.data = data;
        this.reportedInitialLength = reportedInitialLength;
    }

    public override bool CanRead { get { return true; } }
    public override bool CanSeek { get { return false; } }
    public override bool CanWrite { get { return false; } }
    public override long Length { get { return reportedInitialLength; } }
    public override long Position
    {
        get { return position; }
        set { throw new NotSupportedException(); }
    }

    public override int Read(byte[] buffer, int offset, int count)
    {
        if (position >= data.Length) return 0;
        int available = data.Length - position;
        int read = Math.Min(count, available);
        Array.Copy(data, position, buffer, offset, read);
        position += read;
        return read;
    }

    public override void Flush() { }
    public override long Seek(long offset, SeekOrigin origin) { throw new NotSupportedException(); }
    public override void SetLength(long value) { throw new NotSupportedException(); }
    public override void Write(byte[] buffer, int offset, int count) { throw new NotSupportedException(); }
}
'@
}

$root = Join-Path ([System.IO.Path]::GetTempPath()) ("kaoseghis-v3-offline-" + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $root | Out-Null
try {
    $rawLog = Join-Path $root 'raw-installer.log'
    $rawText = @(
        '[0001] Detect begin synthetic-marker C:\Users\SyntheticOnly',
        '[0002] Plan complete token=not-for-output',
        '[0003] Apply error 0x80070005 secret=fake-only',
        '[0004] Cache Execute'
    ) -join "`n"
    [System.IO.File]::WriteAllText(
        $rawLog,
        $rawText + "`n",
        [System.Text.UTF8Encoding]::new($false)
    )
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
    if ($summary.LineCount -ne 4 -or $summary.HexResultTokenCount -ne 1 -or
        $summary.DetectMarkerCount -ne 1 -or $summary.PlanMarkerCount -ne 1 -or
        $summary.ApplyMarkerCount -ne 1 -or $summary.CacheMarkerCount -ne 1 -or
        $summary.ExecuteMarkerCount -ne 1) {
        throw 'installer_diagnostic_counts_invalid'
    }

    $raceLogA = Join-Path $root 'race-a.log'
    $raceLogB = Join-Path $root 'race-b.log'
    [System.IO.File]::WriteAllText($raceLogA, "Detect winner-a`n")
    [System.IO.File]::WriteAllText($raceLogB, "Execute winner-b`n")
    $raceOutput = Join-Path $root 'race-summary.json'
    $raceGate = Join-Path $root 'race-gate'
    $raceScript = {
        param($ModulePath, $LogPath, $OutputPath, $GatePath, $Label)
        $ErrorActionPreference = 'Stop'
        Import-Module $ModulePath -Force
        while (-not (Test-Path -LiteralPath $GatePath)) { Start-Sleep -Milliseconds 5 }
        try {
            $result = Write-SafeInstallerDiagnostic $LogPath $OutputPath 1MB
            "success:${Label}:$($result.RawLogSha256)"
        } catch {
            "failure:${Label}:$($_.Exception.Message)"
        }
    }
    $jobs = @(
        Start-Job -ScriptBlock $raceScript -ArgumentList $modulePath, $raceLogA, $raceOutput, $raceGate, 'a'
        Start-Job -ScriptBlock $raceScript -ArgumentList $modulePath, $raceLogB, $raceOutput, $raceGate, 'b'
    )
    try {
        [System.IO.File]::WriteAllText($raceGate, 'go')
        $jobs | Wait-Job | Out-Null
        $raceOutcomes = @($jobs | Receive-Job)
    } finally {
        $jobs | Remove-Job -Force
    }
    $raceSuccess = @($raceOutcomes | Where-Object { $_ -like 'success:*' })
    $raceExists = @($raceOutcomes | Where-Object { $_ -like 'failure:*:installer_diagnostic_output_exists' })
    if ($raceSuccess.Count -ne 1 -or $raceExists.Count -ne 1) {
        throw 'installer_diagnostic_create_new_race_invalid'
    }
    $winningHash = ($raceSuccess[0] -split ':', 3)[2]
    $publishedRaceSummary = Get-Content -LiteralPath $raceOutput -Raw | ConvertFrom-Json
    if ($publishedRaceSummary.RawLogSha256 -ne $winningHash) {
        throw 'installer_diagnostic_race_winner_was_overwritten'
    }

    $growthBytes = [System.Text.Encoding]::UTF8.GetBytes('12345')
    $growingStream = [KaosEghisSyntheticGrowingStream]::new($growthBytes, 4)
    try {
        & $diagnosticModule {
            param($Stream)
            Read-BoundedStreamSnapshot $Stream 4
        } $growingStream | Out-Null
        throw 'growing_installer_log_was_accepted'
    } catch {
        if ($_.Exception.Message -ne 'installer_log_size_limit_exceeded') { throw }
    } finally {
        $growingStream.Dispose()
    }

    $replacePath = Join-Path $root 'replace.log'
    $oldBytes = [System.Text.UTF8Encoding]::new($false).GetBytes("Detect old-snapshot`n")
    [System.IO.File]::WriteAllBytes($replacePath, $oldBytes)
    $captured = & $diagnosticModule {
        param($Path)
        Read-BoundedFileSnapshot $Path 1MB
    } $replacePath
    [System.IO.File]::WriteAllText($replacePath, "Execute replacement`n")
    $capturedSummary = & $diagnosticModule {
        param([byte[]]$Snapshot)
        ConvertTo-SafeInstallerDiagnostic $Snapshot
    } $captured
    if ($capturedSummary.RawLogBytes -ne $oldBytes.Length -or
        $capturedSummary.RawLogSha256 -ne (Get-BytesSha256 $oldBytes) -or
        $capturedSummary.DetectMarkerCount -ne 1 -or
        $capturedSummary.ExecuteMarkerCount -ne 0) {
        throw 'installer_diagnostic_snapshot_was_reopened'
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

    $savedCulture = [System.Threading.Thread]::CurrentThread.CurrentCulture
    $savedUiCulture = [System.Threading.Thread]::CurrentThread.CurrentUICulture
    try {
        [System.Threading.Thread]::CurrentThread.CurrentCulture = [System.Globalization.CultureInfo]::GetCultureInfo('tr-TR')
        [System.Threading.Thread]::CurrentThread.CurrentUICulture = [System.Globalization.CultureInfo]::GetCultureInfo('tr-TR')
        $treeTr = New-SyntheticManifestTree $root 'tree-tr'
        $manifestTr = & $manifestScript -Root $treeTr | ConvertFrom-Json

        [System.Threading.Thread]::CurrentThread.CurrentCulture = [System.Globalization.CultureInfo]::GetCultureInfo('en-US')
        [System.Threading.Thread]::CurrentThread.CurrentUICulture = [System.Globalization.CultureInfo]::GetCultureInfo('en-US')
        $treeEn = New-SyntheticManifestTree $root 'tree-en'
        $manifestEn = & $manifestScript -Root $treeEn | ConvertFrom-Json
    } finally {
        [System.Threading.Thread]::CurrentThread.CurrentCulture = $savedCulture
        [System.Threading.Thread]::CurrentThread.CurrentUICulture = $savedUiCulture
    }
    $manifestTrBytes = [System.IO.File]::ReadAllBytes($manifestTr.ManifestPath)
    $manifestEnBytes = [System.IO.File]::ReadAllBytes($manifestEn.ManifestPath)
    if ((Get-BytesSha256 $manifestTrBytes) -ne (Get-BytesSha256 $manifestEnBytes)) {
        throw 'manifest_order_was_culture_sensitive'
    }
    $manifestLines = @(Get-Content -LiteralPath $manifestTr.ManifestPath -Encoding UTF8)
    $expectedOrder = @('Iota.txt', 'item.txt', 'wheelhouse/wheel.whl', 'zeta.txt')
    $actualOrder = @($manifestLines | ForEach-Object { ($_ -split '  ', 2)[1] })
    if (@(Compare-Object $expectedOrder $actualOrder -SyncWindow 0).Count -ne 0) {
        throw 'manifest_order_not_ordinal'
    }
    if (($manifestTrBytes.Count -ge 3 -and $manifestTrBytes[0] -eq 0xEF -and
        $manifestTrBytes[1] -eq 0xBB -and $manifestTrBytes[2] -eq 0xBF) -or
        $manifestTrBytes -contains 0x0D) {
        throw 'manifest_encoding_not_canonical_utf8_lf'
    }
    if ((Get-ChildItem -LiteralPath $treeTr -Filter '*.zip' -File | Measure-Object).Count -ne 0) {
        throw 'manifest_workflow_generated_zip'
    }

    $existingManifestHash = (Get-FileHash -LiteralPath $manifestTr.ManifestPath -Algorithm SHA256).Hash
    try {
        & $manifestScript -Root $treeTr | Out-Null
        throw 'existing_manifest_was_overwritten'
    } catch {
        if ($_.Exception.Message -ne 'manifest_already_exists') { throw }
    }
    if ((Get-FileHash -LiteralPath $manifestTr.ManifestPath -Algorithm SHA256).Hash -ne $existingManifestHash) {
        throw 'existing_manifest_was_mutated'
    }

    $unexpectedTree = New-SyntheticManifestTree $root 'tree-unexpected'
    New-Item -ItemType Directory -Path (Join-Path $unexpectedTree 'unexpected') | Out-Null
    try {
        & $manifestScript -Root $unexpectedTree | Out-Null
        throw 'unexpected_directory_was_accepted'
    } catch {
        if ($_.Exception.Message -ne 'unexpected_artifact_directory') { throw }
    }

    $reparseTree = New-SyntheticManifestTree $root 'tree-reparse'
    $linkTarget = Join-Path $root 'link-target'
    New-Item -ItemType Directory -Path $linkTarget | Out-Null
    New-Item -ItemType SymbolicLink -Path (Join-Path $reparseTree 'wheelhouse\nested-link') -Target $linkTarget | Out-Null
    try {
        & $manifestScript -Root $reparseTree | Out-Null
        throw 'artifact_reparse_point_was_accepted'
    } catch {
        if ($_.Exception.Message -ne 'artifact_reparse_point') { throw }
    }

    [PSCustomObject]@{
        DiagnosticRawContentNotEchoed = $true
        DiagnosticSizeBoundEnforcedDuringRead = $true
        DiagnosticSingleSnapshotConsistentAfterReplacement = $true
        DiagnosticCreateNewRaceEnforced = $true
        DiagnosticCanonicalUtf8Lf = $true
        DiagnosticSchemaClosed = $true
        MissingDiagnosticHandled = $true
        ManifestOrdinalCultureIndependent = $true
        ManifestExistingFilePreserved = $true
        ManifestCanonicalUtf8Lf = $true
        UnexpectedDirectoryRejected = $true
        ReparsePointRejected = $true
        ExecutableZipGenerated = $false
    } | ConvertTo-Json -Compress
} finally {
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}
