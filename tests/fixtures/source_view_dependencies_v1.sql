WITH targets(scope, relation_name) AS (
    VALUES ('receptions'::text, %(reception_table)s::text),
           ('orders'::text, %(order_table)s::text)
), known AS (
    SELECT t.scope, c.oid, c.relkind
    FROM targets t
    JOIN pg_catalog.pg_class c ON c.relname=t.relation_name
    JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname=%(schema)s
    LIMIT 3
), scoped_views AS (
    SELECT DISTINCT k.scope, v.oid, v.relkind
    FROM known k
    JOIN pg_catalog.pg_depend d ON d.refobjid=k.oid
    JOIN pg_catalog.pg_rewrite r ON r.oid=d.objid
    JOIN pg_catalog.pg_class v ON v.oid=r.ev_class
    WHERE d.refclassid='pg_catalog.pg_class'::regclass
      AND d.classid='pg_catalog.pg_rewrite'::regclass
      AND v.oid<>k.oid AND v.relkind IN ('v', 'm')
    LIMIT 65
), views AS (
    SELECT DISTINCT oid, relkind FROM scoped_views
), relation_links AS (
    SELECT DISTINCT v.oid AS view_oid, c.oid, c.relkind,
           coalesce(k.scope, 'other') AS scope
    FROM views v
    JOIN pg_catalog.pg_rewrite r ON r.ev_class=v.oid
    JOIN pg_catalog.pg_depend d ON d.objid=r.oid
    JOIN pg_catalog.pg_class c ON c.oid=d.refobjid
    LEFT JOIN known k ON k.oid=c.oid
    WHERE d.classid='pg_catalog.pg_rewrite'::regclass
      AND d.refclassid='pg_catalog.pg_class'::regclass AND c.oid<>v.oid
    LIMIT 129
), routine_links AS (
    SELECT DISTINCT v.oid AS view_oid, d.refobjid
    FROM views v
    JOIN pg_catalog.pg_rewrite r ON r.ev_class=v.oid
    JOIN pg_catalog.pg_depend d ON d.objid=r.oid
    WHERE d.classid='pg_catalog.pg_rewrite'::regclass
      AND d.refclassid='pg_catalog.pg_proc'::regclass
    LIMIT 129
)
SELECT 'relations'::text AS metric, count(*) AS count FROM known
UNION ALL SELECT 'ordinary_relations', count(*) FROM known WHERE relkind='r'
UNION ALL SELECT 'scope_view_links', count(*) FROM scoped_views
UNION ALL SELECT 'reception_views', count(*) FROM scoped_views WHERE scope='receptions'
UNION ALL SELECT 'order_views', count(*) FROM scoped_views WHERE scope='orders'
UNION ALL SELECT 'unique_views', count(*) FROM views
UNION ALL SELECT 'shared_views', count(*) FROM views v
    WHERE (SELECT count(*) FROM scoped_views s WHERE s.oid=v.oid)=2
UNION ALL SELECT 'ordinary_views', count(*) FROM views WHERE relkind='v'
UNION ALL SELECT 'materialized_views', count(*) FROM views WHERE relkind='m'
UNION ALL SELECT 'relation_links', count(*) FROM relation_links
UNION ALL SELECT 'reception_relation_links', count(*) FROM relation_links WHERE scope='receptions'
UNION ALL SELECT 'order_relation_links', count(*) FROM relation_links WHERE scope='orders'
UNION ALL SELECT 'other_ordinary_relation_links', count(*) FROM relation_links
    WHERE scope='other' AND relkind='r'
UNION ALL SELECT 'other_view_relation_links', count(*) FROM relation_links
    WHERE scope='other' AND relkind='v'
UNION ALL SELECT 'other_materialized_relation_links', count(*) FROM relation_links
    WHERE scope='other' AND relkind='m'
UNION ALL SELECT 'other_relation_links', count(*) FROM relation_links
    WHERE scope='other' AND relkind NOT IN ('r', 'v', 'm')
UNION ALL SELECT 'routine_links', count(*) FROM routine_links
ORDER BY 1
LIMIT 18
