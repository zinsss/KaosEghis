# Isolated Windows synthetic test environment

- **Status:** First host-change step completed and post-checked; one bounded reboot
  is approved for the current closed-time window but not executed by this worker;
  bundle, runtime, and test execution remain unapproved
- **Last updated:** 2026-10-08
- **Owning project:** KaosEghis
- **Affected projects:** KaosEghis, orchestration, clinic operations

## Context and safety boundary

KaosEghis needs a Windows-native full-suite result, but the available machine is
also a clinic workstation with a protected live checkout and interactive desktop
launcher. The test process must not see or mutate that checkout, EMR processes,
patient data, credentials, network services, printers, clipboard, or the host
interactive desktop. Administrator status is not a substitute for isolation.

Except for the bounded coordinator step below, this plan does not authorize SSH
use, software installation, optional-feature changes, service/firewall changes,
test execution, or deployment. Never run `main.py`, repository tools/probes, or a
production reader in this gate.

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
  `RestartNeeded=true`, establishing the bounded reboot gate now approved below;
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

### Approved reboot and post-reboot gate

The user approved one coordinator-driven reboot of the expected workstation during
the current closed-time window. Before reboot, the coordinator must fail closed
unless computer name, signed-in account, administrator role, and Sandbox feature
state are exactly the reviewed values. It records the pre-reboot boot timestamp in
coordinator memory, invokes only a local ordinary `Restart-Computer`, and performs
no force, remote target, staging, install, launch, test, service, firewall, or live
checkout command.

The coordinator waits for the existing SSH endpoint to disconnect and return within
a bounded 15-minute window. On return, a read-only PowerShell post-check must:

1. revalidate expected computer, account, and administrator role;
2. prove `LastBootUpTime` is later than the recorded pre-reboot value;
3. require `Containers-DisposableClientVM` state exactly `Enabled`, not
   `EnablePending`; and
4. report only fixed booleans for Component Based Servicing reboot pending, Windows
   Update reboot required, and pending file-rename operations, plus their composite
   pending-restart result. It must not output registry values.

Any context mismatch, missing disconnect, SSH timeout, unchanged boot timestamp,
non-`Enabled` feature state, or remaining pending-restart indicator stops the
workflow. No artifact, child directory, Sandbox launch, runtime, or test step is
authorized by successful reboot verification. This Eghis worker supplies the
procedure only and does not contact or reboot the workstation.

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

Proposed non-live staging root:

```text
C:\KaosClinic-Test\Eghis\
  Inbound\<bundle-id>\
  Results\<run-id>\
```

The staging root must be newly created with an ACL limited to the approving
administrator and SYSTEM. It must not be under, linked to, or populated from the
live checkout.

Prepare the following on a trusted development/build host, then transfer them only
after separate approval:

1. an independent Git bundle containing the exact reviewed commit and its history;
2. a source archive produced from that commit, plus `SOURCE_COMMIT.txt` and a
   SHA-256 manifest for every archive file;
3. an official offline CPython 3.11 installer and recorded publisher/hash;
4. a Windows CPython-3.11 wheelhouse and hash-locked requirements file; and
5. a reviewed Sandbox `.wsb` file and runner script.

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

## Sandbox configuration

The reviewed `.wsb` configuration should enforce the equivalent of:

```xml
<Configuration>
  <Networking>Disable</Networking>
  <PrinterRedirection>Disable</PrinterRedirection>
  <ClipboardRedirection>Disable</ClipboardRedirection>
  <AudioInput>Disable</AudioInput>
  <VideoInput>Disable</VideoInput>
  <VGpu>Disable</VGpu>
  <ProtectedClient>Enable</ProtectedClient>
  <MemoryInMB>8192</MemoryInMB>
  <!-- Map only Inbound read-only and the new Results\run-id writable. -->
</Configuration>
```

The exact mapped-folder XML and runner path must be generated for the approved
run ID and reviewed before launch. The writable results folder must be empty at
start. No parent test directory, user profile, drive root, live checkout, `%APPDATA%`,
`%LOCALAPPDATA%`, SSH material, or credential store is mapped.

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

Before this block, the runner must verify the source and dependency manifests,
create every redirected directory, confirm the results directory is empty, record
`python --version`, `pip check`, and the frozen package inventory, and inspect the
Sandbox adapter/route state without making an external connectivity probe. The
final report must record pass/fail/skip counts and fixed failure summaries without
clinical or credential content; network isolation is recorded only as a fixed
boolean, not raw addresses or routes. Do not add `--noconftest`; the repository
safety fixtures are required. Do not run tests directly from an SSH shell on the
host.

## Execution gates and operations

Even with isolation, the run can consume CPU, memory, and disk on a clinic machine.
Execution therefore requires all of the following:

1. user approval for the exact source commit, Python installer, hash lock,
   PyAutoGUI test-only decision, `.wsb`, runner, mapped paths, and result retention;
2. coordinator completion of the now-approved bounded reboot and the exact
   read-only post-reboot gate above;
3. an operator-approved maintenance window with the live app left untouched and
   no clinical workflow depending on workstation resources;
4. an interactive operator launch of the reviewed `.wsb`; do not attempt to drive
   Windows Sandbox invisibly from the SSH session; and
5. post-run review that results contain only synthetic test names/counts and fixed
   errors before they leave the workstation.

No test result authorizes runtime activation, source access, printing, endpoint
binding, firewall change, credential provisioning, deployment, or use of the live
checkout.

## Rollback and removal

Closing Windows Sandbox destroys its Python install, venv, copied source, temp
files, synthetic databases, process state, and test-local credentials. After result
review and retention approval, remove only the explicit run directory and inbound
bundle beneath `C:\KaosClinic-Test\Eghis`; never use a drive-root target, wildcard,
junction-following deletion, or the live path. Record the exact deleted paths and
whether the retained JUnit/inventory artifacts were archived or removed.

Do not disable Windows Sandbox automatically after the run. Optional-feature
rollback and any reboot beyond the single currently approved reboot require a
separate operator decision because they are host changes. If setup fails before
isolation is proven, remove the new staging run only and report blocked; do not fall
back to host pytest.

## Open decisions and next action

- Execute only the approved bounded reboot procedure, then stop unless the exact
  read-only post-reboot gate succeeds and reports no remaining pending restart.
- Separately approve the exact `.wsb` configuration and a later Sandbox launch,
  or provide a non-production Windows VM/host.
- Approve the official CPython 3.11.9 x64 installer, publisher, and SHA-256.
- Resolve and approve the explicit hash-pinned PyAutoGUI test dependency.
- Approve the maintenance window, resource budget, host staging/results ACLs,
  result retention, and post-reboot validation procedure.
- Approve a later transfer/staging action; established SSH access alone does not
  authorize transfer, launch, installation, or execution.

After those decisions, prepare the offline bundle and submit its manifests, `.wsb`,
and runner for review. Only a subsequent explicit execution approval may stage or
launch it.

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
