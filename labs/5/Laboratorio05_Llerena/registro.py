import csv
import struct
from dataclasses import dataclass

FORMATO = "<i30s20s20sf10s"
TAMANO = struct.calcsize(FORMATO)
CAMPOS = ["Employee_ID", "Employee_Name", "Country", "Department", "Salary", "Joining_Date"]


@dataclass
class Empleado:
    employee_id: int
    employee_name: str
    country: str
    department: str
    salary: float
    joining_date: str

    def clave(self):
        return self.employee_id

    def como_fila(self):
        return [self.employee_id, self.employee_name, self.country, self.department,
                f"{self.salary:.2f}", self.joining_date]


def texto_fijo(valor, tamano):
    return str(valor).encode("utf-8", "ignore")[:tamano].ljust(tamano, b" ")


def texto_libre(bruto):
    return bruto.decode("utf-8", "ignore").rstrip("\x00 ").strip()


def empaquetar(empleado):
    return struct.pack(FORMATO,
                       empleado.employee_id,
                       texto_fijo(empleado.employee_name, 30),
                       texto_fijo(empleado.country, 20),
                       texto_fijo(empleado.department, 20),
                       empleado.salary,
                       texto_fijo(empleado.joining_date, 10))


def desempaquetar(blob, desplazamiento=0):
    valores = struct.unpack_from(FORMATO, blob, desplazamiento)
    return Empleado(valores[0], texto_libre(valores[1]), texto_libre(valores[2]),
                    texto_libre(valores[3]), round(valores[4], 2), texto_libre(valores[5]))


def normalizar(nombre):
    return nombre.strip().lower().replace(" ", "").replace("_", "")


def leer_csv(ruta, limite=None):
    empleados = []
    with open(ruta, newline="", encoding="utf-8-sig") as fuente:
        lector = csv.DictReader(fuente)
        indice = {normalizar(nombre): nombre for nombre in lector.fieldnames}
        faltantes = [campo for campo in CAMPOS if normalizar(campo) not in indice]
        if faltantes:
            raise ValueError(f"al csv le faltan columnas: {', '.join(faltantes)}")
        for fila in lector:
            def valor(campo):
                return fila[indice[normalizar(campo)]].strip()
            empleados.append(Empleado(int(float(valor("Employee_ID"))),
                                      valor("Employee_Name"),
                                      valor("Country"),
                                      valor("Department"),
                                      round(float(valor("Salary")), 2),
                                      valor("Joining_Date")))
            if limite and len(empleados) >= limite:
                break
    return empleados
