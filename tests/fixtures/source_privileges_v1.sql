WITH targets(relation_name) AS (
    VALUES (%(reception_table)s::text), (%(order_table)s::text)
), known AS (
    SELECT c.oid, c.relowner, c.relkind
    FROM targets t
    JOIN pg_catalog.pg_class c ON c.relname=t.relation_name
    JOIN pg_catalog.pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname=%(schema)s
    LIMIT 3
), own_role AS (
    SELECT oid, rolsuper, rolcreaterole, rolcreatedb, rolinherit
    FROM pg_catalog.pg_roles WHERE rolname=current_user
    LIMIT 2
), reachable_roles AS (
    SELECT oid, rolsuper, rolcreaterole, rolcreatedb
    FROM pg_catalog.pg_roles
    WHERE pg_catalog.pg_has_role(oid, 'MEMBER')
    LIMIT 65
), source_schema AS (
    SELECT oid FROM pg_catalog.pg_namespace WHERE nspname=%(schema)s
    LIMIT 2
), definer_routines AS (
    SELECT p.oid
    FROM pg_catalog.pg_proc p JOIN source_schema n ON n.oid=p.pronamespace
    WHERE p.prosecdef
    LIMIT 129
)
SELECT 'relations'::text AS metric, count(*) AS count FROM known
UNION ALL SELECT 'ordinary_relations', count(*) FROM known WHERE relkind='r'
UNION ALL SELECT 'own_roles', count(*) FROM own_role
UNION ALL SELECT 'superuser_roles', count(*) FROM own_role WHERE rolsuper
UNION ALL SELECT 'role_admin_roles', count(*) FROM own_role WHERE rolcreaterole
UNION ALL SELECT 'database_admin_roles', count(*) FROM own_role WHERE rolcreatedb
UNION ALL SELECT 'inherit_roles', count(*) FROM own_role WHERE rolinherit
UNION ALL SELECT 'reachable_roles', count(*) FROM reachable_roles
UNION ALL SELECT 'reachable_privileged_roles', count(*) FROM reachable_roles
    WHERE rolsuper OR rolcreaterole OR rolcreatedb
UNION ALL SELECT 'selectable_relations', count(*) FROM known
    WHERE pg_catalog.has_table_privilege(oid, 'SELECT')
UNION ALL SELECT 'nonselect_relations', count(*) FROM known
    WHERE pg_catalog.has_table_privilege(oid, %(table_nonselect)s)
UNION ALL SELECT 'nonselect_column_relations', count(*) FROM known
    WHERE pg_catalog.has_any_column_privilege(oid, %(column_nonselect)s)
UNION ALL SELECT 'owner_role_relations', count(*) FROM known
    WHERE pg_catalog.pg_has_role(relowner, 'USAGE')
UNION ALL SELECT 'schemas', count(*) FROM source_schema
UNION ALL SELECT 'usable_schemas', count(*) FROM source_schema
    WHERE pg_catalog.has_schema_privilege(oid, 'USAGE')
UNION ALL SELECT 'writable_schemas', count(*) FROM source_schema
    WHERE pg_catalog.has_schema_privilege(oid, %(schema_nonselect)s)
UNION ALL SELECT 'definer_routines', count(*) FROM definer_routines
UNION ALL SELECT 'executable_definer_routines', count(*) FROM definer_routines
    WHERE pg_catalog.has_function_privilege(oid, 'EXECUTE')
ORDER BY 1
LIMIT 19
