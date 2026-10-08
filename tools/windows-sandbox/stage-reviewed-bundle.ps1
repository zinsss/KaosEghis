$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$ExpectedComputer = 'YHSHFM'
$ExpectedAccount = 'YHSHFM\leejs'
$BundleId = 'eghis-d1777c1834e1-win311-v2'
$RunId = 'eghis-d1777c1834e1-win311-v2-run-01'
$Root = 'C:\KaosClinic-Test\Eghis'
$Package = Join-Path $Root "$BundleId.zip"
$ExpectedPackageHash = 'f7e3ca423d5252fa2d261831592d9df57992b0f5cb3fc6d24d0ec912710c9fd7'
$InboundParent = Join-Path $Root 'Inbound'
$ResultsParent = Join-Path $Root 'Results'
$Inbound = Join-Path $InboundParent $BundleId
$Results = Join-Path $ResultsParent $RunId

function Assert-ExpectedContext {
    if (-not [string]::Equals($env:COMPUTERNAME, $ExpectedComputer, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'unexpected_computer' }
    $identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
    if (-not [string]::Equals($identity.Name, $ExpectedAccount, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'unexpected_account' }
    $principal = New-Object System.Security.Principal.WindowsPrincipal($identity)
    if (-not $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'administrator_required' }
    return $identity
}

function Assert-PathSetAbsent([string[]]$Paths) {
    foreach ($path in $Paths) {
        if (Test-Path -LiteralPath $path) { throw 'staging_path_already_exists' }
    }
}

function Assert-SafeDirectory([string]$Path, [string[]]$ExpectedSids) {
    $item = Get-Item -LiteralPath $Path -Force
    if (-not $item.PSIsContainer -or ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) { throw 'unsafe_directory' }
    $acl = Get-Acl -LiteralPath $Path
    if (-not $acl.AreAccessRulesProtected) { throw 'acl_inheritance_enabled' }
    $rules = @($acl.Access | Where-Object { -not $_.IsInherited })
    if ($rules.Count -ne 2) { throw 'unexpected_acl_rule_count' }
    $actualSids = @($rules | ForEach-Object {
        if ($_.AccessControlType -ne [System.Security.AccessControl.AccessControlType]::Allow -or
            $_.FileSystemRights -ne [System.Security.AccessControl.FileSystemRights]::FullControl) {
            throw 'unexpected_acl_rule'
        }
        $_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value
    } | Sort-Object -Unique)
    if (($actualSids -join ',') -ne (($ExpectedSids | Sort-Object -Unique) -join ',')) { throw 'unexpected_acl_principals' }
}

function Set-ExactDirectoryAcl([string]$Path, [System.Security.Principal.SecurityIdentifier]$UserSid) {
    $systemSid = [System.Security.Principal.SecurityIdentifier]::new('S-1-5-18')
    $acl = [System.Security.AccessControl.DirectorySecurity]::new()
    $acl.SetAccessRuleProtection($true, $false)
    foreach ($sid in @($UserSid, $systemSid)) {
        $rule = [System.Security.AccessControl.FileSystemAccessRule]::new(
            $sid,
            [System.Security.AccessControl.FileSystemRights]::FullControl,
            [System.Security.AccessControl.InheritanceFlags]'ContainerInherit, ObjectInherit',
            [System.Security.AccessControl.PropagationFlags]::None,
            [System.Security.AccessControl.AccessControlType]::Allow
        )
        [void]$acl.AddAccessRule($rule)
    }
    Set-Acl -LiteralPath $Path -AclObject $acl
}

$identity = Assert-ExpectedContext
$userSid = $identity.User
$expectedSids = @($userSid.Value, 'S-1-5-18')
Assert-SafeDirectory $Root $expectedSids

$featureState = [string](Get-WindowsOptionalFeature -Online -FeatureName 'Containers-DisposableClientVM').State
if ($featureState -ne 'Enabled') { throw 'sandbox_feature_not_enabled' }
$freeBytes = (Get-PSDrive -Name C).Free
if ($freeBytes -lt 20GB) { throw 'insufficient_free_disk' }
$availableBytes = (Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory * 1KB
if ($availableBytes -lt 12GB) { throw 'insufficient_available_memory' }

if (-not (Test-Path -LiteralPath $Package -PathType Leaf)) { throw 'package_missing' }
$packageItem = Get-Item -LiteralPath $Package -Force
if (($packageItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'package_reparse_point' }
if ((Get-FileHash -LiteralPath $Package -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ExpectedPackageHash) { throw 'package_hash_mismatch' }
$newPaths = @($InboundParent, $ResultsParent, $Inbound, $Results)
Assert-PathSetAbsent $newPaths

foreach ($path in $newPaths) {
    New-Item -ItemType Directory -Path $path -ErrorAction Stop | Out-Null
    Set-ExactDirectoryAcl $path $userSid
    Assert-SafeDirectory $path $expectedSids
}

Expand-Archive -LiteralPath $Package -DestinationPath $Inbound -ErrorAction Stop
$manifest = Join-Path $Inbound 'artifact-manifest.sha256'
$inboundItem = Get-Item -LiteralPath $Inbound -Force
if (($inboundItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'artifact_root_unsafe' }
$descendants = @(Get-ChildItem -LiteralPath $Inbound -Force -Recurse)
foreach ($item in $descendants) {
    if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'artifact_reparse_point' }
}
$directories = @($descendants | Where-Object { $_.PSIsContainer } | ForEach-Object {
    $_.FullName.Substring($Inbound.Length + 1).Replace('\', '/')
} | Sort-Object)
if ($directories.Count -ne 1 -or $directories[0] -ne 'wheelhouse') { throw 'unexpected_artifact_directory' }
$entries = @{}
foreach ($line in Get-Content -LiteralPath $manifest -Encoding UTF8) {
    if ($line -notmatch '^([0-9a-f]{64})  ([A-Za-z0-9][A-Za-z0-9._/\-]*)$') { throw 'malformed_artifact_manifest' }
    $relative = $Matches[2].Replace('\', '/')
    if ([System.IO.Path]::IsPathRooted($relative) -or $relative.Split('/') -contains '..' -or $entries.ContainsKey($relative)) { throw 'unsafe_manifest_path' }
    $entries[$relative] = $Matches[1]
}
$manifestFullPath = [System.IO.Path]::GetFullPath($manifest)
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
    $relative = $file.FullName.Substring($Inbound.Length + 1).Replace('\', '/')
    if (-not $entries.ContainsKey($relative)) { throw 'unexpected_artifact_file' }
    if ((Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entries[$relative]) { throw 'artifact_hash_mismatch' }
}

$installer = Join-Path $Inbound 'python-3.11.9-amd64.exe'
$signature = Get-AuthenticodeSignature -FilePath $installer
if ($signature.Status -ne [System.Management.Automation.SignatureStatus]::Valid) { throw 'python_signature_invalid' }
if ($signature.SignerCertificate.Subject -notmatch '(?i)(^|,\s*)O=Python Software Foundation(,|$)') { throw 'python_signer_unexpected' }

[PSCustomObject]@{
    Computer = $ExpectedComputer
    BundleId = $BundleId
    RunId = $RunId
    PackageHashVerified = $true
    InternalManifestEntries = $entries.Count
    PythonSignatureValid = $true
    SandboxFeatureState = $featureState
    FreeDiskAtLeast20GiB = $true
    AvailableMemoryAtLeast12GiB = $true
    ResultsEmpty = ((Get-ChildItem -LiteralPath $Results -Force | Measure-Object).Count -eq 0)
    InteractiveLaunchFile = (Join-Path $Inbound 'KaosEghisSynthetic.wsb')
    ReadyForInteractiveLaunch = $true
} | ConvertTo-Json -Compress
