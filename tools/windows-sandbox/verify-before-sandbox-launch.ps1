$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$ExpectedComputer = 'YHSHFM'
$ExpectedAccount = 'YHSHFM\leejs'
$BundleId = 'eghis-d1777c1834e1-win311-v2'
$RunId = 'eghis-d1777c1834e1-win311-v2-run-01'
$Root = 'C:\KaosClinic-Test\Eghis'
$Package = Join-Path $Root "$BundleId.zip"
$ExpectedPackageHash = 'f7e3ca423d5252fa2d261831592d9df57992b0f5cb3fc6d24d0ec912710c9fd7'
$Inbound = Join-Path (Join-Path $Root 'Inbound') $BundleId
$Results = Join-Path (Join-Path $Root 'Results') $RunId

function Assert-SafeDirectory([string]$Path, [string[]]$ExpectedSids) {
    $item = Get-Item -LiteralPath $Path -Force
    if (-not $item.PSIsContainer -or ($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) { throw 'unsafe_directory' }
    $acl = Get-Acl -LiteralPath $Path
    if (-not $acl.AreAccessRulesProtected) { throw 'acl_inheritance_enabled' }
    $rules = @($acl.Access | Where-Object { -not $_.IsInherited })
    if ($rules.Count -ne 2) { throw 'unexpected_acl_rule_count' }
    $actualSids = @($rules | ForEach-Object {
        if ($_.AccessControlType -ne [System.Security.AccessControl.AccessControlType]::Allow -or
            $_.FileSystemRights -ne [System.Security.AccessControl.FileSystemRights]::FullControl) { throw 'unexpected_acl_rule' }
        $_.IdentityReference.Translate([System.Security.Principal.SecurityIdentifier]).Value
    } | Sort-Object -Unique)
    if (($actualSids -join ',') -ne (($ExpectedSids | Sort-Object -Unique) -join ',')) { throw 'unexpected_acl_principals' }
}

if (-not [string]::Equals($env:COMPUTERNAME, $ExpectedComputer, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'unexpected_computer' }
$identity = [System.Security.Principal.WindowsIdentity]::GetCurrent()
if (-not [string]::Equals($identity.Name, $ExpectedAccount, [System.StringComparison]::OrdinalIgnoreCase)) { throw 'unexpected_account' }
$principal = New-Object System.Security.Principal.WindowsPrincipal($identity)
if (-not $principal.IsInRole([System.Security.Principal.WindowsBuiltInRole]::Administrator)) { throw 'administrator_required' }
$expectedSids = @($identity.User.Value, 'S-1-5-18')

Assert-SafeDirectory $Root $expectedSids
Assert-SafeDirectory (Join-Path $Root 'Inbound') $expectedSids
Assert-SafeDirectory (Join-Path $Root 'Results') $expectedSids
Assert-SafeDirectory $Inbound $expectedSids
Assert-SafeDirectory $Results $expectedSids
if ((Get-ChildItem -LiteralPath $Results -Force | Measure-Object).Count -ne 0) { throw 'results_not_empty' }
if ([string](Get-WindowsOptionalFeature -Online -FeatureName 'Containers-DisposableClientVM').State -ne 'Enabled') { throw 'sandbox_feature_not_enabled' }
$packageItem = Get-Item -LiteralPath $Package -Force
if (($packageItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) { throw 'package_reparse_point' }
if ((Get-FileHash -LiteralPath $Package -Algorithm SHA256).Hash.ToLowerInvariant() -ne $ExpectedPackageHash) { throw 'package_hash_mismatch' }

$manifest = Join-Path $Inbound 'artifact-manifest.sha256'
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
    -not [string]::Equals([System.IO.Path]::GetFullPath($_.FullName), $manifestFullPath, [System.StringComparison]::OrdinalIgnoreCase)
})
if ($files.Count -ne $entries.Count) { throw 'artifact_file_set_mismatch' }
foreach ($file in $files) {
    $relative = $file.FullName.Substring($Inbound.Length + 1).Replace('\', '/')
    if (-not $entries.ContainsKey($relative)) { throw 'unexpected_artifact_file' }
    if ((Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant() -ne $entries[$relative]) { throw 'artifact_hash_mismatch' }
}

[PSCustomObject]@{
    Computer = $ExpectedComputer
    BundleId = $BundleId
    RunId = $RunId
    DescendantReparsePoints = 0
    AllowedDirectories = @('wheelhouse')
    ManifestFiles = $entries.Count
    ResultsEmpty = $true
    InteractiveLaunchFile = (Join-Path $Inbound 'KaosEghisSynthetic.wsb')
    ReadyForInteractiveLaunch = $true
} | ConvertTo-Json -Compress
