$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest

if ([Environment]::OSVersion.Platform -ne [PlatformID]::Win32NT) {
    throw 'windows_only_probe'
}

Add-Type -TypeDefinition @'
using System;
using System.ComponentModel;
using System.Diagnostics;
using System.Runtime.InteropServices;
using System.Text;

public sealed class KaosEghisJobRunResult
{
    public bool TimedOut;
    public bool RootExited;
    public bool JobBecameEmpty;
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

    [DllImport("kernel32.dll")]
    static extern bool CloseHandle(IntPtr handle);

    static void ThrowLastError(string fixedReason)
    {
        throw new InvalidOperationException(fixedReason, new Win32Exception(Marshal.GetLastWin32Error()));
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

    public static KaosEghisJobRunResult Run(
        string executable, string arguments, int runTimeoutMilliseconds,
        int cleanupTimeoutMilliseconds)
    {
        if (runTimeoutMilliseconds < 1 || cleanupTimeoutMilliseconds < 1)
            throw new ArgumentOutOfRangeException("invalid_probe_timeout");
        Stopwatch clock = Stopwatch.StartNew();
        IntPtr job = IntPtr.Zero;
        PROCESS_INFORMATION process = new PROCESS_INFORMATION();
        bool assigned = false;
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
            if (!AssignProcessToJobObject(job, process.hProcess))
            {
                TerminateProcess(process.hProcess, 901);
                WaitForSingleObject(process.hProcess, (uint)cleanupTimeoutMilliseconds);
                ThrowLastError("job_assignment_failed");
            }
            assigned = true;
            if (ResumeThread(process.hThread) == UInt32.MaxValue)
            {
                TerminateJobObject(job, 902);
                ThrowLastError("probe_resume_failed");
            }
            uint wait = WaitForSingleObject(process.hProcess, (uint)runTimeoutMilliseconds);
            bool timedOut = wait == WAIT_TIMEOUT;
            if (wait != WAIT_OBJECT_0 && !timedOut) ThrowLastError("probe_wait_failed");
            if (timedOut && !TerminateJobObject(job, 903))
                ThrowLastError("job_termination_failed");

            long cleanupDeadline = clock.ElapsedMilliseconds + cleanupTimeoutMilliseconds;
            bool rootExited = WaitForSingleObject(process.hProcess,
                (uint)cleanupTimeoutMilliseconds) == WAIT_OBJECT_0;
            bool empty = false;
            while (clock.ElapsedMilliseconds <= cleanupDeadline)
            {
                if (ActiveProcesses(job) == 0) { empty = true; break; }
                System.Threading.Thread.Sleep(10);
            }
            return new KaosEghisJobRunResult {
                TimedOut = timedOut,
                RootExited = rootExited,
                JobBecameEmpty = empty,
                ElapsedMilliseconds = clock.ElapsedMilliseconds
            };
        }
        finally
        {
            if (assigned && job != IntPtr.Zero) CloseHandle(job);
            if (process.hThread != IntPtr.Zero) CloseHandle(process.hThread);
            if (process.hProcess != IntPtr.Zero) CloseHandle(process.hProcess);
            if (!assigned && job != IntPtr.Zero) CloseHandle(job);
        }
    }
}
'@

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

function Get-WorkerArguments {
    param([Parameter(Mandatory = $true)][string]$Role)
    if ($workerItem.FullName.Contains('"') -or $probeRoot.Contains('"')) {
        throw 'unsafe_probe_argument'
    }
    return ('-NoProfile -NonInteractive -ExecutionPolicy Bypass ' +
        '-File "{0}" -Role {1} -MarkerRoot "{2}"' -f
        $workerItem.FullName, $Role, $probeRoot)
}

$globalClock = [Diagnostics.Stopwatch]::StartNew()
$globalDeadlineMilliseconds = 15000
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
    $normal = Invoke-BoundedProbeScenario (Get-WorkerArguments 'normal') 3000 2000
    if ($normal.TimedOut -or -not $normal.RootExited -or
        -not $normal.JobBecameEmpty) {
        throw 'normal_exit_not_proven'
    }

    $tree = Invoke-BoundedProbeScenario (Get-WorkerArguments 'root') 5000 3000
    if (-not $tree.TimedOut -or -not $tree.RootExited -or
        -not $tree.JobBecameEmpty) {
        throw 'deadline_tree_termination_not_proven'
    }
    foreach ($role in @('root', 'child', 'grandchild')) {
        if (-not (Test-Path -LiteralPath (Join-Path $probeRoot "$role.ready") -PathType Leaf)) {
            throw 'descendant_start_not_proven'
        }
    }
    if ($globalClock.ElapsedMilliseconds -gt $globalDeadlineMilliseconds) {
        throw 'probe_global_deadline_exceeded'
    }

    [PSCustomObject]@{
        Schema = 'kaoseghis.synthetic-job-containment-proof.v1'
        SyntheticOnly = $true
        SuspendedBeforeAssignment = $true
        NormalExitVerified = $true
        RootChildGrandchildStarted = $true
        DeadlineTriggered = $true
        RootExitedAfterTermination = $true
        JobActiveProcessCountReachedZero = $true
        ProbeGlobalDeadlineMilliseconds = $globalDeadlineMilliseconds
        ElapsedMilliseconds = $globalClock.ElapsedMilliseconds
    } | ConvertTo-Json -Compress
} finally {
    $globalClock.Stop()
    Remove-Item -LiteralPath $probeRoot -Recurse -Force -ErrorAction SilentlyContinue
}
