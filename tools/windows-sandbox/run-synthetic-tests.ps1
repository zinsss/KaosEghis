$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$ExpectedSourceCommit = '1dc9250dae01d236e3cfca45b8142e98519478bb'
$ExpectedInstallerHash = '5ee42c4eee1e6b4464bb23722f90b45303f79442df63083f05322f1785f5fdde'
$ExpectedRuntimeHash = '1965edbb4b97913c2cd689a63b2a49624686ec85729525fe0219a267e6b057d5'
$ExpectedRuntimeManifestHash = '75ccb5515181c316e050f29bb5629d90eaffa6756a31f7b2a126297cf7806460'
$ExpectedPythonSmokeHash = '9b77223a802be2539f0f7a2d3c849b472133d454aac919f54941ed4c55e52f09'
$GlobalDeadlineSeconds = 480
$StepBudgets = [ordered]@{
    PythonProvision = 180
    PythonVersion = 30
    PythonBaseSmoke = 30
    PythonVenvSmoke = 30
    VenvCreate = 120
    DependencyInstall = 720
    PipCheck = 60
    DependencyInventory = 60
    FocusedPytest = 600
    FullPytest = 3300
}
if (($StepBudgets.Values | Measure-Object -Sum).Sum -gt 5340) { throw 'invalid_step_budget_total' }
$Deadline = [PSCustomObject]@{
    LimitSeconds = $GlobalDeadlineSeconds
    Stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
}
$Inbound = 'C:\MappedInbound'
$Results = 'C:\MappedResults'
$RunRoot = 'C:\KaosTestRun'
$PythonRoot = Join-Path $RunRoot 'Python'
$PythonExe = Join-Path $PythonRoot 'python.exe'
$VenvRoot = Join-Path $RunRoot 'venv'
$VenvPython = Join-Path $VenvRoot 'Scripts\python.exe'
$Wheelhouse = Join-Path $Inbound 'wheelhouse'
$LockFile = Join-Path $Inbound 'requirements-win311.lock'
$SourceArchive = Join-Path $Inbound 'KaosEghis-1dc9250dae01-source.zip'
$Manifest = Join-Path $Inbound 'artifact-manifest.sha256'
$RuntimeArchive = Join-Path $Inbound 'python-3.11.9-runtime-v5.zip'
$RuntimeManifest = Join-Path $Inbound 'python-runtime-manifest-v5.json'
$RuntimeProvisioner = Join-Path $Inbound 'provision-python-runtime.ps1'
$PythonSmokeScript = Join-Path $Inbound 'python-runtime-smoke.py'
$ExpectedSourceRoot = Join-Path $RunRoot 'src\KaosEghis-1dc9250dae01'

function Stop-FailClosed([string]$Reason) {
    $safeReason = if ($Reason -match '^[a-z0-9_]{1,80}$') { $Reason } else { 'unspecified_failure' }
    [PSCustomObject]@{
        Status = 'blocked'
        Reason = $safeReason
    } | ConvertTo-Json -Compress | Set-Content -LiteralPath (Join-Path $Results 'status.json') -Encoding UTF8
    $safeReason | Set-Content -LiteralPath (Join-Path $Results 'failure.txt') -Encoding ASCII
    throw $safeReason
}

function Invoke-RunProcess(
    [string]$FilePath,
    [string[]]$ArgumentList,
    [int]$TimeoutSeconds,
    [string]$StdoutName,
    [string]$StderrName,
    [string]$TimeoutReason = 'bounded_process_timeout',
    [string]$EvidenceName = ''
) {
    $stdoutPath = Join-Path $Results $StdoutName
    $stderrPath = Join-Path $Results $StderrName
    $result = Invoke-DeadlineProcess $FilePath $ArgumentList $TimeoutSeconds $Deadline $stdoutPath $stderrPath
    if ($EvidenceName) {
        if ($EvidenceName -notmatch '^[a-z0-9][a-z0-9.-]{0,63}\.json$') { Stop-FailClosed 'invalid_process_evidence_name' }
        [PSCustomObject]@{
            ExitCode = $result.ExitCode
            TimedOut = [bool]$result.TimedOut
            DurationMilliseconds = [int64]$result.DurationMilliseconds
            StepTimeoutSeconds = $TimeoutSeconds
            Reason = $result.Reason
        } | ConvertTo-Json -Compress | Set-Content -LiteralPath (Join-Path $Results $EvidenceName) -Encoding UTF8
    }
    if ($result.TimedOut) {
        if ($result.Reason -eq 'global_deadline_exceeded') { Stop-FailClosed 'global_deadline_exceeded' }
        Stop-FailClosed $TimeoutReason
    }
    return $result.ExitCode
}

function Confirm-RunDeadline {
    try {
        Assert-WithinGlobalDeadline $Deadline
    } catch {
        Stop-FailClosed 'global_deadline_exceeded'
    }
}

if (-not (Test-Path -LiteralPath $Inbound -PathType Container)) { throw 'missing_inbound_mapping' }
if (-not (Test-Path -LiteralPath $Results -PathType Container)) { throw 'missing_results_mapping' }
if ((Get-ChildItem -LiteralPath $Results -Force | Measure-Object).Count -ne 0) { throw 'results_not_empty' }

$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent().Name
if ($identity -notmatch '(?i)\\WDAGUtilityAccount$') { Stop-FailClosed 'not_windows_sandbox' }

$defaultRoutes = @(Get-NetRoute -ErrorAction Stop | Where-Object {
    $_.DestinationPrefix -in @('0.0.0.0/0', '::/0')
})
$nonLoopbackAddresses = @(Get-NetIPAddress -ErrorAction Stop | Where-Object {
    $_.IPAddress -notin @('127.0.0.1', '::1') -and
    $_.AddressState -ne 'Duplicate'
})
if ($defaultRoutes.Count -ne 0 -or $nonLoopbackAddresses.Count -ne 0) {
    Stop-FailClosed 'network_isolation_unverified'
}

$inboundItem = Get-Item -LiteralPath $Inbound -Force
if (($inboundItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
    Stop-FailClosed 'artifact_root_unsafe'
}
$descendants = @(Get-ChildItem -LiteralPath $Inbound -Force -Recurse)
foreach ($item in $descendants) {
    if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        Stop-FailClosed 'artifact_reparse_point'
    }
}
$actualDirectories = @($descendants | Where-Object { $_.PSIsContainer } | ForEach-Object {
    $_.FullName.Substring($Inbound.Length + 1).Replace('\', '/')
} | Sort-Object)
if ($actualDirectories.Count -ne 1 -or $actualDirectories[0] -ne 'wheelhouse') {
    Stop-FailClosed 'unexpected_artifact_directory'
}

$manifestEntries = @{}
foreach ($line in Get-Content -LiteralPath $Manifest -Encoding UTF8) {
    if ($line -notmatch '^([0-9a-f]{64})  ([A-Za-z0-9][A-Za-z0-9._/\-]*)$') {
        Stop-FailClosed 'malformed_artifact_manifest'
    }
    $relative = $Matches[2].Replace('\', '/')
    if ([System.IO.Path]::IsPathRooted($relative) -or $relative.Split('/') -contains '..') {
        Stop-FailClosed 'unsafe_manifest_path'
    }
    if ($manifestEntries.ContainsKey($relative)) { Stop-FailClosed 'duplicate_manifest_path' }
    $manifestEntries[$relative] = $Matches[1]
}

$manifestFullPath = [System.IO.Path]::GetFullPath($Manifest)
$actualFiles = @($descendants | Where-Object {
    -not $_.PSIsContainer -and
    -not [string]::Equals(
        [System.IO.Path]::GetFullPath($_.FullName),
        $manifestFullPath,
        [System.StringComparison]::OrdinalIgnoreCase
    )
})
if ($actualFiles.Count -ne $manifestEntries.Count) { Stop-FailClosed 'artifact_file_set_mismatch' }
foreach ($file in $actualFiles) {
    $relative = $file.FullName.Substring($Inbound.Length + 1).Replace('\', '/')
    if (-not $manifestEntries.ContainsKey($relative)) { Stop-FailClosed 'unexpected_artifact_file' }
    $actualHash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    if ($actualHash -ne $manifestEntries[$relative]) { Stop-FailClosed 'artifact_hash_mismatch' }
}

Import-Module (Join-Path $Inbound 'SandboxGuards.psm1') -Force
Confirm-RunDeadline

$sourceCommit = (Get-Content -LiteralPath (Join-Path $Inbound 'SOURCE_COMMIT.txt') -Raw).Trim()
if ($sourceCommit -ne $ExpectedSourceCommit) { Stop-FailClosed 'source_commit_mismatch' }
if ((Get-FileHash -LiteralPath $RuntimeArchive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ExpectedRuntimeHash) {
    Stop-FailClosed 'python_runtime_hash_mismatch'
}
if ((Get-FileHash -LiteralPath $RuntimeManifest -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ExpectedRuntimeManifestHash) {
    Stop-FailClosed 'python_runtime_manifest_hash_mismatch'
}
if ((Get-FileHash -LiteralPath $PythonSmokeScript -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ExpectedPythonSmokeHash) {
    Stop-FailClosed 'python_runtime_smoke_hash_mismatch'
}

$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTHONNOUSERSITE = '1'
foreach ($name in @(
    'PYTHONHOME', 'PYTHONPATH', 'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY',
    'KAOSEGHIS_PACS_API_TOKEN', 'KAOSPACS_INTEGRATION_TOKEN',
    'KAOSPACS_PATIENT_CONTEXT_API_HOST', 'KAOSPACS_PATIENT_CONTEXT_API_PORT',
    'KAOSEGHIS_DB_DSN', 'DATABASE_URL', 'PGHOST', 'PGPORT', 'PGDATABASE',
    'PGUSER', 'PGPASSWORD'
)) {
    Remove-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue
}

New-Item -ItemType Directory -Path $RunRoot -ErrorAction Stop | Out-Null
$provisionArgs = @(
    '-NoLogo', '-NoProfile', '-NonInteractive', '-ExecutionPolicy', 'Bypass',
    '-File', $RuntimeProvisioner, '-ArchivePath', $RuntimeArchive,
    '-ManifestPath', $RuntimeManifest, '-DestinationPath', $PythonRoot
)
if ((Invoke-RunProcess 'powershell.exe' $provisionArgs $StepBudgets.PythonProvision 'python-provision.txt' 'python-provision-error.txt' 'python_runtime_provision_timeout' 'python-provision-process.json') -ne 0) {
    Stop-FailClosed 'python_provision_failed'
}
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) { Stop-FailClosed 'python_missing' }
if ((Invoke-RunProcess $PythonExe @('-I', '--version') $StepBudgets.PythonVersion 'python-version.txt' 'python-version-error.txt') -ne 0) {
    Stop-FailClosed 'python_version_command_failed'
}
$pythonVersion = (Get-Content -LiteralPath (Join-Path $Results 'python-version.txt') -Raw).Trim()
if ($pythonVersion -ne 'Python 3.11.9') { Stop-FailClosed 'python_version_mismatch' }
if ((Invoke-RunProcess $PythonExe @('-I', $PythonSmokeScript, 'base') $StepBudgets.PythonBaseSmoke 'python-smoke-base.txt' 'python-smoke-base-error.txt') -ne 0) {
    Stop-FailClosed 'python_runtime_smoke_failed'
}

if ((Invoke-RunProcess $PythonExe @('-I', '-m', 'venv', $VenvRoot) $StepBudgets.VenvCreate 'venv-create.txt' 'venv-create-error.txt') -ne 0) {
    Stop-FailClosed 'venv_create_failed'
}
if ((Invoke-RunProcess $VenvPython @('-I', $PythonSmokeScript, 'venv') $StepBudgets.PythonVenvSmoke 'python-smoke-venv.txt' 'python-smoke-venv-error.txt') -ne 0) {
    Stop-FailClosed 'python_venv_smoke_failed'
}
if ((Invoke-RunProcess $VenvPython @(
    '-I', '-m', 'pip', '--disable-pip-version-check', 'install', '--no-index', '--require-hashes',
    '--find-links', $Wheelhouse, '-r', $LockFile
) $StepBudgets.DependencyInstall 'dependency-install.txt' 'dependency-install-error.txt') -ne 0) {
    Stop-FailClosed 'dependency_install_failed'
}
if ((Invoke-RunProcess $VenvPython @('-I', '-m', 'pip', 'check') $StepBudgets.PipCheck 'pip-check.txt' 'pip-check-error.txt') -ne 0) {
    Stop-FailClosed 'pip_check_failed'
}
if ((Invoke-RunProcess $VenvPython @('-I', '-m', 'pip', 'freeze', '--all') $StepBudgets.DependencyInventory 'dependency-inventory.txt' 'dependency-inventory-error.txt') -ne 0) {
    Stop-FailClosed 'dependency_inventory_failed'
}

New-Item -ItemType Directory -Path (Join-Path $RunRoot 'src') -ErrorAction Stop | Out-Null
Expand-Archive -LiteralPath $SourceArchive -DestinationPath (Join-Path $RunRoot 'src') -ErrorAction Stop
Confirm-RunDeadline
if (-not (Test-Path -LiteralPath (Join-Path $ExpectedSourceRoot 'tests\conftest.py') -PathType Leaf)) {
    Stop-FailClosed 'source_archive_invalid'
}

foreach ($directory in @('data', 'localappdata', 'appdata', 'temp', 'profile', 'pytest-focused-temp', 'pytest-focused-cache', 'pytest-full-temp', 'pytest-full-cache')) {
    New-Item -ItemType Directory -Path (Join-Path $RunRoot $directory) -ErrorAction Stop | Out-Null
}
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:QT_QPA_PLATFORM = 'offscreen'
$env:KAOSEGHIS_DATA_DIR = Join-Path $RunRoot 'data'
$env:LOCALAPPDATA = Join-Path $RunRoot 'localappdata'
$env:APPDATA = Join-Path $RunRoot 'appdata'
$env:TEMP = Join-Path $RunRoot 'temp'
$env:TMP = Join-Path $RunRoot 'temp'
$env:USERPROFILE = Join-Path $RunRoot 'profile'
foreach ($name in @(
    'HTTP_PROXY', 'HTTPS_PROXY', 'ALL_PROXY', 'NO_PROXY',
    'KAOSEGHIS_PACS_API_TOKEN', 'KAOSPACS_INTEGRATION_TOKEN',
    'KAOSPACS_PATIENT_CONTEXT_API_HOST', 'KAOSPACS_PATIENT_CONTEXT_API_PORT',
    'KAOSEGHIS_DB_DSN', 'DATABASE_URL', 'PGHOST', 'PGPORT', 'PGDATABASE',
    'PGUSER', 'PGPASSWORD'
)) {
    Remove-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue
}

Set-Location -LiteralPath $ExpectedSourceRoot
$focusedArgs = @(
    '-I', '-m', 'pytest', '-ra',
    "--basetemp=$(Join-Path $RunRoot 'pytest-focused-temp')",
    '-o', "cache_dir=$(Join-Path $RunRoot 'pytest-focused-cache')",
    "--junitxml=$(Join-Path $Results 'focused-junit.xml')",
    'tests/test_vaccine_emr_charting.py',
    'tests/test_vaccine_post_print.py'
)
$focusedExit = Invoke-RunProcess $VenvPython $focusedArgs $StepBudgets.FocusedPytest 'pytest-focused.txt' 'pytest-focused-error.txt'
Confirm-RunDeadline
$fullArgs = @(
    '-I', '-m', 'pytest', '-ra',
    "--basetemp=$(Join-Path $RunRoot 'pytest-full-temp')",
    '-o', "cache_dir=$(Join-Path $RunRoot 'pytest-full-cache')",
    "--junitxml=$(Join-Path $Results 'full-junit.xml')"
)
$fullExit = Invoke-RunProcess $VenvPython $fullArgs $StepBudgets.FullPytest 'pytest-full.txt' 'pytest-error.txt'
Confirm-RunDeadline
$resultBytes = (Get-ChildItem -LiteralPath $Results -File | Measure-Object -Property Length -Sum).Sum
if ($resultBytes -gt 200MB) { Stop-FailClosed 'result_size_limit_exceeded' }

[PSCustomObject]@{
    Status = if ($focusedExit -eq 0 -and $fullExit -eq 0) { 'passed' } else { 'failed' }
    SourceCommit = $ExpectedSourceCommit
    SourceTree = 'a6d54f7d1a84c8173f793d5f5444e4dda1f42e62'
    IndependentReviewSha256 = 'c26326f6e95bf028939e5fdf9be6f9693b35c55b974be4c283b87ea487d7a4c3'
    PythonSourceInstallerSha256 = $ExpectedInstallerHash
    PythonRuntimeSha256 = $ExpectedRuntimeHash
    PythonRuntimeManifestSha256 = $ExpectedRuntimeManifestHash
    PythonRuntimeManifestVerified = $true
    NetworkIsolationVerified = $true
    FocusedPytestExitCode = $focusedExit
    FullPytestExitCode = $fullExit
} | ConvertTo-Json -Compress | Set-Content -LiteralPath (Join-Path $Results 'status.json') -Encoding UTF8
if ($focusedExit -ne 0) { exit $focusedExit }
exit $fullExit
