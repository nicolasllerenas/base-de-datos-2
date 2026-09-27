# Laboratorio 01 — Repaso de PostgreSQL

## Contenido

| Archivo | Descripción |
|---|---|
| `Laboratorio01_Solucion.ipynb` | Entregable: notebook ejecutado de inicio a fin con código, planes y respuestas |
| `restaurar.sh` | Restaura `employee_db.zip` en la base `employees` |
| `sql/01_parte1_catalogo.sql` | Consultas A, B y C sobre `pg_catalog` |
| `sql/02_parte2_optimizacion.sql` | `EXPLAIN ANALYZE` originales, índices y consultas optimizadas |
| `sql/03_parte3_procedimientos.sql` | Tabla de auditoría, trigger, procedimiento y llamadas de prueba |
| `parte4_concurrencia.py` | Pool de conexiones y simulación concurrente |

Los archivos de `sql/` están pensados para ejecutarse directamente en DBeaver.

## Ejecutar en Google Colab

El notebook trae una **Parte 0** que detecta el entorno. En Colab no hay servidor PostgreSQL, así
que esa parte lo instala y lo arranca dentro de la VM:

1. Subir `Laboratorio01_Solucion.ipynb` a Colab.
2. Ejecutar todo (`Entorno de ejecución → Ejecutar todas`).
3. Cuando la celda 0.3 lo pida, subir `employee_db.zip`.

Para no subir el dump en cada sesión, dejarlo en Drive y montarlo antes de correr la celda 0.3:

```python
from google.colab import drive
drive.mount('/content/drive')
```

La instalación de PostgreSQL tarda ~1 min la primera vez; la restauración, unos segundos.

## Restaurar la base de datos (local)

El dump fue generado con `pg_dump 18.1` sobre PostgreSQL 17.5 en formato tar, por lo que un
`pg_restore` de PostgreSQL 14 o 15 lo rechaza con `unsupported version (1.16) in file header`.
`restaurar.sh` resuelve eso extrayendo el `restore.sql` y los `.dat` que el propio formato tar
incluye:

```bash
./restaurar.sh employee_db.zip
```

Crea el rol `postgres` (password `123456`) si no existe, recrea la base `employees`, carga las 6
tablas del esquema `employees` y ejecuta `ANALYZE`.

Con PostgreSQL 17 o superior basta el comando del enunciado:

```bash
unzip employee_db.zip
pg_restore -U postgres -d postgres employee_db.tar
```

## Conexión en DBeaver

```
Host      localhost
Puerto    5432
Database  employees
Usuario   postgres
Password  123456
```

## Ejecutar el notebook

```bash
python3 -m venv .venv
.venv/bin/pip install psycopg2-binary pandas jupyter
.venv/bin/jupyter lab Laboratorio01_Solucion.ipynb
```

El notebook es reejecutable: reinicia el estado de los empleados de prueba antes de la Parte 3, así
que produce los mismos resultados en cada corrida.
