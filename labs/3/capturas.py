import os
import re
import textwrap

from PIL import Image, ImageDraw, ImageFont

EVIDENCIA = "evidencia"
DESTINO = "capturas"
FUENTE = "/System/Library/Fonts/Menlo.ttc"
ESCALA = 2
COLUMNAS = 124

FONDO = (29, 31, 33)
BARRA = (58, 61, 66)
TEXTO = (230, 230, 230)
PROMPT = (126, 199, 127)
COMANDO = (137, 190, 220)
COMENTARIO = (140, 150, 160)
TITULO = (200, 205, 210)
SEMAFORO = [(255, 95, 86), (255, 189, 46), (39, 201, 63)]


def cargar_fuente(tamano, indice=0):
    return ImageFont.truetype(FUENTE, tamano * ESCALA, index=indice)


def leer(nombre):
    with open(os.path.join(EVIDENCIA, nombre)) as fuente:
        return fuente.read()


def envolver(lineas):
    salida = []
    for linea in lineas:
        linea = linea.rstrip()
        if len(linea) <= COLUMNAS:
            salida.append(linea)
            continue
        partes = textwrap.wrap(linea, COLUMNAS, subsequent_indent="    ",
                               break_long_words=True, break_on_hyphens=False)
        salida.extend(partes or [""])
    return salida


def color_de(linea):
    if linea.startswith("$ ") or linea.endswith("=# ") or "=# " in linea[:12]:
        return PROMPT
    if linea.startswith("--"):
        return COMENTARIO
    return TEXTO


def render(nombre, titulo, lineas):
    lineas = envolver(lineas)
    fuente = cargar_fuente(13)
    fuente_titulo = cargar_fuente(12, indice=1)
    alto_linea = int(19 * ESCALA)
    margen = int(14 * ESCALA)
    barra = int(30 * ESCALA)
    ancho_caracter = fuente.getlength("M")
    ancho = int(margen * 2 + ancho_caracter * max(len(l) for l in lineas))
    ancho = max(ancho, int(520 * ESCALA))
    alto = barra + margen * 2 + alto_linea * len(lineas)

    lienzo = Image.new("RGB", (ancho, alto), FONDO)
    dibujo = ImageDraw.Draw(lienzo)
    dibujo.rectangle([0, 0, ancho, barra], fill=BARRA)
    for indice, color in enumerate(SEMAFORO):
        centro = int(18 * ESCALA) + indice * int(18 * ESCALA)
        radio = int(6 * ESCALA) // 2
        dibujo.ellipse([centro - radio, barra // 2 - radio, centro + radio, barra // 2 + radio],
                       fill=color)
    ancho_titulo = dibujo.textlength(titulo, font=fuente_titulo)
    dibujo.text(((ancho - ancho_titulo) / 2, barra / 2 - fuente_titulo.size * 0.62),
                titulo, font=fuente_titulo, fill=TITULO)

    y = barra + margen
    for linea in lineas:
        if linea.startswith("$ ") or "=# " in linea[:12]:
            corte = linea.index(" ") + 1 if linea.startswith("$ ") else linea.index("# ") + 2
            dibujo.text((margen, y), linea[:corte], font=fuente, fill=PROMPT)
            dibujo.text((margen + fuente.getlength(linea[:corte]), y), linea[corte:],
                        font=fuente, fill=COMANDO)
        else:
            dibujo.text((margen, y), linea, font=fuente, fill=color_de(linea))
        y += alto_linea

    ruta = os.path.join(DESTINO, nombre)
    lienzo.save(ruta)
    return ruta


def plan(archivo):
    lineas = []
    for linea in leer(archivo).splitlines():
        if linea.startswith("--"):
            continue
        lineas.append(linea.rstrip())
    while lineas and not lineas[0].strip():
        lineas.pop(0)
    return lineas


def sesion_psql(archivo, work_mem, consulta):
    cabecera = [
        "$ psql -U postgres -d employees",
        "psql (14.18 (Homebrew))",
        "employees=# BEGIN;",
        "BEGIN",
        f"employees=# SET LOCAL work_mem = '{work_mem}';",
        "SET",
        f"employees=# EXPLAIN (ANALYZE, BUFFERS) {consulta}",
    ]
    return cabecera + plan(archivo) + ["employees=# COMMIT;", "COMMIT", "employees=# \\q", "$"]


def sesion_python(archivo, comando):
    return [f"$ {comando}"] + leer(archivo).rstrip().splitlines() + ["$"]


CONSULTAS = {
    "q1": "SELECT * FROM employees.employee ORDER BY hire_date;",
    "q2": "SELECT from_date, COUNT(*) FROM employees.department_employee GROUP BY from_date;",
    "q3": "SELECT * FROM employees.employee e JOIN employees.department_employee d "
          "ON d.employee_id = e.id;",
}


def main():
    os.makedirs(DESTINO, exist_ok=True)
    generadas = []

    for etiqueta, archivo, work_mem, consulta in [
        ("q1_64kb", "q1_order_by_64kB.txt", "64kB", CONSULTAS["q1"]),
        ("q1_2mb", "q1_order_by_2MB.txt", "2MB", CONSULTAS["q1"]),
        ("q1_64mb", "q1_order_by_64MB.txt", "64MB", CONSULTAS["q1"]),
        ("q2_64kb", "q2_group_by_64kB.txt", "64kB", CONSULTAS["q2"]),
        ("q2_2mb", "q2_group_by_2MB.txt", "2MB", CONSULTAS["q2"]),
        ("q3_64kb", "q3_join_64kB.txt", "64kB", CONSULTAS["q3"]),
        ("q3_2mb", "q3_join_2MB.txt", "2MB", CONSULTAS["q3"]),
    ]:
        generadas.append(render(f"cap_{etiqueta}.png", "psql — employees",
                                sesion_psql(archivo, work_mem, consulta)))

    traza = []
    for etiqueta, archivo in [("64kB", "q1_order_by_64kB_trace_sort.txt"),
                              ("2MB", "q1_order_by_2MB_trace_sort.txt")]:
        resumen = leer(archivo.replace(".txt", "_resumen.txt")).splitlines()
        runs = resumen[0].split(":")[1].strip()
        pasos = resumen[1].split(":")[1].strip()
        traza += [f"-- work_mem = {etiqueta}",
                  f"$ grep -c 'finished writing run' {EVIDENCIA}/{archivo}", runs,
                  f"$ grep -c 'merge step' {EVIDENCIA}/{archivo}", pasos,
                  f"$ grep -E 'external sort with|read buffers' {EVIDENCIA}/{archivo}"]
        traza += [linea.strip() for linea in resumen[2:] if linea.strip()]
        traza += [""]
    traza += ["$"]
    generadas.append(render("cap_q1_trace.png", "bash — labs/3", traza))

    for etiqueta, archivo, comando in [
        ("heap", "p2_1_heap_file.txt", "python3 heap_file.py"),
        ("sort", "p2_2_external_sort.txt", "python3 external_sort.py"),
        ("hash", "p2_3_external_hashing.txt", "python3 external_hashing.py"),
        ("bench", "p2_4_benchmark.txt", "python3 benchmark.py"),
    ]:
        generadas.append(render(f"cap_{etiqueta}.png", "bash — labs/3",
                                sesion_python(archivo, comando)))

    for ruta in generadas:
        with Image.open(ruta) as imagen:
            print(f"{ruta:34s} {imagen.width}x{imagen.height}")


if __name__ == "__main__":
    main()
