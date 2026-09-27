<div style="background: #86d1f1ff; border-radius: 5px; padding: 1rem; margin-bottom: 1rem">
<img src="https://store.utec.edu.pe/files/Recursos/logo-utec-h.png" alt="Banner" width="150" />   
<div style="font-weight: bold; color: #434549ff; float: right "><u style="font-size: 28px;">Base de Datos II</u> <br />
<span style="float:right"> Profesor Percy Lovon </span> <br /> 
<span style="float:right">  2026 - 1 </span>   
</div> </div>

# Laboratorio 01:  Repaso de PostgreSQL

> **Entregable:** Un Jupyter Notebook reproducible con todo el código ejecutado y las respuestas a las preguntas de análisis.  

## Prerequisito: Restaurar la base de datos

Antes de comenzar, restauren el dump proporcionado por el docente [Employees_DB](https://1drv.ms/u/c/0c2923df9f1f816f/IQBt8UwmNmkVT7KuokPDFEqMAaW1_LgrCve352M7U9TFcqU?e=ChaCwe):

```bash
psql -U postgres -c "CREATE SCHEMA IF NOT EXISTS employees;"
pg_restore -U postgres -d postgres employees_db.tar
```

Verifiquen que existen las siguientes tablas en el esquema `employees`:

![alt text](imagenes/lab1_er.png)

## Parte 1: Exploración del Catálogo del Sistema (4 pts)

> El optimizador de PostgreSQL toma decisiones basándose en estadísticas almacenadas en el catálogo del sistema. En esta parte explorarán ese catálogo para entender el tamaño y estructura de las tablas antes de optimizar cualquier consulta.

### 1.1 Tamaño y estructura de las tablas

Escribir y ejecutar las siguientes consultas sobre `pg_catalog` y responder las preguntas.

- **Consulta A -** Mostrar el número de filas y páginas estimadas por tabla, tambíen mostrar el tamaño total en bytes (MB o KB) de cada tabla.

```sql
-- SQL y Screenshot del resultado
-- Utilice las tablas pg_class y pg_namespace
```

- **Consulta B -** Mostrar las columnas y tipos de dato de cada tabla.
```sql
-- SQL y Screenshot del resultado
-- Utilice las tablas pg_class, pg_namespace, pg_attribute y pg_type
```



- **Consulta C -** Mostrar todos los índices existentes para cada tabla, indicar si dicho indice esta asociado a la llave primaria, también mostrar las columnas en donde se aplica cada índice existente. 
```sql
-- SQL y Screenshot del resultado
-- Utilice las tablas pg_class, pg_namespace, pg_attribute y pg_index
```  


**Preguntas 1.1**

1. ¿Cuál es la tabla con mayor número de filas? ¿Cuántas páginas ocupa en disco?
2. ¿Qué índices de tipo UNIQUE existen actualmente? ¿Cuáles columnas cubren?
3. ¿Para qué sirve `n_distinct` de la tabla `pg_stats` y cómo influye en la elección del tipo de índice?


## Parte 2: Optimización de Consultas (6 pts)

### 2.1 Consulta con JOIN

El siguiente query obtiene el salario promedio actual por departamento, junto con el nombre del departamento y la cantidad de empleados activos.

```sql
-- CONSULTA ORIGINAL (Sin optimizar) - NO modificar, solo analizar
SELECT
    d.dept_name,
    AVG(s.amount)     AS salario_promedio,
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
```

**Ejecutar con EXPLAIN ANALYZE y mostrar el resultado**

```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
-- pegar aqui la consulta 
```

**Preguntas 2.1.1**
1. ¿Qué problemas identifica en el diseño de la consulta?
2. ¿Qué tipo de join eligió el planificador (Hash Join, Nested Loop, Merge Join)? ¿Por qué?
3. ¿Cuántos nodos aparecen en el plan? Identifiquen el nodo más costoso.
4. ¿Cuál es el tiempo total de ejecución (`actual time`)?
5. ¿Hay algún `Seq Scan`? ¿Sobre qué tabla? ¿Es esperable dado el tamaño de la tabla?


**Reescritura y optimización**

Rescribir la consulta y crear los índices que consideren necesarios. Justifiquen **cada índice** creado. Vuelva a analizar el plan de ejecución.

```sql
-- CONSULTA OPTIMIZADA (escriban aquí su versión)
```

**Preguntas 2.1.2**

1. ¿Qué cambió en el plan de ejecución tras agregar los índices?
2. ¿El planificador utilizó todos los índices que crearon? Si alguno no fue usado, ¿por qué creen que sucedió?
3. ¿Cuánto mejoró el tiempo de ejecución? Expresen la mejora en porcentaje.


### 2.2 Consulta con Subconsultas 

El siguiente query lista los departamentos cuyo salario promedio actual supera el salario promedio global de toda la empresa.

```sql
-- CONSULTA ORIGINAL (sin optimizar) — NO modificar, solo analizar
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
```

**Ejecutar con EXPLAIN ANALYZE y mostrar el resultado**

```sql
EXPLAIN (ANALYZE, BUFFERS, FORMAT TEXT)
-- pegar aquí la consulta original
```

**Preguntas 2.2.1**
1. ¿Qué problemas identifica en el diseño de la consulta?
2. ¿Cuántas veces aparece el nodo de la subconsulta de promedio por departamento en el plan? ¿Cuántos `loops` ejecuta cada uno?
3. ¿El planificador reutiliza el resultado del promedio global o lo recalcula por cada fila?
4. ¿Qué patrón anti-eficiente representa esta consulta?


**Reescritura y optimización**

Reescriban la consulta para calcular cada valor **una sola vez** y luego hacer el filtro con un simple `JOIN` o comparación directa.

```sql
-- CONSULTA OPTIMIZADA (escriban aquí su versión)
```

Repitan el `EXPLAIN ANALYZE` y comparen.

**Preguntas 2.2.2**

1. ¿Cuántas veces se evalúa ahora el `avg`? ¿Qué cambió en el plan?
2. ¿Qué índices agregarían para acelerar aún más esta consulta? Justifiquen.
3. ¿Cuánto mejoró el tiempo de ejecución respecto a la consulta original?


## Parte 3: Procedimiento Almacenado y Trigger (6 pts)

> El área de RRHH necesita registrar ajustes salariales. La regla es simple: el historial de salarios **no se modifica**, se cierra el registro vigente y se inserta uno nuevo. Cada ajuste debe quedar en una tabla de auditoría cuyo nombre incluye el año en curso (ej. `audit_salary_2025`), por lo que el `INSERT` de auditoría debe construirse **dinámicamente**.

### 3.1 Tabla de auditoría

```sql
CREATE TABLE IF NOT EXISTS employees.audit_salary_2025 (
    id           BIGSERIAL PRIMARY KEY,
    employee_id  BIGINT      NOT NULL,
    old_amount   BIGINT,
    new_amount   BIGINT      NOT NULL,
    changed_at   TIMESTAMPTZ NOT NULL DEFAULT NOW()
);
```

### 3.2 Trigger - Validar salario mínimo

Creen un trigger `BEFORE INSERT` sobre `employees.salary` que impida insertar un salario menor a $30,000.

```sql
CREATE OR REPLACE FUNCTION employees.fn_validar_salario()

-- Completar la función
```

### 3.3 Procedimiento almacenado - Ajustar salario

Implementen el procedimiento `sp_ajustar_salario`. El paso de auditoría **debe usar `EXECUTE`** con el nombre de tabla construido a partir del año recibido como parámetro.

```sql
CREATE OR REPLACE PROCEDURE employees.sp_ajustar_salario(
    p_employee_id  BIGINT,
    p_nuevo_monto  BIGINT,
    p_anio         INT
)

-- Completar la función con:
--  1. Obtener salario vigente
--  2. Cerrar registro de salario vigente (to_date = CURRENT_DATE)
--  3. Insertar nuevo salario (el trigger valida el monto)
--  4. Insertar auditoria, generar dinámicamente el nombre de la tabla según el año

```

### Llamada de prueba correcta

```sql
-- Llamada valida
CALL employees.sp_ajustar_salario(10001, 75000, 2025);

-- Debe fallar por trigger
CALL employees.sp_ajustar_salario(10001, 20000, 2025);

-- Debe fallar si la tabla del año no existe
CALL employees.sp_ajustar_salario(10001, 75000, 2099);
```

**Preguntas 3**

1. ¿Por qué se usa `EXECUTE` en lugar de un `INSERT` directo para la auditoría?
2. Intenten llamar al procedimiento con `p_nuevo_monto = 15000`. ¿Qué ocurre y en qué paso falla?
3. ¿Qué pasa con la transacción si el `EXECUTE` de auditoría falla (por ejemplo, si la tabla del año no existe)?
   

## Parte 4 : Integración y Concurrencia (4 pts)

> En esta parte integran Python con PostgreSQL usando `psycopg2` y un pool de conexiones, y simulan llamadas concurrentes al procedimiento.

### 4.1 Configuración del pool de conexiones

```python
import psycopg2
from psycopg2 import pool, sql, errors

# Configuren con sus credenciales
DB_CONFIG = {
    "host":     "localhost",
    "port":     5432,
    "dbname":   "employees",
    "user":     "postgres",
    "password": "123456"
}

# Pool con mínimo 2 y máximo 10 conexiones
connection_pool = pool.ThreadedConnectionPool(
    minconn=2,
    maxconn=10,
    **DB_CONFIG
)
```

### 4.2 Función para llamar al procedimiento almacenado

```python
def ajustar_salario(employee_id: int, nuevo_salario: int, thread_id: int):
    # TODO: Llama al procedimiento sp_ajustar_salario desde un hilo.
    pass
```

### 4.3 Simulación concurrente

```python
# IDs de empleados de prueba, ajusten según los datos restaurados
EMPLEADOS_PRUEBA = [10001, 10002, 10003, 10004, 10005]

def simular_ajustes_concurrentes(n_hilos = 6):
    #TODO: Lanza n_hilos hilos que intentan ajustar salarios simultáneamente.
    pass

simular_ajustes_concurrentes(n_hilos=6)
```

### 4.4 Verificación de auditoría

```python
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

        import pandas as pd
        df = pd.DataFrame(rows, columns=cols)
        display(df)
    finally:
        connection_pool.putconn(conn)

ver_auditoria()
```

**Preguntas 4**

1. ¿Qué pasaría si no usaran `conn.autocommit = False` y uno de los pasos del procedimiento fallara a mitad de camino?
2. Observen la salida de la simulación: ¿algún hilo obtuvo un error por validación del trigger? ¿Qué salario lo causó?
3. ¿Qué ventaja ofrece el `ThreadedConnectionPool` frente a abrir y cerrar una conexión nueva en cada hilo?
4. Si dos hilos intentan promover al **mismo empleado** al mismo tiempo, ¿qué mecanismo de PostgreSQL evita la corrupción de datos? ¿Observaron algún comportamiento de espera en la salida?


----
**El notebook debe ejecutarse de inicio a fin sin errores.** Incluyan capturas de pantalla o la salida de celda del `EXPLAIN ANALYZE` original vs. optimizado directamente en el notebook.
