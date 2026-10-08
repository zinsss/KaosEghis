Set-StrictMode -Version Latest

function Read-BoundedStreamSnapshot {
    param(
        [Parameter(Mandatory = $true)][System.IO.Stream]$Stream,
        [int64]$MaximumBytes = 16MB
    )
    if ($MaximumBytes -lt 1) { throw 'invalid_installer_log_limit' }
    $buffer = [byte[]]::new(8192)
    $snapshot = [System.IO.MemoryStream]::new()
    try {
        while (($read = $Stream.Read($buffer, 0, $buffer.Length)) -gt 0) {
            if ($snapshot.Length + $read -gt $MaximumBytes) {
                throw 'installer_log_size_limit_exceeded'
            }
            $snapshot.Write($buffer, 0, $read)
        }
        return ,$snapshot.ToArray()
    } finally {
        $snapshot.Dispose()
    }
}

function Read-BoundedFileSnapshot {
    param(
        [Parameter(Mandatory = $true)][string]$LogPath,
        [int64]$MaximumBytes = 16MB
    )
    if ($MaximumBytes -lt 1) { throw 'invalid_installer_log_limit' }
    try {
        $item = Get-Item -LiteralPath $LogPath -Force -ErrorAction Stop
    } catch [System.Management.Automation.ItemNotFoundException] {
        return $null
    }
    if ($item.PSIsContainer) { throw 'installer_log_not_file' }
    if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'installer_log_reparse_point'
    }

    try {
        $stream = [System.IO.FileStream]::new(
            $LogPath,
            [System.IO.FileMode]::Open,
            [System.IO.FileAccess]::Read,
            [System.IO.FileShare]::Read
        )
    } catch [System.IO.FileNotFoundException] {
        return $null
    } catch [System.IO.DirectoryNotFoundException] {
        return $null
    }
    try {
        $bytes = [byte[]](Read-BoundedStreamSnapshot $stream $MaximumBytes)
        return [PSCustomObject]@{ Bytes = $bytes }
    } finally {
        $stream.Dispose()
    }
}

function New-MissingInstallerDiagnostic {
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

function ConvertTo-SafeInstallerDiagnostic {
    param(
        [Parameter(Mandatory = $true)]
        [AllowEmptyCollection()]
        [byte[]]$Snapshot
    )
    $counts = [ordered]@{
        LineCount = 0
        HexResultTokenCount = 0
        DetectMarkerCount = 0
        PlanMarkerCount = 0
        ApplyMarkerCount = 0
        CacheMarkerCount = 0
        ExecuteMarkerCount = 0
    }
    $snapshotStream = [System.IO.MemoryStream]::new($Snapshot, $false)
    $reader = [System.IO.StreamReader]::new(
        $snapshotStream,
        [System.Text.UTF8Encoding]::new($false, $true),
        $true
    )
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
        $snapshotStream.Dispose()
    }

    $sha256 = [System.Security.Cryptography.SHA256]::Create()
    try {
        $snapshotHash = ([System.BitConverter]::ToString(
            $sha256.ComputeHash($Snapshot)
        )).Replace('-', '').ToLowerInvariant()
    } finally {
        $sha256.Dispose()
    }

    return [PSCustomObject]@{
        Schema = 'kaoseghis.python-installer-diagnostic.v1'
        RawLogPresent = $true
        RawLogBytes = $Snapshot.Length
        RawLogSha256 = $snapshotHash
        LineCount = $counts.LineCount
        HexResultTokenCount = $counts.HexResultTokenCount
        DetectMarkerCount = $counts.DetectMarkerCount
        PlanMarkerCount = $counts.PlanMarkerCount
        ApplyMarkerCount = $counts.ApplyMarkerCount
        CacheMarkerCount = $counts.CacheMarkerCount
        ExecuteMarkerCount = $counts.ExecuteMarkerCount
    }
}

function Get-SafeInstallerDiagnostic {
    param(
        [Parameter(Mandatory = $true)][string]$LogPath,
        [int64]$MaximumBytes = 16MB
    )
    $snapshot = Read-BoundedFileSnapshot $LogPath $MaximumBytes
    if ($null -eq $snapshot) { return New-MissingInstallerDiagnostic }
    return ConvertTo-SafeInstallerDiagnostic $snapshot.Bytes
}

function Write-SafeInstallerDiagnostic {
    param(
        [Parameter(Mandatory = $true)][string]$LogPath,
        [Parameter(Mandatory = $true)][string]$OutputPath,
        [int64]$MaximumBytes = 16MB
    )
    $summary = Get-SafeInstallerDiagnostic $LogPath $MaximumBytes
    $json = ($summary | ConvertTo-Json -Compress) + "`n"
    $bytes = [System.Text.UTF8Encoding]::new($false).GetBytes($json)
    try {
        $output = [System.IO.FileStream]::new(
            $OutputPath,
            [System.IO.FileMode]::CreateNew,
            [System.IO.FileAccess]::Write,
            [System.IO.FileShare]::None
        )
    } catch [System.IO.IOException] {
        if (Test-Path -LiteralPath $OutputPath) {
            throw 'installer_diagnostic_output_exists'
        }
        throw 'installer_diagnostic_output_create_failed'
    }
    try {
        $output.Write($bytes, 0, $bytes.Length)
        $output.Flush($true)
    } finally {
        $output.Dispose()
    }
    return $summary
}

Export-ModuleMember -Function Get-SafeInstallerDiagnostic, Write-SafeInstallerDiagnostic
