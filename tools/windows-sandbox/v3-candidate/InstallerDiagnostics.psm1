Set-StrictMode -Version Latest

function Get-SafeInstallerDiagnostic {
    param(
        [Parameter(Mandatory = $true)][string]$LogPath,
        [int64]$MaximumBytes = 16MB
    )
    if ($MaximumBytes -lt 1) { throw 'invalid_installer_log_limit' }
    if (-not (Test-Path -LiteralPath $LogPath -PathType Leaf)) {
        return [PSCustomObject]@{
            Schema = 'kaoseghis.python-installer-diagnostic.v1'
            RawLogPresent = $false
            RawLogBytes = 0
            RawLogSha256 = $null
            LineCount = 0
            HexResultTokenCount = 0
            DetectMarkerCount = 0
            PlanMarkerCount = 0
            ApplyMarkerCount = 0
            CacheMarkerCount = 0
            ExecuteMarkerCount = 0
        }
    }

    $item = Get-Item -LiteralPath $LogPath -Force
    if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'installer_log_reparse_point'
    }
    if ($item.Length -gt $MaximumBytes) { throw 'installer_log_size_limit_exceeded' }

    $counts = [ordered]@{
        LineCount = 0
        HexResultTokenCount = 0
        DetectMarkerCount = 0
        PlanMarkerCount = 0
        ApplyMarkerCount = 0
        CacheMarkerCount = 0
        ExecuteMarkerCount = 0
    }
    $reader = [System.IO.StreamReader]::new($item.FullName, $true)
    try {
        while (($line = $reader.ReadLine()) -ne $null) {
            $counts.LineCount++
            $counts.HexResultTokenCount += [regex]::Matches(
                $line,
                '(?i)(?<![0-9a-f])0x[0-9a-f]{8}(?![0-9a-f])'
            ).Count
            foreach ($marker in @('Detect', 'Plan', 'Apply', 'Cache', 'Execute')) {
                if ($line -match "(?i)\b$marker\b") {
                    $counts["${marker}MarkerCount"]++
                }
            }
        }
    } finally {
        $reader.Dispose()
    }

    return [PSCustomObject]@{
        Schema = 'kaoseghis.python-installer-diagnostic.v1'
        RawLogPresent = $true
        RawLogBytes = $item.Length
        RawLogSha256 = (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        LineCount = $counts.LineCount
        HexResultTokenCount = $counts.HexResultTokenCount
        DetectMarkerCount = $counts.DetectMarkerCount
        PlanMarkerCount = $counts.PlanMarkerCount
        ApplyMarkerCount = $counts.ApplyMarkerCount
        CacheMarkerCount = $counts.CacheMarkerCount
        ExecuteMarkerCount = $counts.ExecuteMarkerCount
    }
}

function Write-SafeInstallerDiagnostic {
    param(
        [Parameter(Mandatory = $true)][string]$LogPath,
        [Parameter(Mandatory = $true)][string]$OutputPath,
        [int64]$MaximumBytes = 16MB
    )
    $summary = Get-SafeInstallerDiagnostic $LogPath $MaximumBytes
    if (Test-Path -LiteralPath $OutputPath) { throw 'installer_diagnostic_output_exists' }
    $json = ($summary | ConvertTo-Json -Compress) + "`n"
    [System.IO.File]::WriteAllText(
        $OutputPath,
        $json,
        [System.Text.UTF8Encoding]::new($false)
    )
    return $summary
}

Export-ModuleMember -Function Get-SafeInstallerDiagnostic, Write-SafeInstallerDiagnostic
