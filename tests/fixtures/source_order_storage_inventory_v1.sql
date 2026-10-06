WITH profiles AS (
    SELECT c.oid, c.relname, c.relkind,
        max(CASE WHEN a.attname = 'recept_no' THEN
            CASE WHEN t.typname = ANY(%(types)s) THEN t.typname ELSE 'UNREVIEWED' END END) AS reception_type,
        max(CASE WHEN a.attname = 'ord_ymd' THEN
            CASE WHEN t.typname = ANY(%(types)s) THEN t.typname ELSE 'UNREVIEWED' END END) AS date_type,
        max(CASE WHEN a.attname = 'ord_no' THEN
            CASE WHEN t.typname = ANY(%(types)s) THEN t.typname ELSE 'UNREVIEWED' END END) AS number_type,
        max(CASE WHEN a.attname = 'ord_seq_no' THEN
            CASE WHEN t.typname = ANY(%(types)s) THEN t.typname ELSE 'UNREVIEWED' END END) AS sequence_type,
        max(CASE WHEN a.attname = 'ord_cd' THEN
            CASE WHEN t.typname = ANY(%(types)s) THEN t.typname ELSE 'UNREVIEWED' END END) AS code_type
    FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace ns ON ns.oid = c.relnamespace
    JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid
    JOIN pg_catalog.pg_type t ON t.oid = a.atttypid
    WHERE ns.nspname = %(schema)s AND c.relkind = 'r'
      AND a.attnum > 0 AND NOT a.attisdropped AND a.attname = ANY(%(columns)s)
    GROUP BY c.oid, c.relname, c.relkind
    HAVING bool_or(a.attname = 'recept_no')
       AND bool_or(a.attname IN ('ord_no', 'ord_cd'))
    ORDER BY c.relname
    LIMIT %(candidate_limit)s
), classified AS (
    SELECT *, relname ~ %(name_pattern)s AS name_reviewed,
        NOT ('UNREVIEWED' = ANY(ARRAY[reception_type, coalesce(date_type, 'MISSING'),
            coalesce(number_type, 'MISSING'), coalesce(sequence_type, 'MISSING'),
            coalesce(code_type, 'MISSING')])) AS types_reviewed
    FROM profiles
), report AS (
    SELECT 'summary'::text AS section, 'total_candidates'::text AS label,
        ''::text AS kind, ''::text AS reception_type, ''::text AS date_type,
        ''::text AS number_type, ''::text AS sequence_type, ''::text AS code_type,
        false AS selectable, count(*) AS n FROM classified
    UNION ALL SELECT 'summary', 'omitted_names', '', '', '', '', '', '', false, count(*)
        FROM classified WHERE NOT name_reviewed
    UNION ALL SELECT 'summary', 'omitted_types', '', '', '', '', '', '', false, count(*)
        FROM classified WHERE name_reviewed AND NOT types_reviewed
    UNION ALL SELECT 'summary', 'candidate_relations', '', '', '', '', '', '', false, count(*)
        FROM classified WHERE name_reviewed AND types_reviewed
    UNION ALL SELECT 'summary', 'unreviewed_names', '', '', '', '', '', '', false, 0
    UNION ALL SELECT 'summary', 'known_order_relations', '', '', '', '', '', '', false, count(*)
        FROM classified WHERE name_reviewed AND types_reviewed AND relname = %(known_order)s
    UNION ALL SELECT 'candidate', relname::text,
        relkind::text, coalesce(reception_type, 'MISSING'), coalesce(date_type, 'MISSING'),
        coalesce(number_type, 'MISSING'), coalesce(sequence_type, 'MISSING'),
        coalesce(code_type, 'MISSING'), has_table_privilege(oid, 'SELECT'), 1
        FROM classified WHERE name_reviewed AND types_reviewed
)
SELECT section, label, kind, reception_type, date_type, number_type, sequence_type,
       code_type, selectable, n FROM report ORDER BY section, label
LIMIT 72
