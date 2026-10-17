$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
Import-Module (Join-Path $PSScriptRoot 'SandboxGuards.psm1') -Force

$root = Join-Path ([System.IO.Path]::GetTempPath()) ("kaoseghis-sandbox-guards-" + [Guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $root | Out-Null
try {
    $nonemptyParent = Join-Path $root 'nonempty-parent'
    New-Item -ItemType Directory -Path $nonemptyParent | Out-Null
    $sentinel = Join-Path $nonemptyParent 'sentinel.txt'
    'unchanged' | Set-Content -LiteralPath $sentinel -Encoding ASCII
    $sentinelHash = (Get-FileHash -LiteralPath $sentinel -Algorithm SHA256).Hash
    try {
        Assert-PathSetAbsent @($nonemptyParent)
        throw 'nonempty_parent_was_accepted'
    } catch {
        if ($_.Exception.Message -ne 'staging_path_already_exists') { throw }
    }
    if ((Get-FileHash -LiteralPath $sentinel -Algorithm SHA256).Hash -ne $sentinelHash) {
        throw 'nonempty_parent_was_mutated'
    }

    $junctionTarget = Join-Path $root 'junction-target'
    $junction = Join-Path $root 'parent-junction'
    New-Item -ItemType Directory -Path $junctionTarget | Out-Null
    'unchanged' | Set-Content -LiteralPath (Join-Path $junctionTarget 'sentinel.txt') -Encoding ASCII
    # Directory junctions are reparse points and can be created by the normal
    # non-admin Windows test account.  This keeps the guard test representative
    # without requiring Developer Mode or SeCreateSymbolicLinkPrivilege.
    New-Item -ItemType Junction -Path $junction -Target $junctionTarget | Out-Null
    if (-not ((Get-Item -LiteralPath $junction -Force).Attributes -band
        [System.IO.FileAttributes]::ReparsePoint)) {
        throw 'parent_junction_is_not_a_reparse_point'
    }
    try {
        Assert-PathSetAbsent @($junction)
        throw 'parent_junction_was_accepted'
    } catch {
        if ($_.Exception.Message -ne 'staging_path_already_exists') { throw }
    }
    if ((Get-Content -LiteralPath (Join-Path $junctionTarget 'sentinel.txt') -Raw).Trim() -ne 'unchanged') {
        throw 'parent_junction_target_was_mutated'
    }

    $tree = Join-Path $root 'tree'
    $wheelhouse = Join-Path $tree 'wheelhouse'
    New-Item -ItemType Directory -Path $wheelhouse | Out-Null
    'alpha' | Set-Content -LiteralPath (Join-Path $tree 'alpha.txt') -Encoding ASCII
    'wheel' | Set-Content -LiteralPath (Join-Path $wheelhouse 'wheel.whl') -Encoding ASCII
    $manifest = Join-Path $tree 'artifact-manifest.sha256'
    @(
        "$( (Get-FileHash -LiteralPath (Join-Path $tree 'alpha.txt') -Algorithm SHA256).Hash.ToLowerInvariant() )  alpha.txt",
        "$( (Get-FileHash -LiteralPath (Join-Path $wheelhouse 'wheel.whl') -Algorithm SHA256).Hash.ToLowerInvariant() )  wheelhouse/wheel.whl"
    ) | Set-Content -LiteralPath $manifest -Encoding UTF8
    $treeResult = Assert-ExactArtifactTree $tree $manifest @('wheelhouse')
    if ($treeResult.Files -ne 2 -or $treeResult.Directories -ne 1) { throw 'valid_tree_rejected' }

    $unexpected = Join-Path $tree 'unexpected-empty'
    New-Item -ItemType Directory -Path $unexpected | Out-Null
    $unexpectedBefore = Get-Item -LiteralPath $unexpected -Force
    $unexpectedAttributes = $unexpectedBefore.Attributes
    $unexpectedWriteTime = $unexpectedBefore.LastWriteTimeUtc
    try {
        Assert-ExactArtifactTree $tree $manifest @('wheelhouse')
        throw 'unexpected_empty_directory_was_accepted'
    } catch {
        if ($_.Exception.Message -ne 'unexpected_artifact_directory') { throw }
    }
    $unexpectedAfter = Get-Item -LiteralPath $unexpected -Force
    if ($unexpectedAfter.Attributes -ne $unexpectedAttributes -or
        $unexpectedAfter.LastWriteTimeUtc -ne $unexpectedWriteTime) {
        throw 'unexpected_empty_directory_was_mutated'
    }
    Remove-Item -LiteralPath $unexpected

    $nestedTarget = Join-Path $root 'nested-target'
    New-Item -ItemType Directory -Path $nestedTarget | Out-Null
    $nestedSentinel = Join-Path $nestedTarget 'sentinel.txt'
    'unchanged' | Set-Content -LiteralPath $nestedSentinel -Encoding ASCII
    $nestedSentinelHash = (Get-FileHash -LiteralPath $nestedSentinel -Algorithm SHA256).Hash
    $nestedJunction = Join-Path $wheelhouse 'nested-junction'
    New-Item -ItemType Junction -Path $nestedJunction -Target $nestedTarget | Out-Null
    if (-not ((Get-Item -LiteralPath $nestedJunction -Force).Attributes -band
        [System.IO.FileAttributes]::ReparsePoint)) {
        throw 'nested_junction_is_not_a_reparse_point'
    }
    try {
        Assert-ExactArtifactTree $tree $manifest @('wheelhouse')
        throw 'nested_junction_was_accepted'
    } catch {
        if ($_.Exception.Message -ne 'artifact_reparse_point') { throw }
    }
    if ((Get-FileHash -LiteralPath $nestedSentinel -Algorithm SHA256).Hash -ne $nestedSentinelHash) {
        throw 'nested_junction_target_was_mutated'
    }

    $child = Join-Path $root 'long-child.ps1'
    'Start-Sleep -Seconds 30' | Set-Content -LiteralPath $child -Encoding ASCII
    $deadline = New-GlobalDeadline 2
    $result = Invoke-DeadlineProcess $PSHOME/pwsh @('-NoLogo', '-NoProfile', '-NonInteractive', '-File', $child) 30 $deadline `
        (Join-Path $root 'child-out.txt') (Join-Path $root 'child-error.txt')
    if (-not $result.TimedOut -or $result.Reason -ne 'global_deadline_exceeded') {
        throw 'global_deadline_was_not_enforced'
    }
    if ($null -eq $result.PSObject.Properties['ExitCode'] -or
        $null -eq $result.PSObject.Properties['DurationMilliseconds'] -or
        $result.DurationMilliseconds -lt 1000 -or $result.DurationMilliseconds -ge 6000) {
        throw 'bounded_timeout_evidence_invalid'
    }
    if ($deadline.Stopwatch.Elapsed.TotalSeconds -ge 6) { throw 'global_deadline_termination_was_late' }

    $successChild = Join-Path $root 'success-child.ps1'
    "'ok'; exit 0" | Set-Content -LiteralPath $successChild -Encoding ASCII
    $successDeadline = New-GlobalDeadline 10
    $successResult = Invoke-DeadlineProcess $PSHOME/pwsh @('-NoLogo', '-NoProfile', '-NonInteractive', '-File', $successChild) 5 $successDeadline `
        (Join-Path $root 'success-out.txt') (Join-Path $root 'success-error.txt')
    if ($successResult.ExitCode -ne 0 -or $successResult.TimedOut -or $null -ne $successResult.Reason -or
        $successResult.DurationMilliseconds -lt 0 -or $successResult.DurationMilliseconds -ge 5000) {
        throw 'successful_process_evidence_invalid'
    }
    if ((Get-Content -LiteralPath (Join-Path $root 'success-out.txt') -Raw).Trim() -ne 'ok') {
        throw 'successful_process_output_not_flushed'
    }

    [PSCustomObject]@{
        NonemptyParentRejectedWithoutMutation = $true
        ParentJunctionRejectedWithoutMutation = $true
        UnexpectedEmptyDirectoryRejected = $true
        NestedJunctionRejected = $true
        GlobalDeadlineKilledLongChild = $true
        TimeoutEvidenceRecorded = $true
        SuccessfulExitCodeAndDurationRecorded = $true
        RedirectedOutputFlushed = $true
    } | ConvertTo-Json -Compress
} finally {
    Remove-Item -LiteralPath $root -Recurse -Force -ErrorAction SilentlyContinue
}
