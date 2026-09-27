"""Evaluacion experimental del arbol B+ (P3).

Mide tiempo y accesos a disco de la construccion, la busqueda puntual, la
busqueda por rango y la eliminacion; evalua el impacto del orden M; y compara
la busqueda por rango contra un escaneo secuencial y contra el arbol AVL del
laboratorio anterior.
"""

import csv
import json
import os
import random
import struct
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Rectangle

from avl_file import AVLFile
from bplus_tree import TAMANO_CABECERA, BPlusTreeFile, construir
from registro import TAMANO, desempaquetar, empaquetar, leer_csv

CSV = os.path.join("data", "employee.csv")
RESULTADOS = "resultados"
TAMANOS = [1000, 10000, 50000, 100000]
ORDENES = [4, 8, 16, 32, 64, 128, 256]
TAMANO_COMPARACION = 20000
ORDEN_BASE = 64
BUSQUEDAS = 500
RANGOS = 100
ANCHO_RANGO = 500
BAJAS = 500
SEMILLA = 13
COLOR_BPLUS = "#2f6f9f"
COLOR_OTRO = "#c1622c"
COLOR_TERCERO = "#5b8c5a"


class EscaneoSecuencial:
    """Archivo plano ordenado sin indice: la busqueda por rango lo recorre entero."""

    def __init__(self, ruta, bloque):
        self.ruta = ruta
        self.bloque = bloque
        self.por_bloque = max(1, bloque // TAMANO)
        self.lecturas = 0

    def build(self, empleados):
        with open(self.ruta, "wb") as destino:
            for empleado in sorted(empleados, key=lambda registro: registro.employee_id):
                destino.write(empaquetar(empleado))

    def reiniciar_contadores(self):
        self.lecturas = 0

    def range_search(self, clave_inicial, clave_final):
        encontrados = []
        with open(self.ruta, "rb") as fuente:
            while True:
                blob = fuente.read(self.por_bloque * TAMANO)
                if not blob:
                    return encontrados
                self.lecturas += 1
                for posicion in range(0, len(blob) - TAMANO + 1, TAMANO):
                    empleado = desempaquetar(blob, posicion)
                    if clave_inicial <= empleado.employee_id <= clave_final:
                        encontrados.append(empleado)


def limpiar(nombre):
    ruta = os.path.join("data", nombre)
    if os.path.exists(ruta):
        os.remove(ruta)
    return ruta


def cronometrar(estructura, operacion, argumentos):
    """Ejecuta una tanda de operaciones midiendo tiempo y accesos."""
    estructura.reiniciar_contadores()
    inicio = time.perf_counter()
    salidas = [operacion(*argumento) for argumento in argumentos]
    transcurrido = time.perf_counter() - inicio
    lecturas = estructura.lecturas
    escrituras = getattr(estructura, "escrituras", 0)
    return {"total_seg": transcurrido,
            "promedio_ms": transcurrido * 1000 / len(argumentos),
            "lecturas": lecturas,
            "escrituras": escrituras,
            "lecturas_promedio": lecturas / len(argumentos),
            "escrituras_promedio": escrituras / len(argumentos)}, salidas


def experimento_tamanos(base, rng):
    filas = []
    for tamano in TAMANOS:
        empleados = base[:tamano]
        claves = [empleado.employee_id for empleado in empleados]
        buscadas = rng.sample(claves, BUSQUEDAS)
        inicios = rng.sample(claves, RANGOS)
        eliminadas = rng.sample(claves, BAJAS)

        ruta = limpiar("bench_bplus.dat")
        inicio = time.perf_counter()
        arbol = construir(ruta, empleados, ORDEN_BASE)
        construccion = time.perf_counter() - inicio
        io_construccion = {"lecturas": arbol.lecturas, "escrituras": arbol.escrituras}
        resumen = arbol.validar()

        busqueda, salidas = cronometrar(arbol, arbol.search, [(clave,) for clave in buscadas])
        assert all(salida is not None for salida in salidas), "una busqueda fallo"
        rango, _ = cronometrar(arbol, arbol.range_search,
                               [(inicio, inicio + ANCHO_RANGO) for inicio in inicios])
        eliminacion, salidas = cronometrar(arbol, arbol.remove, [(clave,) for clave in eliminadas])
        assert all(salidas), "una eliminacion fallo"
        arbol.validar()

        filas.append({"tamano": tamano,
                      "altura": resumen["altura"],
                      "hojas": resumen["hojas"],
                      "ocupacion_hojas": resumen["ocupacion_hojas"],
                      "bloques": arbol.bloques,
                      "bytes": os.path.getsize(ruta),
                      "construccion": {"total_seg": construccion, **io_construccion},
                      "busqueda": busqueda,
                      "rango": rango,
                      "eliminacion": eliminacion})
        arbol.cerrar()
        print(f"n={tamano:6d}  altura={resumen['altura']}  hojas={resumen['hojas']:5d}  "
              f"ocupacion={resumen['ocupacion_hojas']:.0%}  "
              f"construccion={construccion:6.2f}s ({io_construccion['lecturas'] + io_construccion['escrituras']:8d} I/O)  "
              f"busqueda={busqueda['lecturas_promedio']:.1f} lecturas  "
              f"rango={rango['lecturas_promedio']:.1f} lecturas")
    return filas


def experimento_orden(base, rng):
    empleados = base[:TAMANO_COMPARACION]
    claves = [empleado.employee_id for empleado in empleados]
    buscadas = rng.sample(claves, BUSQUEDAS)
    inicios = rng.sample(claves, RANGOS)
    filas = []
    for orden in ORDENES:
        ruta = limpiar("bench_orden.dat")
        inicio = time.perf_counter()
        arbol = construir(ruta, empleados, orden)
        construccion = time.perf_counter() - inicio
        resumen = arbol.validar()
        busqueda, _ = cronometrar(arbol, arbol.search, [(clave,) for clave in buscadas])
        rango, _ = cronometrar(arbol, arbol.range_search,
                               [(inicio, inicio + ANCHO_RANGO) for inicio in inicios])
        filas.append({"orden": orden,
                      "bloque": arbol.bloque,
                      "altura": resumen["altura"],
                      "hojas": resumen["hojas"],
                      "ocupacion_hojas": resumen["ocupacion_hojas"],
                      "bytes": os.path.getsize(ruta),
                      "construccion_seg": construccion,
                      "construccion_io": arbol.lecturas + arbol.escrituras,
                      "busqueda_lecturas": busqueda["lecturas_promedio"],
                      "busqueda_ms": busqueda["promedio_ms"],
                      "rango_lecturas": rango["lecturas_promedio"],
                      "rango_ms": rango["promedio_ms"]})
        arbol.cerrar()
        print(f"M={orden:4d}  bloque={arbol.bloque:6d}B  altura={resumen['altura']}  "
              f"hojas={resumen['hojas']:5d}  archivo={os.path.getsize(ruta) / 1e6:5.2f}MB  "
              f"busqueda={busqueda['lecturas_promedio']:5.1f} lecturas  "
              f"rango={rango['lecturas_promedio']:6.1f} lecturas")
    return filas


def experimento_rango(base, rng):
    empleados = base[:TAMANO_COMPARACION]
    claves = [empleado.employee_id for empleado in empleados]
    inicios = rng.sample(claves, RANGOS)
    argumentos = [(inicio, inicio + ANCHO_RANGO) for inicio in inicios]

    arbol = construir(limpiar("cmp_bplus.dat"), empleados, ORDEN_BASE)
    bplus, salida_bplus = cronometrar(arbol, arbol.range_search, argumentos)

    plano = EscaneoSecuencial(limpiar("cmp_plano.dat"), arbol.bloque)
    plano.build(empleados)
    secuencial, salida_plano = cronometrar(plano, plano.range_search, argumentos)

    avl = AVLFile(limpiar("cmp_avl.dat"))
    for empleado in empleados:
        avl.insert(empleado)
    avl.lecturas = 0
    avl.reiniciar_contador()
    inicio = time.perf_counter()
    salida_avl = [avl.range_search(*argumento) for argumento in argumentos]
    transcurrido = time.perf_counter() - inicio
    arbol_avl = {"total_seg": transcurrido,
                 "promedio_ms": transcurrido * 1000 / len(argumentos),
                 "lecturas_promedio": avl.accesos / len(argumentos)}

    for una, otra, tercera in zip(salida_bplus, salida_plano, salida_avl):
        claves_bplus = [empleado.employee_id for empleado in una]
        assert claves_bplus == [empleado.employee_id for empleado in otra], "rangos distintos"
        assert claves_bplus == [empleado.employee_id for empleado in tercera], "rangos distintos"
    registros = sum(len(bloque) for bloque in salida_bplus) / len(argumentos)

    arbol.cerrar()
    avl.cerrar()
    print(f"rango de {ANCHO_RANGO} claves ({registros:.0f} registros) sobre {TAMANO_COMPARACION}: "
          f"B+ {bplus['promedio_ms']:.3f} ms / {bplus['lecturas_promedio']:.1f} lecturas | "
          f"secuencial {secuencial['promedio_ms']:.3f} ms / {secuencial['lecturas_promedio']:.1f} | "
          f"AVL {arbol_avl['promedio_ms']:.3f} ms / {arbol_avl['lecturas_promedio']:.1f}")
    return {"registros_por_rango": registros, "bplus": bplus, "secuencial": secuencial,
            "avl": arbol_avl}


def grafica_escalamiento(filas):
    figura, ejes = plt.subplots(2, 2, figsize=(9.5, 6.4))
    tamanos = [fila["tamano"] for fila in filas]
    paneles = [
        (lambda f: f["construccion"]["total_seg"], "Construcción del índice", "segundos", True),
        (lambda f: f["construccion"]["lecturas"] + f["construccion"]["escrituras"],
         "I/O de la construcción", "bloques leídos + escritos", True),
        (lambda f: f["busqueda"]["lecturas_promedio"], "Búsqueda puntual",
         "lecturas por búsqueda", False),
        (lambda f: f["rango"]["lecturas_promedio"],
         f"Búsqueda por rango (ancho {ANCHO_RANGO})", "lecturas por rango", False),
    ]
    for eje, (extraer, titulo, etiqueta, logaritmica) in zip(ejes.flat, paneles):
        valores = [extraer(fila) for fila in filas]
        eje.plot(tamanos, valores, marker="o", color=COLOR_BPLUS)
        for x, y in zip(tamanos, valores):
            eje.annotate(f"{y:,.0f}".replace(",", " ") if y >= 10 else f"{y:.1f}",
                         (x, y), textcoords="offset points", xytext=(0, 7),
                         ha="center", fontsize=8)
        eje.set_xscale("log")
        if logaritmica:
            eje.set_yscale("log")
        eje.set_title(titulo, fontsize=10)
        eje.set_xlabel("registros (N)")
        eje.set_ylabel(etiqueta)
        eje.grid(True, linestyle=":", alpha=0.6)
        eje.spines["top"].set_visible(False)
        eje.spines["right"].set_visible(False)
    figura.tight_layout()
    figura.savefig(os.path.join(RESULTADOS, "escalamiento.png"), dpi=160)
    plt.close(figura)


def grafica_orden(filas):
    figura, (izquierda, derecha) = plt.subplots(1, 2, figsize=(9.5, 3.8))
    ordenes = [fila["orden"] for fila in filas]

    izquierda.plot(ordenes, [fila["altura"] for fila in filas], marker="o", color=COLOR_BPLUS,
                   label="Altura del árbol")
    izquierda.plot(ordenes, [fila["busqueda_lecturas"] for fila in filas], marker="s",
                   color=COLOR_OTRO, label="Lecturas por búsqueda")
    izquierda.set_xscale("log", base=2)
    izquierda.set_xticks(ordenes)
    izquierda.set_xticklabels(ordenes)
    izquierda.set_xlabel("orden M")
    izquierda.set_ylabel("bloques")
    izquierda.set_title(f"Altura y costo de búsqueda ({TAMANO_COMPARACION} registros)", fontsize=10)
    izquierda.legend(fontsize=8)

    derecha.plot(ordenes, [fila["construccion_io"] for fila in filas], marker="o",
                 color=COLOR_BPLUS, label="I/O de construcción")
    derecha.set_xscale("log", base=2)
    derecha.set_yscale("log")
    derecha.set_xticks(ordenes)
    derecha.set_xticklabels(ordenes)
    derecha.set_xlabel("orden M")
    derecha.set_ylabel("bloques", color=COLOR_BPLUS)
    gemelo = derecha.twinx()
    gemelo.plot(ordenes, [fila["bytes"] / 1e6 for fila in filas], marker="s", color=COLOR_OTRO,
                label="Tamaño del archivo")
    gemelo.set_ylabel("MB", color=COLOR_OTRO)
    derecha.set_title("Costo de construcción y espacio", fontsize=10)
    lineas = derecha.get_lines() + gemelo.get_lines()
    derecha.legend(lineas, [linea.get_label() for linea in lineas], fontsize=8)

    for eje in (izquierda, derecha, gemelo):
        eje.spines["top"].set_visible(False)
    for eje in (izquierda, derecha):
        eje.grid(True, linestyle=":", alpha=0.6)
    figura.tight_layout()
    figura.savefig(os.path.join(RESULTADOS, "orden_m.png"), dpi=160)
    plt.close(figura)


def grafica_rango(comparacion):
    etiquetas = ["Árbol B+", "Escaneo secuencial", "Árbol AVL"]
    lecturas = [comparacion["bplus"]["lecturas_promedio"],
                comparacion["secuencial"]["lecturas_promedio"],
                comparacion["avl"]["lecturas_promedio"]]
    tiempos = [comparacion["bplus"]["promedio_ms"], comparacion["secuencial"]["promedio_ms"],
               comparacion["avl"]["promedio_ms"]]
    colores = [COLOR_BPLUS, COLOR_OTRO, COLOR_TERCERO]
    figura, (izquierda, derecha) = plt.subplots(1, 2, figsize=(9.5, 3.8))
    for eje, valores, titulo, etiqueta in [
        (izquierda, lecturas, "Lecturas de bloque por rango", "bloques leídos"),
        (derecha, tiempos, "Tiempo por rango", "ms")]:
        eje.bar(etiquetas, valores, color=colores, width=0.55)
        for posicion, valor in enumerate(valores):
            eje.text(posicion, valor, f"{valor:,.1f}".replace(",", " "), ha="center",
                     va="bottom", fontsize=9)
        eje.set_yscale("log")
        eje.set_title(titulo, fontsize=10)
        eje.set_ylabel(etiqueta)
        eje.grid(True, axis="y", linestyle=":", alpha=0.6)
        eje.spines["top"].set_visible(False)
        eje.spines["right"].set_visible(False)
        eje.tick_params(axis="x", labelsize=9)
    figura.tight_layout()
    figura.savefig(os.path.join(RESULTADOS, "rango_comparacion.png"), dpi=160)
    plt.close(figura)


def grafica_diagrama(orden=ORDEN_BASE):
    """Dibuja el formato binario de la cabecera y de los dos tipos de nodo."""
    bloque = TAMANO_CABECERA + (orden - 1) * TAMANO
    figura, eje = plt.subplots(figsize=(9.5, 4.4))
    eje.set_xlim(0, 100)
    eje.set_ylim(0, 10)
    eje.axis("off")

    def barra(y, piezas, titulo):
        eje.text(0, y + 2.05, titulo, fontsize=10, fontweight="bold")
        inicio = 0.0
        for ancho, etiqueta, detalle, color in piezas:
            eje.add_patch(Rectangle((inicio, y), ancho, 1.5, facecolor=color,
                                    edgecolor="#33383d", linewidth=0.8))
            eje.text(inicio + ancho / 2, y + 0.95, etiqueta, ha="center", va="center",
                     fontsize=8, color="#12161a")
            eje.text(inicio + ancho / 2, y + 0.42, detalle, ha="center", va="center",
                     fontsize=7, color="#3d454d")
            inicio += ancho

    barra(7.2, [(18, "tipo", "1 B", "#bcd9ee"),
                (18, "reservado", "1 B", "#e6ebef"),
                (18, "n_claves", "2 B", "#bcd9ee"),
                (23, "next_leaf", "4 B", "#f0c9a8"),
                (23, "prev_leaf", "4 B", "#f0c9a8")],
          f"Cabecera del bloque ({TAMANO_CABECERA} bytes)")
    barra(3.9, [(18, "cabecera", f"{TAMANO_CABECERA} B", "#bcd9ee"),
                (40, f"claves separadoras x {orden - 1}", f"{(orden - 1) * 4} B (4 B c/u)", "#cfe3f3"),
                (30, f"punteros a bloque x {orden}", f"{orden * 4} B (4 B c/u)", "#a9c9e4"),
                (12, "relleno", f"{bloque - TAMANO_CABECERA - (2 * orden - 1) * 4} B", "#e6ebef")],
          f"Nodo interno (bloque de {bloque} bytes)")
    barra(0.6, [(18, "cabecera", f"{TAMANO_CABECERA} B", "#bcd9ee"),
                (82, f"registros completos x {orden - 1}",
                 f"{(orden - 1) * TAMANO} B ({TAMANO} B c/u: id, nombre, país, área, sueldo, fecha)",
                 "#f5dcc4")],
          f"Nodo hoja (bloque de {bloque} bytes)")
    eje.text(0, 0.0, "next_leaf y prev_leaf solo se usan en las hojas; en los nodos internos valen −1.",
             fontsize=7.5, color="#5a6572")
    figura.tight_layout()
    figura.savefig(os.path.join(RESULTADOS, "diagrama_nodos.png"), dpi=160)
    plt.close(figura)


def main():
    os.makedirs(RESULTADOS, exist_ok=True)
    todos = leer_csv(CSV)
    base = todos[:]
    random.Random(SEMILLA).shuffle(base)

    print(f"dataset: {len(todos)} registros, registro de {TAMANO} bytes\n")
    print("--- escalamiento con M = 64 ---")
    filas = experimento_tamanos(base, random.Random(SEMILLA))
    print("\n--- impacto del orden M ---")
    ordenes = experimento_orden(base, random.Random(SEMILLA))
    print("\n--- busqueda por rango: B+ vs escaneo secuencial vs AVL ---")
    comparacion = experimento_rango(base, random.Random(SEMILLA))

    with open(os.path.join(RESULTADOS, "metricas.json"), "w") as destino:
        json.dump({"tamanos": filas, "ordenes": ordenes, "rango": comparacion}, destino, indent=2)
    with open(os.path.join(RESULTADOS, "metricas.csv"), "w", newline="") as destino:
        escritor = csv.writer(destino)
        escritor.writerow(["experimento", "parametro", "operacion", "tiempo_ms",
                           "lecturas", "escrituras"])
        for fila in filas:
            escritor.writerow(["tamano", fila["tamano"], "construccion",
                               f"{fila['construccion']['total_seg'] * 1000:.1f}",
                               fila["construccion"]["lecturas"], fila["construccion"]["escrituras"]])
            for operacion in ("busqueda", "rango", "eliminacion"):
                escritor.writerow(["tamano", fila["tamano"], operacion,
                                   f"{fila[operacion]['promedio_ms']:.4f}",
                                   f"{fila[operacion]['lecturas_promedio']:.1f}",
                                   f"{fila[operacion]['escrituras_promedio']:.1f}"])
        for fila in ordenes:
            escritor.writerow(["orden", fila["orden"], "busqueda",
                               f"{fila['busqueda_ms']:.4f}", f"{fila['busqueda_lecturas']:.1f}", 0])

    grafica_escalamiento(filas)
    grafica_orden(ordenes)
    grafica_rango(comparacion)
    grafica_diagrama()
    for nombre in ("bench_bplus.dat", "bench_orden.dat", "cmp_bplus.dat", "cmp_plano.dat",
                   "cmp_avl.dat"):
        limpiar(nombre)
    print(f"\nresultados en {RESULTADOS}/")


if __name__ == "__main__":
    main()
