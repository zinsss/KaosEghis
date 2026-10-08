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
foreach ($literal in @(
    '$GlobalDeadlineSeconds = 5400',
    'PythonInstall = 480',
    'VenvCreate = 120',
    'DependencyInstall = 720',
    'PipCheck = 60',
    'DependencyInventory = 60',
    'Pytest = 3300',
    'Invoke-DeadlineProcess $FilePath',
    'Assert-WithinGlobalDeadline $Deadline',
    "Stop-FailClosed 'global_deadline_exceeded'",
    'Confirm-RunDeadline'
)) {
    if (-not $runner.Contains($literal)) { throw 'runner_deadline_contract_missing' }
}
$budgetTotal = 480 + 120 + 720 + 60 + 60 + 3300
if ($budgetTotal -ne 4740 -or $budgetTotal -ge 5400) { throw 'runner_budget_total_invalid' }

[PSCustomObject]@{
    ExactVgpuTag = $true
    WrongCaseVgpuAbsent = $true
    AbsenceGatePrecedesMutation = $true
    GlobalDeadlineSeconds = 5400
    ChildBudgetTotalSeconds = $budgetTotal
    OverheadReserveSeconds = 5400 - $budgetTotal
} | ConvertTo-Json -Compress
