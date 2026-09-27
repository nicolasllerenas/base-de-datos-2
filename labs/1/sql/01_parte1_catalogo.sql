-- Consulta A
SELECT
    n.nspname                                      AS esquema,
    c.relname                                      AS tabla,
    c.reltuples::BIGINT                            AS filas_estimadas,
    c.relpages                                     AS paginas_estimadas,
    pg_total_relation_size(c.oid)                  AS bytes_totales,
    pg_size_pretty(pg_total_relation_size(c.oid))  AS tamano_total,
    pg_size_pretty(pg_relation_size(c.oid))        AS tamano_datos,
    pg_size_pretty(pg_indexes_size(c.oid))         AS tamano_indices
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
WHERE n.nspname = 'employees'
  AND c.relkind = 'r'
ORDER BY pg_total_relation_size(c.oid) DESC;

-- Consulta B
SELECT
    c.relname                            AS tabla,
    a.attnum                             AS posicion,
    a.attname                            AS columna,
    format_type(a.atttypid, a.atttypmod) AS tipo_dato,
    t.typname                            AS tipo_base,
    a.attnotnull                         AS not_null
FROM pg_class c
JOIN pg_namespace n ON n.oid = c.relnamespace
JOIN pg_attribute a ON a.attrelid = c.oid
JOIN pg_type      t ON t.oid = a.atttypid
WHERE n.nspname = 'employees'
  AND c.relkind = 'r'
  AND a.attnum > 0
  AND NOT a.attisdropped
ORDER BY c.relname, a.attnum;

-- Consulta C
SELECT
    t.relname                                  AS tabla,
    i.relname                                  AS indice,
    am.amname                                  AS metodo,
    ix.indisprimary                            AS es_primary_key,
    ix.indisunique                             AS es_unique,
    string_agg(a.attname, ', ' ORDER BY k.ord) AS columnas,
    pg_size_pretty(pg_relation_size(i.oid))    AS tamano
FROM pg_index ix
JOIN pg_class     t  ON t.oid  = ix.indrelid
JOIN pg_class     i  ON i.oid  = ix.indexrelid
JOIN pg_namespace n  ON n.oid  = t.relnamespace
JOIN pg_am        am ON am.oid = i.relam
JOIN LATERAL unnest(ix.indkey) WITH ORDINALITY AS k(attnum, ord) ON TRUE
JOIN pg_attribute a  ON a.attrelid = t.oid AND a.attnum = k.attnum
WHERE n.nspname = 'employees'
GROUP BY t.relname, i.relname, am.amname, ix.indisprimary, ix.indisunique, i.oid
ORDER BY t.relname, i.relname;

-- Pregunta 3: n_distinct
SELECT tablename, attname, n_distinct, null_frac, correlation
FROM pg_stats
WHERE schemaname = 'employees'
ORDER BY tablename, attname;
