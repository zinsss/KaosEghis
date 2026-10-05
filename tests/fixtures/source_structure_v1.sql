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
), edges AS (
    SELECT k.scope, 'parent_links'::text AS metric, i.inhparent AS object_id
    FROM known k JOIN pg_catalog.pg_inherits i ON i.inhrelid=k.oid
    UNION
    SELECT k.scope, 'child_links', i.inhrelid
    FROM known k JOIN pg_catalog.pg_inherits i ON i.inhparent=k.oid
    UNION
    SELECT k.scope, 'outgoing_foreign_keys', c.oid
    FROM known k JOIN pg_catalog.pg_constraint c ON c.conrelid=k.oid
    WHERE c.contype='f'
    UNION
    SELECT k.scope, 'incoming_foreign_keys', c.oid
    FROM known k JOIN pg_catalog.pg_constraint c ON c.confrelid=k.oid
    WHERE c.contype='f'
    UNION
    SELECT k.scope,
           CASE WHEN v.relkind='v' THEN 'dependent_views'
                ELSE 'dependent_materialized_views' END,
           v.oid
    FROM known k
    JOIN pg_catalog.pg_depend d ON d.refobjid=k.oid
    JOIN pg_catalog.pg_rewrite r ON r.oid=d.objid
    JOIN pg_catalog.pg_class v ON v.oid=r.ev_class
    WHERE d.refclassid='pg_catalog.pg_class'::regclass
      AND d.classid='pg_catalog.pg_rewrite'::regclass
      AND v.oid<>k.oid AND v.relkind IN ('v', 'm')
), bounded_edges AS (
    SELECT scope, metric, object_id FROM edges LIMIT 65
), metrics(metric) AS (
    VALUES ('parent_links'::text), ('child_links'),
           ('outgoing_foreign_keys'), ('incoming_foreign_keys'),
           ('dependent_views'), ('dependent_materialized_views')
)
SELECT 'summary'::text AS section, 'relations'::text AS scope,
       ''::text AS detail, count(*) AS count FROM known
UNION ALL
SELECT 'summary', 'relationships', '', count(*) FROM bounded_edges
UNION ALL
SELECT 'relation', scope,
       CASE WHEN relkind IN ('r', 'p', 'v', 'm', 'f') THEN relkind::text
            ELSE 'UNREVIEWED' END, 1 FROM known
UNION ALL
SELECT 'links', t.scope, m.metric, count(e.object_id)
FROM targets t CROSS JOIN metrics m
LEFT JOIN bounded_edges e ON e.scope=t.scope AND e.metric=m.metric
GROUP BY t.scope, m.metric
ORDER BY 1, 2, 3
LIMIT 17
