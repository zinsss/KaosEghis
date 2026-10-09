# Eghis → KaosOrders Non-PHI Evidence Statements v1

- **Status:** review candidate; execution prohibited pending independent PASS
- **Date:** 2026-10-09
- **Owner:** KaosEghis
- **Affected projects:** KaosEghis, KaosOrders, orchestration, integration review
- **Normative protocol:** orchestration `e341737`

This document freezes the exact UTF-8/LF statement bytes for the first bounded
metadata-only evidence run. The digest of each statement covers every byte from
its `-- BEGIN` line through its `-- END` line, including the final LF. No other
statement, comment, session query, discovery query, or retry is in this inventory.

The statements return only allowlisted booleans and source metadata. They do not
read patient rows, source values, clinical text, demographics, identifiers, or
counts. They do not assign `source_id`, `mapping_revision`, or clinical meaning.

## `EKO-C00` — transaction control preamble

```sql
-- BEGIN EKO-C00
BEGIN TRANSACTION ISOLATION LEVEL REPEATABLE READ READ ONLY;
-- END EKO-C00
```

## `EKO-C01` — statement timeout

```sql
-- BEGIN EKO-C01
SET LOCAL statement_timeout = '1500ms';
-- END EKO-C01
```

## `EKO-C02` — lock timeout

```sql
-- BEGIN EKO-C02
SET LOCAL lock_timeout = '100ms';
-- END EKO-C02
```

## `EKO-C03` — idle transaction timeout

```sql
-- BEGIN EKO-C03
SET LOCAL idle_in_transaction_session_timeout = '5000ms';
-- END EKO-C03
```

## `EKO-P00` — least-privilege preflight

```sql
-- BEGIN EKO-P00
WITH target_relations(schema_name, relation_name) AS (
    VALUES
        ('public'::text, 'h1opdin'::text),
        ('public'::text, 'h2opd_doct_ord'::text),
        ('public'::text, 'hz_mst_ptnt'::text)
), relation_privileges AS (
    SELECT
        COUNT(c.oid) = 3 AS all_relations_present,
        BOOL_AND(COALESCE(has_table_privilege(current_user, c.oid, 'SELECT'), FALSE)) AS all_select,
        BOOL_AND(COALESCE(NOT has_table_privilege(current_user, c.oid, 'INSERT'), FALSE)) AS no_insert,
        BOOL_AND(COALESCE(NOT has_table_privilege(current_user, c.oid, 'UPDATE'), FALSE)) AS no_update,
        BOOL_AND(COALESCE(NOT has_table_privilege(current_user, c.oid, 'DELETE'), FALSE)) AS no_delete,
        BOOL_AND(COALESCE(NOT has_table_privilege(current_user, c.oid, 'TRUNCATE'), FALSE)) AS no_truncate,
        BOOL_AND(COALESCE(NOT has_table_privilege(current_user, c.oid, 'REFERENCES'), FALSE)) AS no_references,
        BOOL_AND(COALESCE(NOT has_table_privilege(current_user, c.oid, 'TRIGGER'), FALSE)) AS no_trigger
    FROM target_relations t
    LEFT JOIN pg_catalog.pg_namespace n ON n.nspname = t.schema_name
    LEFT JOIN pg_catalog.pg_class c
      ON c.relnamespace = n.oid
     AND c.relname = t.relation_name
     AND c.relkind IN ('r', 'p', 'v', 'm')
), non_system_function_execute AS (
    SELECT EXISTS (
        SELECT 1
        FROM pg_catalog.pg_proc p
        JOIN pg_catalog.pg_namespace n ON n.oid = p.pronamespace
        WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
          AND n.nspname !~ '^pg_toast'
          AND has_function_privilege(current_user, p.oid, 'EXECUTE')
    ) AS present
), non_system_relation_write AS (
    SELECT EXISTS (
        SELECT 1
        FROM pg_catalog.pg_class c
        JOIN pg_catalog.pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
          AND n.nspname !~ '^pg_toast'
          AND c.relkind IN ('r', 'p', 'v', 'm', 'f')
          AND (
              has_table_privilege(current_user, c.oid, 'INSERT')
              OR has_table_privilege(current_user, c.oid, 'UPDATE')
              OR has_table_privilege(current_user, c.oid, 'DELETE')
              OR has_table_privilege(current_user, c.oid, 'TRUNCATE')
              OR has_table_privilege(current_user, c.oid, 'REFERENCES')
              OR has_table_privilege(current_user, c.oid, 'TRIGGER')
          )
    ) AS present
), non_system_schema_create AS (
    SELECT EXISTS (
        SELECT 1
        FROM pg_catalog.pg_namespace n
        WHERE n.nspname NOT IN ('pg_catalog', 'information_schema')
          AND n.nspname !~ '^pg_toast'
          AND has_schema_privilege(current_user, n.oid, 'CREATE')
    ) AS present
)
SELECT
    current_setting('transaction_read_only') = 'on' AS transaction_read_only,
    r.all_relations_present,
    r.all_select,
    r.no_insert,
    r.no_update,
    r.no_delete,
    r.no_truncate,
    r.no_references,
    r.no_trigger,
    NOT has_database_privilege(current_user, current_database(), 'CREATE') AS no_database_create,
    NOT has_database_privilege(current_user, current_database(), 'TEMP') AS no_database_temp,
    NOT has_schema_privilege(current_user, 'public', 'CREATE') AS no_public_schema_create,
    NOT f.present AS no_non_system_function_execute,
    NOT w.present AS no_non_system_relation_write,
    NOT s.present AS no_non_system_schema_create
FROM relation_privileges r
CROSS JOIN non_system_function_execute f
CROSS JOIN non_system_relation_write w
CROSS JOIN non_system_schema_create s;
-- END EKO-P00
```

## `EKO-V01` — source database version class

```sql
-- BEGIN EKO-V01
SELECT current_setting('server_version_num') AS source_version_class;
-- END EKO-V01
```

## `EKO-M10` — closed candidate-column metadata

```sql
-- BEGIN EKO-M10
WITH target_columns(relation_id, relation_name, column_id, column_name) AS (
    VALUES
        ('PARENT'::text, 'h1opdin'::text, 'clinic_day'::text, 'clinic_ymd'::text),
        ('PARENT', 'h1opdin', 'encounter_key', 'recept_no'),
        ('PARENT', 'h1opdin', 'patient_join_key', 'ptnt_no'),
        ('PARENT', 'h1opdin', 'raw_state', 'proc_gb'),
        ('PARENT', 'h1opdin', 'hold_flag', 'hold_yn'),
        ('CHILD', 'h2opd_doct_ord', 'encounter_key', 'recept_no'),
        ('CHILD', 'h2opd_doct_ord', 'order_day', 'ord_ymd'),
        ('CHILD', 'h2opd_doct_ord', 'order_number', 'ord_no'),
        ('CHILD', 'h2opd_doct_ord', 'order_sequence', 'ord_seq_no'),
        ('CHILD', 'h2opd_doct_ord', 'catalog_code', 'ord_cd'),
        ('CHILD', 'h2opd_doct_ord', 'catalog_name', 'medfee_nm'),
        ('CHILD', 'h2opd_doct_ord', 'user_code', 'user_cd'),
        ('CHILD', 'h2opd_doct_ord', 'user_name', 'user_nm'),
        ('CHILD', 'h2opd_doct_ord', 'order_type', 'ord_type'),
        ('CHILD', 'h2opd_doct_ord', 'department_code', 'proc_dept_cd'),
        ('CHILD', 'h2opd_doct_ord', 'cancel_flag', 'dc_yn'),
        ('CHILD', 'h2opd_doct_ord', 'activity_flag', 'act_yn'),
        ('PATIENT', 'hz_mst_ptnt', 'patient_join_key', 'ptnt_no'),
        ('PATIENT', 'hz_mst_ptnt', 'patient_name_candidate', 'ptnt_nm')
)
SELECT
    t.relation_id,
    t.column_id,
    a.attnum IS NOT NULL AS column_present,
    CASE WHEN a.attnum IS NULL THEN NULL ELSE pg_catalog.format_type(a.atttypid, a.atttypmod) END AS data_type,
    CASE WHEN a.attnum IS NULL THEN NULL ELSE NOT a.attnotnull END AS nullable,
    CASE WHEN a.attnum IS NULL THEN NULL ELSE a.attgenerated <> '' END AS generated,
    CASE WHEN a.attnum IS NULL THEN NULL ELSE a.attidentity <> '' END AS identity
FROM target_columns t
LEFT JOIN pg_catalog.pg_namespace n ON n.nspname = 'public'
LEFT JOIN pg_catalog.pg_class c
  ON c.relnamespace = n.oid
 AND c.relname = t.relation_name
 AND c.relkind IN ('r', 'p', 'v', 'm')
LEFT JOIN pg_catalog.pg_attribute a
  ON a.attrelid = c.oid
 AND a.attname = t.column_name
 AND a.attnum > 0
 AND NOT a.attisdropped
ORDER BY t.relation_id COLLATE "C", t.column_id COLLATE "C";
-- END EKO-M10
```

## `EKO-K20` — closed key/index metadata

```sql
-- BEGIN EKO-K20
WITH target_keys(relation_id, relation_name, key_id, key_columns) AS (
    VALUES
        ('PARENT'::text, 'h1opdin'::text, 'encounter_key'::text,
         ARRAY['recept_no']::text[]),
        ('CHILD', 'h2opd_doct_ord', 'four_part_key',
         ARRAY['recept_no', 'ord_ymd', 'ord_no', 'ord_seq_no']::text[]),
        ('PATIENT', 'hz_mst_ptnt', 'patient_join_key',
         ARRAY['ptnt_no']::text[])
)
SELECT
    t.relation_id,
    t.key_id,
    COALESCE(x.matching_index_count, 0) AS matching_index_count,
    COALESCE(x.any_unique, FALSE) AS any_unique,
    COALESCE(x.any_primary, FALSE) AS any_primary,
    COALESCE(x.all_valid, FALSE) AS all_valid,
    COALESCE(x.all_ready, FALSE) AS all_ready,
    x.single_index_method
FROM target_keys t
LEFT JOIN LATERAL (
    SELECT
        COUNT(*)::integer AS matching_index_count,
        BOOL_OR(i.indisunique) AS any_unique,
        BOOL_OR(i.indisprimary) AS any_primary,
        BOOL_AND(i.indisvalid) AS all_valid,
        BOOL_AND(i.indisready) AS all_ready,
        CASE WHEN COUNT(DISTINCT am.amname::text) = 1 THEN MIN(am.amname::text) ELSE NULL END AS single_index_method
    FROM pg_catalog.pg_namespace n
    JOIN pg_catalog.pg_class c
      ON c.relnamespace = n.oid
     AND c.relname = t.relation_name
     AND c.relkind IN ('r', 'p')
    JOIN pg_catalog.pg_index i ON i.indrelid = c.oid
    JOIN pg_catalog.pg_class ic ON ic.oid = i.indexrelid
    JOIN pg_catalog.pg_am am ON am.oid = ic.relam
    WHERE n.nspname = 'public'
      AND i.indexprs IS NULL
      AND i.indpred IS NULL
      AND ARRAY(
          SELECT a.attname::text
          FROM unnest(i.indkey) WITH ORDINALITY AS k(attnum, ordinality)
          JOIN pg_catalog.pg_attribute a
            ON a.attrelid = c.oid
           AND a.attnum = k.attnum
          WHERE k.ordinality <= i.indnkeyatts
          ORDER BY k.ordinality
      ) = t.key_columns
) x ON TRUE
ORDER BY t.relation_id COLLATE "C", t.key_id COLLATE "C";
-- END EKO-K20
```

## `EKO-C99` — mandatory rollback

```sql
-- BEGIN EKO-C99
ROLLBACK;
-- END EKO-C99
```

## Change history

- **2026-10-09:** Froze five transaction-control statements and four metadata-only
  evidence statements for independent
  review. No statement was executed and no source, credential, host, row, value,
  runtime, mapping identity, or deployment was accessed or changed.
- **2026-10-09:** Confirmed during Orders review remediation that the frozen
  `EKO-K20` SELECT returns exactly eight allowlisted columns. Statement bytes and
  all nine SHA-256 values are unchanged; only the owning package schema and pure
  injected validator were corrected to match them.
