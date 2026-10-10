# Independent Current-Day Complete-Order Parity

Date: 2026-10-10. Synthetic model and memory collection only. No source operation,
wire format, persistence, session connection or runtime activation.

## Reviewed References

- Sender started on clean `main` at
  `fa238a2e4a9b6b48fa49f3f5d9ac847c54b67368`, origin
  `https://github.com/zinsss/KaosEghis.git`.
- Sender Orders documentation checkpoint:
  `5fc962e9867e0692eb36701fd853c6b76a21f8da`.
- Receiver was reviewed in a separate clean, temporary detached checkout at
  `0f3b8c13e77b03994d66da7e8d5a7414e035a3ea`, origin
  `https://github.com/zinsss/KaosOrders.git`. The receiver repository and services
  were not modified.
- Reviewed receiver `app/current_day_orders_shadow.py`, its focused tests,
  `docs/current-day-orders-model.md`, `docs/current-day-memory-design.md` and
  `docs/privacy.md`.

## Identity And Field Agreement

| Item | Independent sender decision matching the receiver |
| --- | --- |
| Contract / version | `kaosorders.current-day-orders` / `1` |
| Projection / timezone | `kaosorders-current-day-orders-v1` / `Asia/Seoul` |
| Production mapping revision | Unassigned and unapproved; no default field |
| Parent identity | Exact nonblank encounter ID, at most 128 code points |
| Parent states | REGISTERED, IN_PROGRESS, ON_HOLD, CONSULTATION_COMPLETED, PAYMENT_COMPLETED, CANCELLED |
| Order identity | Encounter ID, exact date, order number, order sequence; all four parts |
| `catalog_code`, `user_code` | Required fields; explicit NULL or exact text, at most 128 code points |
| `catalog_name`, `user_name` | Required fields; explicit NULL or exact text, at most 256 code points |
| `order_type`, `department_code` | Required fields; explicit NULL or exact text, at most 128 code points |
| Order state | Typed ACTIVE or CANCELLED; not inferred from qualifiers |
| `dc_yn`, `act_yn` | Required strict typed Y/N facts; no inferred meaning |
| `daily_quantity`, `frequency_count`, `day_count` | Required, independent explicit NULL or exact finite Decimal; integer digits <= 18 and scale <= 12 |
| Excluded facts | No hold_opd, demographics, notes, insurance, units, display/category decisions, PACS fields, delivery cursors or payload |

Text preserves NULL, empty, spaces, padding and distinct Unicode sequences. No
trim, normalization, fallback, translation or substitution. Control/format,
surrogate and line/paragraph-separator characters are rejected. Keys cannot be
blank or padded. Date values are exact `date`, not datetime or string coercions.
Unknown fields are rejected rather than retained.

The sender holds native immutable Decimal values. The receiver wraps the same
sign/digits/exponent representation in `SyntheticExactDecimal`. This is a local
implementation difference, not a policy difference or an agreed wire encoding.
Compatibility compares `Decimal.as_tuple()`, not ordinary numeric equality:
`1.0` differs from `1.00`; `0` differs from `-0`. Order equality, hashing and
same-key replacement preserve those distinctions.

No string/int/bool/float coercion, arithmetic, multiplication, rounding, quantize,
default, unit or cross-field derivation is performed. Numeric limits use the
receiver's exact tuple rule: `max(len(digits) + exponent, 0) <= 18` and
`max(-exponent, 0) <= 12`, including zero. Thus `0E+17` is accepted while `0E+18`
and `0E-13` are rejected. Negative values are structurally accepted in synthetic
tests, not approved as clinically meaningful source values.

## Collection And Failure Semantics

`KaosEghis/core/emr_current_day_orders_shadow.py` is independent of receiver code,
old source models and all runtime modules. Construction requires literal
`synthetic_fixture=True`. Collections use one explicit synthetic day, without a
wall clock, midnight timer, session, generation, revision or source reader.

- Retain all non-cancelled parents, including no-order parents and both distinct
  consultation-completed and payment-completed states.
- Retain every child of included parents, including active/cancelled, fee and
  unclassified children. No type, department or billing filter is applied.
- Exclude cancelled parents and their children; restored parents can reappear.
- Validate every input before filtering, including excluded children. Reject
  duplicates, orphans and caps above 10,000 parents / 100,000 children.
- Sort parents by identity and children by the complete four-part identity.
- Compare complete facts; same-key text/numeric edits replace the complete fact.
  Key reuse, disappearance and reappearance are set observations, not inferred
  clinical cancellation/restoration events or event times.
- Build and validate a detached candidate before atomic in-memory replacement.
  Rejected inputs preserve accepted state. Returned inspection objects are also
  detached. Representations and validation reasons do not include fact values.
- Initial `None` means unavailable; an explicitly constructed empty synthetic
  collection is distinct. Failure/partial/timeout/unavailable/unverified result
  objects are not accepted as collections and cannot clear prior state.

This API accepts caller-supplied **complete synthetic inputs only**. It cannot
prove that arbitrary empty tuples or caller-selected parents came from a verified
production read. Future source authority/completeness and current-KST-day/session
fences remain separate requirements. A synthetic child with a different order
date tests four-part identity only; it does not authorize historical EMR reads or
establish production child-date boundaries.

## Independent Compatibility Method

`tests/current_day_orders_contract_cases.py` contains reusable synthetic
known-answer cases, not canonical payloads or a wire fixture. The sender fixture
in `tests/test_emr_current_day_orders_shadow.py` runs them against sender classes.
No sender module or committed test imports receiver code.

The same cases were copied to an external temporary test directory and executed
in a separate receiver-side Python process against the exact detached reference.
Its test-only facade mapped these public entry points:

| Sender facade | Receiver entry point |
| --- | --- |
| `SyntheticEncounter` | `SyntheticEncounterContext` |
| `SyntheticOrderKey` | `SyntheticCurrentDayOrderKey` |
| `SyntheticOrder` | `SyntheticCurrentDayOrder` |
| `SyntheticCollectionMemory` | `SyntheticCurrentDayCollectionMemory` |
| `build_synthetic_collection` | `build_synthetic_current_day_collection` |
| `compare_synthetic_collections` | `compare_synthetic_current_day_collections` |

The facade wraps only actual Decimal arguments through receiver
`SyntheticExactDecimal.from_decimal(..., synthetic_fixture=True)`; NULL, missing
fields and invalid input types remain unchanged. Receiver numeric observations
use `.value.as_tuple()`. Remaining enums, context, qualifier and error classes use
their receiver equivalents. No validators are weakened, no foreign class is
passed to the sender, and no cross-repository Python class identity is compared.

Both independent implementations compare against the same primitive expected
enum values, four-part keys, complete facts and exact decimal tuples. Coverage
includes NULL/scale/signed zero/bounds, invalid types, all retained flags, full
parent/child scope, edits/reuse/absence/return, duplicate/orphan/overflow,
redaction, detached state and preservation after rejection. These are behavioral
results, not wire/JSON/hash parity claims.

## Verification

- Sender focused model and dependency tests: **340 passed**.
- Exact receiver, same independent known-answer cases: **339 passed**.
- Source/shadow/shared-reader/PACS/flu/patient-context/order-text/outbox regression
  group: **3,172 passed**.
- Full isolated sender suite: **4,972 passed, 26 failed** in 183.77 seconds.
- An unchanged archive of starting commit `fa238a2` reproduced all 26 failures
  while running `test_vaccine_label.py` and `test_vaccine_shortcuts.py`:
  **258 passed, 26 failed**. Comparing JUnit failure identities found zero
  differences. These are the existing 24 label font/ink and two shortcut layout
  failures, not new model regressions; no UI code or assertion was changed.

Sender tests use the repository's blocked-network/mock-database/isolated-mutex
configuration and a temporary data directory. The separate receiver process
blocks network resolution and connection and imports only the pure model, not
receiver application settings or runtime. No live EMR/DB/API operation occurred.
The receiver checkout remains unchanged. Existing v1/v2, order-text proof,
fixture/hash/store, serializer/outbox, reader and runtime files remain unchanged.

Sender focused command: `python -m pytest tests/test_emr_current_day_orders_shadow.py -q --tb=short`.
The regression group selected `test_*.py` filenames matching
`source|shadow|eghis_db|emr_read|pacs|flu|patient_context|order_text|outbox`.
Full-suite command: `python -m pytest -q --tb=short`. Each process used an isolated
temporary `KAOSEGHIS_DATA_DIR`; UI tests used `QT_QPA_PLATFORM=offscreen` and
`__COMPAT_LAYER=RunAsInvoker`. Test reports stayed in temporary directories and
are not committed.

## Gates And Next Receiver Handoff

All [source-evidence gates](kaoseghis-source-evidence-gates.md) remain unresolved:
authoritative current-day membership; save/child consistency; verified-empty
authority; complete reception/retained-qualifier mapping without hold_opd;
all-category cancellation/deletion/restoration/key reuse; safe demographic
derivation; least privilege; order-text coverage/content safety. The limited
qty/divide/days observations do not approve all-category numeric mapping,
NULL/domain/scale, negative-value validity or units. Synthetic validation resolves
none of these source gates. `EghisSourceDayReader` remains UNAVAILABLE.

Next, pin the completed sender commit and receiver `0f3b8c13e77b03994d66da7e8d5a7414e035a3ea`.
Re-run the shared known-answer cases in the receiver's own test facade and record
the local Decimal/wrapper distinction. Then review **design only** for a separate
volatile session boundary around this complete-order model: explicit full-read
success versus failure, current KST day/generation recheck, fresh full snapshot
after restart/rollover, and preservation of valid same-day state after rejection.
Do not silently reuse the old v2 fact identity, source_epoch/revision semantics or
modify its coordinator to accept this model.

That handoff does not authorize a wire parser/serializer/canonical fixture,
session implementation, source SQL/live access, HTTP/auth/token, transport,
publisher/retry worker, durable storage, settings/triggers, board/PACS changes,
deployment or service restart. No endpoint or production mapping is approved.
Never send normalized-source data to `/api/v1/order-snapshots`.
