-- 2.1 Consulta original
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT
    d.dept_name,
    AVG(s.amount)        AS salario_promedio,
    COUNT(DISTINCT e.id) AS total_empleados
FROM employees.employee e,
     employees.department_employee de,
     employees.salary s,
     employees.department d
WHERE e.id       = de.employee_id
  AND e.id       = s.employee_id
  AND de.department_id = d.id
  AND de.to_date  > CURRENT_DATE
  AND s.to_date   > CURRENT_DATE
GROUP BY d.dept_name
ORDER BY salario_promedio DESC;

-- 2.1 Indices
CREATE INDEX IF NOT EXISTS ix_salary_vigente
    ON employees.salary (to_date, employee_id, amount);

CREATE INDEX IF NOT EXISTS ix_dept_emp_vigente
    ON employees.department_employee (to_date, department_id, employee_id);

ANALYZE employees.salary;
ANALYZE employees.department_employee;

-- 2.1 Consulta optimizada
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
WITH salario_vigente AS (
    SELECT s.employee_id, s.amount
    FROM employees.salary s
    WHERE s.to_date > CURRENT_DATE
),
depto_vigente AS (
    SELECT de.employee_id, de.department_id
    FROM employees.department_employee de
    WHERE de.to_date > CURRENT_DATE
)
SELECT
    d.dept_name,
    AVG(sv.amount) AS salario_promedio,
    COUNT(*)       AS total_empleados
FROM depto_vigente dv
JOIN salario_vigente sv     ON sv.employee_id = dv.employee_id
JOIN employees.department d ON d.id = dv.department_id
GROUP BY d.dept_name
ORDER BY salario_promedio DESC;

-- 2.2 Consulta original
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
SELECT
    d.dept_name,
    (SELECT AVG(s.amount)
     FROM employees.salary s
     JOIN employees.department_employee de ON de.employee_id = s.employee_id
     WHERE de.department_id = d.id
       AND s.to_date  > CURRENT_DATE
       AND de.to_date > CURRENT_DATE) AS promedio_depto
FROM employees.department d
WHERE
    (SELECT AVG(s.amount)
     FROM employees.salary s
     JOIN employees.department_employee de ON de.employee_id = s.employee_id
     WHERE de.department_id = d.id
       AND s.to_date  > CURRENT_DATE
       AND de.to_date > CURRENT_DATE)
    >
    (SELECT AVG(s2.amount)
     FROM employees.salary s2
     WHERE s2.to_date > CURRENT_DATE)
ORDER BY promedio_depto DESC;

-- 2.2 Consulta optimizada
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
WITH promedio_depto AS (
    SELECT de.department_id, AVG(s.amount) AS promedio
    FROM employees.department_employee de
    JOIN employees.salary s ON s.employee_id = de.employee_id
                           AND s.to_date > CURRENT_DATE
    WHERE de.to_date > CURRENT_DATE
    GROUP BY de.department_id
),
promedio_global AS (
    SELECT AVG(s.amount) AS promedio
    FROM employees.salary s
    WHERE s.to_date > CURRENT_DATE
)
SELECT
    d.dept_name,
    p.promedio AS promedio_depto
FROM promedio_depto p
JOIN employees.department d ON d.id = p.department_id
CROSS JOIN promedio_global g
WHERE p.promedio > g.promedio
ORDER BY promedio_depto DESC;
