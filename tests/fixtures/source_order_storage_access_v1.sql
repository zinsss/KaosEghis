WITH candidates AS (
    SELECT c.oid, c.relname,
        bool_or(a.attname = 'ord_ymd') AS has_day,
        bool_or(a.attname = 'ord_no') AS has_number,
        bool_or(a.attname = 'ord_seq_no') AS has_sequence,
        bool_or(a.attname = 'ord_cd') AS has_code
    FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace ns ON ns.oid = c.relnamespace
    JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid
    WHERE ns.nspname = %(schema)s AND c.relkind = 'r'
      AND a.attnum > 0 AND NOT a.attisdropped AND a.attname = ANY(%(columns)s)
    GROUP BY c.oid, c.relname
    HAVING bool_or(a.attname = 'recept_no') AND bool_or(a.attname IN ('ord_no', 'ord_cd'))
    ORDER BY c.relname
    LIMIT %(candidate_limit)s
), capabilities AS (
    SELECT relname = %(known_order)s AS known,
        has_table_privilege(oid, 'SELECT') AS table_select,
        has_any_column_privilege(oid, 'SELECT') AS any_select,
        has_column_privilege(oid, 'recept_no', 'SELECT') AS reception_select,
        has_day AND has_number AND has_sequence AS full_key,
        CASE WHEN has_day AND has_number AND has_sequence THEN
            has_column_privilege(oid, 'recept_no', 'SELECT')
            AND has_column_privilege(oid, 'ord_ymd', 'SELECT')
            AND has_column_privilege(oid, 'ord_no', 'SELECT')
            AND has_column_privilege(oid, 'ord_seq_no', 'SELECT') ELSE false END AS key_select,
        CASE WHEN has_code THEN has_column_privilege(oid, 'ord_cd', 'SELECT') ELSE false END AS code_select
    FROM candidates
), report AS (
    SELECT 'candidate_relations' AS metric, count(*) AS n FROM capabilities
    UNION ALL SELECT 'known_relations', count(*) FROM capabilities WHERE known
    UNION ALL SELECT 'known_table_select', count(*) FROM capabilities WHERE known AND table_select
    UNION ALL SELECT 'known_any_column_select', count(*) FROM capabilities WHERE known AND any_select
    UNION ALL SELECT 'other_relations', count(*) FROM capabilities WHERE NOT known
    UNION ALL SELECT 'other_table_select', count(*) FROM capabilities WHERE NOT known AND table_select
    UNION ALL SELECT 'other_any_column_select', count(*) FROM capabilities WHERE NOT known AND any_select
    UNION ALL SELECT 'other_reception_select', count(*) FROM capabilities WHERE NOT known AND reception_select
    UNION ALL SELECT 'other_four_part_keys', count(*) FROM capabilities WHERE NOT known AND full_key
    UNION ALL SELECT 'other_four_part_select', count(*) FROM capabilities WHERE NOT known AND key_select
    UNION ALL SELECT 'other_code_select', count(*) FROM capabilities WHERE NOT known AND code_select
)
SELECT metric, n FROM report ORDER BY metric
LIMIT 12
