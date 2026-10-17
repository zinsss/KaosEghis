$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$ExpectedComputer = 'YHSHFM'
$ExpectedAccount = 'YHSHFM\leejs'
$RunId = 'eghis-1dc9250dae01-win311-v5-run-04'
$Root = 'E:\Kaos\.staging\KaosEghis-1dc9250dae01d236e3cfca45b8142e98519478bb-v5-run-04'
$Results = Join-Path (Join-Path $Root 'Results') $RunId
$ReturnArchive = Join-Path $Root "$RunId-results.zip"
$AllowedNames = @(
    'status.json', 'failure.txt', 'focused-junit.xml', 'full-junit.xml',
    'pytest-focused.txt', 'pytest-focused-error.txt', 'pytest-full.txt', 'pytest-error.txt',
    'python-version.txt', 'python-version-error.txt',
    'python-provision.txt', 'python-provision-error.txt', 'python-provision-process.json',
    'python-smoke-base.txt', 'python-smoke-base-error.txt',
    'python-smoke-venv.txt', 'python-smoke-venv-error.txt',
    'venv-create.txt', 'venv-create-error.txt', 'dependency-install.txt',
    'dependency-install-error.txt', 'pip-check.txt', 'pip-check-error.txt',
    'dependency-inventory.txt', 'dependency-inventory-error.txt'
)

if (-not [string]::Equals($env:COMPUTERNAME, $ExpectedComputer, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'unexpected_computer' }
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
if (-not [string]::Equals($identity.Name, $ExpectedAccount, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'unexpected_account' }
$principal = New-Object System.Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'administrator_required' }

$item = Get-Item -LiteralPath $Results -Force
if (-not $item.PSIsContainer -or ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) { throw 'unsafe_results_path' }
$acl = Get-Acl -LiteralPath $Results
if (-not $acl.AreAccessRulesProtected) { throw 'results_acl_inheritance_enabled' }
$expectedSids = @($identity.User.Value, 'S-1-5-18') | Sort-Object
$rules = @($acl.Access | Where-Object { -not $_.IsInherited })
$actualSids = @($rules | ForEach-Object {
    if ($_.AccessControlType -ne [System.Security.AccessControl.AccessControlType]::Allow -or
        $_.FileSystemRights -ne [System.Security.AccessControl.FileSystemRights]::FullControl) { throw 'unexpected_results_acl_rule' }
    $_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value
} | Sort-Object)
if ($rules.Count -ne 2 -or ($actualSids -join ',') -ne ($expectedSids -join ',')) { throw 'unexpected_results_acl' }

$files = @(Get-ChildItem -LiteralPath $Results -File)
if ($files.Count -eq 0) { throw 'results_empty' }
if (@(Get-ChildItem -LiteralPath $Results -Directory -Force).Count -ne 0) { throw 'unexpected_results_directory' }
foreach ($file in $files) {
    if (($file.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'result_reparse_point' }
    if ($file.Name -notin $AllowedNames) { throw 'unexpected_result_file' }
}
$totalBytes = ($files | Measure-Object -Property Length -Sum).Sum
if ($totalBytes -gt 200MB) { throw 'result_size_limit_exceeded' }
$statusPath = Join-Path $Results 'status.json'
if (-not (Test-Path -LiteralPath $statusPath -PathType Leaf)) { throw 'status_missing' }
$status = Get-Content -LiteralPath $statusPath -Raw | ConvertFrom-Json
if ($status.Status -notin @('passed', 'failed', 'blocked')) { throw 'unexpected_status' }
if (Test-Path -LiteralPath $ReturnArchive) { throw 'return_archive_already_exists' }

# An approving reviewer must inspect the fixed result file set for synthetic-only,
# non-sensitive content before running this packaging step.
Compress-Archive -LiteralPath ($files.FullName) -DestinationPath $ReturnArchive -CompressionLevel Optimal
$returnHash = (Get-FileHash -LiteralPath $ReturnArchive -Algorithm SHA256).Hash.ToLowerInvariant()
[PSCustomObject]@{
    Computer = $ExpectedComputer
    RunId = $RunId
    Files = @($files.Name | Sort-Object)
    TotalBytes = $totalBytes
    Status = $status.Status
    FocusedJunitPresent = (Test-Path -LiteralPath (Join-Path $Results 'focused-junit.xml') -PathType Leaf)
    FullJunitPresent = (Test-Path -LiteralPath (Join-Path $Results 'full-junit.xml') -PathType Leaf)
    ReturnArchive = $ReturnArchive
    ReturnArchiveSha256 = $returnHash
    RetainUntilUtc = [DateTime]::UtcNow.AddDays(7).ToString('o')
} | ConvertTo-Json -Compress
