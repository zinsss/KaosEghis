$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$ExpectedSourceCommit = 'd1777c1834e129e93441bdb208c780e322401a48'
$ExpectedInstallerHash = '5ee42c4eee1e6b4464bb23722f90b45303f79442df63083f05322f1785f5fdde'
$GlobalDeadlineSeconds = 5400
$StepBudgets = [ordered]@{
    PythonInstall = 480
    VenvCreate = 120
    DependencyInstall = 720
    PipCheck = 60
    DependencyInventory = 60
    Pytest = 3300
}
if (($StepBudgets.Values | Measure-Object -Sum).Sum -gt 4740) { throw 'invalid_step_budget_total' }
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
$SourceArchive = Join-Path $Inbound 'KaosEghis-d1777c1834e1-source.zip'
$Manifest = Join-Path $Inbound 'artifact-manifest.sha256'
$Installer = Join-Path $Inbound 'python-3.11.9-amd64.exe'
$ExpectedSourceRoot = Join-Path $RunRoot 'src\KaosEghis-d1777c1834e1'

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
    [string]$StderrName
) {
    $stdoutPath = Join-Path $Results $StdoutName
    $stderrPath = Join-Path $Results $StderrName
    $result = Invoke-DeadlineProcess $FilePath $ArgumentList $TimeoutSeconds $Deadline $stdoutPath $stderrPath
    if ($result.TimedOut) { Stop-FailClosed $result.Reason }
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
if ((Get-FileHash -LiteralPath $Installer -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ExpectedInstallerHash) {
    Stop-FailClosed 'python_installer_hash_mismatch'
}
$signature = Get-AuthenticodeSignature -FilePath $Installer
if ($signature.Status -ne [System.Management.Automation.SignatureStatus]::Valid) {
    Stop-FailClosed 'python_signature_invalid'
}
if ($signature.SignerCertificate.Subject -notmatch '(?i)(^|,\s*)O=Python Software Foundation(,|$)') {
    Stop-FailClosed 'python_signer_unexpected'
}

New-Item -ItemType Directory -Path $RunRoot -ErrorAction Stop | Out-Null
$installArgs = @(
    '/quiet', 'InstallAllUsers=0', "TargetDir=$PythonRoot", 'Include_launcher=0',
    'Include_test=0', 'Include_doc=0', 'Include_tcltk=1', 'Include_pip=1',
    'PrependPath=0', 'AssociateFiles=0', 'Shortcuts=0'
)
if ((Invoke-RunProcess $Installer $installArgs $StepBudgets.PythonInstall 'python-install.txt' 'python-install-error.txt') -ne 0) {
    Stop-FailClosed 'python_install_failed'
}
if (-not (Test-Path -LiteralPath $PythonExe -PathType Leaf)) { Stop-FailClosed 'python_missing' }
$pythonVersion = (& $PythonExe --version 2>&1).ToString().Trim()
if ($pythonVersion -ne 'Python 3.11.9') { Stop-FailClosed 'python_version_mismatch' }
$pythonVersion | Set-Content -LiteralPath (Join-Path $Results 'python-version.txt') -Encoding ASCII

if ((Invoke-RunProcess $PythonExe @('-m', 'venv', $VenvRoot) $StepBudgets.VenvCreate 'venv-create.txt' 'venv-create-error.txt') -ne 0) {
    Stop-FailClosed 'venv_create_failed'
}
if ((Invoke-RunProcess $VenvPython @(
    '-m', 'pip', '--disable-pip-version-check', 'install', '--no-index', '--require-hashes',
    '--find-links', $Wheelhouse, '-r', $LockFile
) $StepBudgets.DependencyInstall 'dependency-install.txt' 'dependency-install-error.txt') -ne 0) {
    Stop-FailClosed 'dependency_install_failed'
}
if ((Invoke-RunProcess $VenvPython @('-m', 'pip', 'check') $StepBudgets.PipCheck 'pip-check.txt' 'pip-check-error.txt') -ne 0) {
    Stop-FailClosed 'pip_check_failed'
}
if ((Invoke-RunProcess $VenvPython @('-m', 'pip', 'freeze', '--all') $StepBudgets.DependencyInventory 'dependency-inventory.txt' 'dependency-inventory-error.txt') -ne 0) {
    Stop-FailClosed 'dependency_inventory_failed'
}

New-Item -ItemType Directory -Path (Join-Path $RunRoot 'src') -ErrorAction Stop | Out-Null
Expand-Archive -LiteralPath $SourceArchive -DestinationPath (Join-Path $RunRoot 'src') -ErrorAction Stop
Confirm-RunDeadline
if (-not (Test-Path -LiteralPath (Join-Path $ExpectedSourceRoot 'tests\conftest.py') -PathType Leaf)) {
    Stop-FailClosed 'source_archive_invalid'
}

foreach ($directory in @('data', 'localappdata', 'appdata', 'temp', 'profile', 'pytest-temp', 'pytest-cache')) {
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
    'KAOSPACS_PATIENT_CONTEXT_API_HOST', 'KAOSPACS_PATIENT_CONTEXT_API_PORT'
)) {
    Remove-Item -LiteralPath "Env:$name" -ErrorAction SilentlyContinue
}

Set-Location -LiteralPath $ExpectedSourceRoot
$testArgs = @(
    '-m', 'pytest', '-ra',
    "--basetemp=$(Join-Path $RunRoot 'pytest-temp')",
    '-o', "cache_dir=$(Join-Path $RunRoot 'pytest-cache')",
    "--junitxml=$(Join-Path $Results 'junit.xml')"
)
$testExit = Invoke-RunProcess $VenvPython $testArgs $StepBudgets.Pytest 'pytest-full.txt' 'pytest-error.txt'
Confirm-RunDeadline
$resultBytes = (Get-ChildItem -LiteralPath $Results -File | Measure-Object -Property Length -Sum).Sum
if ($resultBytes -gt 200MB) { Stop-FailClosed 'result_size_limit_exceeded' }

[PSCustomObject]@{
    Status = if ($testExit -eq 0) { 'passed' } else { 'failed' }
    SourceCommit = $ExpectedSourceCommit
    PythonInstallerSha256 = $ExpectedInstallerHash
    PythonSignatureValid = $true
    NetworkIsolationVerified = $true
    PytestExitCode = $testExit
} | ConvertTo-Json -Compress | Set-Content -LiteralPath (Join-Path $Results 'status.json') -Encoding UTF8
exit $testExit
