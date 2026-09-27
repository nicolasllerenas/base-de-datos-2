"""Arbol B+ persistente en memoria secundaria.

Cada nodo del arbol ocupa exactamente un bloque fisico del archivo, cuyo tamano
queda determinado por el orden M:

    BLOQUE(M) = CABECERA (12 bytes) + (M - 1) * 88 bytes de registro

Un nodo interno guarda hasta M-1 claves separadoras y M punteros a bloques hijo;
una hoja guarda hasta M-1 registros completos mas el puntero al siguiente y al
anterior bloque hoja, que es lo que permite resolver un rango recorriendo las
hojas sin volver a bajar por el arbol.
"""

import os
import random
import struct
import sys
from dataclasses import dataclass, field

from registro import TAMANO, Empleado, desempaquetar, empaquetar, leer_csv

FORMATO_ARCHIVO = "<iiiiii"
TAMANO_ARCHIVO = struct.calcsize(FORMATO_ARCHIVO)
FORMATO_CABECERA = "<BBHii"
TAMANO_CABECERA = struct.calcsize(FORMATO_CABECERA)
INTERNO, HOJA = 0, 1
NULO = -1
ORDEN = 64


@dataclass
class Nodo:
    """Imagen en memoria de un bloque del archivo."""

    hoja: bool
    bloque: int = NULO
    claves: list = field(default_factory=list)
    hijos: list = field(default_factory=list)
    registros: list = field(default_factory=list)
    siguiente: int = NULO
    anterior: int = NULO

    def ocupacion(self):
        return len(self.registros) if self.hoja else len(self.claves)

    def claves_de_hoja(self):
        return [registro.employee_id for registro in self.registros]


class BPlusTreeFile:
    """Archivo indexado por arbol B+ sobre el Employee_ID."""

    def __init__(self, ruta, orden=ORDEN):
        self.ruta = ruta
        self.lecturas = 0
        self.escrituras = 0
        nuevo = not os.path.exists(ruta) or os.path.getsize(ruta) < TAMANO_ARCHIVO
        if nuevo:
            with open(ruta, "wb") as destino:
                destino.write(struct.pack(FORMATO_ARCHIVO, NULO, 0, 0, 0, orden, NULO))
        self.flujo = open(ruta, "r+b")
        self.flujo.seek(0)
        (self.raiz, self.bloques, self.altura, self.registros,
         self.orden, self.libre) = struct.unpack(FORMATO_ARCHIVO,
                                                 self.flujo.read(TAMANO_ARCHIVO))
        self.maximo = self.orden - 1
        self.minimo_hoja = (self.orden) // 2
        self.minimo_interno = (self.orden + 1) // 2 - 1
        self.bloque = TAMANO_CABECERA + self.maximo * TAMANO

    def cerrar(self):
        self._guardar_cabecera()
        self.flujo.close()

    def reiniciar_contadores(self):
        self.lecturas = 0
        self.escrituras = 0

    @property
    def accesos(self):
        return self.lecturas + self.escrituras

    # ------------------------------------------------------------------ disco

    def _guardar_cabecera(self):
        self.flujo.seek(0)
        self.flujo.write(struct.pack(FORMATO_ARCHIVO, self.raiz, self.bloques, self.altura,
                                     self.registros, self.orden, self.libre))

    def _desplazamiento(self, bloque):
        return TAMANO_ARCHIVO + bloque * self.bloque

    def read_node(self, bloque):
        """Lee un bloque del archivo y lo convierte en un Nodo."""
        self.flujo.seek(self._desplazamiento(bloque))
        blob = self.flujo.read(self.bloque)
        self.lecturas += 1
        tipo, _, cantidad, siguiente, anterior = struct.unpack_from(FORMATO_CABECERA, blob)
        nodo = Nodo(hoja=tipo == HOJA, bloque=bloque, siguiente=siguiente, anterior=anterior)
        cursor = TAMANO_CABECERA
        if nodo.hoja:
            for _ in range(cantidad):
                nodo.registros.append(desempaquetar(blob, cursor))
                cursor += TAMANO
        else:
            nodo.claves = list(struct.unpack_from(f"<{cantidad}i", blob, cursor))
            cursor += cantidad * 4
            nodo.hijos = list(struct.unpack_from(f"<{cantidad + 1}i", blob, cursor))
        return nodo

    def write_node(self, nodo):
        """Serializa un Nodo y lo escribe en su bloque."""
        blob = bytearray(self.bloque)
        struct.pack_into(FORMATO_CABECERA, blob, 0, HOJA if nodo.hoja else INTERNO, 0,
                         nodo.ocupacion(), nodo.siguiente, nodo.anterior)
        cursor = TAMANO_CABECERA
        if nodo.hoja:
            for empleado in nodo.registros:
                blob[cursor:cursor + TAMANO] = empaquetar(empleado)
                cursor += TAMANO
        else:
            struct.pack_into(f"<{len(nodo.claves)}i", blob, cursor, *nodo.claves)
            cursor += len(nodo.claves) * 4
            struct.pack_into(f"<{len(nodo.hijos)}i", blob, cursor, *nodo.hijos)
        self.flujo.seek(self._desplazamiento(nodo.bloque))
        self.flujo.write(blob)
        self.escrituras += 1

    def _reservar(self, nodo):
        """Asigna un bloque libre (reutilizando la lista de libres) y escribe el nodo."""
        if self.libre != NULO:
            nodo.bloque = self.libre
            self.libre = self.read_node(self.libre).siguiente
        else:
            nodo.bloque = self.bloques
            self.bloques += 1
        self.write_node(nodo)
        return nodo.bloque

    def _liberar(self, nodo):
        """Devuelve el bloque de un nodo fusionado a la lista de libres."""
        nodo.siguiente = self.libre
        nodo.claves, nodo.hijos, nodo.registros = [], [], []
        self.write_node(nodo)
        self.libre = nodo.bloque

    # --------------------------------------------------------------- busqueda

    @staticmethod
    def _posicion(claves, clave):
        """Primer indice cuya clave es mayor que la buscada (busqueda binaria)."""
        inicio, fin = 0, len(claves)
        while inicio < fin:
            medio = (inicio + fin) // 2
            if clave < claves[medio]:
                fin = medio
            else:
                inicio = medio + 1
        return inicio

    def _hoja_de(self, clave):
        """Desciende de la raiz a la hoja donde deberia estar la clave."""
        if self.raiz == NULO:
            return None
        nodo = self.read_node(self.raiz)
        while not nodo.hoja:
            nodo = self.read_node(nodo.hijos[self._posicion(nodo.claves, clave)])
        return nodo

    def search(self, clave):
        """Devuelve el registro con esa clave o None si no existe."""
        hoja = self._hoja_de(clave)
        if hoja is None:
            return None
        for empleado in hoja.registros:
            if empleado.employee_id == clave:
                return empleado
        return None

    def range_search(self, clave_inicial, clave_final):
        """Devuelve los registros del intervalo recorriendo la lista de hojas."""
        encontrados = []
        hoja = self._hoja_de(clave_inicial)
        while hoja is not None:
            for empleado in hoja.registros:
                if empleado.employee_id > clave_final:
                    return encontrados
                if empleado.employee_id >= clave_inicial:
                    encontrados.append(empleado)
            if hoja.siguiente == NULO:
                break
            hoja = self.read_node(hoja.siguiente)
        return encontrados

    def load(self):
        """Recorre todas las hojas en orden y devuelve el archivo completo."""
        if self.raiz == NULO:
            return []
        nodo = self.read_node(self.raiz)
        while not nodo.hoja:
            nodo = self.read_node(nodo.hijos[0])
        todos = []
        while True:
            todos.extend(nodo.registros)
            if nodo.siguiente == NULO:
                return todos
            nodo = self.read_node(nodo.siguiente)

    # -------------------------------------------------------------- insercion

    def insert(self, empleado):
        """Inserta un registro dividiendo los nodos que se desborden."""
        if self.raiz == NULO:
            raiz = Nodo(hoja=True, registros=[empleado])
            self.raiz = self._reservar(raiz)
            self.altura = 1
            self.registros = 1
            self._guardar_cabecera()
            return True
        promocion = self._insertar(self.raiz, empleado)
        if promocion is not None:
            clave, derecha = promocion
            nueva = Nodo(hoja=False, claves=[clave], hijos=[self.raiz, derecha])
            self.raiz = self._reservar(nueva)
            self.altura += 1
        self.registros += 1
        self._guardar_cabecera()
        return True

    def _insertar(self, bloque, empleado):
        """Inserta recursivamente y devuelve (clave, bloque) si hubo split."""
        nodo = self.read_node(bloque)
        if nodo.hoja:
            posicion = self._posicion(nodo.claves_de_hoja(), empleado.employee_id)
            nodo.registros.insert(posicion, empleado)
            if nodo.ocupacion() <= self.maximo:
                self.write_node(nodo)
                return None
            return self._dividir_hoja(nodo)
        indice = self._posicion(nodo.claves, empleado.employee_id)
        promocion = self._insertar(nodo.hijos[indice], empleado)
        if promocion is None:
            return None
        clave, derecha = promocion
        nodo.claves.insert(indice, clave)
        nodo.hijos.insert(indice + 1, derecha)
        if nodo.ocupacion() <= self.maximo:
            self.write_node(nodo)
            return None
        return self._dividir_interno(nodo)

    def _dividir_hoja(self, nodo):
        """Parte una hoja en dos y copia hacia arriba la primera clave derecha."""
        corte = (self.maximo + 1) // 2
        derecha = Nodo(hoja=True, registros=nodo.registros[corte:],
                       siguiente=nodo.siguiente, anterior=nodo.bloque)
        nodo.registros = nodo.registros[:corte]
        bloque_derecha = self._reservar(derecha)
        if derecha.siguiente != NULO:
            posterior = self.read_node(derecha.siguiente)
            posterior.anterior = bloque_derecha
            self.write_node(posterior)
        nodo.siguiente = bloque_derecha
        self.write_node(nodo)
        return derecha.registros[0].employee_id, bloque_derecha

    def _dividir_interno(self, nodo):
        """Parte un nodo interno y sube la clave del medio."""
        medio = len(nodo.claves) // 2
        clave = nodo.claves[medio]
        derecha = Nodo(hoja=False, claves=nodo.claves[medio + 1:], hijos=nodo.hijos[medio + 1:])
        nodo.claves = nodo.claves[:medio]
        nodo.hijos = nodo.hijos[:medio + 1]
        bloque_derecha = self._reservar(derecha)
        self.write_node(nodo)
        return clave, bloque_derecha

    # ------------------------------------------------------------ eliminacion

    def remove(self, clave):
        """Elimina fisicamente la clave y rebalancea con prestamo o fusion."""
        if self.raiz == NULO:
            return False
        if not self._eliminar(self.raiz, clave):
            return False
        raiz = self.read_node(self.raiz)
        if not raiz.hoja and len(raiz.claves) == 0:
            self.raiz = raiz.hijos[0]
            self.altura -= 1
            self._liberar(raiz)
        elif raiz.hoja and not raiz.registros:
            self._liberar(raiz)
            self.raiz = NULO
            self.altura = 0
        self.registros -= 1
        self._guardar_cabecera()
        return True

    def _eliminar(self, bloque, clave):
        nodo = self.read_node(bloque)
        if nodo.hoja:
            claves = nodo.claves_de_hoja()
            if clave not in claves:
                return False
            del nodo.registros[claves.index(clave)]
            self.write_node(nodo)
            return True
        indice = self._posicion(nodo.claves, clave)
        if not self._eliminar(nodo.hijos[indice], clave):
            return False
        self._reparar(nodo, indice)
        return True

    def _reparar(self, padre, indice):
        """Repone el minimo de ocupacion del hijo indicado."""
        hijo = self.read_node(padre.hijos[indice])
        minimo = self.minimo_hoja if hijo.hoja else self.minimo_interno
        if hijo.ocupacion() >= minimo:
            return
        if indice > 0:
            izquierda = self.read_node(padre.hijos[indice - 1])
            if izquierda.ocupacion() > minimo:
                self._prestar_de_izquierda(padre, indice, izquierda, hijo)
                return
        if indice < len(padre.hijos) - 1:
            derecha = self.read_node(padre.hijos[indice + 1])
            if derecha.ocupacion() > minimo:
                self._prestar_de_derecha(padre, indice, hijo, derecha)
                return
        if indice > 0:
            self._fusionar(padre, indice - 1)
        else:
            self._fusionar(padre, indice)

    def _prestar_de_izquierda(self, padre, indice, izquierda, hijo):
        if hijo.hoja:
            hijo.registros.insert(0, izquierda.registros.pop())
            padre.claves[indice - 1] = hijo.registros[0].employee_id
        else:
            hijo.claves.insert(0, padre.claves[indice - 1])
            hijo.hijos.insert(0, izquierda.hijos.pop())
            padre.claves[indice - 1] = izquierda.claves.pop()
        self.write_node(izquierda)
        self.write_node(hijo)
        self.write_node(padre)

    def _prestar_de_derecha(self, padre, indice, hijo, derecha):
        if hijo.hoja:
            hijo.registros.append(derecha.registros.pop(0))
            padre.claves[indice] = derecha.registros[0].employee_id
        else:
            hijo.claves.append(padre.claves[indice])
            hijo.hijos.append(derecha.hijos.pop(0))
            padre.claves[indice] = derecha.claves.pop(0)
        self.write_node(derecha)
        self.write_node(hijo)
        self.write_node(padre)

    def _fusionar(self, padre, indice):
        """Une el hijo indice con su hermano derecho y baja la clave separadora."""
        izquierda = self.read_node(padre.hijos[indice])
        derecha = self.read_node(padre.hijos[indice + 1])
        if izquierda.hoja:
            izquierda.registros.extend(derecha.registros)
            izquierda.siguiente = derecha.siguiente
            if derecha.siguiente != NULO:
                posterior = self.read_node(derecha.siguiente)
                posterior.anterior = izquierda.bloque
                self.write_node(posterior)
        else:
            izquierda.claves.append(padre.claves[indice])
            izquierda.claves.extend(derecha.claves)
            izquierda.hijos.extend(derecha.hijos)
        del padre.claves[indice]
        del padre.hijos[indice + 1]
        self.write_node(izquierda)
        self.write_node(padre)
        self._liberar(derecha)

    # ------------------------------------------------------------ diagnostico

    def validar(self):
        """Comprueba los invariantes del arbol y devuelve un resumen."""
        if self.raiz == NULO:
            return {"registros": 0, "altura": 0, "hojas": 0, "ocupacion_hojas": 0.0}
        profundidades = set()
        hojas = []
        pendientes = [(self.raiz, 1, None, None)]
        while pendientes:
            bloque, nivel, minimo, maximo = pendientes.pop()
            nodo = self.read_node(bloque)
            claves = nodo.claves_de_hoja() if nodo.hoja else nodo.claves
            if claves != sorted(claves):
                raise AssertionError(f"claves desordenadas en el bloque {bloque}")
            if minimo is not None and claves and claves[0] < minimo:
                raise AssertionError(f"clave fuera del rango del padre en {bloque}")
            if maximo is not None and claves and claves[-1] >= maximo:
                raise AssertionError(f"clave fuera del rango del padre en {bloque}")
            if bloque != self.raiz:
                minimo_esperado = self.minimo_hoja if nodo.hoja else self.minimo_interno
                if nodo.ocupacion() < minimo_esperado:
                    raise AssertionError(f"subocupacion en el bloque {bloque}")
            if nodo.hoja:
                profundidades.add(nivel)
                hojas.append(nodo)
            else:
                if len(nodo.hijos) != len(nodo.claves) + 1:
                    raise AssertionError(f"punteros inconsistentes en {bloque}")
                limites = [minimo] + nodo.claves + [maximo]
                for posicion, hijo in enumerate(nodo.hijos):
                    pendientes.append((hijo, nivel + 1, limites[posicion], limites[posicion + 1]))
        if len(profundidades) != 1:
            raise AssertionError(f"hojas a distinta profundidad: {sorted(profundidades)}")
        if profundidades.pop() != self.altura:
            raise AssertionError("la altura de la cabecera no coincide")
        recorrido = [empleado.employee_id for empleado in self.load()]
        if recorrido != sorted(recorrido):
            raise AssertionError("la lista enlazada de hojas no esta ordenada")
        if len(recorrido) != self.registros:
            raise AssertionError("el conteo de registros no coincide")
        return {"registros": len(recorrido),
                "altura": self.altura,
                "hojas": len(hojas),
                "ocupacion_hojas": sum(h.ocupacion() for h in hojas) / (len(hojas) * self.maximo)}


def construir(ruta, empleados, orden=ORDEN):
    """Crea el archivo desde cero e inserta todos los empleados."""
    if os.path.exists(ruta):
        os.remove(ruta)
    arbol = BPlusTreeFile(ruta, orden)
    for empleado in empleados:
        arbol.insert(empleado)
    return arbol


def main():
    ruta_csv = sys.argv[1] if len(sys.argv) > 1 else os.path.join("data", "employee.csv")
    orden = int(sys.argv[2]) if len(sys.argv) > 2 else ORDEN
    empleados = leer_csv(ruta_csv, 5000)
    arbol = construir(os.path.join("data", "demo_bplus.dat"), empleados, orden)

    print(f"B+ Tree File sobre {ruta_csv}")
    print(f"  orden M            : {arbol.orden} (hasta {arbol.maximo} claves por nodo)")
    print(f"  tamano de bloque   : {arbol.bloque} bytes = {TAMANO_CABECERA} de cabecera + "
          f"{arbol.maximo} x {TAMANO}")
    print(f"  registros          : {arbol.registros}")
    print(f"  altura             : {arbol.altura}")
    print(f"  bloques usados     : {arbol.bloques} ({os.path.getsize(arbol.ruta)} bytes)")

    clave = empleados[len(empleados) // 2].employee_id
    arbol.reiniciar_contadores()
    encontrado = arbol.search(clave)
    print(f"  search({clave}) -> {encontrado.employee_name}, {encontrado.department} "
          f"[{arbol.lecturas} lecturas]")
    print(f"  search(1) -> {arbol.search(1)}")

    nuevo = Empleado(999999, "Nicolas Llerena", "Peru", "Development", 54321.0, "04/09/2026")
    arbol.reiniciar_contadores()
    arbol.insert(nuevo)
    print(f"  insert(999999) -> {arbol.lecturas} lecturas, {arbol.escrituras} escrituras, "
          f"altura={arbol.altura}")
    print(f"  search(999999) -> {arbol.search(999999).employee_name}")

    inicial = empleados[10].employee_id
    final = inicial + 500
    arbol.reiniciar_contadores()
    rango = arbol.range_search(inicial, final)
    print(f"  rangeSearch({inicial}, {final}) -> {len(rango)} registros "
          f"[{arbol.lecturas} lecturas]")
    for empleado in rango[:3]:
        print(f"      {empleado.employee_id}  {empleado.employee_name:22s} {empleado.department}")

    arbol.reiniciar_contadores()
    print(f"  remove({clave}) -> {arbol.remove(clave)} "
          f"[{arbol.lecturas} lecturas, {arbol.escrituras} escrituras]")
    print(f"  search({clave}) tras eliminar -> {arbol.search(clave)}")

    resumen = arbol.validar()
    print(f"  validacion         : {resumen['registros']} registros, altura {resumen['altura']}, "
          f"{resumen['hojas']} hojas, ocupacion {resumen['ocupacion_hojas']:.0%}")
    arbol.cerrar()

    print("  prueba de estres de la eliminacion (invariantes tras cada tanda):")
    rng = random.Random(11)
    mezcla = empleados[:3000]
    rng.shuffle(mezcla)
    for orden_prueba in (4, 8, 64):
        prueba = construir(os.path.join("data", "demo_estres.dat"), mezcla, orden_prueba)
        vivos = {empleado.employee_id: empleado for empleado in mezcla}
        claves = list(vivos)
        rng.shuffle(claves)
        for numero, clave in enumerate(claves[:2500], 1):
            assert prueba.remove(clave), f"no se elimino {clave}"
            del vivos[clave]
            if numero % 500 == 0:
                prueba.validar()
                assert [e.employee_id for e in prueba.load()] == sorted(vivos)
        assert prueba.remove(claves[0]) is False
        final = prueba.validar()
        print(f"      M={orden_prueba:3d}: 3000 altas y 2500 bajas -> quedan "
              f"{final['registros']} registros, altura {final['altura']}, "
              f"{final['hojas']} hojas, invariantes correctas")
        prueba.cerrar()
    os.remove(os.path.join("data", "demo_estres.dat"))


if __name__ == "__main__":
    main()
