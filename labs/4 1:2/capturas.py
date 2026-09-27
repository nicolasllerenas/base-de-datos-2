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


def salida(archivo, comando):
    return [f"$ {comando}"] + leer(archivo).rstrip().splitlines() + ["$"]


def main():
    os.makedirs(DESTINO, exist_ok=True)
    generadas = []
    for etiqueta, archivo, comando in [
        ("datos", "p0_datos.txt", "python3 exportar_csv.py 100000"),
        ("bplus", "p1_bplus.txt", "python3 bplus_tree.py"),
        ("bench", "p3_benchmark.txt", "python3 benchmark.py"),
    ]:
        generadas.append(render(f"cap_{etiqueta}.png", "bash — labs/4.5", salida(archivo, comando)))
    for ruta in generadas:
        with Image.open(ruta) as imagen:
            print(f"{ruta:28s} {imagen.width}x{imagen.height}")


if __name__ == "__main__":
    main()
