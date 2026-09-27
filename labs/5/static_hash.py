import os
import random
import struct
import sys

from registro import TAMANO, Empleado, desempaquetar, empaquetar, leer_csv

FORMATO_ARCHIVO = "<iiii"
TAMANO_ARCHIVO = struct.calcsize(FORMATO_ARCHIVO)
FORMATO_CABECERA = "<ii"
TAMANO_CABECERA = struct.calcsize(FORMATO_CABECERA)
NULO = -1
BUCKETS = 101
FACTOR_BLOQUE = 8


class StaticHashFile:
    def __init__(self, ruta, buckets=BUCKETS, factor_bloque=FACTOR_BLOQUE):
        self.ruta = ruta
        self.lecturas = 0
        self.escrituras = 0
        nuevo = not os.path.exists(ruta) or os.path.getsize(ruta) < TAMANO_ARCHIVO
        if nuevo:
            with open(ruta, "wb") as destino:
                destino.write(struct.pack(FORMATO_ARCHIVO, buckets, factor_bloque, buckets, NULO))
        self.flujo = open(ruta, "r+b")
        self.flujo.seek(0)
        self.buckets, self.factor_bloque, self.bloques, self.libre = struct.unpack(
            FORMATO_ARCHIVO, self.flujo.read(TAMANO_ARCHIVO))
        self.bloque = TAMANO_CABECERA + self.factor_bloque * TAMANO
        if nuevo:
            for numero in range(self.buckets):
                self._escribir(numero, [], NULO)

    def cerrar(self):
        self._guardar_cabecera()
        self.flujo.close()

    def reiniciar_contadores(self):
        self.lecturas = 0
        self.escrituras = 0

    @property
    def accesos(self):
        return self.lecturas + self.escrituras

    def hash(self, clave):
        return clave % self.buckets

    def _guardar_cabecera(self):
        self.flujo.seek(0)
        self.flujo.write(struct.pack(FORMATO_ARCHIVO, self.buckets, self.factor_bloque,
                                     self.bloques, self.libre))

    def _leer(self, numero):
        self.flujo.seek(TAMANO_ARCHIVO + numero * self.bloque)
        blob = self.flujo.read(self.bloque)
        self.lecturas += 1
        cantidad, siguiente = struct.unpack_from(FORMATO_CABECERA, blob)
        registros = [desempaquetar(blob, TAMANO_CABECERA + posicion * TAMANO)
                     for posicion in range(cantidad)]
        return registros, siguiente

    def _escribir(self, numero, registros, siguiente):
        blob = bytearray(self.bloque)
        struct.pack_into(FORMATO_CABECERA, blob, 0, len(registros), siguiente)
        for posicion, empleado in enumerate(registros):
            inicio = TAMANO_CABECERA + posicion * TAMANO
            blob[inicio:inicio + TAMANO] = empaquetar(empleado)
        self.flujo.seek(TAMANO_ARCHIVO + numero * self.bloque)
        self.flujo.write(blob)
        self.escrituras += 1

    def _nuevo_overflow(self):
        if self.libre != NULO:
            numero = self.libre
            _, self.libre = self._leer(numero)
        else:
            numero = self.bloques
            self.bloques += 1
        self._escribir(numero, [], NULO)
        self._guardar_cabecera()
        return numero

    def _liberar(self, numero):
        self._escribir(numero, [], self.libre)
        self.libre = numero
        self._guardar_cabecera()

    def cadena(self, clave):
        numeros = []
        numero = self.hash(clave)
        while numero != NULO:
            numeros.append(numero)
            _, numero = self._leer(numero)
        return numeros

    def insert(self, empleado):
        numero = self.hash(empleado.employee_id)
        while True:
            registros, siguiente = self._leer(numero)
            if len(registros) < self.factor_bloque:
                registros.append(empleado)
                self._escribir(numero, registros, siguiente)
                return True
            if siguiente == NULO:
                nuevo = self._nuevo_overflow()
                self._escribir(numero, registros, nuevo)
                self._escribir(nuevo, [empleado], NULO)
                return True
            numero = siguiente

    def search(self, clave):
        numero = self.hash(clave)
        while numero != NULO:
            registros, siguiente = self._leer(numero)
            for empleado in registros:
                if empleado.employee_id == clave:
                    return empleado
            numero = siguiente
        return None

    def remove(self, clave):
        numero = self.hash(clave)
        cadena = []
        while numero != NULO:
            registros, siguiente = self._leer(numero)
            cadena.append((numero, registros, siguiente))
            numero = siguiente
        for numero, registros, siguiente in cadena:
            indice = next((i for i, empleado in enumerate(registros)
                           if empleado.employee_id == clave), None)
            if indice is None:
                continue
            ultimo_numero, ultimos, ultimo_siguiente = cadena[-1]
            if numero == ultimo_numero:
                registros.pop(indice)
                self._escribir(numero, registros, siguiente)
            else:
                registros[indice] = ultimos.pop()
                self._escribir(numero, registros, siguiente)
                self._escribir(ultimo_numero, ultimos, ultimo_siguiente)
            if not cadena[-1][1] and len(cadena) > 1:
                anterior_numero, anteriores, _ = cadena[-2]
                self._escribir(anterior_numero, anteriores, NULO)
                self._liberar(ultimo_numero)
            return True
        return False


    def load(self):
        todos = []
        for primario in range(self.buckets):
            numero = primario
            while numero != NULO:
                registros, numero = self._leer(numero)
                todos.extend(registros)
        return todos

    def estadisticas(self):
        longitudes = []
        registros_totales = 0
        for primario in range(self.buckets):
            longitud = 0
            numero = primario
            while numero != NULO:
                registros, numero = self._leer(numero)
                registros_totales += len(registros)
                longitud += 1
            longitudes.append(longitud)
        capacidad = self.buckets * self.factor_bloque
        return {"registros": registros_totales,
                "buckets_primarios": self.buckets,
                "factor_bloque": self.factor_bloque,
                "capacidad_primaria": capacidad,
                "factor_carga": registros_totales / capacidad,
                "cadena_promedio": sum(longitudes) / len(longitudes),
                "cadena_maxima": max(longitudes),
                "con_overflow": sum(1 for longitud in longitudes if longitud > 1),
                "bloques": self.bloques,
                "bytes": os.path.getsize(self.ruta)}


def construir(ruta, empleados, buckets=BUCKETS, factor_bloque=FACTOR_BLOQUE):
    if os.path.exists(ruta):
        os.remove(ruta)
    archivo = StaticHashFile(ruta, buckets, factor_bloque)
    for empleado in empleados:
        archivo.insert(empleado)
    return archivo


def main():
    ruta_csv = sys.argv[1] if len(sys.argv) > 1 else os.path.join("data", "employee.csv")
    cantidad = int(sys.argv[2]) if len(sys.argv) > 2 else 1200
    empleados = leer_csv(ruta_csv, cantidad)
    archivo = construir(os.path.join("data", "demo_hash.dat"), empleados)
    resumen = archivo.estadisticas()

    print(f"Static Hash File sobre {ruta_csv}")
    print(f"  buckets primarios  : {resumen['buckets_primarios']} (h(k) = k mod "
          f"{resumen['buckets_primarios']})")
    print(f"  factor de bloque   : {resumen['factor_bloque']} registros por bucket")
    print(f"  tamano de bloque   : {archivo.bloque} bytes = {TAMANO_CABECERA} de cabecera + "
          f"{resumen['factor_bloque']} x {TAMANO}")
    print(f"  registros          : {resumen['registros']}  "
          f"(factor de carga {resumen['factor_carga']:.2f})")
    print(f"  cadenas            : promedio {resumen['cadena_promedio']:.2f} bloques, "
          f"maxima {resumen['cadena_maxima']}, {resumen['con_overflow']} buckets con overflow")

    clave = empleados[len(empleados) // 2].employee_id
    archivo.reiniciar_contadores()
    encontrado = archivo.search(clave)
    print(f"  search({clave}) -> {encontrado.employee_name}, {encontrado.department} "
          f"[{archivo.lecturas} lecturas, bucket {archivo.hash(clave)}]")
    archivo.reiniciar_contadores()
    print(f"  search(1) -> {archivo.search(1)} [{archivo.lecturas} lecturas]")

    nuevo = Empleado(999999, "Nicolas Llerena", "Peru", "Development", 54321.0, "09/09/2026")
    archivo.reiniciar_contadores()
    archivo.insert(nuevo)
    print(f"  insert(999999) -> bucket {archivo.hash(999999)}, cadena "
          f"{archivo.cadena(999999)} [{archivo.lecturas}L {archivo.escrituras}E]")

    objetivo = archivo.hash(999999)
    cadena_antes = archivo.cadena(999999)
    del_claves = [empleado.employee_id for empleado in archivo.load()
                  if archivo.hash(empleado.employee_id) == objetivo][:archivo.factor_bloque]
    print(f"  bucket {objetivo} antes  : cadena de {len(cadena_antes)} bloques {cadena_antes}")
    for clave_baja in del_claves:
        archivo.remove(clave_baja)
    cadena_despues = archivo.cadena(999999)
    print(f"  tras {len(del_claves)} bajas   : cadena de {len(cadena_despues)} bloques "
          f"{cadena_despues}, lista de libres = {archivo.libre}")
    print(f"  el bloque liberado se reutiliza en la siguiente alta: ", end="")
    reciclado = archivo._nuevo_overflow()
    print(f"bloque {reciclado}")
    archivo._liberar(reciclado)

    validos = archivo.load()
    print(f"  registros validos  : {len(validos)} (sin duplicados: "
          f"{len({empleado.employee_id for empleado in validos})})")
    archivo.cerrar()

    print("  prueba de estres de la eliminacion:")
    rng = random.Random(5)
    mezcla = leer_csv(ruta_csv, 2000)
    rng.shuffle(mezcla)
    for buckets, factor in ((7, 3), (23, 4), (101, 8)):
        prueba = construir(os.path.join("data", "demo_estres.dat"), mezcla, buckets, factor)
        vivos = {empleado.employee_id: empleado for empleado in mezcla}
        claves = list(vivos)
        rng.shuffle(claves)
        for numero, clave in enumerate(claves[:1800], 1):
            assert prueba.remove(clave), f"no se elimino {clave}"
            del vivos[clave]
            if numero % 600 == 0:
                assert sorted(e.employee_id for e in prueba.load()) == sorted(vivos)
                assert prueba.search(clave) is None
        libres = 0
        siguiente = prueba.libre
        while siguiente != NULO:
            libres += 1
            _, siguiente = prueba._leer(siguiente)
        resumen = prueba.estadisticas()
        print(f"      M={buckets:3d} FB={factor}: 2000 altas y 1800 bajas -> quedan "
              f"{resumen['registros']} registros, cadena maxima {resumen['cadena_maxima']}, "
              f"{libres} bloques reciclables")
        prueba.cerrar()
    os.remove(os.path.join("data", "demo_estres.dat"))


if __name__ == "__main__":
    main()
