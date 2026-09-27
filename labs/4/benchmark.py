import csv
import json
import os
import random
import time

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from avl_file import AVLFile
from registro import leer_csv
from sequential_file import SequentialFile

CSV = os.path.join("data", "employee.csv")
RESULTADOS = "resultados"
TAMANOS = [1000, 2500, 5000, 10000, 20000]
FACTORES_K = [8, 16, 32, 64, 128]
OPERACIONES = 500
RANGOS = 100
ANCHO_RANGO = 250
SEMILLA = 7
COLOR_SEQ = "#2f6f9f"
COLOR_AVL = "#c1622c"


def rutas_limpias(nombres):
    for nombre in nombres:
        ruta = os.path.join("data", nombre)
        if os.path.exists(ruta):
            os.remove(ruta)


def nuevo_secuencial(k=32):
    rutas_limpias(["bench_seq.dat", "bench_seq_aux.dat"])
    return SequentialFile(os.path.join("data", "bench_seq.dat"),
                          os.path.join("data", "bench_seq_aux.dat"), k=k)


def nuevo_avl():
    rutas_limpias(["bench_avl.dat"])
    return AVLFile(os.path.join("data", "bench_avl.dat"))


def cronometrar(estructura, operacion, argumentos):
    estructura.reiniciar_contador()
    inicio = time.perf_counter()
    resultados = [operacion(*argumento) for argumento in argumentos]
    transcurrido = time.perf_counter() - inicio
    return {
        "total_seg": transcurrido,
        "promedio_ms": transcurrido * 1000 / len(argumentos),
        "accesos": estructura.accesos,
        "accesos_promedio": estructura.accesos / len(argumentos),
    }, resultados


def medir(tamano, base, pool, rng):
    empleados = base[:tamano]
    claves = [empleado.employee_id for empleado in empleados]
    buscadas = rng.sample(claves, OPERACIONES)
    eliminadas = rng.sample(claves, OPERACIONES)
    inicios = rng.sample(claves, RANGOS)
    rangos = [(inicio, inicio + ANCHO_RANGO) for inicio in inicios]

    secuencial = nuevo_secuencial()
    inicio = time.perf_counter()
    secuencial.build(empleados)
    construccion_seq = time.perf_counter() - inicio

    avl = nuevo_avl()
    inicio = time.perf_counter()
    avl.build(empleados)
    construccion_avl = time.perf_counter() - inicio

    medidas = {"tamano": tamano,
               "construccion": {"secuencial": construccion_seq, "avl": construccion_avl},
               "altura_avl": avl.altura(),
               "reconstrucciones": 0}

    for nombre, argumentos, funcion_seq, funcion_avl in [
        ("busqueda", [(clave,) for clave in buscadas], secuencial.search, avl.search),
        ("rango", [(a, b) for a, b in rangos], secuencial.range_search, avl.range_search),
        ("insercion", [(empleado,) for empleado in pool], secuencial.insert, avl.insert),
        ("eliminacion", [(clave,) for clave in eliminadas], secuencial.remove, avl.remove),
    ]:
        antes = secuencial.reconstrucciones
        metricas_seq, salida_seq = cronometrar(secuencial, funcion_seq, argumentos)
        metricas_avl, salida_avl = cronometrar(avl, funcion_avl, argumentos)
        if nombre == "busqueda":
            assert all((a is None) == (b is None) and (a is None or a.employee_id == b.employee_id)
                       for a, b in zip(salida_seq, salida_avl)), "las busquedas no coinciden"
        if nombre == "rango":
            assert all([e.employee_id for e in a] == [e.employee_id for e in b]
                       for a, b in zip(salida_seq, salida_avl)), "los rangos no coinciden"
        if nombre == "insercion":
            medidas["reconstrucciones"] = secuencial.reconstrucciones - antes
        if nombre == "rango":
            medidas["registros_por_rango"] = sum(len(bloque) for bloque in salida_seq) / RANGOS
        medidas[nombre] = {"secuencial": metricas_seq, "avl": metricas_avl}

    medidas["validos_secuencial"] = len(secuencial.load())
    medidas["validos_avl"] = len(avl.load())
    assert medidas["validos_secuencial"] == medidas["validos_avl"], "los conjuntos difieren"
    avl.cerrar()
    return medidas


def medir_factor_k(base, pool, rng):
    empleados = base[:10000]
    claves = [empleado.employee_id for empleado in empleados]
    buscadas = rng.sample(claves, OPERACIONES)
    filas = []
    for k in FACTORES_K:
        secuencial = nuevo_secuencial(k)
        secuencial.build(empleados)
        insercion, _ = cronometrar(secuencial, secuencial.insert,
                                   [(empleado,) for empleado in pool])
        faltan = k - secuencial.registros(secuencial.ruta_auxiliar)
        relleno = base[10000:10000 + faltan]
        for empleado in relleno:
            secuencial.insert(empleado)
        busqueda, _ = cronometrar(secuencial, secuencial.search, [(clave,) for clave in buscadas])
        recientes = [(empleado.employee_id,) for empleado in relleno]
        busqueda_aux, _ = cronometrar(secuencial, secuencial.search, recientes)
        filas.append({"k": k,
                      "reconstrucciones": secuencial.reconstrucciones,
                      "auxiliar": secuencial.registros(secuencial.ruta_auxiliar),
                      "insercion_total_seg": insercion["total_seg"],
                      "busqueda_promedio_ms": busqueda["promedio_ms"],
                      "busqueda_accesos": busqueda["accesos_promedio"],
                      "busqueda_auxiliar_accesos": busqueda_aux["accesos_promedio"]})
    return filas


def grafica_tiempos(filas):
    figura, ejes = plt.subplots(2, 2, figsize=(9.5, 6.4))
    tamanos = [fila["tamano"] for fila in filas]
    paneles = [
        ("insercion", "total_seg", f"Inserción de {OPERACIONES} registros", "segundos"),
        ("busqueda", "promedio_ms", "Búsqueda por Employee_ID", "ms por operación"),
        ("rango", "promedio_ms", f"Búsqueda por rango (ancho {ANCHO_RANGO})", "ms por operación"),
        ("eliminacion", "promedio_ms", "Eliminación por Employee_ID", "ms por operación"),
    ]
    for eje, (operacion, metrica, titulo, etiqueta) in zip(ejes.flat, paneles):
        for nombre, color, clave in [("Sequential File", COLOR_SEQ, "secuencial"),
                                     ("AVL File", COLOR_AVL, "avl")]:
            valores = [fila[operacion][clave][metrica] for fila in filas]
            eje.plot(tamanos, valores, marker="o", color=color, label=nombre)
        eje.set_title(titulo, fontsize=10)
        eje.set_xlabel("registros en el archivo")
        eje.set_ylabel(etiqueta)
        eje.grid(True, linestyle=":", alpha=0.6)
        eje.spines["top"].set_visible(False)
        eje.spines["right"].set_visible(False)
        eje.legend(fontsize=8)
    figura.tight_layout()
    figura.savefig(os.path.join(RESULTADOS, "tiempos.png"), dpi=160)
    plt.close(figura)


def grafica_accesos(fila):
    operaciones = ["busqueda", "rango", "insercion", "eliminacion"]
    etiquetas = ["Búsqueda", "Rango", "Inserción", "Eliminación"]
    secuencial = [fila[operacion]["secuencial"]["accesos_promedio"] for operacion in operaciones]
    avl = [fila[operacion]["avl"]["accesos_promedio"] for operacion in operaciones]
    posiciones = range(len(operaciones))
    figura, eje = plt.subplots(figsize=(7.4, 4.0))
    eje.bar([p - 0.2 for p in posiciones], secuencial, 0.4, color=COLOR_SEQ, label="Sequential File")
    eje.bar([p + 0.2 for p in posiciones], avl, 0.4, color=COLOR_AVL, label="AVL File")
    for posicion, (valor_seq, valor_avl) in enumerate(zip(secuencial, avl)):
        eje.text(posicion - 0.2, valor_seq, f"{valor_seq:.0f}", ha="center", va="bottom", fontsize=8)
        eje.text(posicion + 0.2, valor_avl, f"{valor_avl:.0f}", ha="center", va="bottom", fontsize=8)
    eje.set_yscale("log")
    eje.set_xticks(list(posiciones))
    eje.set_xticklabels(etiquetas)
    eje.set_ylabel("accesos a disco por operación (escala log)")
    eje.set_title(f"Accesos promedio con {fila['tamano']} registros")
    eje.grid(True, axis="y", linestyle=":", alpha=0.6)
    eje.spines["top"].set_visible(False)
    eje.spines["right"].set_visible(False)
    eje.legend()
    figura.tight_layout()
    figura.savefig(os.path.join(RESULTADOS, "accesos.png"), dpi=160)
    plt.close(figura)


def grafica_factor_k(filas):
    figura, eje = plt.subplots(figsize=(7.4, 4.0))
    ks = [fila["k"] for fila in filas]
    eje.plot(ks, [fila["insercion_total_seg"] for fila in filas], marker="o", color=COLOR_SEQ,
             label=f"Inserción de {OPERACIONES} registros (s)")
    eje.set_xlabel("k (registros que admite el auxiliar)")
    eje.set_ylabel("segundos", color=COLOR_SEQ)
    eje.set_xscale("log", base=2)
    eje.set_xticks(ks)
    eje.set_xticklabels(ks)
    eje.grid(True, linestyle=":", alpha=0.6)
    gemelo = eje.twinx()
    gemelo.plot(ks, [fila["busqueda_auxiliar_accesos"] for fila in filas], marker="s",
                color=COLOR_AVL, label="Accesos al buscar un registro del auxiliar")
    gemelo.set_ylabel("accesos por búsqueda", color=COLOR_AVL)
    eje.set_title("Sequential File: efecto de k con 10 000 registros")
    lineas = eje.get_lines() + gemelo.get_lines()
    eje.legend(lineas, [linea.get_label() for linea in lineas], fontsize=8, loc="center right")
    figura.tight_layout()
    figura.savefig(os.path.join(RESULTADOS, "factor_k.png"), dpi=160)
    plt.close(figura)


def main():
    os.makedirs(RESULTADOS, exist_ok=True)
    todos = leer_csv(CSV)
    rng = random.Random(SEMILLA)
    barajado = todos[:]
    rng.shuffle(barajado)
    pool = barajado[:OPERACIONES]
    base = barajado[OPERACIONES:]

    filas = []
    for tamano in TAMANOS:
        medidas = medir(tamano, base, pool, random.Random(SEMILLA + tamano))
        filas.append(medidas)
        print(f"n={tamano:6d}  altura_avl={medidas['altura_avl']:2d}  "
              f"reconstrucciones={medidas['reconstrucciones']:3d}  "
              f"busqueda seq={medidas['busqueda']['secuencial']['promedio_ms']:.3f} ms / "
              f"avl={medidas['busqueda']['avl']['promedio_ms']:.3f} ms  |  "
              f"insercion seq={medidas['insercion']['secuencial']['total_seg']:6.2f} s / "
              f"avl={medidas['insercion']['avl']['total_seg']:.2f} s")

    factores = medir_factor_k(base, pool, random.Random(SEMILLA))
    for fila in factores:
        print(f"k={fila['k']:4d}  reconstrucciones={fila['reconstrucciones']:3d}  "
              f"auxiliar={fila['auxiliar']:4d}  insercion={fila['insercion_total_seg']:6.2f} s  "
              f"busqueda en datos={fila['busqueda_accesos']:5.1f} accesos  "
              f"en auxiliar={fila['busqueda_auxiliar_accesos']:6.1f} accesos")

    with open(os.path.join(RESULTADOS, "metricas.json"), "w") as destino:
        json.dump({"tamanos": filas, "factor_k": factores}, destino, indent=2)

    with open(os.path.join(RESULTADOS, "metricas.csv"), "w", newline="") as destino:
        escritor = csv.writer(destino)
        escritor.writerow(["registros", "estructura", "operacion", "total_seg", "promedio_ms",
                           "accesos_totales", "accesos_promedio"])
        for fila in filas:
            for operacion in ("insercion", "busqueda", "rango", "eliminacion"):
                for etiqueta, clave in (("sequential", "secuencial"), ("avl", "avl")):
                    metricas = fila[operacion][clave]
                    escritor.writerow([fila["tamano"], etiqueta, operacion,
                                       f"{metricas['total_seg']:.4f}",
                                       f"{metricas['promedio_ms']:.4f}",
                                       metricas["accesos"],
                                       f"{metricas['accesos_promedio']:.1f}"])

    grafica_tiempos(filas)
    grafica_accesos(filas[-1])
    grafica_factor_k(factores)
    print(f"\nresultados en {RESULTADOS}/")


if __name__ == "__main__":
    main()
