# Laboratorio 03 — External Algorithms

Entregable principal: **`Informe_Laboratorio03.docx`**.

## Archivos

| Archivo | Contenido |
|---|---|
| `heap_file.py` | Heap file paginado: `export_to_heap`, `read_page`, `write_page`, `count_pages` y la clase `HeapFile` con contadores de I/O |
| `external_sort.py` | Two-Phase Multiway Merge Sort: `generate_runs`, `multiway_merge`, `external_sort` |
| `external_hashing.py` | External hashing para el GROUP BY: `partition_data`, `aggregate_partitions`, `external_hash_group_by` |
| `export_data.py` | Exporta `employee` y `department_employee` de PostgreSQL a los heap files binarios |
| `benchmark.py` | Corre ambos algoritmos con 64/128/256/512 KB y 1 MB, y genera métricas y gráficas |
| `capturar_planes.sh`, `sql/parte1_planes.sql` | `EXPLAIN ANALYZE` de la Parte 1 con `work_mem` reducido |
| `capturas.py` | Renderiza la salida de `evidencia/` como imágenes de terminal para el informe |
| `informe.py` | Arma el informe en Word a partir de `evidencia/`, `capturas/` y `resultados/` |
| `data/` | `employee.bin`, `department_employee.bin`, los CSV de origen y el GROUP BY de referencia |
| `evidencia/` | Salidas literales de psql y de los programas |
| `capturas/` | Imágenes de la salida de psql y de los programas usadas en el informe |
| `resultados/` | `metricas.json`, `metricas.csv` y las gráficas |

## Requisitos

- PostgreSQL con la base `employees` del Laboratorio 01 restaurada (`../1/restaurar.sh`).
- `python3 -m venv .venv && .venv/bin/pip install matplotlib python-docx` (solo `benchmark.py` e `informe.py`
  lo necesitan; los tres módulos de la Parte 2 corren con la librería estándar).

## Reproducir

```bash
make datos     # exporta los heap files desde PostgreSQL
make planes    # captura los planes de la Parte 1
make pruebas   # ejecuta los tres modulos de la Parte 2
make bench     # tabla comparativa y graficas
make capturas  # imagenes de terminal con la salida real
make informe   # regenera el informe .docx
```

Cada módulo también corre solo:

```bash
python3 heap_file.py
python3 external_sort.py data/employee.bin hire_date 65536
python3 external_hashing.py data/department_employee.bin from_date 65536
```
