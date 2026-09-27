import os
import struct
import sys

from registro import FORMATO, Empleado, desempaquetar, empaquetar, leer_csv

FORMATO_REGISTRO = FORMATO + "B"
TAMANO_REGISTRO = struct.calcsize(FORMATO_REGISTRO)
ACTIVO = 1
ELIMINADO = 0
K_AUXILIAR = 32


class SequentialFile:
    def __init__(self, ruta_datos, ruta_auxiliar=None, k=K_AUXILIAR):
        self.ruta_datos = ruta_datos
        self.ruta_auxiliar = ruta_auxiliar or ruta_datos.replace(".dat", "_aux.dat")
        self.k = k
        self.accesos = 0
        self.reconstrucciones = 0
        for ruta in (self.ruta_datos, self.ruta_auxiliar):
            if not os.path.exists(ruta):
                open(ruta, "wb").close()

    def reiniciar_contador(self):
        self.accesos = 0

    def registros(self, ruta=None):
        return os.path.getsize(ruta or self.ruta_datos) // TAMANO_REGISTRO

    def _leer(self, flujo, posicion):
        flujo.seek(posicion * TAMANO_REGISTRO)
        blob = flujo.read(TAMANO_REGISTRO)
        self.accesos += 1
        return desempaquetar(blob), blob[-1]

    def _escribir(self, flujo, posicion, empleado, estado):
        flujo.seek(posicion * TAMANO_REGISTRO)
        flujo.write(empaquetar(empleado) + struct.pack("<B", estado))
        self.accesos += 1

    def build(self, empleados):
        ordenados = sorted(empleados, key=lambda empleado: empleado.employee_id)
        with open(self.ruta_datos, "wb") as destino:
            for empleado in ordenados:
                destino.write(empaquetar(empleado) + struct.pack("<B", ACTIVO))
                self.accesos += 1
        open(self.ruta_auxiliar, "wb").close()
        return len(ordenados)

    def insert(self, empleado):
        with open(self.ruta_auxiliar, "r+b") as auxiliar:
            posicion = self.registros(self.ruta_auxiliar)
            self._escribir(auxiliar, posicion, empleado, ACTIVO)
        if self.registros(self.ruta_auxiliar) > self.k:
            self._reconstruir()
        return True

    def search(self, clave):
        with open(self.ruta_datos, "rb") as datos:
            inicio, fin = 0, self.registros() - 1
            while inicio <= fin:
                medio = (inicio + fin) // 2
                empleado, estado = self._leer(datos, medio)
                if empleado.employee_id == clave:
                    return empleado if estado == ACTIVO else None
                if empleado.employee_id < clave:
                    inicio = medio + 1
                else:
                    fin = medio - 1
        with open(self.ruta_auxiliar, "rb") as auxiliar:
            for posicion in range(self.registros(self.ruta_auxiliar)):
                empleado, estado = self._leer(auxiliar, posicion)
                if empleado.employee_id == clave:
                    return empleado if estado == ACTIVO else None
        return None

    def remove(self, clave):
        with open(self.ruta_datos, "r+b") as datos:
            inicio, fin = 0, self.registros() - 1
            while inicio <= fin:
                medio = (inicio + fin) // 2
                empleado, estado = self._leer(datos, medio)
                if empleado.employee_id == clave:
                    if estado == ELIMINADO:
                        return False
                    self._escribir(datos, medio, empleado, ELIMINADO)
                    return True
                if empleado.employee_id < clave:
                    inicio = medio + 1
                else:
                    fin = medio - 1
        with open(self.ruta_auxiliar, "r+b") as auxiliar:
            for posicion in range(self.registros(self.ruta_auxiliar)):
                empleado, estado = self._leer(auxiliar, posicion)
                if empleado.employee_id == clave and estado == ACTIVO:
                    self._escribir(auxiliar, posicion, empleado, ELIMINADO)
                    return True
        return False

    def range_search(self, clave_inicial, clave_final):
        encontrados = []
        with open(self.ruta_datos, "rb") as datos:
            total = self.registros()
            inicio, fin, limite = 0, total - 1, total
            while inicio <= fin:
                medio = (inicio + fin) // 2
                empleado, _ = self._leer(datos, medio)
                if empleado.employee_id >= clave_inicial:
                    limite = medio
                    fin = medio - 1
                else:
                    inicio = medio + 1
            posicion = limite
            while posicion < total:
                empleado, estado = self._leer(datos, posicion)
                if empleado.employee_id > clave_final:
                    break
                if estado == ACTIVO:
                    encontrados.append(empleado)
                posicion += 1
        with open(self.ruta_auxiliar, "rb") as auxiliar:
            for posicion in range(self.registros(self.ruta_auxiliar)):
                empleado, estado = self._leer(auxiliar, posicion)
                if estado == ACTIVO and clave_inicial <= empleado.employee_id <= clave_final:
                    encontrados.append(empleado)
        encontrados.sort(key=lambda empleado: empleado.employee_id)
        return encontrados

    def load(self):
        return self.range_search(-2 ** 31, 2 ** 31 - 1)

    def _reconstruir(self):
        pendientes = []
        with open(self.ruta_auxiliar, "rb") as auxiliar:
            for posicion in range(self.registros(self.ruta_auxiliar)):
                empleado, estado = self._leer(auxiliar, posicion)
                if estado == ACTIVO:
                    pendientes.append(empleado)
        pendientes.sort(key=lambda empleado: empleado.employee_id)

        temporal = self.ruta_datos + ".tmp"
        indice = 0
        with open(self.ruta_datos, "rb") as datos, open(temporal, "wb") as destino:
            def volcar(empleado):
                destino.write(empaquetar(empleado) + struct.pack("<B", ACTIVO))
                self.accesos += 1

            for posicion in range(self.registros()):
                empleado, estado = self._leer(datos, posicion)
                if estado != ACTIVO:
                    continue
                while indice < len(pendientes) and pendientes[indice].employee_id < empleado.employee_id:
                    volcar(pendientes[indice])
                    indice += 1
                volcar(empleado)
            while indice < len(pendientes):
                volcar(pendientes[indice])
                indice += 1

        os.replace(temporal, self.ruta_datos)
        open(self.ruta_auxiliar, "wb").close()
        self.reconstrucciones += 1


def main():
    ruta_csv = sys.argv[1] if len(sys.argv) > 1 else os.path.join("data", "employee.csv")
    empleados = leer_csv(ruta_csv)[:2000]
    archivo = SequentialFile(os.path.join("data", "demo_seq.dat"),
                             os.path.join("data", "demo_seq_aux.dat"), k=16)
    archivo.build(empleados)

    print(f"Sequential File sobre {ruta_csv}")
    print(f"  tamano de registro : {TAMANO_REGISTRO} bytes (112 de datos + 1 de estado)")
    print(f"  registros cargados : {archivo.registros()}")
    print(f"  k del auxiliar     : {archivo.k}")

    clave = empleados[len(empleados) // 2].employee_id
    archivo.reiniciar_contador()
    encontrado = archivo.search(clave)
    print(f"  search({clave}) -> {encontrado.employee_name}, {encontrado.department} "
          f"[{archivo.accesos} accesos]")

    nuevo = Empleado(999999, "Nicolas Llerena", 23, "Peru", "Engineering", "Analyst",
                     54321.5, "01/09/2026")
    archivo.reiniciar_contador()
    archivo.insert(nuevo)
    print(f"  insert(999999) -> auxiliar con {archivo.registros(archivo.ruta_auxiliar)} "
          f"registros [{archivo.accesos} accesos]")
    print(f"  search(999999) -> {archivo.search(999999).employee_name}")

    for extra in range(16):
        archivo.insert(Empleado(900000 + extra, f"Temporal {extra}", 30, "Peru", "Sales",
                                "Analyst", 1000.0 + extra, "01/01/2026"))
    print(f"  tras superar k     : reconstrucciones={archivo.reconstrucciones}, "
          f"auxiliar={archivo.registros(archivo.ruta_auxiliar)}, datos={archivo.registros()}")

    archivo.reiniciar_contador()
    print(f"  remove({clave}) -> {archivo.remove(clave)} [{archivo.accesos} accesos]")
    print(f"  search({clave}) tras eliminar -> {archivo.search(clave)}")

    inicial, final = empleados[10].employee_id, empleados[10].employee_id + 500
    archivo.reiniciar_contador()
    rango = archivo.range_search(inicial, final)
    print(f"  rangeSearch({inicial}, {final}) -> {len(rango)} empleados "
          f"[{archivo.accesos} accesos]")
    for empleado in rango[:3]:
        print(f"      {empleado.employee_id}  {empleado.employee_name:22s} {empleado.department}")
    print(f"  registros validos  : {len(archivo.load())}")


if __name__ == "__main__":
    main()
