$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$probePath = Join-Path $PSScriptRoot 'Test-JobObjectContainment.ps1'
$workerPath = Join-Path $PSScriptRoot 'SyntheticProcessTree.ps1'
$probe = Get-Content -LiteralPath $probePath -Raw
$worker = Get-Content -LiteralPath $workerPath -Raw

foreach ($literal in @(
    'CREATE_SUSPENDED',
    'JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE',
    'AssignProcessToJobObject',
    'ResumeThread',
    'TerminateJobObject',
    'TerminateProcess',
    'GetExitCodeProcess',
    'if (!TerminateProcess(process, 901))',
    'if (!TerminateJobObject(job, exitCode))',
    'WaitForSingleObject(process, (uint)remaining) != WAIT_OBJECT_0',
    'if (processCreated && !cleanupProven)',
    'QueryInformationJobObject',
    'ActiveProcesses(job) == 0',
    'Stopwatch.StartNew()',
    '$globalDeadlineMilliseconds = 15000',
    'Invoke-BoundedProbeScenario',
    '$remaining = $globalDeadlineMilliseconds - $globalClock.ElapsedMilliseconds',
    "Schema = 'kaoseghis.synthetic-job-containment-proof.v1'",
    '$envelopeStatusAllowlist -cnotcontains $Status',
    '$envelopeReasonAllowlist -cnotcontains $Reason',
    '$normal.ExitCode -ne 0',
    'Assert-ExactProbeMarkers',
    'Remove-ExactProbeRoot',
    "Reason = 'proof_complete'",
    "Reason = 'probe_cleanup_failed'"
)) {
    if (-not $probe.Contains($literal)) { throw 'containment_probe_contract_missing' }
}
$assignIndex = $probe.IndexOf('AssignProcessToJobObject(job, process.hProcess)')
$resumeIndex = $probe.IndexOf('ResumeThread(process.hThread)')
if ($assignIndex -lt 0 -or $resumeIndex -lt 0 -or $assignIndex -ge $resumeIndex) {
    throw 'containment_assignment_order_invalid'
}
foreach ($role in @(
    "'normal'", "'nonzero-before-marker'", "'root'", "'child'", "'grandchild'"
)) {
    if (-not $worker.Contains($role)) { throw 'synthetic_tree_role_missing' }
}
$negativeExitIndex = $worker.IndexOf("if (`$Role -eq 'nonzero-before-marker') { exit 23 }")
$markerWriteIndex = $worker.IndexOf('Write-RoleMarker $Role')
if ($negativeExitIndex -lt 0 -or $markerWriteIndex -lt 0 -or
    $negativeExitIndex -ge $markerWriteIndex) {
    throw 'negative_worker_marks_before_nonzero_exit'
}
if ($probe.Contains('SilentlyContinue')) { throw 'silent_cleanup_failure_allowed' }
$cleanupCallIndex = $probe.LastIndexOf('Remove-ExactProbeRoot')
$envelopeIndex = $probe.LastIndexOf('$envelope = New-ClosedProbeEnvelope')
if ($cleanupCallIndex -lt 0 -or $envelopeIndex -lt 0 -or
    $cleanupCallIndex -ge $envelopeIndex) {
    throw 'success_envelope_precedes_cleanup'
}
foreach ($forbidden in @(
    'Invoke-WebRequest', 'Invoke-RestMethod', 'System.Net', 'E:\Kaos',
    'KaosEghis.exe', 'patient', 'credential', 'artifact-manifest.sha256'
)) {
    if ($probe.Contains($forbidden) -or $worker.Contains($forbidden)) {
        throw 'containment_probe_boundary_violation'
    }
}

$start = [Diagnostics.ProcessStartInfo]::new()
$start.FileName = (Get-Process -Id $PID).Path
$start.Arguments = '-NoProfile -NonInteractive -File "{0}"' -f $probePath
$start.UseShellExecute = $false
$start.RedirectStandardOutput = $true
$start.RedirectStandardError = $true
$process = [Diagnostics.Process]::Start($start)
if ($null -eq $process) { throw 'closed_failure_probe_start_failed' }
try {
    $stdout = $process.StandardOutput.ReadToEnd()
    $stderr = $process.StandardError.ReadToEnd()
    $process.WaitForExit()
    $exitCode = $process.ExitCode
} finally {
    $process.Dispose()
}
if ($exitCode -ne 1 -or -not [string]::IsNullOrEmpty($stderr)) {
    throw 'closed_failure_process_contract_invalid'
}
$failure = $stdout | ConvertFrom-Json
$expectedFields = @(
    'Schema', 'Status', 'Reason', 'SyntheticOnly', 'SuspendedBeforeAssignment',
    'NormalExitVerified', 'NormalMarkerVerified', 'NegativeWorkerPrepared',
    'RootChildGrandchildStarted', 'DeadlineTriggered',
    'RootExitedAfterTermination', 'JobActiveProcessCountReachedZero',
    'CleanupVerified', 'ProbeGlobalDeadlineMilliseconds', 'ElapsedMilliseconds'
)
if (@(Compare-Object $expectedFields @($failure.PSObject.Properties.Name)).Count -ne 0 -or
    $failure.Schema -ne 'kaoseghis.synthetic-job-containment-proof.v1' -or
    $failure.Status -ne 'blocked' -or $failure.Reason -ne 'wrong_platform' -or
    -not $failure.SyntheticOnly -or -not $failure.NegativeWorkerPrepared -or
    -not $failure.CleanupVerified) {
    throw 'closed_failure_envelope_invalid'
}

[PSCustomObject]@{
    CandidateOnly = $true
    WindowsExecutionPerformed = $false
    CreateSuspendedBeforeAssignment = $true
    KillOnJobCloseConfigured = $true
    DeadlineTerminationAndEmptyJobRequired = $true
    SyntheticRootChildGrandchildRequired = $true
    ExitCodeAndExactMarkerRequired = $true
    NegativeWorkerPreparedWithoutExecution = $true
    CleanupPrecedesSuccessEnvelope = $true
    ClosedFailureEnvelopeVerifiedOnLinux = $true
    ClinicalOrNetworkLiteralAbsent = $true
} | ConvertTo-Json -Compress
