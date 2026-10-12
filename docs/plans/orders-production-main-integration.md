# Orders production integration on `origin/main`

Status: approved mapping implemented on the feature branch. Runtime transport remains disabled.

## Base and preservation

- Base: `origin/main` at `1a96baf818f624d26217fd9fb36c053ebc01d4f2`.
- Working branch: `feature/orders-production-reader`.
- The existing `build/eghis-9992d13-win311-v4` checkout and its uncommitted
  Windows Sandbox changes are intentionally untouched.
- Do not merge the 80-commit branch wholesale.

## Change selection

Reimplement or selectively port only these product concerns:

1. bounded current-day reception/order read;
2. verified read-only connection and physical-close proof;
3. EGHIS source-row to current-day Orders mapping;
4. closed canonical schema validation;
5. fail-closed runtime boundary and privacy-safe counters;
6. synthetic, contract, boundary and Windows tests.

Exclude from this branch:

- evidence-window approvals and run artifacts;
- Windows Sandbox bundles and generated manifests;
- temporary observation-node documentation;
- synthetic HTTP runtime unless a production consumer needs the same boundary;
- historical gate-result documents that do not describe the final product.

## Approved production mapping

The owner approved mapping revision `eghis-current-day-orders-2026-10-12`:

- `proc_gb` 10/20/25/30/40/50 maps to REGISTERED, IN_PROGRESS,
  ON_HOLD, CONSULTATION_COMPLETED, PAYMENT_COMPLETED and CANCELLED;
- `hold_yn` is a strict Y/N validity gate and never remaps reception state;
- `dc_yn` Y maps to CANCELLED and N maps to ACTIVE; `act_yn` remains a
  strict retained Y/N fact;
- keys use lossless source text representation and the four-part child key;
- `qty`, `divide` and `days` retain exact Decimal sign/digits/exponent and NULL;
- only the current KST clinic day is accepted.

Any unmapped value, contradictory row, overflow, timeout, uncertain cleanup or
unverified empty result rejects the whole candidate snapshot. No row is dropped or
defaulted to obtain a valid result.

## Source evidence bound into the approval

Existing evidence supports the candidate source columns and these operator labels:

- `proc_gb=10`: registered/waiting;
- `proc_gb=20`: in consultation;
- `proc_gb=25`: on hold;
- `proc_gb=30`: consultation completed, before payment;
- `proc_gb=40`: payment completed;
- `proc_gb=50`: cancelled.

Unknown reception codes, invalid/NULL/blank retained flags, off-day children,
ambiguous rows and inconsistent results reject the whole snapshot. The excluded
`hold_opd` column is not read or used to resolve ambiguity.

## Merge-ready gates

1. Mapping revision approved and represented by closed tests.
2. Implementation and tests pass on H4 from this clean `origin/main` branch.
3. A fixed commit SHA passes isolated Windows tests on YHSHFM.
4. One approved read-only live transformation reports only aggregate counts and
   fixed error classes; no source rows, payloads, identifiers or patient data are
   printed or persisted.
5. Runtime sending stays off by default; no production deployment is part of the
   merge-preparation change.
6. Branch is clean and rebased or merged onto the then-current `origin/main`.
