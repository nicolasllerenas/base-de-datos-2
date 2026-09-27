CREATE TABLE IF NOT EXISTS employees.audit_salary_2025 (
    id           BIGSERIAL PRIMARY KEY,
    employee_id  BIGINT      NOT NULL,
    old_amount   BIGINT,
    new_amount   BIGINT      NOT NULL,
    changed_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE OR REPLACE FUNCTION employees.fn_validar_salario()
RETURNS TRIGGER
LANGUAGE plpgsql
AS $$
BEGIN
    IF NEW.amount < 30000 THEN
        RAISE EXCEPTION 'Salario invalido: % es menor al minimo permitido de 30000 (empleado %)',
              NEW.amount, NEW.employee_id
              USING ERRCODE = 'check_violation';
    END IF;
    RETURN NEW;
END;
$$;

DROP TRIGGER IF EXISTS trg_validar_salario ON employees.salary;

CREATE TRIGGER trg_validar_salario
BEFORE INSERT ON employees.salary
FOR EACH ROW
EXECUTE FUNCTION employees.fn_validar_salario();

CREATE OR REPLACE PROCEDURE employees.sp_ajustar_salario(
    p_employee_id  BIGINT,
    p_nuevo_monto  BIGINT,
    p_anio         INT
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_old_amount BIGINT;
    v_from_date  DATE;
    v_tabla      TEXT := 'audit_salary_' || p_anio;
BEGIN
    SELECT s.amount, s.from_date
      INTO v_old_amount, v_from_date
      FROM employees.salary s
     WHERE s.employee_id = p_employee_id
       AND s.to_date > CURRENT_DATE
     ORDER BY s.from_date DESC
     LIMIT 1
       FOR UPDATE;

    IF NOT FOUND THEN
        RAISE EXCEPTION 'El empleado % no tiene un salario vigente', p_employee_id
              USING ERRCODE = 'no_data_found';
    END IF;

    UPDATE employees.salary
       SET to_date = CURRENT_DATE
     WHERE employee_id = p_employee_id
       AND from_date   = v_from_date;

    INSERT INTO employees.salary (employee_id, amount, from_date, to_date)
    VALUES (p_employee_id, p_nuevo_monto, CURRENT_DATE, DATE '9999-01-01')
    ON CONFLICT (employee_id, from_date)
    DO UPDATE SET amount  = EXCLUDED.amount,
                  to_date = EXCLUDED.to_date;

    EXECUTE format(
        'INSERT INTO employees.%I (employee_id, old_amount, new_amount) VALUES ($1, $2, $3)',
        v_tabla
    ) USING p_employee_id, v_old_amount, p_nuevo_monto;
END;
$$;

CALL employees.sp_ajustar_salario(10001, 75000, 2025);

CALL employees.sp_ajustar_salario(10001, 20000, 2025);

CALL employees.sp_ajustar_salario(10001, 75000, 2099);
