# KaosEghis-scan

Last updated: 2026-07-21

## Purpose

`KaosEghis-scan` is a document-scanning plugin for KaosEghis. Its first implemented scope is deliberately small:

- acquire pages from a Canon DR-C125 scanner
- produce one PDF document per scan job
- place the completed PDF in a short-lived local spool
- display the completed PDF in KaosEghis when PDF preview support is available
- let the operator drag the PDF into a browser upload control or open its folder
- empty the dedicated temporary folder on a configurable minute interval

The scanner component is non-GUI. Operator controls live in the top-level `Scan` tab, while NAPS2 acquisition runs as an asynchronous console process.

## Ownership Boundary

### KaosEghis-scan owns

- Canon DR-C125 device discovery and acquisition
- scan-job state
- image-to-PDF assembly
- temporary local PDF storage
- PDF preview and native file drag-out
- opening the dedicated spool folder for manual browser upload
- privacy cleanup of the dedicated spool
- reporting scan and cleanup failures to KaosEghis

### The destination PACS/browser workflow owns

- accepting the operator's manual PDF upload
- PACS-side validation and durable storage
- conversion to an appropriate DICOM object if required
- association with the correct imaging/order lifecycle
- PACS audit and downstream forwarding

KaosEghis-scan must not upload to KaosPACS, Orthanc, MWL, or DICOM storage. A PDF being present in the spool means only that it is ready for the operator to upload manually; it does not mean the document has been accepted by PACS.

## Planned Flow

```text
Canon DR-C125
      |
      v
non-GUI scan service
      |
      v
temporary page files
      |
      v
assembled PDF in dedicated spool
      |
      +----> in-app preview
      |
      +----> native file drag to browser upload control
      |
      +----> View folder fallback
      |
      v
interval cleanup
```

Upload is fully manual. KaosEghis-scan does not call a PACS upload API, attach the document to a patient, or infer that a browser upload succeeded.

## Operator Surface

The implemented plugin surface contains:

- scan command and acquisition status
- list of completed PDFs in the `ready` spool
- selected-document PDF preview
- a fixed narrow file column beside a wide preview; there is no operator-resizable
  splitter because the preview is the primary working area
- a clear drag handle or draggable document row
- `View folder`
- `Delete selected`
- cleanup interval and status

For drag-out, the PySide6 UI starts a native `QDrag` carrying a local file URL in `QMimeData`. This allows compatible browser file-upload controls to receive the PDF as if it were dragged from File Explorer. Browser pages differ, so `View folder` remains the dependable fallback.

The application should use Qt PDF preview support when available. If PDF rendering support is unavailable, it should show file name, creation time, page count when known, and the open/drag controls without blocking scanning.

Dragging or opening a PDF must not delete it. A completed drag operation does not prove that the browser accepted or stored the document.

## Scanner Integration

The Canon DR-C125 is accessed through NAPS2 Console and its saved `Canon DR-C125 Native` profile. The tested profile uses the Canon TWAIN driver with Native Transfer because NAPS2 memory transfer returned `Invalid stride` with this scanner.

Current executable discovery checks the normal 64-bit and 32-bit NAPS2 installation directories, then the system path. The scan command uses the saved profile and does not use `--noprofile`.

Planned acquisition settings include:

- device identifier or configured scanner name
- simplex or duplex
- feeder use
- page size
- color mode
- resolution
- blank-page handling, if reliably supported

These settings must not be hard-coded to a workstation-specific device identifier. Device discovery failures should stop the scan job cleanly and leave no document marked ready for upload.

## PDF Spool

The spool is the dedicated `<KaosEghis data>/temp` directory, currently `E:\Kaos\KaosEghis\data\temp` on the configured workstation. It is not a general user Documents, Downloads, Desktop, or shared temporary folder.

Recommended properties:

- stable location below the configured KaosEghis data directory
- filenames formatted as `YYYYMMDDHHMM.pdf`
- no patient name, chart number, DOB, order description, or accession in filenames
- temporary extension while the PDF is being assembled
- atomic rename to `.pdf` only after PDF creation succeeds
- minimal sidecar metadata, if needed, stored locally and removed with the PDF

Current layout:

```text
<KaosEghis data>/temp/
  YYYYMMDDHHMM.pdf
```

Only completed `.pdf` files are shown for manual upload. An incomplete or failed scan is discarded and must never be exposed as draggable. A second scan in the same minute is blocked rather than overwriting the existing PDF.

## Cleanup and Privacy

Scanned documents may contain sensitive clinical and identifying information. Local PDF storage is temporary operational storage, not an archive.

Cleanup setting:

- `scan_cleanup_interval_minutes`, default `30`, allowed range `1` to `1440`

Cleanup rules:

- operate only inside the resolved dedicated scan spool
- verify the cleanup root before every deletion pass
- do not follow symbolic links, junctions, or reparse points outside the spool
- never delete a file belonging to an active scan job or currently open drag operation
- remove all direct files in the dedicated temporary folder at each timer interval
- allow the operator to run the same cleanup immediately with `Clean now`
- start the timer when the Scan tab is constructed; do not perform an immediate startup deletion
- restart the timer after a successful scan so a new PDF receives the full configured interval
- record only job ID, timestamps, outcome, and safe error category in cleanup logs
- do not log filenames if they could contain imported identifying text

The cleanup operation must be fail-closed: an unresolved or unexpected spool path means no deletion occurs. Cleanup failures should be visible to the operator because retained documents represent a privacy risk.

Secure erasure cannot be guaranteed on SSDs or all Windows filesystems. The design therefore minimizes retention and file duplication rather than claiming forensic secure deletion.

## Data Minimization

The scanner service should not embed patient information into the filename or PDF metadata. Scan jobs should use an opaque local job ID.

Do not persist or log:

- raw scanner images after PDF assembly
- patient name in filenames or logs
- resident registration number
- DOB or sex unless a future upload contract explicitly requires them
- phone, address, diagnosis, EMR notes, or insurance information
- browser credentials, cookies, or authentication tokens

Temporary page images should be removed as soon as PDF assembly succeeds or the job is abandoned.

## Reliability Rules

- one scan job controls the configured scanner at a time
- cancellation leaves no file marked ready
- PDF validation occurs before the job enters `ready`
- manual upload readiness is not treated as upload success
- cleanup, acquisition, preview, and file drag must not race on the same job
- application shutdown should close scanner resources and preserve only well-defined recoverable jobs
- a scanner or PDF failure must not affect PACS polling, macros, Flu-Report, or other plugins

## Proposed Job States

- `scanning`
- `assembling`
- `ready`
- `failed`
- `expired`

`expired` means the temporary local document was removed by privacy cleanup. It is not an imaging lifecycle state and must not be sent to KaosPACS as PACS expiry.

## Future Settings

- scanner device name or identifier
- scanner driver mode
- duplex mode
- color mode
- resolution
- PDF spool directory
- cleanup interval

No browser/PACS credential or scanner credential should be stored or displayed by the scan plugin.

## Initial Test Plan

- scanner service can be imported without opening a GUI
- missing scanner returns a controlled unavailable result
- successful multi-page acquisition produces one valid PDF
- incomplete jobs never enter the ready spool
- filenames and PDF metadata contain no patient identifiers
- ready PDF can be previewed when Qt PDF support is available
- ready PDF exposes a native local-file drag payload
- opening or dragging a PDF does not mark it uploaded or delete it
- cleanup ignores active scan jobs and active drag operations
- cleanup removes direct files when the configured timer fires
- cleanup never removes files outside the dedicated spool
- cleanup refuses an unresolved or unsafe spool path
- View folder resolves only to the dedicated temporary folder
- no direct Orthanc, MWL, or DICOM write exists

## Non-Goals for the First Milestone

- OCR
- document classification
- automatic patient matching
- PACS upload of any kind from KaosEghis-scan
- browser automation or automatic attachment to a patient
- direct Orthanc upload
- direct DICOM creation or transmission
- permanent document archive in KaosEghis
- broad scanner-vendor abstraction before the Canon DR-C125 path is proven
