import os
import struct
import sys
from dataclasses import dataclass

from registro import FORMATO, TAMANO, Empleado, desempaquetar, empaquetar, leer_csv

FORMATO_CABECERA = "<iii"
TAMANO_CABECERA = struct.calcsize(FORMATO_CABECERA)
FORMATO_ENLACES = "<iii"
TAMANO_NODO = TAMANO + struct.calcsize(FORMATO_ENLACES)
NULO = -1


@dataclass
class Nodo:
    empleado: Empleado
    izquierda: int = NULO
    derecha: int = NULO
    altura: int = 1

    def clave(self):
        return self.empleado.employee_id


class AVLFile:
    def __init__(self, ruta):
        self.ruta = ruta
        self.accesos = 0
        if not os.path.exists(ruta) or os.path.getsize(ruta) < TAMANO_CABECERA:
            with open(ruta, "wb") as destino:
                destino.write(struct.pack(FORMATO_CABECERA, NULO, NULO, 0))
        self.flujo = open(ruta, "r+b")
        self.flujo.seek(0)
        self.raiz, self.libre, self.nodos = struct.unpack(FORMATO_CABECERA,
                                                          self.flujo.read(TAMANO_CABECERA))

    def cerrar(self):
        self._guardar_cabecera()
        self.flujo.close()

    def reiniciar_contador(self):
        self.accesos = 0

    def _guardar_cabecera(self):
        self.flujo.seek(0)
        self.flujo.write(struct.pack(FORMATO_CABECERA, self.raiz, self.libre, self.nodos))

    def _desplazamiento(self, posicion):
        return TAMANO_CABECERA + posicion * TAMANO_NODO

    def _leer(self, posicion):
        self.flujo.seek(self._desplazamiento(posicion))
        blob = self.flujo.read(TAMANO_NODO)
        self.accesos += 1
        izquierda, derecha, altura = struct.unpack_from(FORMATO_ENLACES, blob, TAMANO)
        return Nodo(desempaquetar(blob), izquierda, derecha, altura)

    def _escribir(self, posicion, nodo):
        self.flujo.seek(self._desplazamiento(posicion))
        self.flujo.write(empaquetar(nodo.empleado) +
                         struct.pack(FORMATO_ENLACES, nodo.izquierda, nodo.derecha, nodo.altura))
        self.accesos += 1

    def _nuevo(self, empleado):
        nodo = Nodo(empleado)
        if self.libre != NULO:
            posicion = self.libre
            self.libre = self._leer(posicion).izquierda
        else:
            posicion = (os.path.getsize(self.ruta) - TAMANO_CABECERA) // TAMANO_NODO
        self._escribir(posicion, nodo)
        self.nodos += 1
        return posicion

    def _liberar(self, posicion, nodo):
        nodo.izquierda = self.libre
        nodo.derecha = NULO
        nodo.altura = 0
        self._escribir(posicion, nodo)
        self.libre = posicion
        self.nodos -= 1

    def _altura(self, posicion):
        return 0 if posicion == NULO else self._leer(posicion).altura

    def _rotar_derecha(self, posicion, nodo):
        pivote_posicion = nodo.izquierda
        pivote = self._leer(pivote_posicion)
        nodo.izquierda = pivote.derecha
        pivote.derecha = posicion
        nodo.altura = 1 + max(self._altura(nodo.izquierda), self._altura(nodo.derecha))
        self._escribir(posicion, nodo)
        pivote.altura = 1 + max(self._altura(pivote.izquierda), self._altura(pivote.derecha))
        self._escribir(pivote_posicion, pivote)
        return pivote_posicion

    def _rotar_izquierda(self, posicion, nodo):
        pivote_posicion = nodo.derecha
        pivote = self._leer(pivote_posicion)
        nodo.derecha = pivote.izquierda
        pivote.izquierda = posicion
        nodo.altura = 1 + max(self._altura(nodo.izquierda), self._altura(nodo.derecha))
        self._escribir(posicion, nodo)
        pivote.altura = 1 + max(self._altura(pivote.izquierda), self._altura(pivote.derecha))
        self._escribir(pivote_posicion, pivote)
        return pivote_posicion

    def _balancear(self, posicion, nodo):
        izquierda = self._altura(nodo.izquierda)
        derecha = self._altura(nodo.derecha)
        nodo.altura = 1 + max(izquierda, derecha)
        balance = izquierda - derecha
        if balance > 1:
            hijo = self._leer(nodo.izquierda)
            if self._altura(hijo.izquierda) < self._altura(hijo.derecha):
                nodo.izquierda = self._rotar_izquierda(nodo.izquierda, hijo)
            return self._rotar_derecha(posicion, nodo)
        if balance < -1:
            hijo = self._leer(nodo.derecha)
            if self._altura(hijo.derecha) < self._altura(hijo.izquierda):
                nodo.derecha = self._rotar_derecha(nodo.derecha, hijo)
            return self._rotar_izquierda(posicion, nodo)
        self._escribir(posicion, nodo)
        return posicion

    def build(self, empleados):
        for empleado in empleados:
            self.insert(empleado)
        return self.nodos

    def insert(self, empleado):
        self.raiz = self._insertar(self.raiz, empleado)
        self._guardar_cabecera()
        return True

    def _insertar(self, posicion, empleado):
        if posicion == NULO:
            return self._nuevo(empleado)
        nodo = self._leer(posicion)
        if empleado.employee_id < nodo.clave():
            nodo.izquierda = self._insertar(nodo.izquierda, empleado)
        elif empleado.employee_id > nodo.clave():
            nodo.derecha = self._insertar(nodo.derecha, empleado)
        else:
            return posicion
        return self._balancear(posicion, nodo)

    def search(self, clave):
        posicion = self.raiz
        while posicion != NULO:
            nodo = self._leer(posicion)
            if clave == nodo.clave():
                return nodo.empleado
            posicion = nodo.izquierda if clave < nodo.clave() else nodo.derecha
        return None

    def remove(self, clave):
        self.raiz, eliminado = self._eliminar(self.raiz, clave)
        self._guardar_cabecera()
        return eliminado

    def _eliminar(self, posicion, clave):
        if posicion == NULO:
            return NULO, False
        nodo = self._leer(posicion)
        if clave < nodo.clave():
            nodo.izquierda, eliminado = self._eliminar(nodo.izquierda, clave)
        elif clave > nodo.clave():
            nodo.derecha, eliminado = self._eliminar(nodo.derecha, clave)
        else:
            eliminado = True
            if nodo.izquierda == NULO or nodo.derecha == NULO:
                hijo = nodo.izquierda if nodo.izquierda != NULO else nodo.derecha
                self._liberar(posicion, nodo)
                return hijo, True
            sucesor = self._leer(self._minimo(nodo.derecha))
            nodo.empleado = sucesor.empleado
            nodo.derecha, _ = self._eliminar(nodo.derecha, sucesor.clave())
        if not eliminado:
            return posicion, False
        return self._balancear(posicion, nodo), True

    def _minimo(self, posicion):
        while True:
            nodo = self._leer(posicion)
            if nodo.izquierda == NULO:
                return posicion
            posicion = nodo.izquierda

    def range_search(self, clave_inicial, clave_final):
        encontrados = []
        self._rango(self.raiz, clave_inicial, clave_final, encontrados)
        return encontrados

    def _rango(self, posicion, clave_inicial, clave_final, encontrados):
        if posicion == NULO:
            return
        nodo = self._leer(posicion)
        if nodo.clave() > clave_inicial:
            self._rango(nodo.izquierda, clave_inicial, clave_final, encontrados)
        if clave_inicial <= nodo.clave() <= clave_final:
            encontrados.append(nodo.empleado)
        if nodo.clave() < clave_final:
            self._rango(nodo.derecha, clave_inicial, clave_final, encontrados)

    def load(self):
        return self.range_search(-2 ** 31, 2 ** 31 - 1)

    def altura(self):
        return self._altura(self.raiz)


def main():
    ruta_csv = sys.argv[1] if len(sys.argv) > 1 else os.path.join("data", "employee.csv")
    empleados = leer_csv(ruta_csv)[:2000]
    ruta = os.path.join("data", "demo_avl.dat")
    if os.path.exists(ruta):
        os.remove(ruta)
    arbol = AVLFile(ruta)
    arbol.build(empleados)

    print(f"AVL File sobre {ruta_csv}")
    print(f"  tamano de nodo     : {TAMANO_NODO} bytes (112 de datos + 12 de enlaces)")
    print(f"  nodos en el arbol  : {arbol.nodos}")
    print(f"  altura del arbol   : {arbol.altura()} (log2({arbol.nodos}) = "
          f"{len(bin(arbol.nodos)) - 3})")

    clave = empleados[len(empleados) // 2].employee_id
    arbol.reiniciar_contador()
    encontrado = arbol.search(clave)
    print(f"  search({clave}) -> {encontrado.employee_name}, {encontrado.department} "
          f"[{arbol.accesos} accesos]")

    nuevo = Empleado(999999, "Nicolas Llerena", 23, "Peru", "Development", "Engineer",
                     54321.0, "01/09/2026")
    arbol.reiniciar_contador()
    arbol.insert(nuevo)
    print(f"  insert(999999) -> altura={arbol.altura()}, nodos={arbol.nodos} "
          f"[{arbol.accesos} accesos]")
    print(f"  search(999999) -> {arbol.search(999999).employee_name}")

    arbol.reiniciar_contador()
    print(f"  remove({clave}) -> {arbol.remove(clave)} [{arbol.accesos} accesos], "
          f"altura={arbol.altura()}, nodos={arbol.nodos}")
    print(f"  search({clave}) tras eliminar -> {arbol.search(clave)}")

    inicial, final = empleados[10].employee_id, empleados[10].employee_id + 500
    arbol.reiniciar_contador()
    rango = arbol.range_search(inicial, final)
    print(f"  rangeSearch({inicial}, {final}) -> {len(rango)} empleados "
          f"[{arbol.accesos} accesos]")
    for empleado in rango[:3]:
        print(f"      {empleado.employee_id}  {empleado.employee_name:22s} {empleado.department}")

    recorrido = arbol.load()
    ordenado = all(recorrido[i].employee_id < recorrido[i + 1].employee_id
                   for i in range(len(recorrido) - 1))
    print(f"  recorrido inorden  : {len(recorrido)} registros, ordenado={ordenado}")
    arbol.cerrar()


if __name__ == "__main__":
    main()
