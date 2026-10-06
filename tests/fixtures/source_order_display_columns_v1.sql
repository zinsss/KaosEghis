WITH target AS (
    SELECT c.oid FROM pg_catalog.pg_class c
    JOIN pg_catalog.pg_namespace ns ON ns.oid = c.relnamespace
    WHERE ns.nspname = %(schema)s AND c.relname = %(table)s AND c.relkind = 'r'
), cols AS (
    SELECT CASE WHEN a.attname ~ %(identifier_pattern)s THEN a.attname::text ELSE 'UNREVIEWED' END AS name,
           CASE WHEN t.typname = ANY(%(types)s) THEN t.typname::text ELSE 'OTHER_TYPE' END AS kind,
           NOT a.attnotnull AS nullable,
           has_column_privilege(a.attrelid, a.attnum, 'SELECT') AS selectable
    FROM target c JOIN pg_catalog.pg_attribute a ON a.attrelid = c.oid
    JOIN pg_catalog.pg_type t ON t.oid = a.atttypid
    WHERE a.attnum > 0 AND NOT a.attisdropped
      AND a.attname ~ %(candidate_pattern)s AND a.attname <> ALL(%(excluded)s)
    ORDER BY a.attnum
    LIMIT 129
), report AS (
    SELECT 'summary'::text AS section, 'relations'::text AS name, ''::text AS kind,
           false AS nullable, false AS selectable, count(*) AS n FROM target
    UNION ALL SELECT 'summary', 'columns', '', false, false, count(*) FROM cols
    UNION ALL SELECT 'column', name, kind, nullable, selectable, 1 FROM cols
)
SELECT section, name, kind, nullable, selectable, n FROM report
ORDER BY section DESC, name
LIMIT 131
