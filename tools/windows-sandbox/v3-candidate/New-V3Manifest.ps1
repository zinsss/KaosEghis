param(
    [Parameter(Mandatory = $true)][string]$Root
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$rootItem = Get-Item -LiteralPath $Root -Force
if (-not $rootItem.PSIsContainer -or
    ($rootItem.Attributes -band [System.IO.FileAttributes]::ReparsePoint)) {
    throw 'artifact_root_unsafe'
}

$descendants = @(Get-ChildItem -LiteralPath $rootItem.FullName -Force -Recurse)
foreach ($item in $descendants) {
    if (($item.Attributes -band [System.IO.FileAttributes]::ReparsePoint) -ne 0) {
        throw 'artifact_reparse_point'
    }
}

$directories = @($descendants | Where-Object { $_.PSIsContainer } | ForEach-Object {
    $_.FullName.Substring($rootItem.FullName.Length + 1).Replace('\', '/')
} | Sort-Object)
if ($directories.Count -ne 1 -or $directories[0] -ne 'wheelhouse') {
    throw 'unexpected_artifact_directory'
}

$manifestPath = Join-Path $rootItem.FullName 'artifact-manifest.sha256'
$manifestFullPath = [System.IO.Path]::GetFullPath($manifestPath)
$files = @($descendants | Where-Object {
    -not $_.PSIsContainer -and
    -not [string]::Equals(
        [System.IO.Path]::GetFullPath($_.FullName),
        $manifestFullPath,
        [System.StringComparison]::OrdinalIgnoreCase
    )
} | Sort-Object FullName)
if ($files.Count -eq 0) { throw 'empty_artifact_set' }

$lines = foreach ($file in $files) {
    $relative = $file.FullName.Substring($rootItem.FullName.Length + 1).Replace('\', '/')
    if ($relative -notmatch '^[A-Za-z0-9][A-Za-z0-9._/\-]*$' -or
        [System.IO.Path]::IsPathRooted($relative) -or
        $relative.Split('/') -contains '..') {
        throw 'unsafe_artifact_path'
    }
    $hash = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash.ToLowerInvariant()
    "$hash  $relative"
}

$temporaryPath = "$manifestPath.pending"
if (Test-Path -LiteralPath $temporaryPath) { throw 'manifest_pending_path_exists' }
try {
    $manifestText = ($lines -join "`n") + "`n"
    [System.IO.File]::WriteAllText(
        $temporaryPath,
        $manifestText,
        [System.Text.UTF8Encoding]::new($false)
    )
    Move-Item -LiteralPath $temporaryPath -Destination $manifestPath -Force
} finally {
    if (Test-Path -LiteralPath $temporaryPath) {
        Remove-Item -LiteralPath $temporaryPath -Force
    }
}

[PSCustomObject]@{
    ManifestPath = $manifestPath
    Entries = $lines.Count
    ManifestSha256 = (Get-FileHash -LiteralPath $manifestPath -Algorithm SHA256).Hash.ToLowerInvariant()
} | ConvertTo-Json -Compress
