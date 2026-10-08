# Isolated Windows synthetic test environment

- **Status:** Reviewed v2 bundle was staged and launched once; the Sandbox run
  failed closed during the 480-second Python-install step before product tests.
  Sanitized evidence is archived locally, host artifacts are retained under the
  protected root through the approved retention boundary, and no retry is approved.
  The corrected offline v3 diagnostic/manifest candidate passed independent review.
  Authoritative logging evidence passed review. The first synthetic Job Object
  candidate failed review, received one bounded candidate-only remediation, and
  passed final independent re-review. The user has now fixed the intended target
  to the centrally registered Windows machine `YHSHFM`, SSH alias `yhshfm`, owner
  `zin`, and Windows account `leejs`. Central inventory still marks its access as
  unverified and identifies it as the live KaosEghis runtime. Because no distinct
  Windows host is available, the user explicitly approved YHSHFM only as the host
  for an isolated Windows Sandbox. The later approved plan replaces the SSH-first
  observation path with a future Windows Hub/OpenClaw node enrollment. Initial node
  authority is observation-only and pairing is not authorized by this documentation
  change. Orchestration contract
  `openclaw-yhshfm-observation-route-v1.md` is now active at reviewed commit
  `e3126870afe8c5455057a2a31b109e78af77ee76`; H4 is ready, but YHSHFM still has no
  installed, paired, or admitted node. Synthetic execution remains separately gated
  by Windows Sandbox. No v3
  executable bundle,
  manifest identity, ZIP, transfer, Windows probe execution, or installer execution
  exists.
- **Last updated:** 2026-10-08
- **Owning project:** KaosEghis
- **Affected projects:** KaosEghis, orchestration, clinic operations

## Context and safety boundary

KaosEghis needs a Windows-native full-suite result, but the available machine is
also a clinic workstation with a protected live checkout and interactive desktop
launcher. The test process must not see or mutate that checkout, EMR processes,
patient data, credentials, network services, printers, clipboard, or the host
interactive desktop. Administrator status is not a substitute for isolation.

Artifact preparation did not authorize workstation contact. The user later approved
one staging and interactive Sandbox execution only after independent review of the
exact hashes, signature evidence, lock, configuration, runner, paths, resource
bounds, ACLs, retention, and return procedure recorded below. That completed run
never permitted host Python installation, another reboot, service/firewall changes,
deployment, `main.py`, repository probes, or a production reader.

### Completed first host-change boundary

The user authorized and the coordinator completed only these two host changes
through the already-established administrative channel:

1. enable Windows optional feature `Containers-DisposableClientVM` with dependency
   enablement and `-NoRestart`; and
2. create only `C:\KaosClinic-Test\Eghis`, empty, non-reparse, with inheritance
   disabled and full-control allow entries only for the approving administrator
   and SYSTEM.

The command must verify expected computer/user/admin context first, accept an
already-enabled feature, reject an unexpected feature state, and treat any existing
staging root as acceptable only when it is empty and its protected ACL is already
exact. Otherwise it stops without repairing or replacing existing content. A newly
created root whose ACL cannot be secured is removed only if still empty.

Independent post-check/review recorded all of the following without clinical
payload or credential content:

- `Containers-DisposableClientVM` is `Enabled`; the coordinator result reported
  `RestartNeeded=true` before the subsequently completed bounded reboot below;
- `C:\KaosClinic-Test\Eghis` exists, is empty, and is not a reparse point;
- its DACL has inheritance disabled and exactly two full-control allow principals,
  `YHSHFM\leejs` and SYSTEM; and
- the protected live checkout remained on `main` at `5fc962e` with tracked and
  staged state clean.

This completed step does not include a reboot, bundle/source transfer, clone,
Python or dependency installation, Sandbox launch, test run, firewall/service
change, live checkout change, or creation of any child under the staging root. The
Eghis worker did not contact or mutate the workstation; it records coordinator and
independent review evidence only.

### Completed reboot and post-reboot gate

The user approved and the coordinator completed one reboot of the expected
workstation during the closed-time window. The preflight confirmed computer
`YHSHFM`, account `YHSHFM\leejs`, administrator role, and
`Containers-DisposableClientVM` state `Enabled`. The reboot was scheduled once,
and the coordinator observed the SSH endpoint disconnect and return.

The read-only post-check recorded a new boot time of
`2026-10-08T17:47:44.5000000+09:00` and confirmed:

1. `Containers-DisposableClientVM` state is `Enabled` and
   `EnablePending=false`;
2. Component Based Servicing `RebootPending=false`;
3. Windows Update `RebootRequired=false`; and
4. `PendingFileRenameOperations=false`.

The staging root also remains empty with ACL inheritance protected and exactly
SYSTEM and `YHSHFM\leejs` as principals. No artifact transfer, installation,
Sandbox launch, test, or deployment occurred. Successful reboot verification does
not authorize any of those later steps. This Eghis worker did not contact or mutate
the workstation; it records only the coordinator's sanitized completion evidence.

## Repository evidence

- `pyproject.toml` requires Python 3.11 or newer. The observed workstation Python
  is 3.11.0, but the test runtime need not and should not reuse the host install.
- `requirements.txt` includes PySide6, cryptography, keyring, psutil,
  PyGetWindow, psycopg2-binary, pywinauto, Windows-only pyvda, pynput, and pytest.
  The ranges are not a reproducible lock.
- Static import inspection also finds test/runtime imports of PyAutoGUI and the
  pywin32/comtypes modules normally supplied with the Windows automation stack.
  PyAutoGUI is not declared in `requirements.txt`; this must be resolved in the
  offline test lock rather than fetched ad hoc on the workstation.
- `tests/conftest.py` blocks non-test socket/DNS access, unmocked PostgreSQL
  connections, ordinary WebEngine navigation, the live EMR mutex, and low-level
  PyAutoGUI input. Those Python guards are defense in depth, not an OS security
  boundary for every UIA, native printer, subprocess, or extension call.

## Selected topology

### Observation-only OpenClaw node

The user approved replacing the SSH-first/YHSHFM Windows Sandbox-first environment
observation path with future enrollment of YHSHFM as a Windows Hub/OpenClaw node.
Enrollment itself still requires a separately controlled installation and pairing
step; this documentation task does not contact the host, install software, generate
or relay a setup code, or approve a pairing request.

The initial node permission set is closed and observation-only:

- allow only `device.info`, `device.status`, and `system.which`;
- deny `system.run`, every file read/write/mutation or transfer surface, application
  or service control, camera, microphone/talk, notifications, location, screen
  snapshot or recording, and any access to the live Eghis checkout, data, services,
  credentials, processes, logs, or clinical workflow; and
- treat node pairing/admission as transport identity only. Pairing never authorizes
  a command-surface or permission expansion; any expansion requires a new explicit
  user decision, reviewed capability policy, and updated durable plan.

The accepted central route contract is
`/srv/projects/KaosClinic/orchestration/contracts/openclaw-yhshfm-observation-route-v1.md`
at orchestration commit `e3126870afe8c5455057a2a31b109e78af77ee76`:

- the H4 Gateway remains loopback-only and OpenClaw supervises tailnet-only
  HTTPS/WSS Serve exposure;
- Gateway authentication remains token-based,
  `gateway.auth.allowTailscale=false`, and Tailscale identity never bypasses the
  Gateway token;
- Funnel and LAN/public binds are absent/prohibited; and
- SSH auto-approval and node plugin tools are disabled, while non-observation
  command families are denied by policy.

Independent review passed that contract and reported zero devices, nodes, or
pending requests. No YHSHFM installation, contact, pairing, or command occurred.
The remaining installation must begin locally at the YHSHFM interactive desktop.
Credentials and setup codes stay outside chat, logs, repositories, and worker
output. After a fresh attempt, re-list requests and approve only the exact matching
device and node request IDs. Before approving the node command surface,
`openclaw nodes describe` must prove the effective command set is exactly
`device.info`, `device.status`, and `system.which`; any additional effective command
is a fail-closed rejection.

Windows Sandbox is not required merely to obtain those three non-clinical,
read-only observations. The node is not a containment boundary and must never run
synthetic tests on the host. Any Windows-native synthetic execution still requires
the separately approved, independently reviewed Windows Sandbox gate below with
synthetic fixtures only and no live-resource mapping. The SSH configuration and
key-registration work previously proposed for this observation path is stopped and
superseded; its historical evidence remains below for auditability.

### Synthetic execution containment

Use **Windows Sandbox with host networking, printer redirection, clipboard,
audio/video input, and vGPU disabled**. Map only an immutable inbound bundle and a
new empty results directory. Do not expose any host drive or directory containing
the live checkout, application data, credentials, or patient information.

Windows Sandbox is preferred over a local venv, a second ordinary Windows account,
WSL, or a Git worktree:

- an ordinary process/account can still enumerate the host desktop, printers,
  processes, drives, and network;
- WSL does not exercise the required Windows/PySide6/pywinauto behavior;
- a Git worktree shares repository metadata/object storage and is inappropriate
  for separation from a protected checkout; and
- Sandbox gives a disposable Windows kernel/container boundary while preserving
  Windows-specific imports and Qt behavior.

If Windows Sandbox cannot be enabled without unacceptable host change or restart,
stop. The fallback is a separately approved non-production Windows VM or host, not
direct execution on the clinic desktop and not enabling Hyper-V implicitly.

## Host staging layout and source provenance

Exact non-live staging layout for bundle `eghis-d1777c1834e1-win311-v2` and run
`eghis-d1777c1834e1-win311-v2-run-01`:

```text
C:\KaosClinic-Test\Eghis\
  eghis-d1777c1834e1-win311-v2.zip
  Inbound\eghis-d1777c1834e1-win311-v2\
  Results\eghis-d1777c1834e1-win311-v2-run-01\
```

The completed staging root retains its protected two-principal ACL. Each inbound
and results run directory must be newly created with the same exact principals and
must not be under, linked to, or populated from the live checkout.

The trusted development host prepared the following for independent review. After
review passed, the coordinator transferred only the exact v2 ZIP and used it for
the single bounded run recorded below:

1. an independent Git bundle containing the exact reviewed commit and its history;
2. a source archive produced from that commit, plus `SOURCE_COMMIT.txt` and a
   SHA-256 manifest for every archive file;
3. an official offline CPython 3.11 installer and recorded publisher/hash;
4. a Windows CPython-3.11 wheelhouse and hash-locked requirements file; and
5. a Sandbox `.wsb`, fail-closed runner, staging procedure, and result-packaging
   procedure.

On the workstation, provenance verification may create an **independent clone**
from the offline Git bundle under the staging root and detach it at the reviewed
commit. Do not use `git clone` from the live checkout, `--reference`, alternates,
hard links, junctions, or `git worktree`. The independent clone is a verification
input only; the Sandbox consumes the read-only source archive and manifest.

## Python and dependency plan

Use the official **CPython 3.11.9 64-bit Windows installer**, the final 3.11
bugfix release with Windows binary installers. Before execution, operations must
approve and record its publisher signature and SHA-256. Do not substitute an
unreviewed 3.12/3.13 build or reuse the host's global 3.11.0 interpreter.

Inside each disposable Sandbox instance:

1. install that offline CPython build into `C:\KaosTestRun\Python` for the Sandbox
   user only, with no PATH, file-association, launcher, or all-users changes;
2. create `C:\KaosTestRun\venv`;
3. install only with `--no-index --require-hashes` from the read-only wheelhouse;
4. run `pip check` and save a machine-readable/frozen dependency inventory; and
5. fail before collection if the source manifest, Python version, wheel hashes,
   or locked dependency inventory differs from the approved bundle.

The lock must include all transitive wheels and an explicit test-only PyAutoGUI
decision. Preferred resolution is a reviewed repository test dependency declaration;
for the first isolated gate, a separately listed and hash-pinned test-only wheel is
acceptable only with user approval. It must not alter production requirements.

### Prepared artifact evidence

The exact source under test is
`d1777c1834e129e93441bdb208c780e322401a48`. The build-host artifact is ignored by
Git at `build/windows-sandbox-prep/eghis-d1777c1834e1-win311-v2.zip`; it is
310,597,385 bytes with SHA-256
`f7e3ca423d5252fa2d261831592d9df57992b0f5cb3fc6d24d0ec912710c9fd7`.
Its 51-entry internal manifest has SHA-256
`14ac22894d0b53338109d893926203391551f879b1c285cd4c6660440f131381`.
The package includes:

- source archive SHA-256
  `3b946718deef6e6235f5ce992587d79975121d05fe22a8571699207e1feea823`;
- complete-history Git bundle SHA-256
  `e4847bdc029f8b009b88e36ee044c9777d214e90816177b3f284decbe7f04509`;
- the 41-wheel Windows CPython 3.11 x64 wheelhouse and lock SHA-256
  `2031389cd549154316a0d8109d0b5ceccb51d4a6c65cfc4f2161f06569f80c72`;
- official `python-3.11.9-amd64.exe`, SHA-256
  `5ee42c4eee1e6b4464bb23722f90b45303f79442df63083f05322f1785f5fdde`;
  and
- the exact `.wsb`, runner, source identity, and redacted signature evidence.

The installer came from the HTTPS Python.org 3.11.9 release path. Build-host
`osslsigncode 2.9` verified one SHA-256 signature, matching file digest, RFC3161
timestamp `2024-04-02T12:54:37Z`, Python Software Foundation signer, DigiCert code
signing/timestamp chains, and CRLs. Windows staging and the Sandbox runner repeat
hash and Authenticode signer/status checks before use.

The lock deliberately adds **PyAutoGUI 0.9.54 only to this disposable test
environment** because repository code/tests import it while production
`requirements.txt` does not declare it. PyAutoGUI, MouseInfo, PyScreeze, and
PyTweening were built on the trusted development host as pure `py3-none-any`
wheels with setuptools 84.0.0; their exact hashes are in the lock and manifest.
No production dependency file changed.

### Independent review failure and bounded remediation

Independent review rejected commit `9e684aa9a8d1c7d2a2eb761a40b0011494ea2931`
and ZIP SHA-256
`9b4576c4e2ba50f0f54c62d89ee629dfddca44ce9538f8a5c4042bdb62123967`.
That `v1` ZIP is superseded and must never be transferred, staged, or launched; its
bytes were not modified in place. This sole retry creates `v2` because review found:

1. the case-sensitive WSB element was incorrectly spelled `VGpu` instead of `vGPU`;
2. staging could change an existing parent ACL before proving all four parent/run
   paths absent, while both staging and the Sandbox runner did not close the full
   directory/reparse-point set; and
3. independent child budgets could exceed the stated 90-minute window before
   accounting for setup and validation overhead.

The remediation uses the exact `vGPU` element; requires all four staging paths
absent before the first creation or ACL mutation; accepts only one inbound directory
named `wheelhouse`; rejects all descendant reparse points and any extra file or
directory after extraction, immediately before launch, and again inside Sandbox;
and applies the monotonic global deadline described below. Automated guard checks
exercise unchanged rejection of a nonempty parent and parent symlink, rejection of
an unexpected empty directory and nested symlink, exact XML element case, mutation
ordering, and termination of a fake long-running child at the global deadline.

### Completed v2 execution and sanitized evidence

Independent final review passed commit
`4c5f9293d8bd142426a8d1b4ec5926e8989e005c` and the exact v2 identities above.
During the approved closed-time window, the coordinator reported that all host,
account, administrator, Sandbox-feature, pending-restart, resource, path, staging,
ACL, and pre-launch gates passed. The exact v2 ZIP was staged, and interactive run
`eghis-d1777c1834e1-win311-v2-run-01` was launched once. The Sandbox was closed
after the runner failed closed; it was not retried.

The runner returned `Status=blocked` with fixed reason
`bounded_process_timeout` at the Python-install step's 480-second budget. Both
installer output files are empty. Product test collection never began, JUnit is
absent, and there are therefore no pass/fail/skip counts. This is a step timeout,
not evidence that the 5,400-second global deadline expired.

The sanitized result archive is retained on the H4 development host at
`build/windows-sandbox-results/eghis-d1777c1834e1-win311-v2-run-01-results.zip`:

- size: 541 bytes;
- SHA-256:
  `1eb1720f6812f1e31b6849b2026c1f0d63440183f701d600995414f46b4ce29b`;
- exact contents: `failure.txt` (25 bytes), `status.json` (60 bytes),
  `python-install.txt` (0 bytes), and `python-install-error.txt` (0 bytes).

The fixed status and empty streams prove only that the quiet installer process did
not finish within its reviewed budget. They do not distinguish a slow installer,
blocked child/bootstrapper activity, host resource contention, or another Windows
installer condition, so none of those possibilities is accepted as the cause.
There is no evidence of a Python exit code, installer diagnostic, dependency step,
source extraction, or product-test behavior.

Host bundle, inbound, results, and return artifacts remain under the approved
protected staging root. No cleanup is authorized; retention ends no later than
`2026-10-15T10:28:50Z`, subject to a separately reviewed exact-path cleanup step.

### Offline v3 evidence and bounded design

The pinned installer remains the exact 3.11.9 executable with SHA-256
`5ee42c4eee1e6b4464bb23722f90b45303f79442df63083f05322f1785f5fdde`.
Offline inspection identifies it as a WiX Burn bootstrapper. Embedded engine text
contains the `log` command-line token, the fixed error `Must specify a path for
log`, package-log allocation messages, `burn.clean.room`, active-parent state,
elevated/unelevated pipe coordination, elevated-child launch, and child-process
wait messages. This supports a candidate `/log <path>` diagnostic boundary and
proves the executable has multi-process orchestration. It does **not** prove that a
child caused the v2 timeout, that a process detached or reparented, or that the
current `taskkill /T` covered every process.

The current `Invoke-DeadlineProcess` waits only the `Start-Process` bootstrapper
PID. On Windows timeout it invokes `taskkill /PID <pid> /T /F`, but it neither
checks the command's exit code nor verifies that the root and descendants exited.
The existing fake-child test runs on the Linux development host, where .NET
`Kill(true)` is used, so it is not evidence for Windows `taskkill`, Burn clean-room
behavior, elevation pipes, detached children, or reparenting. The v2 result shows
the observed bootstrapper PID remained active through 480 seconds; nothing more
about its process topology is known.

The reserved next identity is `eghis-d1777c1834e1-win311-v3`, but it is a design
label only. The repository contains candidate-only modules under
`tools/windows-sandbox/v3-candidate/`:

- `InstallerDiagnostics.psm1` opens the Sandbox-local raw log once with read-only
  sharing, reads one in-memory snapshot while enforcing the byte cap on every read,
  and derives byte count, SHA-256, lines, and markers only from those same bytes. It
  preserves an existing zero-byte log as present (distinct from a missing path),
  emits only a closed JSON summary, and publishes it through atomic create-new with
  no overwrite. It never returns a log line, path, username, argument, or token.
- `New-V3Manifest.ps1` deterministically hashes an exact candidate tree, permits
  only the `wheelhouse` directory, rejects reparse points and unsafe paths, sorts
  canonical relative paths with ordinal comparison, rejects distinct source paths
  that collide under Windows ordinal-ignore-case comparison, and publishes a fresh
  manifest without overwriting an existing final path. It does not create or
  compress a ZIP.
- `test-v3-offline-contract.ps1` proves synthetic raw content is not echoed,
  races two distinct create-new diagnostic writers, simulates growth beyond the
  byte cap, replaces the source path after snapshot capture, and verifies the
  published summary still matches the one snapshot. It also proves missing versus
  existing-empty log semantics, closed schema, canonical UTF-8/LF output,
  culture-independent ordinal manifest order, Linux-host rejection of a Windows
  case-insensitive path collision, immutable pre-existing manifest,
  unexpected-directory/reparse rejection, and no ZIP.

Independent review of the first candidate commit `55994fad5407751e284c74d5c635c41b0541ac2c`
failed because its diagnostic output used a check-then-write overwrite race, its
log size/hash/counts did not come from one enforced bounded snapshot, and its
manifest publication overwrote existing output and used culture-sensitive sorting.
This sole remediation corrects only those three gaps. The diagnostic output now
uses `FileMode.CreateNew`; the log is read once from one handle into a per-read
bounded snapshot and never reopened for hashing; and manifest publication refuses
an existing final path, uses no-overwrite `File.Move`, and orders relative paths
with `StringComparer.Ordinal`.

A second independent review then found two remaining fail-closed gaps: PowerShell
pipeline enumeration collapsed an existing empty byte array into the same state as
a missing file, and a case-sensitive development filesystem could admit paths that
collide on Windows. The user explicitly approved one additional bounded remediation
on 2026-10-08. The file reader now returns an explicit snapshot wrapper, including
an empty byte array, while a missing path still returns no wrapper; all diagnostic
fields remain derived from that same bounded snapshot. Manifest input now uses a
separate `StringComparer.OrdinalIgnoreCase` collision set while retaining
`StringComparer.Ordinal` for canonical output ordering. This exception does not
authorize runner wiring, artifact or ZIP generation, transfer, execution, host
cleanup, deployment, or access to YHSHFM or clinical data.

#### Authoritative `/log` evidence

The accepted syntax for the pinned full installer is the minimal pair
`/log <absolute-log-path>`. The path must be an absolute path beneath the
unmapped Sandbox-local diagnostic directory; it is never a URL and does not enable
network collection. This conclusion is grounded in the following upstream evidence:

- Python Software Foundation, **CPython `v3.11.9` —
  `Tools/msi/get_externals.bat`**, lines 48-60,
  <https://github.com/python/cpython/blob/v3.11.9/Tools/msi/get_externals.bat#L48-L60>:
  the exact release source selects the `wix-314` binary dependency for Windows
  installer builds. The same tag's **`Tools/msi/README.txt`**,
  <https://github.com/python/cpython/blob/v3.11.9/Tools/msi/README.txt>, identifies
  WiX as the installer toolset and the bundle EXE as the command-line entry point.
- WiX Toolset upstream, **WiX 3.14 RTM Burn `core.cpp`**, lines 1081-1096,
  <https://github.com/wixtoolset/wix3/blob/wix314rtm/src/burn/engine/core.cpp#L1081-L1096>:
  the parser accepts either `l` or `log`, case-insensitively, after `-` or `/`,
  requires one following argument, and copies that argument as the log-file path.
  WiX 3.14.1 contains the same parser at the corresponding lines:
  <https://github.com/wixtoolset/wix3/blob/wix3141rtm/src/burn/engine/core.cpp#L1081-L1096>.
- WiX Toolset upstream, **WiX 3.14 RTM Burn `logging.cpp`**, lines 51-104,
  <https://github.com/wixtoolset/wix3/blob/wix314rtm/src/burn/engine/logging.cpp#L51-L104>:
  a supplied path is opened as the requested log; explicit open failure is fatal,
  unlike best-effort default logging. The resulting log can contain installer paths
  and package details, so the raw file remains Sandbox-local and only the closed,
  bounded summary may enter mapped Results.

The Python 3.11 user guide's **Installing Without UI** section,
<https://docs.python.org/3.11/using/windows.html#installing-without-ui>, documents
`/quiet`, `/passive`, `/uninstall`, and feature `name=value` options but does not
document `/log`; it is supporting context, not the authority for the logging switch.
Static inspection of the already pinned 3.11.9 installer (SHA-256 above) confirms
the matching fixed Burn messages `Must specify a path for log.` and
`Failed to copy log file path.` without executing it. The source evidence settles
the syntax and open behavior, but it does not authorize running the installer.

#### Synthetic process-containment proof candidate

The candidate-only files `Test-JobObjectContainment.ps1` and
`SyntheticProcessTree.ps1` create no KaosEghis install and reference no clinic path.
The controller creates PowerShell suspended, applies a Job Object with
`JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE`, assigns the process before resuming it, and
uses monotonic `Stopwatch` budgets. A normal synthetic process must exit with code
zero, produce exactly `normal.ready` with fixed `synthetic-normal` content, and
leave no other marker. The deadline scenario starts a synthetic root, child, and
grandchild, reaches its four-second run limit, calls `TerminateJobObject`, waits on
the original root handle, obtains its exit code, and requires the Job Object's
active-process count to reach zero. Both scenarios and explicit cleanup must finish
within the 15-second probe deadline. Success is emitted only after the exact four
allowlisted marker files and unique temp root are explicitly deleted and absence is
verified. Success and failure share one closed nonclinical JSON field set; failures
map to fixed allowlisted reasons and never echo exceptions, paths, PIDs, Win32 text,
stdout, stderr, or host details. `test-job-object-containment-contract.ps1`
provides Linux-safe structural checks plus a real wrong-platform failure-envelope
check, but it is not Windows execution evidence.

Independent review of commit `844647fe817fafaeb61b86eda91de5e36809a7c3`
accepted the upstream `/log` evidence and suspended-before-assignment ordering but
rejected four proof gaps: no exit-code or exact normal-marker assertion, success
before silent cleanup, raw failure propagation, and unchecked cleanup in
assignment/resume/termination paths. The bounded remediation adds
`GetExitCodeProcess`, exact marker-set/content checks, explicit deadline-bounded
cleanup before output, fixed closed envelopes, and checked terminate/wait/job-empty
postconditions with fallback cleanup that retains native handles until cleanup is
proven. The worker also has a future `nonzero-before-marker` role that exits with a
fixed nonzero code before writing anything. Offline tests prove its ordering, but
this remediation does not execute that Windows case or any native Windows probe.

Execution acceptance requires all of the following on one separately approved
Windows Sandbox host. The current exception is YHSHFM: its live checkout, data,
services, desktop applications, devices, network, and clinical workflow remain
prohibited resources, and only synthetic fixtures inside the isolated Sandbox are
eligible for a later separately approved execution:

1. record the exact machine ID, separately approved control-channel identity and
   authentication boundary, Windows build, protected/prohibited host paths,
   separate staging root, approved Windows account and coordinator context,
   Sandbox feature/restart state, approving owner, maintenance window, and
   sufficient CPU/RAM/disk before transfer;
2. independently review the exact candidate commit and hashes, then transfer only
   the probe scripts into a fixed-memory Sandbox with exact case-sensitive `vGPU`
   disablement; disable networking, clipboard, printer, audio, video, and device
   sharing, map probe input read-only, and map only a new empty result directory
   writable;
3. observe the fixed JSON booleans for create-suspended-before-assignment, normal
   zero exit and exact marker, root/child/grandchild start, timeout,
   original-root-handle exit, zero active job processes, exact cleanup, and the
   15-second monotonic bound;
4. additionally review and exercise fail-closed assignment/resume failure and an
   attempted breakaway/detach case, plus the prepared nonzero-before-marker worker,
   before this helper can replace the runner's current process boundary; do not
   infer those Windows results from offline structural checks;
5. preserve no raw process output, PID list, dump, installer, package, source tree,
   or host path, and destroy the Sandbox after returning only the reviewed JSON; and
6. before transfer, perform read-only feature/restart/disk/RAM/path/ACL preflight and
   prove the approved account has an active interactive desktop with `quser` or an
   equivalent session API; remote process enumeration alone is insufficient; and
7. treat any missing marker, nonzero active count, exceeded deadline, absent
   interactive session, host ambiguity, or containment error as a blocker with no
   installer or product-test follow-on and no same-directory rerun.

Read-only OpenClaw presence discovery on 2026-10-08 returned no people or devices.
At that time no registered non-clinic Windows Sandbox target, stable device
identity, or execution authorization target could be named, and YHSHFM remained
excluded. This was the original plan; the later explicit YHSHFM Sandbox-host
exception below supersedes only that target-selection restriction.

Later on 2026-10-08 the user designated non-clinic target label `winbox`, owned by
`zin`, and authorized only the reviewed synthetic containment transfer/execution
gate. Validation initially stopped because no fixed SSH host was available. The
user then clarified that label as central machine `YHSHFM`, registered SSH alias
`yhshfm`, Windows account `leejs`, and owner `zin`. Central inventory confirms the
machine, registered hostname, alias, and OS, but also identifies `YHSHFM` as the
live KaosEghis runtime and retains `unverified-access`. The user subsequently chose
YHSHFM because no distinct Windows host is available. This permits only a
no-change read-only preflight and potential later Sandbox-only synthetic execution;
it never permits touching the live checkout, data, services, clinical workflow, or
other host resources.

A locked-context, local-only `ssh -G yhshfm` inspection stopped before connection.
It resolved a different user, used the default identity search rather than an
explicit dedicated key, left `IdentitiesOnly` and `BatchMode` disabled, and used
ask-on-first-use host-key behavior instead of an independently verified pinned key.
Consequently the approved SSH execution identity and trust chain are not present,
and account/admin, Sandbox/restart/resource/ACL state, protected and staging paths,
and the interactive desktop session remain unproven. Per the fail-closed gate, no
authentication attempt, transfer, staging, Windows command, Sandbox launch,
cleanup, or execution occurred.

The proposed runner delta, intentionally **not wired or packaged yet**, is:

1. keep the 5,400-second monotonic global deadline and do not change any individual
   budget without new timing evidence;
2. place the Burn raw log only in an unmapped `C:\KaosTestRun\diagnostics` path,
   pass the independently confirmed logging syntax to the pinned installer, and
   delete it with the Sandbox instance;
3. after installer exit or verified process-tree termination, write only
   `python-installer-diagnostic.json` to mapped Results using the closed summary;
4. add only that JSON filename to the reviewed result allowlist, retain the 200-MiB
   total result cap, and reject malformed/oversized summaries;
5. replace the race-prone start/kill boundary with a Windows containment mechanism
   that enrolls the suspended bootstrapper before it may create descendants,
   prevents unreviewed breakaway, terminates the containment object on timeout,
   and fails closed unless root/child/grandchild exit is proven; and
6. retain fixed/redacted status reasons and never export the raw installer log.

A Windows Job Object with kill-on-close is the candidate containment mechanism,
but it is not accepted merely from design knowledge. Final integration requires an
independent Windows Sandbox synthetic probe that covers normal exit, timeout,
child and grandchild processes, attempted detach/reparent/breakaway, PID reuse
defense, assignment failure, and global-deadline expiry. If the reviewed mechanism
cannot prove containment, v3 packaging remains blocked. The exact CPython 3.11.9
and WiX source evidence for logging syntax is now captured above but still requires
independent acceptance before runner wiring; embedded strings alone remain
insufficient authority for final bytes.

#### v3 acceptance and sequencing gates

1. Independently review this evidence, candidate modules, closed diagnostic schema,
   and process-containment design.
2. Independently review the authoritative logging evidence and the candidate
   synthetic containment scripts; retain the absolute Sandbox-local path rule.
3. Implement the runner/process helper only after the approved Windows Sandbox
   synthetic containment probe, including failure and breakaway cases, passes;
   preserve the global cap and fail closed on any unverified cleanup.
4. Assemble a fresh v3 candidate tree and run `New-V3Manifest.ps1`; record a new
   entry count and manifest SHA-256. Never reuse or edit the v2 manifest.
5. Only after code/design review, build one final v3 ZIP, record its new size and
   SHA-256, and perform a second exact-artifact review. This task does not perform
   that build.
6. Transfer, staging, Sandbox execution, or host cleanup each remain separately
   gated. No execution approval follows from accepting the offline design.

## Sandbox configuration

The review candidate `tools/windows-sandbox/KaosEghisSynthetic.wsb` enforces:

```xml
<Configuration>
  <Networking>Disable</Networking>
  <PrinterRedirection>Disable</PrinterRedirection>
  <ClipboardRedirection>Disable</ClipboardRedirection>
  <AudioInput>Disable</AudioInput>
  <VideoInput>Disable</VideoInput>
  <vGPU>Disable</vGPU>
  <ProtectedClient>Enable</ProtectedClient>
  <MemoryInMB>8192</MemoryInMB>
  <!-- Map only Inbound read-only and the new Results\run-id writable. -->
</Configuration>
```

The exact mapped paths are the inbound and results run directories above. Only
inbound is read-only and only the new results directory is writable. The runner is
`C:\MappedInbound\run-synthetic-tests.ps1`. The writable results folder must be
empty at start. No parent test directory, user profile, drive root, live checkout,
`%APPDATA%`, `%LOCALAPPDATA%`, SSH material, or credential store is mapped.

## Guarded test command

The Sandbox runner copies the verified read-only source archive into
`C:\KaosTestRun\src`, then creates fresh data/temp/profile directories. It removes
proxy and KaosEghis service-token variables if present and sets only synthetic
locations. The pytest invocation is:

```powershell
$ErrorActionPreference = 'Stop'
$env:PYTHONDONTWRITEBYTECODE = '1'
$env:PYTEST_DISABLE_PLUGIN_AUTOLOAD = '1'
$env:QT_QPA_PLATFORM = 'offscreen'
$env:KAOSEGHIS_DATA_DIR = 'C:\KaosTestRun\data'
$env:LOCALAPPDATA = 'C:\KaosTestRun\localappdata'
$env:APPDATA = 'C:\KaosTestRun\appdata'
$env:TEMP = 'C:\KaosTestRun\temp'
$env:TMP = 'C:\KaosTestRun\temp'
$env:USERPROFILE = 'C:\KaosTestRun\profile'
Remove-Item Env:HTTP_PROXY,Env:HTTPS_PROXY,Env:ALL_PROXY,Env:NO_PROXY -ErrorAction SilentlyContinue
Remove-Item Env:KAOSEGHIS_PACS_API_TOKEN,Env:KAOSPACS_INTEGRATION_TOKEN,Env:KAOSPACS_PATIENT_CONTEXT_API_HOST,Env:KAOSPACS_PATIENT_CONTEXT_API_PORT -ErrorAction SilentlyContinue
Set-Location -LiteralPath 'C:\KaosTestRun\src'
& 'C:\KaosTestRun\venv\Scripts\python.exe' -m pytest -ra `
  --basetemp='C:\KaosTestRun\pytest-temp' `
  -o cache_dir='C:\KaosTestRun\pytest-cache' `
  --junitxml='C:\MappedResults\junit.xml' 2>&1 |
  Tee-Object -FilePath 'C:\MappedResults\pytest-full.txt'
$pytestExit = $LASTEXITCODE
exit $pytestExit
```

The prepared runner verifies the exact artifact files **and** sole allowed
`wheelhouse` directory, rejects every descendant reparse point, and then verifies
source identity, installer hash/signature, Sandbox account, absence of default
routes and non-loopback addresses, empty results, Python 3.11.9, hash-only offline
installation, `pip check`, and frozen inventory before pytest. A monotonic 5,400-
second global deadline bounds all work. Child budgets are 480 seconds for install,
120 for venv creation, 720 for dependencies, 60 each for `pip check` and inventory,
and 3,300 for pytest: 4,740 seconds total with 660 seconds reserved for validation
and other overhead. Every child timeout is capped by remaining global time; expiry
kills the process tree, writes fixed `global_deadline_exceeded`, and prevents later
steps. Results over 200 MiB are rejected. The final report contains only fixed
status fields and synthetic test artifacts; network isolation is a boolean, never
raw addresses/routes. The runner keeps `tests/conftest.py`; tests must not use
`--noconftest` or run from a host SSH shell.

## Execution gates and operations

Even with isolation, the run can consume CPU, memory, and disk on a clinic machine.
Execution therefore requires all of the following:

1. independent review acceptance of the exact source commit, package/manifest
   hashes, CPython evidence, lock and PyAutoGUI decision, `.wsb`, guard module,
   four operational scripts and two guard-test scripts,
   mapped paths, resource bounds, ACL, retention, and return process;
2. the completed coordinator reboot and successful read-only post-reboot gate
   recorded above;
3. a closed-time maintenance window capped at 90 minutes, with no clinical workflow
   depending on workstation resources, at least 20 GiB free on C:, at least 12 GiB
   available RAM, and the live app/checkout left untouched;
4. an interactive operator launch of the reviewed `.wsb`; do not attempt to drive
   Windows Sandbox invisibly from the SSH session; and
5. post-run review that results contain only synthetic test names/counts and fixed
   errors before they leave the workstation.

No test result authorizes runtime activation, source access, printing, endpoint
binding, firewall change, credential provisioning, deployment, or use of the live
checkout.

### Exact reviewed staging, launch, and return sequence

The coordinator performed this sequence through sanitized result return. Step 9
remains pending and is not authorized by the execution approval:

1. transfer the one reviewed ZIP to
   `C:\KaosClinic-Test\Eghis\eghis-d1777c1834e1-win311-v2.zip`, then verify its
   exact size/hash before extraction;
2. run reviewed `tools/windows-sandbox/stage-reviewed-bundle.ps1` via the established
   administrative channel. It fails closed on host/account/admin/feature/resource,
   root safety, ACL, path reuse, package/manifest/hash, or Authenticode mismatch;
3. independently inspect the staging JSON, confirm all four parent/run paths were
   absent before creation, the new directories have protected ACLs with exactly
   `YHSHFM\leejs` and SYSTEM full control, and Results is empty;
4. immediately before launch run reviewed
   `tools/windows-sandbox/verify-before-sandbox-launch.ps1`; require an exact
   file/directory manifest match, no descendant reparse points, and empty Results;
5. during the bounded window, have the operator interactively open only the emitted
   `KaosEghisSynthetic.wsb` path. Do not launch it invisibly through SSH;
6. allow the mapped runner to finish, then close Sandbox. Never rerun into the same
   result directory;
7. review the allowlisted result files locally for synthetic-only, non-sensitive
   content. Only after that review run
   `tools/windows-sandbox/package-reviewed-results.ps1` via the established channel;
8. record the returned ZIP hash, transfer only that reviewed result ZIP, and retain
   protected inbound/results/return artifacts for at most seven days or until the
   accepted report is archived, whichever is earlier; and
9. remove only the explicit bundle/run paths in a separately reviewed cleanup step.
   Do not use wildcards, follow reparse points, or touch the live checkout.

## Rollback and removal

Closing Windows Sandbox destroys its Python install, venv, copied source, temp
files, synthetic databases, process state, and test-local credentials. After the
reviewed result ZIP is safely archived, retain host artifacts no longer than seven
days. Remove only the explicit run directory, inbound bundle directory, source ZIP,
and result ZIP beneath `C:\KaosClinic-Test\Eghis`; never use a drive-root target,
wildcard, junction-following deletion, or the live path. Record the exact deleted
paths and whether JUnit/inventory artifacts were archived.

Do not disable Windows Sandbox automatically after the run. Optional-feature
rollback and any reboot beyond the single completed reboot require a separate
operator decision because they are host changes. If setup fails before
isolation is proven, remove the new staging run only and report blocked; do not fall
back to host pytest.

## Open decisions and next action

- Preserve the v2 result as the canonical first-run evidence. Do not reuse its run
  directory or rerun the unchanged v2 bundle.
- The completed offline analysis supports only the closed diagnostic summary and
  deterministic manifest workflow. Upstream evidence now establishes the `/log`
  syntax and explicit-open behavior. Next review must accept that evidence and the
  containment candidate; actual proof remains blocked on a fixed, trusted Windows
  Sandbox execution context.
- The user clarified the candidate-only target as central machine `YHSHFM`
  (Windows), registered SSH alias `yhshfm`, exact Windows account `leejs`, and
  owner `zin`. The central inventory agrees on the machine, registered hostname,
  alias, and OS but still records `unverified-access` and identifies it as the live
  KaosEghis runtime. The user explicitly accepted this host only for a no-change
  read-only preflight and a later separately approved Sandbox-only synthetic run
  because no distinct Windows host is available. The live checkout, data, services,
  clinical workflow, and all non-Sandbox execution remain prohibited.
- The user superseded the SSH-first observation/preflight route with a future
  Windows Hub/OpenClaw node route. Do not continue SSH key registration or use SSH
  as a fallback for this path. The earlier local-only `ssh -G` failure remains
  historical evidence, not an active prerequisite list.
- The H4 Gateway route, token authentication boundary, tailnet-only Serve topology,
  and deny policy are accepted through orchestration commit `e3126870`. Remaining
  work is the separately controlled YHSHFM-local node installation and exact-ID
  admission. Never generate or relay a setup code through worker output, and never
  approve by recency or position.
- Initial admission must expose only `device.info`, `device.status`, and
  `system.which`. Deny `system.run`, file access/mutation/transfer, app/service
  control, camera, microphone/talk, notifications, location, screen capture/record,
  and all live Eghis checkout/data/service/clinical access. Pairing does not expand
  this boundary.
- The node may support read-only environment observation without Sandbox, but it is
  not containment. Synthetic test execution still requires separate approval and
  the independently reviewed isolated Windows Sandbox gate; it must not run through
  the observation node on the host.
- Cleanup of the retained exact host paths requires separate approval and must occur
  by the retention deadline; absence of approval is not permission to broaden or
  automate deletion.
- Any artifact or procedure change invalidates the recorded hashes and requires a
  new bundle ID and review; never patch the staged package in place.
- The rejected `v1` identity and SHA-256 remain permanently prohibited; only the
  reviewed `v2` identity was used for this completed attempt.
- The Windows node path is approved as the replacement design but is not installed,
  paired, admitted, or activated. Its observation-only permissions and separate
  installation/pairing review remain mandatory. It is not a workaround for the
  failed run or permission to retry v2.
- H4 currently reports zero devices, zero nodes, and zero pending requests. Local
  YHSHFM installation must keep the setup credential off chat and handoffs. Approve
  only freshly re-listed exact request IDs, then require `nodes describe` to show
  exactly the three observation commands before admitting the node surface.

Do not contact YHSHFM, retry Sandbox, alter v2 bytes, or clean up host artifacts
until the applicable next action is separately approved and reviewed.

## Revision history

- **2026-10-08:** Created the documentation-only Windows Sandbox plan from the
  supplied read-only workstation inventory and repository dependency/test guards.
  No remote access, installation, host mutation, test execution, or deployment
  occurred.
- **2026-10-08:** Recorded the user's bounded approval for a coordinator to enable
  only `Containers-DisposableClientVM` with `-NoRestart` and create the empty,
  protected staging root. Reboot, staging children, bundles, runtime installation,
  Sandbox launch, and tests remain unapproved; this worker executed no host action.
- **2026-10-08:** Recorded coordinator execution and independent review: the
  Sandbox feature is enabled with restart still needed; the staging root is empty,
  non-reparse, and protected by the exact administrator/SYSTEM full-control DACL;
  the live checkout remained tracked/staged clean on `main@5fc962e`. The Eghis
  worker did not contact or mutate the workstation. Reboot and every later artifact,
  launch, and test step remain separately gated.
- **2026-10-08:** Recorded user approval for one coordinator-driven reboot in the
  current closed-time window and fixed the post-reboot gate: exact context, advanced
  boot timestamp, feature exactly `Enabled`, and fixed pending-restart booleans.
  Artifacts, installation, Sandbox launch, runtime, and tests remain unapproved;
  this Eghis worker did not contact or mutate the workstation.
- **2026-10-08:** Recorded coordinator completion of the single approved reboot and
  its sanitized post-check evidence: SSH went down and returned, the boot timestamp
  advanced, Sandbox remained `Enabled` with no enable-pending or reported restart
  indicators, and the protected staging root remained empty with the exact two
  principals. No artifact, installation, Sandbox launch, test, or deployment
  occurred; this Eghis worker did not contact or mutate the workstation.
- **2026-10-08:** Recorded the user's conditional approval for the next bounded
  phase and prepared the exact H4 offline artifact set, CPython signature evidence,
  Windows 3.11 lock/wheelhouse with the test-only PyAutoGUI decision, disabled-
  network `.wsb`, fail-closed runner, staging/return scripts, fixed paths/resource
  bounds/ACL/retention, and downstream sequence. Independent review is still
  required before staging or launch; this worker did not contact the workstation.
- **2026-10-08:** Recorded independent review FAIL for `v1` and completed the sole
  bounded remediation as new `v2`: corrected the case-sensitive `vGPU` element,
  moved the all-path absence gate before mutation, closed exact directory and
  descendant reparse semantics across staging/prelaunch/Sandbox, and replaced the
  additive child limits with a 5,400-second monotonic global deadline and 660-second
  overhead reserve. Added automated unchanged-parent, junction, unexpected-directory,
  nested-junction, exact-tag, ordering, and fake-long-child checks. No workstation
  contact, transfer, staging, launch, test, or deployment occurred.
- **2026-10-08:** Recorded the independently reviewed v2 execution handoff. All
  preflight and staging gates passed, but the one interactive Sandbox run failed
  closed at the 480-second Python-install budget with fixed
  `bounded_process_timeout`, empty installer streams, no JUnit, and no product test
  counts. Recorded the 541-byte sanitized result ZIP identity, protected-host
  retention deadline, evidence-limited cause analysis, new-bundle-only diagnostic
  boundary, and deferred OpenClaw-node security gate. This documentation worker did
  not contact YHSHFM, retry Sandbox, mutate host artifacts, or change bundle bytes.
- **2026-10-08:** Completed offline v3 analysis. Recorded pinned Burn logging and
  multi-process evidence, the current Windows termination-proof gap, and a bounded
  Job-Object candidate with explicit Windows synthetic acceptance gates. Added a
  candidate closed installer-diagnostic summarizer, deterministic manifest-only
  generator, and synthetic contract test. Reserved the v3 label without generating
  a manifest identity or executable ZIP. No YHSHFM contact, v2 retry, transfer,
  host cleanup, deployment, or live-data access occurred.
- **2026-10-08:** Recorded the first v3 candidate review FAIL and completed the one
  bounded remediation: atomic create-new diagnostic output, one-handle/per-read-
  bounded snapshot derivation, and ordinal/no-overwrite manifest publication.
  Added concurrent-writer, synthetic growth, post-snapshot replacement, existing-
  manifest immutability, and cross-culture ordering assertions. No v3 artifact,
  host contact, v2 retry, cleanup, deployment, or live-data access occurred.
- **2026-10-08:** Recorded the second v3 candidate review FAIL and the user's
  explicit one-more-remediation exception. Preserved an existing zero-byte log as
  present through an explicit snapshot wrapper, rejected Windows
  case-insensitive relative-path collisions before manifest publication, and added
  synthetic empty/missing and Linux collision assertions while retaining ordinal
  canonical sorting. The candidate-only boundary is unchanged; no package/ZIP,
  workstation contact, execution, cleanup, push, deployment, or clinical-data
  access occurred.
- **2026-10-08:** After independent PASS and user `go`, recorded authoritative
  CPython 3.11.9/WiX 3.14 `/log <path>` source evidence and explicit-log behavior.
  Added a candidate-only create-suspended/Job-Object synthetic containment probe
  plus an offline contract check and fixed acceptance matrix. Read-only presence
  discovery found no registered non-clinic Windows target, so no execution approval
  can yet be requested. No v3 manifest/ZIP, transfer, Windows execution, installer
  run, host cleanup, push, deployment, or live/clinical access occurred.
- **2026-10-08:** Recorded independent FAIL of the first Job Object candidate and
  completed the single bounded candidate-only remediation. Added original-process
  exit-code and exact marker proof, a nonzero-before-marker future worker, checked
  native terminate/wait/job-empty cleanup with handle retention, exact temp-root
  cleanup before success, and a closed fixed-reason success/failure envelope.
  Linux-safe tests exercise the wrong-platform failure envelope and structural
  guarantees only. No Windows native execution, manifest/ZIP, transfer, host
  contact/cleanup, push, merge, deployment, or live/clinical access occurred.
- **2026-10-08:** Recorded final independent PASS of the bounded containment
  remediation and the user's subsequent candidate-only execution approval for the
  designated non-clinic `winbox`/`zin` label. Local and Gateway read-only SSH
  context checks found no fixed alias, dedicated identity, or pinned host key, and
  presence listed no device. The gate therefore stopped before connection; no host
  authentication, transfer, staging, Windows/Sandbox execution, cleanup, package,
  push, merge, deployment, or live/clinical access occurred.
- **2026-10-08:** Reconciled the user's clarified `YHSHFM`/`yhshfm`/Windows/
  `leejs`/owner-`zin` tuple with central inventory. A local-only `ssh -G` check
  proved that the locked context still lacks the required exact account, dedicated
  identity, non-interactive settings, and independently verified pinned host key.
  The gate remains blocked before connection; no authentication, host command,
  transfer, Windows/Sandbox execution, packaging, cleanup, push, deployment, or
  clinical-data access occurred.
- **2026-10-08:** Recorded the user's explicit plan change selecting YHSHFM as the
  Sandbox host because no distinct Windows host is available. The exception allows
  only a no-change read-only preflight at this gate and never authorizes contact
  with the live checkout, data, services, or clinical workflow. Local-only SSH
  resolution still lacked the dedicated identity, non-interactive options, and
  independently pinned host key, so no authentication, host command, transfer,
  staging, Windows/Sandbox execution, packaging, cleanup, push, deployment, or
  clinical-data access occurred.
- **2026-10-08:** Recorded the user's replacement of the SSH-first observation path
  with a future YHSHFM Windows Hub/OpenClaw node. Fixed the initial allowlist to
  `device.info`, `device.status`, and `system.which`; explicitly denied command,
  file, control, sensor, screen, and live-clinic surfaces; and separated node
  observation from Sandbox containment. Pairing, installation, setup-code handling,
  host contact, file transfer, testing, cleanup, and deployment did not occur.
- **2026-10-08:** Recorded independent PASS for orchestration commit `e3126870`,
  which activates the H4 loopback-only Gateway through supervised tailnet-only
  HTTPS/WSS Serve with token authentication, `allowTailscale=false`, no Funnel, and
  observation-only node deny policy. H4 had zero devices, nodes, and pending
  requests. Fixed the remaining local-install/exact-ID admission gate and the
  requirement that `nodes describe` expose exactly the three approved observation
  commands. No YHSHFM contact, installation, pairing, command, transfer, test,
  cleanup, or deployment occurred.
