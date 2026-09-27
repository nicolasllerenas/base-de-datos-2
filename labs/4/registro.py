import csv
import struct
from dataclasses import dataclass

FORMATO = "<i30si20s20s20sf10s"
TAMANO = struct.calcsize(FORMATO)
CAMPOS = ["Employee_ID", "Employee_Name", "Age", "Country", "Department", "Position",
          "Salary", "Joining_Date"]


@dataclass
class Empleado:
    employee_id: int
    employee_name: str
    age: int
    country: str
    department: str
    position: str
    salary: float
    joining_date: str

    def clave(self):
        return self.employee_id

    def como_fila(self):
        return [self.employee_id, self.employee_name, self.age, self.country,
                self.department, self.position, f"{self.salary:.2f}", self.joining_date]


def texto_fijo(valor, tamano):
    return str(valor).encode("utf-8", "ignore")[:tamano].ljust(tamano, b" ")


def texto_libre(bruto):
    return bruto.decode("utf-8", "ignore").rstrip("\x00 ").strip()


def empaquetar(empleado, *extras):
    base = struct.pack(FORMATO,
                       empleado.employee_id,
                       texto_fijo(empleado.employee_name, 30),
                       empleado.age,
                       texto_fijo(empleado.country, 20),
                       texto_fijo(empleado.department, 20),
                       texto_fijo(empleado.position, 20),
                       empleado.salary,
                       texto_fijo(empleado.joining_date, 10))
    return base + struct.pack(f"<{'i' * len(extras)}", *extras) if extras else base


def desempaquetar(blob):
    valores = struct.unpack_from(FORMATO, blob)
    return Empleado(valores[0], texto_libre(valores[1]), valores[2], texto_libre(valores[3]),
                    texto_libre(valores[4]), texto_libre(valores[5]), round(valores[6], 2),
                    texto_libre(valores[7]))


def normalizar(nombre):
    return nombre.strip().lower().replace(" ", "").replace("_", "")


def leer_csv(ruta):
    with open(ruta, newline="", encoding="utf-8-sig") as fuente:
        lector = csv.DictReader(fuente)
        indice = {normalizar(nombre): nombre for nombre in lector.fieldnames}
        faltantes = [campo for campo in CAMPOS if normalizar(campo) not in indice]
        if faltantes:
            raise ValueError(f"al csv le faltan columnas: {', '.join(faltantes)}")
        empleados = []
        for fila in lector:
            def valor(campo):
                return fila[indice[normalizar(campo)]].strip()
            empleados.append(Empleado(
                int(float(valor("Employee_ID"))),
                valor("Employee_Name"),
                int(float(valor("Age"))),
                valor("Country"),
                valor("Department"),
                valor("Position"),
                round(float(valor("Salary")), 2),
                valor("Joining_Date"),
            ))
    return empleados


def escribir_csv(ruta, empleados):
    with open(ruta, "w", newline="", encoding="utf-8") as destino:
        escritor = csv.writer(destino)
        escritor.writerow(CAMPOS)
        for empleado in empleados:
            escritor.writerow(empleado.como_fila())
