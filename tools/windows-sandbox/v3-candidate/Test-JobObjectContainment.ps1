$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

$envelopeStatusAllowlist = @('complete', 'blocked')
$envelopeReasonAllowlist = @(
    'proof_complete', 'wrong_platform', 'probe_initialization_failed',
    'probe_internal_error', 'probe_cleanup_failed', 'unsafe_probe_worker',
    'unsafe_probe_argument', 'probe_root_exists', 'job_create_failed',
    'job_limit_failed', 'probe_process_create_failed', 'job_assignment_failed',
    'assignment_cleanup_terminate_failed', 'assignment_cleanup_wait_failed',
    'probe_resume_failed', 'resume_cleanup_terminate_failed',
    'resume_cleanup_wait_failed', 'resume_cleanup_job_not_empty',
    'probe_wait_failed', 'job_query_failed', 'deadline_cleanup_terminate_failed',
    'deadline_cleanup_wait_failed', 'deadline_cleanup_job_not_empty',
    'normal_cleanup_terminate_failed', 'normal_cleanup_wait_failed',
    'normal_cleanup_job_not_empty', 'fallback_cleanup_terminate_failed',
    'fallback_cleanup_wait_failed', 'fallback_cleanup_job_not_empty',
    'invalid_probe_timeout', 'normal_job_not_empty', 'process_exit_code_failed',
    'normal_exit_not_proven', 'probe_marker_invalid',
    'unexpected_probe_marker', 'deadline_tree_termination_not_proven',
    'probe_global_deadline_exceeded'
)

function New-ClosedProbeEnvelope {
    param(
        [Parameter(Mandatory = $true)][string]$Status,
        [Parameter(Mandatory = $true)][string]$Reason,
        [bool]$SuspendedBeforeAssignment = $false,
        [bool]$NormalExitVerified = $false,
        [bool]$NormalMarkerVerified = $false,
        [bool]$RootChildGrandchildStarted = $false,
        [bool]$DeadlineTriggered = $false,
        [bool]$RootExitedAfterTermination = $false,
        [bool]$JobActiveProcessCountReachedZero = $false,
        [bool]$CleanupVerified = $false,
        [long]$ElapsedMilliseconds = 0
    )
    if ($envelopeStatusAllowlist -cnotcontains $Status -or
        $envelopeReasonAllowlist -cnotcontains $Reason) {
        throw 'invalid_probe_envelope'
    }
    return [PSCustomObject][ordered]@{
        Schema = 'kaoseghis.synthetic-job-containment-proof.v1'
        Status = $Status
        Reason = $Reason
        SyntheticOnly = $true
        SuspendedBeforeAssignment = $SuspendedBeforeAssignment
        NormalExitVerified = $NormalExitVerified
        NormalMarkerVerified = $NormalMarkerVerified
        NegativeWorkerPrepared = $true
        RootChildGrandchildStarted = $RootChildGrandchildStarted
        DeadlineTriggered = $DeadlineTriggered
        RootExitedAfterTermination = $RootExitedAfterTermination
        JobActiveProcessCountReachedZero = $JobActiveProcessCountReachedZero
        CleanupVerified = $CleanupVerified
        ProbeGlobalDeadlineMilliseconds = 15000
        ElapsedMilliseconds = $ElapsedMilliseconds
    }
}

if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    New-ClosedProbeEnvelope 'blocked' 'wrong_platform' -CleanupVerified $true |
        ConvertTo-Json -Compress
    exit 1
}

try {
    Add-Type -TypeDefinition @'
using System;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;

public sealed class KaosEghisJobRunResult
{
    public bool TimedOut;
    public bool RootExited;
    public bool JobBecameEmpty;
    public bool ExitCodeAvailable;
    public uint ExitCode;
    public long ElapsedMilliseconds;
}

public static class KaosEghisJobProbe
{
    const uint CREATE_SUSPENDED = 0x00000004;
    const uint CREATE_NO_WINDOW = 0x08000000;
    const uint JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE = 0x00002000;
    const uint WAIT_OBJECT_0 = 0x00000000;
    const uint WAIT_TIMEOUT = 0x00000102;
    const int JobObjectBasicAccountingInformation = 1;
    const int JobObjectExtendedLimitInformation = 9;

    [StructLayout(LayoutKind.Sequential, CharSet = CharSet.Unicode)]
    struct STARTUPINFO
    {
        public uint cb;
        public string lpReserved;
        public string lpDesktop;
        public string lpTitle;
        public uint dwX;
        public uint dwY;
        public uint dwXSize;
        public uint dwYSize;
        public uint dwXCountChars;
        public uint dwYCountChars;
        public uint dwFillAttribute;
        public uint dwFlags;
        public ushort wShowWindow;
        public ushort cbReserved2;
        public IntPtr lpReserved2;
        public IntPtr hStdInput;
        public IntPtr hStdOutput;
        public IntPtr hStdError;
    }

    [StructLayout(LayoutKind.Sequential)]
    struct PROCESS_INFORMATION
    {
        public IntPtr hProcess;
        public IntPtr hThread;
        public uint dwProcessId;
        public uint dwThreadId;
    }

    [StructLayout(LayoutKind.Sequential)]
    struct JOBOBJECT_BASIC_LIMIT_INFORMATION
    {
        public long PerProcessUserTimeLimit;
        public long PerJobUserTimeLimit;
        public uint LimitFlags;
        public UIntPtr MinimumWorkingSetSize;
        public UIntPtr MaximumWorkingSetSize;
        public uint ActiveProcessLimit;
        public UIntPtr Affinity;
        public uint PriorityClass;
        public uint SchedulingClass;
    }

    [StructLayout(LayoutKind.Sequential)]
    struct IO_COUNTERS
    {
        public ulong ReadOperationCount;
        public ulong WriteOperationCount;
        public ulong OtherOperationCount;
        public ulong ReadTransferCount;
        public ulong WriteTransferCount;
        public ulong OtherTransferCount;
    }

    [StructLayout(LayoutKind.Sequential)]
    struct JOBOBJECT_EXTENDED_LIMIT_INFORMATION
    {
        public JOBOBJECT_BASIC_LIMIT_INFORMATION BasicLimitInformation;
        public IO_COUNTERS IoInfo;
        public UIntPtr ProcessMemoryLimit;
        public UIntPtr JobMemoryLimit;
        public UIntPtr PeakProcessMemoryUsed;
        public UIntPtr PeakJobMemoryUsed;
    }

    [StructLayout(LayoutKind.Sequential)]
    struct JOBOBJECT_BASIC_ACCOUNTING_INFORMATION
    {
        public long TotalUserTime;
        public long TotalKernelTime;
        public long ThisPeriodTotalUserTime;
        public long ThisPeriodTotalKernelTime;
        public uint TotalPageFaultCount;
        public uint TotalProcesses;
        public uint ActiveProcesses;
        public uint TotalTerminatedProcesses;
    }

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern IntPtr CreateJobObject(IntPtr attributes, string name);

    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool SetInformationJobObject(
        IntPtr job, int informationClass, IntPtr information, uint informationLength);

    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool QueryInformationJobObject(
        IntPtr job, int informationClass, IntPtr information, uint informationLength,
        IntPtr returnLength);

    [DllImport("kernel32.dll", CharSet = CharSet.Unicode, SetLastError = true)]
    static extern bool CreateProcess(
        string applicationName, StringBuilder commandLine, IntPtr processAttributes,
        IntPtr threadAttributes, bool inheritHandles, uint creationFlags,
        IntPtr environment, string currentDirectory, ref STARTUPINFO startupInfo,
        out PROCESS_INFORMATION processInformation);

    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool AssignProcessToJobObject(IntPtr job, IntPtr process);

    [DllImport("kernel32.dll", SetLastError = true)]
    static extern uint ResumeThread(IntPtr thread);

    [DllImport("kernel32.dll", SetLastError = true)]
    static extern uint WaitForSingleObject(IntPtr handle, uint milliseconds);

    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool TerminateJobObject(IntPtr job, uint exitCode);

    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool TerminateProcess(IntPtr process, uint exitCode);

    [DllImport("kernel32.dll", SetLastError = true)]
    static extern bool GetExitCodeProcess(IntPtr process, out uint exitCode);

    [DllImport("kernel32.dll")]
    static extern bool CloseHandle(IntPtr handle);

    static void ThrowLastError(string fixedReason)
    {
        throw new InvalidOperationException(fixedReason);
    }

    static uint ActiveProcesses(IntPtr job)
    {
        int size = Marshal.SizeOf(typeof(JOBOBJECT_BASIC_ACCOUNTING_INFORMATION));
        IntPtr buffer = Marshal.AllocHGlobal(size);
        try
        {
            if (!QueryInformationJobObject(job, JobObjectBasicAccountingInformation,
                buffer, (uint)size, IntPtr.Zero)) ThrowLastError("job_query_failed");
            return ((JOBOBJECT_BASIC_ACCOUNTING_INFORMATION)
                Marshal.PtrToStructure(buffer,
                    typeof(JOBOBJECT_BASIC_ACCOUNTING_INFORMATION))).ActiveProcesses;
        }
        finally { Marshal.FreeHGlobal(buffer); }
    }

    static bool WaitForEmptyJob(IntPtr job, Stopwatch clock, long deadlineMilliseconds)
    {
        while (clock.ElapsedMilliseconds <= deadlineMilliseconds)
        {
            if (ActiveProcesses(job) == 0) return true;
            System.Threading.Thread.Sleep(10);
        }
        return false;
    }

    static void TerminateUnassignedProcess(
        IntPtr process, Stopwatch clock, long cleanupDeadlineMilliseconds)
    {
        if (WaitForSingleObject(process, 0) == WAIT_OBJECT_0) return;
        if (!TerminateProcess(process, 901))
            throw new InvalidOperationException("assignment_cleanup_terminate_failed");
        long remaining = cleanupDeadlineMilliseconds - clock.ElapsedMilliseconds;
        if (remaining < 1 || WaitForSingleObject(process, (uint)remaining) != WAIT_OBJECT_0)
            throw new InvalidOperationException("assignment_cleanup_wait_failed");
    }

    static void TerminateAssignedJob(
        IntPtr job, IntPtr process, uint exitCode, Stopwatch clock,
        long cleanupDeadlineMilliseconds, string terminateReason, string waitReason,
        string emptyReason)
    {
        if (!TerminateJobObject(job, exitCode))
            throw new InvalidOperationException(terminateReason);
        long remaining = cleanupDeadlineMilliseconds - clock.ElapsedMilliseconds;
        if (remaining < 1 || WaitForSingleObject(process, (uint)remaining) != WAIT_OBJECT_0)
            throw new InvalidOperationException(waitReason);
        if (!WaitForEmptyJob(job, clock, cleanupDeadlineMilliseconds))
            throw new InvalidOperationException(emptyReason);
    }

    public static KaosEghisJobRunResult Run(
        string executable, string arguments, int runTimeoutMilliseconds,
        int cleanupTimeoutMilliseconds)
    {
        if (runTimeoutMilliseconds < 1 || cleanupTimeoutMilliseconds < 1)
            throw new InvalidOperationException("invalid_probe_timeout");
        Stopwatch clock = Stopwatch.StartNew();
        IntPtr job = IntPtr.Zero;
        PROCESS_INFORMATION process = new PROCESS_INFORMATION();
        bool assigned = false;
        bool processCreated = false;
        bool cleanupProven = false;
        long cleanupDeadline = -1;
        try
        {
            job = CreateJobObject(IntPtr.Zero, null);
            if (job == IntPtr.Zero) ThrowLastError("job_create_failed");
            JOBOBJECT_EXTENDED_LIMIT_INFORMATION limits =
                new JOBOBJECT_EXTENDED_LIMIT_INFORMATION();
            limits.BasicLimitInformation.LimitFlags = JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;
            int limitSize = Marshal.SizeOf(limits);
            IntPtr limitBuffer = Marshal.AllocHGlobal(limitSize);
            try
            {
                Marshal.StructureToPtr(limits, limitBuffer, false);
                if (!SetInformationJobObject(job, JobObjectExtendedLimitInformation,
                    limitBuffer, (uint)limitSize)) ThrowLastError("job_limit_failed");
            }
            finally { Marshal.FreeHGlobal(limitBuffer); }

            STARTUPINFO startup = new STARTUPINFO();
            startup.cb = (uint)Marshal.SizeOf(startup);
            StringBuilder command = new StringBuilder("\"" + executable + "\" " + arguments);
            if (!CreateProcess(executable, command, IntPtr.Zero, IntPtr.Zero, false,
                CREATE_SUSPENDED | CREATE_NO_WINDOW, IntPtr.Zero, null, ref startup,
                out process)) ThrowLastError("probe_process_create_failed");
            processCreated = true;
            if (!AssignProcessToJobObject(job, process.hProcess))
            {
                cleanupDeadline = clock.ElapsedMilliseconds + cleanupTimeoutMilliseconds;
                TerminateUnassignedProcess(
                    process.hProcess, clock, cleanupDeadline);
                cleanupProven = true;
                throw new InvalidOperationException("job_assignment_failed");
            }
            assigned = true;
            if (ResumeThread(process.hThread) == UInt32.MaxValue)
            {
                cleanupDeadline = clock.ElapsedMilliseconds + cleanupTimeoutMilliseconds;
                TerminateAssignedJob(
                    job, process.hProcess, 902, clock, cleanupDeadline,
                    "resume_cleanup_terminate_failed", "resume_cleanup_wait_failed",
                    "resume_cleanup_job_not_empty");
                cleanupProven = true;
                throw new InvalidOperationException("probe_resume_failed");
            }
            uint wait = WaitForSingleObject(process.hProcess, (uint)runTimeoutMilliseconds);
            bool timedOut = wait == WAIT_TIMEOUT;
            if (wait != WAIT_OBJECT_0 && !timedOut) ThrowLastError("probe_wait_failed");
            bool rootExited = wait == WAIT_OBJECT_0;
            bool empty = false;
            if (timedOut)
            {
                cleanupDeadline = clock.ElapsedMilliseconds + cleanupTimeoutMilliseconds;
                TerminateAssignedJob(
                    job, process.hProcess, 903, clock, cleanupDeadline,
                    "deadline_cleanup_terminate_failed", "deadline_cleanup_wait_failed",
                    "deadline_cleanup_job_not_empty");
                rootExited = true;
                empty = true;
                cleanupProven = true;
            }
            else
            {
                cleanupDeadline = clock.ElapsedMilliseconds + cleanupTimeoutMilliseconds;
                empty = WaitForEmptyJob(job, clock, cleanupDeadline);
                if (!empty)
                {
                    TerminateAssignedJob(
                        job, process.hProcess, 904, clock, cleanupDeadline,
                        "normal_cleanup_terminate_failed", "normal_cleanup_wait_failed",
                        "normal_cleanup_job_not_empty");
                    cleanupProven = true;
                    throw new InvalidOperationException("normal_job_not_empty");
                }
                cleanupProven = true;
            }
            uint processExitCode;
            if (!GetExitCodeProcess(process.hProcess, out processExitCode))
                throw new InvalidOperationException("process_exit_code_failed");
            return new KaosEghisJobRunResult {
                TimedOut = timedOut,
                RootExited = rootExited,
                JobBecameEmpty = empty,
                ExitCodeAvailable = true,
                ExitCode = processExitCode,
                ElapsedMilliseconds = clock.ElapsedMilliseconds
            };
        }
        finally
        {
            if (processCreated && !cleanupProven)
            {
                if (cleanupDeadline < 0)
                    cleanupDeadline = clock.ElapsedMilliseconds + cleanupTimeoutMilliseconds;
                if (assigned)
                {
                    TerminateAssignedJob(
                        job, process.hProcess, 905, clock, cleanupDeadline,
                        "fallback_cleanup_terminate_failed", "fallback_cleanup_wait_failed",
                        "fallback_cleanup_job_not_empty");
                }
                else
                {
                    TerminateUnassignedProcess(
                        process.hProcess, clock, cleanupDeadline);
                }
                cleanupProven = true;
            }
            if (!processCreated || cleanupProven)
            {
                if (process.hThread != IntPtr.Zero) CloseHandle(process.hThread);
                if (process.hProcess != IntPtr.Zero) CloseHandle(process.hProcess);
                if (job != IntPtr.Zero) CloseHandle(job);
            }
        }
    }
}
'@
} catch {
    New-ClosedProbeEnvelope 'blocked' 'probe_initialization_failed' -CleanupVerified $true |
        ConvertTo-Json -Compress
    exit 1
}

$fixedReasons = $envelopeReasonAllowlist

function Resolve-FixedProbeReason {
    param([Parameter(Mandatory = $true)][Exception]$Exception)
    $cursor = $Exception
    while ($null -ne $cursor) {
        if ($fixedReasons -contains $cursor.Message) { return $cursor.Message }
        $cursor = $cursor.InnerException
    }
    return 'probe_internal_error'
}

function Get-WorkerArguments {
    param([Parameter(Mandatory = $true)][string]$Role)
    if ($workerItem.FullName.Contains('"') -or $probeRoot.Contains('"')) {
        throw 'unsafe_probe_argument'
    }
    return ('-NoProfile -NonInteractive -ExecutionPolicy Bypass ' +
        '-File "{0}" -Role {1} -MarkerRoot "{2}"' -f
        $workerItem.FullName, $Role, $probeRoot)
}

function Assert-ExactProbeMarkers {
    param([Parameter(Mandatory = $true)][hashtable]$Expected)
    $items = @(Get-ChildItem -LiteralPath $probeRoot -Force)
    if ($items.Count -ne $Expected.Count) { throw 'unexpected_probe_marker' }
    $strictUtf8 = [Text.UTF8Encoding]::new($false, $true)
    foreach ($item in $items) {
        if ($item.PSIsContainer -or
            ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
            -not $Expected.ContainsKey($item.Name)) {
            throw 'unexpected_probe_marker'
        }
        $actual = $strictUtf8.GetString([IO.File]::ReadAllBytes($item.FullName))
        if ($actual -cne $Expected[$item.Name]) { throw 'probe_marker_invalid' }
    }
}

function Remove-ExactProbeRoot {
    $cleanupDeadline = [Math]::Min(
        $globalDeadlineMilliseconds,
        $globalClock.ElapsedMilliseconds + 2000)
    $allowed = @('normal.ready', 'root.ready', 'child.ready', 'grandchild.ready')
    $rootItem = Get-Item -LiteralPath $probeRoot -Force -ErrorAction Stop
    if (-not $rootItem.PSIsContainer -or
        ($rootItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'probe_cleanup_failed'
    }
    $items = @(Get-ChildItem -LiteralPath $rootItem.FullName -Force)
    foreach ($item in $items) {
        if ($globalClock.ElapsedMilliseconds -ge $cleanupDeadline -or
            $item.PSIsContainer -or
            ($item.Attributes -band [IO.FileAttributes]::ReparsePoint) -or
            $allowed -cnotcontains $item.Name) {
            throw 'probe_cleanup_failed'
        }
        [IO.File]::Delete($item.FullName)
        if (Test-Path -LiteralPath $item.FullName) { throw 'probe_cleanup_failed' }
    }
    if ($globalClock.ElapsedMilliseconds -ge $cleanupDeadline) {
        throw 'probe_cleanup_failed'
    }
    [IO.Directory]::Delete($rootItem.FullName, $false)
    if (Test-Path -LiteralPath $probeRoot) { throw 'probe_cleanup_failed' }
}

$terminalStatus = 'blocked'
$terminalReason = 'probe_internal_error'
$suspendedBeforeAssignment = $false
$normalExitVerified = $false
$normalMarkerVerified = $false
$rootChildGrandchildStarted = $false
$deadlineTriggered = $false
$rootExitedAfterTermination = $false
$jobActiveProcessCountReachedZero = $false
$cleanupVerified = $false
$probeRootCreated = $false
$globalClock = [Diagnostics.Stopwatch]::StartNew()
$globalDeadlineMilliseconds = 15000
$probeRoot = $null

function Invoke-BoundedProbeScenario {
    param(
        [Parameter(Mandatory = $true)][string]$Arguments,
        [Parameter(Mandatory = $true)][int]$RunBudgetMilliseconds,
        [Parameter(Mandatory = $true)][int]$CleanupBudgetMilliseconds
    )
    $remaining = $globalDeadlineMilliseconds - $globalClock.ElapsedMilliseconds
    $required = $RunBudgetMilliseconds + $CleanupBudgetMilliseconds + 250
    if ($remaining -lt $required) { throw 'probe_global_deadline_exceeded' }
    return [KaosEghisJobProbe]::Run(
        $powershell, $Arguments, $RunBudgetMilliseconds, $CleanupBudgetMilliseconds)
}

try {
    $worker = Join-Path $PSScriptRoot 'SyntheticProcessTree.ps1'
    $workerItem = Get-Item -LiteralPath $worker -Force -ErrorAction Stop
    if ($workerItem.PSIsContainer -or
        ($workerItem.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'unsafe_probe_worker'
    }
    $powershell = (Get-Process -Id $PID).Path
    $probeRoot = Join-Path ([IO.Path]::GetTempPath()) (
        'kaoseghis-v3-containment-' + [Guid]::NewGuid().ToString('N'))
    if (Test-Path -LiteralPath $probeRoot) { throw 'probe_root_exists' }
    New-Item -ItemType Directory -Path $probeRoot | Out-Null
    $probeRootCreated = $true

    $normal = Invoke-BoundedProbeScenario (Get-WorkerArguments 'normal') 2000 1000
    $suspendedBeforeAssignment = $true
    if ($normal.TimedOut -or -not $normal.RootExited -or
        -not $normal.JobBecameEmpty -or -not $normal.ExitCodeAvailable -or
        $normal.ExitCode -ne 0) {
        throw 'normal_exit_not_proven'
    }
    Assert-ExactProbeMarkers @{
        'normal.ready' = "synthetic-normal`n"
    }
    $normalExitVerified = $true
    $normalMarkerVerified = $true

    $tree = Invoke-BoundedProbeScenario (Get-WorkerArguments 'root') 4000 2000
    if (-not $tree.TimedOut -or -not $tree.RootExited -or
        -not $tree.JobBecameEmpty -or -not $tree.ExitCodeAvailable) {
        throw 'deadline_tree_termination_not_proven'
    }
    Assert-ExactProbeMarkers @{
        'normal.ready' = "synthetic-normal`n"
        'root.ready' = "synthetic-root`n"
        'child.ready' = "synthetic-child`n"
        'grandchild.ready' = "synthetic-grandchild`n"
    }
    $rootChildGrandchildStarted = $true
    $deadlineTriggered = $true
    $rootExitedAfterTermination = $true
    $jobActiveProcessCountReachedZero = $true
    if ($globalClock.ElapsedMilliseconds -gt $globalDeadlineMilliseconds) {
        throw 'probe_global_deadline_exceeded'
    }
    $terminalStatus = 'complete'
    $terminalReason = 'proof_complete'
} catch {
    $terminalStatus = 'blocked'
    $terminalReason = Resolve-FixedProbeReason $_.Exception
} finally {
    if ($probeRootCreated) {
        try {
            Remove-ExactProbeRoot
            $cleanupVerified = $true
        } catch {
            $terminalStatus = 'blocked'
            $terminalReason = 'probe_cleanup_failed'
            $cleanupVerified = $false
        }
    } else {
        $cleanupVerified = $true
    }
    $globalClock.Stop()
}

$envelopeParameters = @{
    Status = $terminalStatus
    Reason = $terminalReason
    SuspendedBeforeAssignment = $suspendedBeforeAssignment
    NormalExitVerified = $normalExitVerified
    NormalMarkerVerified = $normalMarkerVerified
    RootChildGrandchildStarted = $rootChildGrandchildStarted
    DeadlineTriggered = $deadlineTriggered
    RootExitedAfterTermination = $rootExitedAfterTermination
    JobActiveProcessCountReachedZero = $jobActiveProcessCountReachedZero
    CleanupVerified = $cleanupVerified
    ElapsedMilliseconds = $globalClock.ElapsedMilliseconds
}
$envelope = New-ClosedProbeEnvelope @envelopeParameters
$envelope | ConvertTo-Json -Compress
if ($terminalStatus -ne 'complete') { exit 1 }
