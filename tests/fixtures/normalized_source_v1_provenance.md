# Normalized Source Fixture Provenance

Repository: `zinsss/KaosOrders`
Exact commit: `7c9275fb74680f46e4d459c821c7d501758c6b1c`
Copied from the same `tests/fixtures/` paths, without content changes.
Both files contain synthetic data only, not production rows or patient exports.

| File | Reference Git blob | Contract content SHA-256 |
| --- | --- | --- |
| `normalized_source_v1_full.json` | `794a11b1faa8e91282e9acd4f509f3c6a6aff1ce` | `4173c829519b0884a9cca0a7ee216ee8d6bfa05147427de1a16f638bf2c93030` |
| `normalized_source_v1_empty.json` | `12d3b9937bc9b9b2213830335a29f582083d6ac0` | `d286948d18b2e7b66f86f1a1b6c7931f58cd1753e8572e1338df85f1f37fecef` |

The digest covers canonical parsed JSON without `content_sha256`, not the file's
indentation or platform line endings. Git blob IDs above identify reference bytes.
Tests construct source facts separately and require exact parsed-object equality,
including nulls, ordering, decimal strings and the digest.

Reference files reviewed: `docs/normalized-source-contract-v1.md`,
`app/source_contract.py`, `app/source_shadow.py`, `tests/test_source_contract.py`
and `tests/test_source_reconciliation.py`. No receiver code is vendored or imported
by application runtime. This is offline draft parity, not an approved endpoint.
