# KaosOrders Signal Capture Plan

Last updated: 2026-09-10

## Status

KaosOrders is planned as a separate staff-facing order-board service. KaosEghis will
remain the eGHIS-side adapter: it observes configured eGHIS operator actions, reads
the database in read-only mode, and later publishes verified order state to KaosOrders.

The captured controls and timing below are planning data only. They do not enable a
runtime listener, change eGHIS, or post any patient/order data today.

## Verified eGHIS Action Targets

The following controls were captured from the current eGHIS `진료실` window. Their
common stable scope is:

```text
stackPanel1 (Pane)
  > eghisPanel2 (Pane)
  > 진료실 (Window)
  > 이지스 전자차트 2.0 (Window)
```

| Business action | Visible name | Shortcut | Automation ID | Control type |
| --- | --- | --- | --- | --- |
| Hold / temporary save | `임시저장(F6)` | `F6` | `BtnF6` | `Button` |
| Complete / send / confirm / print series | `완료(F7)` | `F7` | `BtnF7` | `Button` |

`F7` can drive a multi-stage eGHIS flow (send, confirmation, and prescription print),
so neither key nor button activation is evidence that a source order was successfully
saved. They are only triggers for later reconciliation.

## Chart-Number Snapshot

Before observing an F6/F7 action, the adapter should capture the currently displayed
chart number. The current operator layout has a chart-number coordinate fallback at
`(222, 115)`.

Coordinates are display/DPI/layout dependent and must stay editable configuration,
not a hard-coded identity. A verified UIA target for the chart number takes precedence
when one is available. The captured value is used only to scope the later read-only
query; it must not be placed in routine logs or a Raspberry Pi signal.

## Fixed Reconciliation Delay

For each chart number:

1. The first observed F6, F7, `BtnF6`, or `BtnF7` captures the chart number and starts
   one fixed 20-second timer.
2. Further F6/F7/button triggers for that same chart are ignored during that window;
   they do not reset the timer.
3. A different chart number receives its own independent 20-second timer.
4. At expiry, KaosEghis runs one narrow, read-only eGHIS query for that chart number
   and determines the actual current order/reception state.
5. Only that verified result may be published to the future KaosOrders service.

This allows the complete F7 send/confirm/print sequence to settle while preventing
duplicate database reads and duplicate downstream notifications.

## Source-State Rules

- F6 / `BtnF6` is an intent signal for an eGHIS `보류` workflow.
- F7 / `BtnF7` is an intent signal for a `완료` workflow.
- The source database query, not the UI signal, is authoritative.
- `보류` patients appear only when they have relevant verified categories.
- `취소` is a source cancellation and withdraws affected source orders.
- `완료` closes the eGHIS encounter; it must not be treated as imaging completion or
  source cancellation.

## Privacy and Integration Boundary

- KaosEghis reads eGHIS only with read-only access.
- The eventual Raspberry Pi receives a non-PHI reload signal and pulls only its
  transient worklist from KaosOrders.
- The Raspberry Pi does not store patient or order data.
- Routine diagnostics must not log patient name, chart number, resident ID, diagnosis,
  raw source rows, or complete order payloads.
- KaosOrders must not connect directly to eGHIS, KaosPACS, Orthanc, or DICOM services.

## Next Implementation Work

1. Add configurable F6/F7 and `BtnF6`/`BtnF7` signal targets to the future KaosOrders
   adapter.
2. Implement the chart-scoped fixed-delay queue with tests for deduplication and
   independent patients.
3. Verify the narrow read-only queries for `보류`, `완료`, and `취소` against the
   production eGHIS schema before creating any downstream worklist entries.
4. Define the authenticated, minimal KaosEghis-to-KaosOrders publish contract.
