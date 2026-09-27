\set ECHO all

BEGIN;
SET LOCAL work_mem = '64kB';
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM employees.employee ORDER BY hire_date;
COMMIT;

BEGIN;
SET LOCAL work_mem = '2MB';
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM employees.employee ORDER BY hire_date;
COMMIT;

BEGIN;
SET LOCAL work_mem = '64MB';
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM employees.employee ORDER BY hire_date;
COMMIT;

BEGIN;
SET LOCAL work_mem = '64kB';
EXPLAIN (ANALYZE, BUFFERS)
SELECT from_date, COUNT(*) FROM employees.department_employee GROUP BY from_date;
COMMIT;

BEGIN;
SET LOCAL work_mem = '2MB';
EXPLAIN (ANALYZE, BUFFERS)
SELECT from_date, COUNT(*) FROM employees.department_employee GROUP BY from_date;
COMMIT;

BEGIN;
SET LOCAL work_mem = '64kB';
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM employees.employee e
JOIN employees.department_employee d ON d.employee_id = e.id;
COMMIT;

BEGIN;
SET LOCAL work_mem = '2MB';
EXPLAIN (ANALYZE, BUFFERS)
SELECT * FROM employees.employee e
JOIN employees.department_employee d ON d.employee_id = e.id;
COMMIT;
