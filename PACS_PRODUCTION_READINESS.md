# PACS Production Readiness

Last updated: 2026-06-29

## Current Milestone

KaosEghis-pacs has reached its first production-ready milestone for workstation-local PACS bridging.

Completed milestones:

- [x] Plugins UI
- [x] Local worklist
- [x] Read-only PostgreSQL adapter
- [x] Cancellation tracking
- [x] KaosPACS API bridge
- [x] Manual worklist editor
- [x] Auto polling
- [x] Reconciliation
- [x] PACS settings UI
- [x] Local audit

## Architecture Summary

KaosEghis-pacs operates as an EMR-side bridge:

- reads Eghis DB in read-only mode
- stores a minimal local SQLite worklist
- stores a minimal local PACS audit trail
- communicates outward only through the local KaosPACS API

KaosEghis-pacs does not:

- write directly to DICOM
- write directly to Orthanc
- write directly to MWL

## Deployment Assumptions

- single Windows workstation
- KaosPACS reachable on loopback or local network path configured by the operator
- local SQLite available in the KaosEghis data directory
- operator-driven desktop workflow

## Known Limitations

- Single workstation assumption
- No HA/failover
- No authentication layer between KaosEghis and local KaosPACS (loopback deployment)
- Future multi-site support
- Future queue monitoring
- Future performance metrics

## Safety Notes

- Eghis DB access is read-only
- startup validation does not poll, sync, or reconcile automatically
- KaosPACS sync is explicit/manual
- dry-run mode can keep poll live while simulating sync and reconcile
- audit uses sanitized summaries and sanitized error categories only

## Privacy Notes

KaosEghis-pacs keeps only the minimum local fields needed for worklist bridging:

- patient_name
- chart_no
- study
- modality
- requested_at
- accession_or_order_id
- status
- source
- sync state
- timestamps

It does not permanently store:

- resident registration number
- DOB
- sex
- phone
- address
- diagnosis
- EMR notes
- insurance information
- raw SQL result rows
- raw KaosPACS payloads
