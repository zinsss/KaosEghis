# Isolated Windows synthetic test environment

- **Status:** Host feature/reboot gates completed; exact offline synthetic-test
  bundle prepared in H4 and awaiting independent artifact review before the
  conditionally approved staging and interactive Sandbox run
- **Last updated:** 2026-10-08
- **Owning project:** KaosEghis
- **Affected projects:** KaosEghis, orchestration, clinic operations

## Context and safety boundary

KaosEghis needs a Windows-native full-suite result, but the available machine is
also a clinic workstation with a protected live checkout and interactive desktop
launcher. The test process must not see or mutate that checkout, EMR processes,
patient data, credentials, network services, printers, clipboard, or the host
interactive desktop. Administrator status is not a substitute for isolation.

Artifact preparation does not authorize workstation contact. The user's next-phase
approval permits staging and interactive Sandbox execution only after independent
review of the exact hashes, signature evidence, lock, configuration, runner, paths,
resource bounds, ACLs, retention, and return procedure recorded below. It never
permits host Python installation, another reboot, service/firewall changes,
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

The trusted development host prepared the following for independent review; none
has been transferred to the workstation:

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

### Exact downstream staging, launch, and return sequence

After independent review passes, the coordinator may perform only this sequence:

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

- Independent review must accept this exact commit plus the external ZIP hash,
  internal manifest, CPython evidence, dependency lock/custom pure wheels, `.wsb`,
  runner, staging/return scripts, paths, bounds, ACL, retention, and return process.
- The coordinator must select and record the actual closed-time 90-minute window
  and recheck the 20-GiB/12-GiB resource thresholds immediately before staging.
- Any artifact or procedure change invalidates the recorded hashes and requires a
  new bundle ID and review; never patch the staged package in place.
- The rejected `v1` identity and SHA-256 remain permanently prohibited; only the
  reviewed `v2` identity may advance.

After review passes, execute only the exact downstream sequence above. If review or
any host precondition fails, stop without transfer, extraction, Sandbox launch, or
test execution.

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
