#!/usr/bin/env bash
set -euo pipefail

DB="${1:-employees}"
USUARIO="${2:-postgres}"
DESTINO="evidencia"
mkdir -p "$DESTINO"

Q1="SELECT * FROM employees.employee ORDER BY hire_date;"
Q2="SELECT from_date, COUNT(*) FROM employees.department_employee GROUP BY from_date;"
Q3="SELECT * FROM employees.employee e JOIN employees.department_employee d ON d.employee_id = e.id;"

plan() {
  local etiqueta="$1" work_mem="$2" consulta="$3"
  local salida="$DESTINO/${etiqueta}_${work_mem}.txt"
  {
    echo "-- work_mem = $work_mem"
    echo "-- $consulta"
    echo
    psql -U "$USUARIO" -d "$DB" -X -q <<SQL
BEGIN;
SET LOCAL work_mem = '$work_mem';
EXPLAIN (ANALYZE, BUFFERS) $consulta
COMMIT;
SQL
  } > "$salida" 2>&1
  echo "  $salida"
}

trace() {
  local etiqueta="$1" work_mem="$2" consulta="$3"
  local salida="$DESTINO/${etiqueta}_${work_mem}_trace_sort.txt"
  psql -U "$USUARIO" -d "$DB" -X -q > "$salida" 2>&1 <<SQL
BEGIN;
SET LOCAL work_mem = '$work_mem';
SET LOCAL max_parallel_workers_per_gather = 0;
SET LOCAL client_min_messages = LOG;
SET LOCAL trace_sort = on;
EXPLAIN (ANALYZE) $consulta
COMMIT;
SQL
  {
    echo "runs generados : $(grep -c 'finished writing run' "$salida" || true)"
    echo "merge steps    : $(grep -c 'merge step' "$salida" || true)"
    grep -E 'switching to external sort|using .* KB of memory|external sort ended' "$salida" || true
  } > "${salida%.txt}_resumen.txt"
  echo "  $salida"
}

echo "Consulta 1: ORDER BY hire_date"
plan q1_order_by 64kB "$Q1"
plan q1_order_by 2MB "$Q1"
plan q1_order_by 64MB "$Q1"
trace q1_order_by 64kB "$Q1"
trace q1_order_by 2MB "$Q1"

echo "Consulta 2: GROUP BY from_date"
plan q2_group_by 64kB "$Q2"
plan q2_group_by 2MB "$Q2"

echo "Consulta 3: JOIN employee_id"
plan q3_join 64kB "$Q3"
plan q3_join 2MB "$Q3"

psql -U "$USUARIO" -d "$DB" -X -q -c \
  "\copy (SELECT from_date, COUNT(*) AS conteo FROM employees.department_employee GROUP BY from_date ORDER BY from_date) TO 'data/group_by_referencia.csv' CSV HEADER"
echo "  data/group_by_referencia.csv"
