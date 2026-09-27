import os
import subprocess
import sys

PAISES = ["Peru", "Chile", "Colombia", "Mexico", "Argentina", "Brasil", "Espana", "Uruguay",
          "Ecuador", "Bolivia", "Panama", "Costa Rica"]

CONSULTA = """
SELECT e.id AS "Employee_ID",
       e.first_name || ' ' || e.last_name AS "Employee_Name",
       (ARRAY[{paises}])[(e.id % {total}) + 1] AS "Country",
       d.dept_name AS "Department",
       s.amount AS "Salary",
       to_char(e.hire_date, 'DD/MM/YYYY') AS "Joining_Date"
FROM employees.employee e
JOIN employees.department_employee de ON de.employee_id = e.id AND de.to_date = '9999-01-01'
JOIN employees.department d ON d.id = de.department_id
JOIN employees.salary s ON s.employee_id = e.id AND s.to_date = '9999-01-01'
ORDER BY e.id
LIMIT {limite}
"""


def main():
    limite = int(sys.argv[1]) if len(sys.argv) > 1 else 100000
    database = sys.argv[2] if len(sys.argv) > 2 else "employees"
    usuario = sys.argv[3] if len(sys.argv) > 3 else "postgres"
    ruta = os.path.join("data", "employee.csv")
    os.makedirs("data", exist_ok=True)

    consulta = CONSULTA.format(paises=", ".join(f"'{pais}'" for pais in PAISES),
                               total=len(PAISES), limite=limite)
    subprocess.run(["psql", "-U", usuario, "-d", database, "-X", "-q", "-c",
                    f"\\copy ({consulta}) TO '{ruta}' CSV HEADER"], check=True)

    with open(ruta) as fuente:
        filas = sum(1 for _ in fuente) - 1
    print(f"{ruta}: {filas} registros, {os.path.getsize(ruta)} bytes")
    with open(ruta) as fuente:
        for numero, linea in enumerate(fuente):
            if numero > 3:
                break
            print(f"  {linea.rstrip()}")


if __name__ == "__main__":
    main()
