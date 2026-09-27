import os
import subprocess
import sys

from heap_file import PAGE_SIZE, SCHEMAS, export_to_heap

DATA_DIR = "data"
CONSULTAS = {
    "employee": "SELECT id, birth_date, first_name, last_name, gender, hire_date FROM employees.employee",
    "department_employee": "SELECT employee_id, department_id, from_date, to_date FROM employees.department_employee",
}


def export_csv(nombre, consulta, database, usuario):
    csv_path = os.path.join(DATA_DIR, f"{nombre}.csv")
    subprocess.run(
        ["psql", "-U", usuario, "-d", database, "-X", "-q", "-c",
         f"\\copy ({consulta}) TO '{csv_path}' CSV HEADER"],
        check=True,
    )
    return csv_path


def main():
    database = sys.argv[1] if len(sys.argv) > 1 else "employees"
    usuario = sys.argv[2] if len(sys.argv) > 2 else "postgres"
    os.makedirs(DATA_DIR, exist_ok=True)
    for nombre, consulta in CONSULTAS.items():
        csv_path = export_csv(nombre, consulta, database, usuario)
        heap_path = os.path.join(DATA_DIR, f"{nombre}.bin")
        info = export_to_heap(csv_path, heap_path, SCHEMAS[nombre]["record_format"], PAGE_SIZE)
        print(nombre)
        for clave in ("record_format", "record_size", "records_per_page", "records", "pages", "bytes"):
            print(f"  {clave:16s}: {info[clave]}")


if __name__ == "__main__":
    main()
