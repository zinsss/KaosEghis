$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$wsbPath = Join-Path $PSScriptRoot 'KaosEghisSynthetic.wsb'
$stagePath = Join-Path $PSScriptRoot 'stage-reviewed-bundle.ps1'
$runnerPath = Join-Path $PSScriptRoot 'run-synthetic-tests.ps1'

$xml = [xml](Get-Content -LiteralPath $wsbPath -Raw)
$vGpu = $xml.SelectSingleNode('/Configuration/vGPU')
$wrongCase = $xml.SelectSingleNode('/Configuration/VGpu')
if ($null -eq $vGpu -or $vGpu.InnerText -ne 'Disable' -or $null -ne $wrongCase) {
    throw 'wsb_vgpu_tag_invalid'
}

$stage = Get-Content -LiteralPath $stagePath -Raw
$absenceCall = $stage.IndexOf('Assert-PathSetAbsent $newPaths', [System.StringComparison]::Ordinal)
$firstCreate = $stage.IndexOf('New-Item -ItemType Directory -Path $path', [System.StringComparison]::Ordinal)
$firstAclMutation = $stage.IndexOf('Set-ExactDirectoryAcl $path', [System.StringComparison]::Ordinal)
if ($absenceCall -lt 0 -or $firstCreate -lt 0 -or $firstAclMutation -lt 0 -or
    $absenceCall -ge $firstCreate -or $absenceCall -ge $firstAclMutation) {
    throw 'staging_mutation_precedes_absence_gate'
}

$runner = Get-Content -LiteralPath $runnerPath -Raw
$packager = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'package-reviewed-results.ps1') -Raw
foreach ($literal in @(
    '$GlobalDeadlineSeconds = 1200',
    'VcRuntimeInstall = 300',
    "Sum).Sum -gt 5460",
    'PythonProvision = 180',
    'PythonVersion = 30',
    'PythonBaseSmoke = 30',
    'PythonVenvSmoke = 30',
    'VenvCreate = 120',
    'DependencyInstall = 720',
    'PipCheck = 60',
    'Win32UiSmoke = 30',
    'DependencyInventory = 60',
    'FocusedPytest = 600',
    'FullPytest = 3300',
    "'tests/test_app_notification_ui.py'",
    "'tests/test_emr_signal_probe.py'",
    "'tests/test_kdca_portal_launch.py'",
    'Invoke-DeadlineProcess $FilePath',
    'Assert-WithinGlobalDeadline $Deadline',
    "Stop-FailClosed 'global_deadline_exceeded'",
    'Confirm-RunDeadline',
    "'python-provision-process.json'",
    "'vc-runtime-install-process.json'",
    "Stop-FailClosed 'vc_runtime_hash_mismatch'",
    "Stop-FailClosed 'vc_runtime_install_failed'",
    "Stop-FailClosed 'win32ui_import_failed'",
    'DurationMilliseconds = [int64]$result.DurationMilliseconds',
    'TimedOut = [bool]$result.TimedOut',
    'ExitCode = $result.ExitCode'
)) {
    if (-not $runner.Contains($literal)) { throw 'runner_deadline_contract_missing' }
}
$guards = Get-Content -LiteralPath (Join-Path $PSScriptRoot 'SandboxGuards.psm1') -Raw
foreach ($literal in @('$process.WaitForExit()', '$process.Refresh()', 'DurationMilliseconds')) {
    if (-not $guards.Contains($literal)) { throw 'process_exit_stabilization_missing' }
}
foreach ($literal in @(
    'Confirm-PytestJUnitPassed',
    'if ($ProcessExitCode -ne 0)',
    'Read-PytestJUnitSummary $Path',
    'FocusedJUnitTests = $focusedJUnit.Tests',
    'FullJUnitTests = $fullJUnit.Tests'
)) {
    if (-not $runner.Contains($literal)) { throw 'runner_junit_contract_missing' }
}
foreach ($literal in @(
    'function Read-PytestJUnitSummary',
    "SelectNodes('//testsuite[not(descendant::testsuite)]')",
    '$tests -lt 1 -or $errors -ne 0 -or $failures -ne 0',
    "throw 'pytest_junit_not_passing'"
)) {
    if (-not $guards.Contains($literal)) { throw 'junit_parser_contract_missing' }
}
foreach ($literal in @(
    'Read-PassingJUnit',
    "if (`$status.Status -eq 'passed')",
    "throw 'passing_junit_contradiction'",
    "throw 'passing_status_incomplete'",
    "throw 'passing_status_junit_mismatch'"
)) {
    if (-not $packager.Contains($literal)) { throw 'packager_junit_contract_missing' }
}
$budgetTotal = 300 + 180 + 30 + 30 + 30 + 120 + 720 + 60 + 30 + 60 + 600 + 3300
if ($budgetTotal -ne 5460) { throw 'runner_budget_total_invalid' }

[PSCustomObject]@{
    ExactVgpuTag = $true
    WrongCaseVgpuAbsent = $true
    AbsenceGatePrecedesMutation = $true
    GlobalDeadlineSeconds = 1200
    ChildBudgetTotalSeconds = $budgetTotal
    ChildBudgetsCappedByGlobalDeadline = $true
    ProvisionEvidenceAllowlisted = $true
    VcRuntimeInstallEvidenceAllowlisted = $true
    Win32UiSmokeGatePresent = $true
    ProcessExitStabilizationPresent = $true
    PytestJUnitCrossCheckPresent = $true
    PackagerJUnitCrossCheckPresent = $true
} | ConvertTo-Json -Compress
