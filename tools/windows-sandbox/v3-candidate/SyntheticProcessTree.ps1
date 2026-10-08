param(
    [Parameter(Mandatory = $true)]
    [ValidateSet('normal', 'nonzero-before-marker', 'root', 'child', 'grandchild')]
    [string]$Role,
    [Parameter(Mandatory = $true)][string]$MarkerRoot
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    throw 'windows_only_probe'
}
$markerRootItem = Get-Item -LiteralPath $MarkerRoot -Force -ErrorAction Stop
if (-not $markerRootItem.PSIsContainer -or
    ($markerRootItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
    throw 'unsafe_marker_root'
}

function Write-RoleMarker {
    param([Parameter(Mandatory = $true)][string]$Name)
    $path = Join-Path $markerRootItem.FullName "$Name.ready"
    $bytes = [Text.UTF8Encoding]::new($false).GetBytes("synthetic-$Name`n")
    $stream = [IO.FileStream]::new(
        $path,
        [IO.FileMode]::CreateNew,
        [IO.FileAccess]::Write,
        [IO.FileShare]::None
    )
    try {
        $stream.Write($bytes, 0, $bytes.Length)
        $stream.Flush($true)
    } finally {
        $stream.Dispose()
    }
}

function Start-SyntheticDescendant {
    param([Parameter(Mandatory = $true)][string]$DescendantRole)
    if ($PSCommandPath.Contains('"') -or $markerRootItem.FullName.Contains('"')) {
        throw 'unsafe_probe_argument'
    }
    $start = [Diagnostics.ProcessStartInfo]::new()
    $start.FileName = (Get-Process -Id $PID).Path
    $start.Arguments = ('-NoProfile -NonInteractive -ExecutionPolicy Bypass ' +
        '-File "{0}" -Role {1} -MarkerRoot "{2}"' -f
        $PSCommandPath, $DescendantRole, $markerRootItem.FullName)
    $start.UseShellExecute = $false
    $start.CreateNoWindow = $true
    $process = [Diagnostics.Process]::Start($start)
    if ($null -eq $process) { throw 'synthetic_descendant_start_failed' }
    $process.Dispose()
}

if ($Role -eq 'nonzero-before-marker') { exit 23 }
Write-RoleMarker $Role
switch ($Role) {
    'normal' { exit 0 }
    'root' { Start-SyntheticDescendant 'child' }
    'child' { Start-SyntheticDescendant 'grandchild' }
}

while ($true) { Start-Sleep -Seconds 60 }
