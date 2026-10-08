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
    'QueryInformationJobObject',
    'ActiveProcesses(job) == 0',
    'Stopwatch.StartNew()',
    '$globalDeadlineMilliseconds = 15000',
    'Invoke-BoundedProbeScenario',
    '$remaining = $globalDeadlineMilliseconds - $globalClock.ElapsedMilliseconds',
    "Schema = 'kaoseghis.synthetic-job-containment-proof.v1'",
    'RootChildGrandchildStarted = $true'
)) {
    if (-not $probe.Contains($literal)) { throw 'containment_probe_contract_missing' }
}
$assignIndex = $probe.IndexOf('AssignProcessToJobObject(job, process.hProcess)')
$resumeIndex = $probe.IndexOf('ResumeThread(process.hThread)')
if ($assignIndex -lt 0 -or $resumeIndex -lt 0 -or $assignIndex -ge $resumeIndex) {
    throw 'containment_assignment_order_invalid'
}
foreach ($role in @("'normal'", "'root'", "'child'", "'grandchild'")) {
    if (-not $worker.Contains($role)) { throw 'synthetic_tree_role_missing' }
}
foreach ($forbidden in @(
    'Invoke-WebRequest', 'Invoke-RestMethod', 'System.Net', 'E:\Kaos',
    'KaosEghis.exe', 'patient', 'credential', 'artifact-manifest.sha256'
)) {
    if ($probe.Contains($forbidden) -or $worker.Contains($forbidden)) {
        throw 'containment_probe_boundary_violation'
    }
}

[PSCustomObject]@{
    CandidateOnly = $true
    WindowsExecutionPerformed = $false
    CreateSuspendedBeforeAssignment = $true
    KillOnJobCloseConfigured = $true
    DeadlineTerminationAndEmptyJobRequired = $true
    SyntheticRootChildGrandchildRequired = $true
    ClinicalOrNetworkLiteralAbsent = $true
} | ConvertTo-Json -Compress
