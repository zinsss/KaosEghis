Set-StrictMode -Version Latest

function Assert-PathSetAbsent {
    param(
        [Parameter(Mandatory = $true)]
        [string[]]$Paths,
        [string]$Reason = 'staging_path_already_exists'
    )
    foreach ($path in $Paths) {
        if (Test-Path -LiteralPath $path) { throw $Reason }
    }
}

function Read-ArtifactManifest {
    param([Parameter(Mandatory = $true)][string]$ManifestPath)
    $entries = @{}
    foreach ($line in Get-Content -LiteralPath $ManifestPath -Encoding UTF8) {
        if ($line -notmatch '^([0-9a-f]{64})  ([A-Za-z0-9][A-Za-z0-9._/\-]*)$') {
            throw 'malformed_artifact_manifest'
        }
        $relative = $Matches[2].Replace('\', '/')
        if ([System.IO.Path]::IsPathRooted($relative) -or $relative.Split('/') -contains '..') {
            throw 'unsafe_manifest_path'
        }
        if ($entries.ContainsKey($relative)) { throw 'duplicate_manifest_path' }
        $entries[$relative] = $Matches[1]
    }
    return $entries
}

function Assert-ExactArtifactTree {
    param(
        [Parameter(Mandatory = $true)][string]$Root,
        [Parameter(Mandatory = $true)][string]$ManifestPath,
        [string[]]$AllowedDirectories = @('wheelhouse')
    )
    $rootItem = Get-Item -LiteralPath $Root -Force
    if (-not $rootItem.PSIsContainer -or
        ($rootItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
        throw 'artifact_root_unsafe'
    }
    $manifestItem = Get-Item -LiteralPath $ManifestPath -Force
    if ($manifestItem.PSIsContainer -or
        ($manifestItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
        throw 'artifact_manifest_unsafe'
    }

    $entries = Read-ArtifactManifest $ManifestPath
    $descendants = @(Get-ChildItem -LiteralPath $Root -Force -Recurse)
    foreach ($item in $descendants) {
        if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
            throw 'artifact_reparse_point'
        }
    }

    $directories = @($descendants | Where-Object { $_.PSIsContainer } | ForEach-Object {
        $_.FullName.Substring($Root.Length + 1).Replace('\', '/')
    } | Sort-Object)
    $expectedDirectories = @($AllowedDirectories | Sort-Object)
    if (@(Compare-Object -ReferenceObject $expectedDirectories -DifferenceObject $directories).Count -ne 0) {
        throw 'unexpected_artifact_directory'
    }

    $manifestFullPath = [System.IO.Path]::GetFullPath($ManifestPath)
    $files = @($descendants | Where-Object {
        -not $_.PSIsContainer -and
        -not [string]::Equals(
            [System.IO.Path]::GetFullPath($_.FullName),
            $manifestFullPath,
            [System.StringComparison]::OrdinalIgnoreCase
        )
    })
    if ($files.Count -ne $entries.Count) { throw 'artifact_file_set_mismatch' }
    foreach ($file in $files) {
        $relative = $file.FullName.Substring($Root.Length + 1).Replace('\', '/')
        if (-not $entries.ContainsKey($relative)) { throw 'unexpected_artifact_file' }
        $actualHash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
        if ($actualHash -ne $entries[$relative]) { throw 'artifact_hash_mismatch' }
    }
    return [PSCustomObject]@{
        Files = $files.Count
        Directories = $directories.Count
    }
}

function New-GlobalDeadline {
    param([Parameter(Mandatory = $true)][int]$LimitSeconds)
    if ($LimitSeconds -lt 1) { throw 'invalid_global_deadline' }
    return [PSCustomObject]@{
        LimitSeconds = $LimitSeconds
        Stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    }
}

function Get-RemainingDeadlineMilliseconds {
    param([Parameter(Mandatory = $true)]$Deadline)
    $remaining = [math]::Floor(($Deadline.LimitSeconds - $Deadline.Stopwatch.Elapsed.TotalSeconds) * 1000)
    return [math]::Max(0, [int64]$remaining)
}

function Assert-WithinGlobalDeadline {
    param([Parameter(Mandatory = $true)]$Deadline)
    if ((Get-RemainingDeadlineMilliseconds $Deadline) -le 0) {
        throw 'global_deadline_exceeded'
    }
}

function Invoke-DeadlineProcess {
    param(
        [Parameter(Mandatory = $true)][string]$FilePath,
        [string[]]$ArgumentList = @(),
        [Parameter(Mandatory = $true)][int]$StepTimeoutSeconds,
        [Parameter(Mandatory = $true)]$Deadline,
        [Parameter(Mandatory = $true)][string]$StdoutPath,
        [Parameter(Mandatory = $true)][string]$StderrPath
    )
    $processStopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    $remainingMilliseconds = Get-RemainingDeadlineMilliseconds $Deadline
    if ($remainingMilliseconds -le 0) {
        $processStopwatch.Stop()
        return [PSCustomObject]@{
            ExitCode = $null
            TimedOut = $true
            DurationMilliseconds = [int64]$processStopwatch.ElapsedMilliseconds
            Reason = 'global_deadline_exceeded'
        }
    }
    $stepMilliseconds = [int64]$StepTimeoutSeconds * 1000
    $effectiveMilliseconds = [math]::Min($stepMilliseconds, $remainingMilliseconds)
    $globalLimited = $remainingMilliseconds -le $stepMilliseconds

    $process = Start-Process -FilePath $FilePath -ArgumentList $ArgumentList -PassThru -NoNewWindow `
        -RedirectStandardOutput $StdoutPath -RedirectStandardError $StderrPath
    if (-not $process.WaitForExit([int]$effectiveMilliseconds)) {
        if ([System.Environment]::OSVersion.Platform -eq [System.PlatformID]::Win32NT) {
            & taskkill.exe /PID $process.Id /T /F *> $null
        } else {
            $process.Kill($true)
        }
        $terminationObserved = $process.WaitForExit(2000)
        if ($terminationObserved) { $process.Refresh() }
        $processStopwatch.Stop()
        $timedOutExitCode = if ($terminationObserved) { try { [int]$process.ExitCode } catch { $null } } else { $null }
        return [PSCustomObject]@{
            ExitCode = $timedOutExitCode
            TimedOut = $true
            DurationMilliseconds = [int64]$processStopwatch.ElapsedMilliseconds
            Reason = if ($globalLimited) { 'global_deadline_exceeded' } else { 'bounded_process_timeout' }
        }
    }
    # Complete the unbounded wait only after the bounded wait proved termination.
    # This flushes redirected streams and refreshes the stable process exit code.
    $process.WaitForExit()
    $process.Refresh()
    $exitCode = [int]$process.ExitCode
    $processStopwatch.Stop()
    if ((Get-RemainingDeadlineMilliseconds $Deadline) -le 0) {
        return [PSCustomObject]@{
            ExitCode = $exitCode
            TimedOut = $true
            DurationMilliseconds = [int64]$processStopwatch.ElapsedMilliseconds
            Reason = 'global_deadline_exceeded'
        }
    }
    return [PSCustomObject]@{
        ExitCode = $exitCode
        TimedOut = $false
        DurationMilliseconds = [int64]$processStopwatch.ElapsedMilliseconds
        Reason = $null
    }
}

Export-ModuleMember -Function Assert-PathSetAbsent, Read-ArtifactManifest, Assert-ExactArtifactTree, `
    New-GlobalDeadline, Get-RemainingDeadlineMilliseconds, Assert-WithinGlobalDeadline, `
    Invoke-DeadlineProcess
