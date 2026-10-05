# Normalized Source V2 Fixture Provenance

Synthetic-only sender fixtures created on 2026-10-05. No production data, source
rows, live reads, ordering allocation or patient export was used.

Receiver planning reference: `zinsss/KaosOrders`
`6837845fc4c691075bab41c6e07ef69e8562580b`,
`docs/normalized-source-contract-v2-plan.md`.
Sender starting point: `51d7601327ab4db58155960b8e0be75ea029e43f`.
The receiver has agreed the projection but has not independently parsed these
new fixtures yet. These are sender golden candidates, not completed cross-repo parity.

Identity: `kaosorders.normalized-source`, version `2`, projection
`kaosorders-all-orders-v2`, mapping `synthetic-v2`. No production mapping is approved.

| Fixture | Contract content SHA-256 |
| --- | --- |
| `normalized_source_v2_full.json` | `a6b7e348c734c7af4c1f7467e0f66ec84dfaa4904fe53d53a1a389ddc9b17c2d` |
| `normalized_source_v2_empty.json` | `f03a8a244b8c3d324d6011d0c15f49c49ce2567872665ba1e4e1efb8413daf16` |

Files contain canonical compact, sorted-key, Unicode-preserving UTF-8 JSON plus
one LF and no BOM. The scoped `.gitattributes` pins LF. The content digest excludes
`content_sha256` and the file's final LF. Whole-file SHA-256 values are:

- Full: `fa7761900c9e5209ac00d191ea15a2804855247e45cfa446d86f2c71162ad474`
- Empty: `33cdadbb1fb2841bfec6e6b38a4a2b7dd817da995fd6e989b6caca15ee52aad1`

The illustrative six encounters and first four orders derive from the existing
synthetic v1 fixture scenarios originally supplied by KaosOrders at
`7c9275fb74680f46e4d459c821c7d501758c6b1c`. V1 fixtures remain unchanged.
V2 uses fresh synthetic batch IDs, a new version/projection/mapping identity,
qualifiers containing only `hold_yn`, and an additional unclassified order with
exact-decimal examples. No raw excluded value is retained in these fixtures.
This one-time synthetic fixture preparation is not an application v1-to-v2 adapter.
Tests independently construct v2 source aliases, normalize and serialize them,
and assert both parsed equality and exact canonical file bytes.

Full: six encounters covering every normalized reception state and five orders;
no-order encounters, cancelled parent with active child, cancelled child, fee and
unclassified rows are retained. Empty: a separate synthetic day with explicit
complete-read assertions, no encounters and no orders. These fixture dates are
not assertions about clinic activity on those dates.

`O` sex is a synthetic contract-domain example inherited from v1, not approval of
an EMR source mapping. Null demographics remain null. Values have no inferred
clinical units. The stricter sender decimal limits remain sender limits pending
receiver agreement; fixture acceptance alone does not establish those as contract
requirements. No field except `observed_at` is an observation timestamp, and none
is a clinical edit, cancellation, payment, administration or examination time.

Next: KaosOrders independently implement its separate pure v2 parser and verify
these exact bytes/hashes before any v2 persistence proof. Keep v1 stores, outbox,
receipts, fixtures and validators unchanged. No endpoint or token is approved;
`/api/v1/order-snapshots` remains prohibited for this payload.
