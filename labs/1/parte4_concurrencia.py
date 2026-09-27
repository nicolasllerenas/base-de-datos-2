import threading
import time

import pandas as pd
import psycopg2
from psycopg2 import pool, sql, errors

DB_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "employees",
    "user":     "postgres",
    "password": "123456",
}

connection_pool = pool.ThreadedConnectionPool(minconn=2, maxconn=10, **DB_CONFIG)

EMPLEADOS_PRUEBA = [10001, 10002, 10003, 10004, 10005]
SALARIOS_PRUEBA  = [95000, 88000, 25000, 70000, 61000, 99000]

resultados = []
resultados_lock = threading.Lock()


def ajustar_salario(employee_id, nuevo_salario, thread_id, anio=2025, retencion=0.5, barrera=None):
    if barrera is not None:
        barrera.wait()

    inicio = time.perf_counter()
    conn = connection_pool.getconn()
    conn.autocommit = False
    estado, sqlstate, detalle = "OK", None, ""
    try:
        with conn.cursor() as cur:
            cur.execute(
                sql.SQL("CALL employees.sp_ajustar_salario(%s, %s, %s)"),
                (employee_id, nuevo_salario, anio),
            )
            time.sleep(retencion)
        conn.commit()
    except errors.CheckViolation as e:
        conn.rollback()
        estado, sqlstate, detalle = "ERROR TRIGGER", e.pgcode, str(e).splitlines()[0]
    except errors.UndefinedTable as e:
        conn.rollback()
        estado, sqlstate, detalle = "ERROR AUDITORIA", e.pgcode, str(e).splitlines()[0]
    except psycopg2.Error as e:
        conn.rollback()
        estado, sqlstate, detalle = "ERROR", e.pgcode, str(e).splitlines()[0]
    finally:
        connection_pool.putconn(conn)

    fila = {
        "thread": thread_id,
        "employee_id": employee_id,
        "nuevo_salario": nuevo_salario,
        "estado": estado,
        "segundos": round(time.perf_counter() - inicio, 3),
        "sqlstate": sqlstate,
        "detalle": detalle,
    }
    with resultados_lock:
        resultados.append(fila)
    print(f"[hilo {thread_id}] empleado={employee_id} salario={nuevo_salario} -> "
          f"{estado} en {fila['segundos']} s {detalle}")
    return fila


def simular_ajustes_concurrentes(n_hilos=6):
    resultados.clear()
    barrera = threading.Barrier(n_hilos)
    hilos = []
    for i in range(n_hilos):
        hilo = threading.Thread(
            target=ajustar_salario,
            args=(EMPLEADOS_PRUEBA[i % len(EMPLEADOS_PRUEBA)],
                  SALARIOS_PRUEBA[i % len(SALARIOS_PRUEBA)],
                  i),
            kwargs={"barrera": barrera},
        )
        hilos.append(hilo)
        hilo.start()
    for hilo in hilos:
        hilo.join()
    return pd.DataFrame(sorted(resultados, key=lambda r: r["thread"]))


def ver_auditoria():
    conn = connection_pool.getconn()
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT employee_id, old_amount, new_amount, changed_at
                FROM employees.audit_salary_2025
                ORDER BY changed_at DESC
                LIMIT 20;
            """)
            rows = cur.fetchall()
            cols = [desc[0] for desc in cur.description]
        return pd.DataFrame(rows, columns=cols)
    finally:
        connection_pool.putconn(conn)


if __name__ == "__main__":
    print(simular_ajustes_concurrentes(n_hilos=6).to_string(index=False))
    print()
    print(ver_auditoria().to_string(index=False))
    connection_pool.closeall()
