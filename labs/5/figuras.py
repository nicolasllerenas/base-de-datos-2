"""Genera las figuras del informe: diagramas de P2, P3 y P4 y las graficas de P1."""

import json
import os
import random

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import FancyArrowPatch, Rectangle

from registro import leer_csv
from static_hash import construir

RESULTADOS = "resultados"
CLAVES = [10, 13, 34, 6, 23, 12, 15, 73, 28, 19, 67, 17, 41, 87, 57, 27, 11]
FB = 3
AZUL = "#2f6f9f"
NARANJA = "#c1622c"
CLARO = "#dbe9f5"
CREMA = "#f7e2cd"
GRIS = "#eceff2"


def bits(clave, profundidad):
    return format(clave % (2 ** profundidad), f"0{profundidad}b")


# --------------------------------------------------------------- simulaciones

def extendible(claves, D=2, fb=FB):
    """Corre el algoritmo del enunciado y devuelve la traza y los estados."""
    fases = []
    while True:
        directorio, buckets, siguiente = {"0": 0, "1": 1}, {0: [[], None], 1: [[], None]}, 2
        traza, rehash = [], False
        instantaneas = {}
        for clave in claves:
            h = bits(clave, D)
            while True:
                entrada = next(e for e in directorio if h.startswith(e))
                registros, overflow = buckets[directorio[entrada]]
                if len(registros) < fb:
                    registros.append(clave)
                    traza.append((clave, h, entrada, "entra directo"))
                    break
                if overflow is not None:
                    if len(overflow) < fb:
                        overflow.append(clave)
                        traza.append((clave, h, entrada, "va a la cadena"))
                        break
                    traza.append((clave, h, entrada, f"cadena llena: rehashing a D={D + 1}"))
                    rehash = True
                    break
                if len(entrada) < D:
                    viejos = registros
                    del directorio[entrada]
                    izquierda, derecha = entrada + "0", entrada + "1"
                    for prefijo in (izquierda, derecha):
                        directorio[prefijo] = siguiente
                        buckets[siguiente] = [[], None]
                        siguiente += 1
                    for viejo in viejos:
                        destino = izquierda if bits(viejo, D).startswith(izquierda) else derecha
                        buckets[directorio[destino]][0].append(viejo)
                    traza.append((clave, h, entrada, f"split en {izquierda} / {derecha}"))
                    continue
                buckets[directorio[entrada]][1] = [clave]
                traza.append((clave, h, entrada, "abre bucket de overflow"))
                break
            instantaneas[clave] = (dict(directorio),
                                   {k: [list(v[0]), list(v[1]) if v[1] else None]
                                    for k, v in buckets.items()})
            if rehash:
                break
        fases.append({"D": D, "traza": traza, "directorio": directorio, "buckets": buckets,
                      "instantaneas": instantaneas, "rehash": rehash})
        if not rehash:
            return fases
        D += 1


def lineal(claves, n=2, fb=FB):
    buckets = {0: [[], []], 1: [[], []]}
    nivel, puntero, traza = 0, 0, []
    for clave in claves:
        base = n * (2 ** nivel)
        indice = clave % base
        if indice < puntero:
            indice = clave % (base * 2)
        if len(buckets[indice][0]) < fb:
            buckets[indice][0].append(clave)
            traza.append((clave, indice, nivel, puntero, "entra directo"))
            continue
        buckets[indice][1].append(clave)
        nuevo = puntero + base
        todos = buckets[puntero][0] + buckets[puntero][1]
        buckets[nuevo] = [[], []]
        buckets[puntero] = [[], []]
        for viejo in todos:
            caja = buckets[viejo % (base * 2)]
            (caja[0] if len(caja[0]) < fb else caja[1]).append(viejo)
        detalle = f"overflow en B{indice}, split de B{puntero} en B{nuevo}"
        puntero += 1
        if puntero == base:
            puntero, nivel = 0, nivel + 1
            detalle += f", sube a nivel {nivel}"
        traza.append((clave, indice, nivel, puntero, detalle))
    return traza, buckets, nivel, puntero


# ------------------------------------------------------------------- dibujos

def caja(eje, x, y, ancho, alto, texto, color, tamano=9, borde="#33383d"):
    eje.add_patch(Rectangle((x, y), ancho, alto, facecolor=color, edgecolor=borde, linewidth=0.9))
    eje.text(x + ancho / 2, y + alto / 2, texto, ha="center", va="center", fontsize=tamano)


def flecha(eje, origen, destino, color="#5a6572"):
    eje.add_patch(FancyArrowPatch(origen, destino, arrowstyle="-|>", mutation_scale=9,
                                  color=color, linewidth=0.9,
                                  connectionstyle="arc3,rad=0.06"))


def dibujar_directorio(eje, directorio, buckets, titulo, fb=FB):
    """Dibuja el indice a la izquierda y los buckets con sus cadenas a la derecha."""
    entradas = sorted(directorio, key=lambda prefijo: (prefijo.ljust(4, "0"), len(prefijo)))
    alto, hueco = 0.62, 0.22
    eje.set_title(titulo, fontsize=9.5, loc="left")
    for fila, entrada in enumerate(entradas):
        y = -(fila * (alto + hueco))
        caja(eje, 0, y, 1.05, alto, entrada, CLARO, 9)
        registros, overflow = buckets[directorio[entrada]]
        contenido = "  ".join(f"{clave:2d}" for clave in registros)
        relleno = "  ".join(["··"] * (fb - len(registros)))
        etiqueta = f"B{directorio[entrada]}   {contenido}{'  ' + relleno if relleno else ''}"
        caja(eje, 2.0, y, 2.5, alto, etiqueta.strip(), CREMA if registros else GRIS, 8.5)
        flecha(eje, (1.1, y + alto / 2), (1.95, y + alto / 2))
        if overflow:
            texto = "  ".join(f"{clave:2d}" for clave in overflow)
            caja(eje, 5.0, y, 1.9, alto, f"ovf   {texto}", "#f3cfae", 8.5)
            flecha(eje, (4.55, y + alto / 2), (4.95, y + alto / 2), NARANJA)
    eje.set_xlim(-0.2, 7.2)
    eje.set_ylim(-(len(entradas) * (alto + hueco)) - 0.1, alto + 0.15)
    eje.axis("off")


def figura_extendible(fases):
    fase2, fase3 = fases[0], fases[1]
    figura, ejes = plt.subplots(2, 1, figsize=(7.0, 5.4))
    directorio, buckets = fase2["instantaneas"][12]
    dibujar_directorio(ejes[0], directorio, buckets,
                       "a) D = 2, tras el split que provoca la clave 23")
    directorio, buckets = fase2["instantaneas"][27]
    dibujar_directorio(ejes[1], directorio, buckets,
                       "b) D = 2, cadenas llenas justo antes del rehashing")
    figura.tight_layout()
    figura.savefig(os.path.join(RESULTADOS, "p2_extendible_d2.png"), dpi=170)
    plt.close(figura)

    figura, eje = plt.subplots(figsize=(6.4, 4.2))
    dibujar_directorio(eje, fase3["directorio"], fase3["buckets"],
                       "Estado final tras el rehashing (D = 3)")
    figura.tight_layout()
    figura.savefig(os.path.join(RESULTADOS, "p2_extendible_final.png"), dpi=170)
    plt.close(figura)


def figura_trie(fase3):
    """Dibuja el directorio de P3 como arbol binario con las hojas apuntando a buckets."""
    directorio = fase3["directorio"]
    buckets = fase3["buckets"]
    hojas = sorted(directorio, key=lambda prefijo: prefijo.ljust(3, "0"))
    posiciones = {}
    figura, eje = plt.subplots(figsize=(9.5, 4.6))

    for fila, hoja in enumerate(hojas):
        posiciones[hoja] = (len(hoja) * 1.55, -fila * 1.0)
    internos = set()
    for hoja in hojas:
        for corte in range(len(hoja)):
            internos.add(hoja[:corte])
    for nodo in internos:
        hijos = [posiciones[h] for h in posiciones if h.startswith(nodo) and len(h) > len(nodo)]
        hijos += [posiciones[n] for n in internos
                  if n.startswith(nodo) and len(n) == len(nodo) + 1 and n in posiciones]
        if not hijos:
            continue
        posiciones[nodo] = (len(nodo) * 1.55, sum(y for _, y in hijos) / len(hijos))
    for nodo in sorted(internos, key=len, reverse=True):
        hijos = [n for n in list(internos) + hojas if len(n) == len(nodo) + 1 and n.startswith(nodo)]
        alturas = [posiciones[h][1] for h in hijos if h in posiciones]
        if alturas:
            posiciones[nodo] = (len(nodo) * 1.55, sum(alturas) / len(alturas))

    for nodo in internos:
        for bit in "01":
            hijo = nodo + bit
            if hijo in posiciones:
                inicio, fin = posiciones[nodo], posiciones[hijo]
                eje.plot([inicio[0], fin[0]], [inicio[1], fin[1]], color="#5a6572", linewidth=0.9)
                eje.text((inicio[0] + fin[0]) / 2, (inicio[1] + fin[1]) / 2 + 0.12, bit,
                         fontsize=8, color=AZUL, ha="center")
    for nodo in internos:
        x, y = posiciones[nodo]
        eje.add_patch(plt.Circle((x, y), 0.12, facecolor="white", edgecolor=AZUL, linewidth=1.2,
                                 zorder=3))
        if nodo == "":
            eje.text(x - 0.22, y, "raíz", fontsize=8, ha="right", va="center", color=AZUL)
    for hoja in hojas:
        x, y = posiciones[hoja]
        caja(eje, x - 0.34, y - 0.22, 0.68, 0.44, hoja, CLARO, 8)
        registros, overflow = buckets[directorio[hoja]]
        contenido = "  ".join(f"{clave:2d}" for clave in registros) or "vacío"
        caja(eje, 6.3, y - 0.22, 2.0, 0.44, f"B{directorio[hoja]}   {contenido}",
             CREMA if registros else GRIS, 8)
        flecha(eje, (x + 0.36, y), (6.25, y))
        if overflow:
            texto = "  ".join(f"{clave:2d}" for clave in overflow)
            caja(eje, 8.5, y - 0.22, 1.3, 0.44, f"ovf  {texto}", "#f3cfae", 8)
            flecha(eje, (8.32, y), (8.45, y), NARANJA)
    eje.set_xlim(-0.6, 10.1)
    eje.set_ylim(-len(hojas) + 0.3, 0.7)
    eje.axis("off")
    eje.set_title("Trie de directorio con D = 3: las hojas guardan el puntero al bucket",
                  fontsize=9.5, loc="left")
    figura.tight_layout()
    figura.savefig(os.path.join(RESULTADOS, "p3_trie.png"), dpi=170)
    plt.close(figura)


def figura_lineal(buckets, nivel, puntero, base):
    figura, eje = plt.subplots(figsize=(7.6, 4.4))
    numeros = sorted(buckets)
    alto, hueco = 0.62, 0.2
    for fila, numero in enumerate(numeros):
        y = -(fila * (alto + hueco))
        registros, overflow = buckets[numero]
        marca = "  <- p" if numero == puntero else ""
        caja(eje, 0, y, 0.95, alto, f"B{numero}", CLARO if numero != puntero else "#bcd9ee", 9)
        contenido = "  ".join(f"{clave:2d}" for clave in registros) or "vacío"
        caja(eje, 1.15, y, 2.4, alto, contenido, CREMA if registros else GRIS, 8.5)
        if overflow:
            texto = "  ".join(f"{clave:2d}" for clave in overflow)
            caja(eje, 3.8, y, 1.5, alto, f"ovf  {texto}", "#f3cfae", 8.5)
            flecha(eje, (3.6, y + alto / 2), (3.75, y + alto / 2), NARANJA)
        if marca:
            eje.text(5.5, y + alto / 2, "← puntero p", fontsize=8.5, color=NARANJA, va="center")
    eje.set_xlim(-0.2, 7.2)
    eje.set_ylim(-(len(numeros) * (alto + hueco)) - 0.1, alto + 0.2)
    eje.axis("off")
    eje.set_title(f"Linear hashing: estado final con nivel = {nivel}, p = {puntero} "
                  f"y {len(numeros)} buckets", fontsize=9.5, loc="left")
    figura.tight_layout()
    figura.savefig(os.path.join(RESULTADOS, "p4_lineal.png"), dpi=170)
    plt.close(figura)


def estados_lineales(claves, n=2, fb=FB):
    buckets = {0: [[], []], 1: [[], []]}
    nivel, puntero = 0, 0
    estados = [("inicio: 2 buckets · L=0, p=0",
                {k: [list(v[0]), list(v[1])] for k, v in buckets.items()}, nivel, puntero)]
    for clave in claves:
        base = n * (2 ** nivel)
        indice = clave % base
        if indice < puntero:
            indice = clave % (base * 2)
        if len(buckets[indice][0]) < fb:
            buckets[indice][0].append(clave)
            continue
        buckets[indice][1].append(clave)
        nuevo_bucket = puntero + base
        todos = buckets[puntero][0] + buckets[puntero][1]
        buckets[nuevo_bucket] = [[], []]
        buckets[puntero] = [[], []]
        for viejo in todos:
            caja = buckets[viejo % (base * 2)]
            (caja[0] if len(caja[0]) < fb else caja[1]).append(viejo)
        anterior = puntero
        puntero += 1
        if puntero == base:
            puntero, nivel = 0, nivel + 1
        estados.append((f"{clave}: overflow B{indice} · split B{anterior}→B{nuevo_bucket} · "
                        f"L={nivel}, p={puntero}",
                        {k: [list(v[0]), list(v[1])] for k, v in buckets.items()}, nivel, puntero))
    return estados


def panel_lineal(eje, titulo, buckets, puntero, filas_panel):
    alto, hueco = 0.5, 0.16
    eje.set_title(titulo, fontsize=11.5, loc="left", pad=6)
    for fila, numero in enumerate(sorted(buckets)):
        y = -(fila * (alto + hueco))
        registros, overflow = buckets[numero]
        resaltado = numero == puntero
        caja(eje, 0, y, 0.7, alto, f"B{numero}", "#bcd9ee" if resaltado else CLARO, 12)
        contenido = "  ".join(str(clave) for clave in registros) or "—"
        caja(eje, 0.85, y, 2.0, alto, contenido, CREMA if registros else GRIS, 12)
        if overflow:
            texto = "  ".join(str(clave) for clave in overflow)
            caja(eje, 3.05, y, 1.05, alto, texto, "#f3cfae", 12)
            flecha(eje, (2.9, y + alto / 2), (3.0, y + alto / 2), NARANJA)
        if resaltado:
            eje.text(4.3, y + alto / 2, "p", fontsize=12, color=NARANJA, va="center")
    eje.set_xlim(-0.1, 4.7)
    eje.set_ylim(-(filas_panel * (alto + hueco)) + hueco, alto + 0.1)
    eje.axis("off")


def figura_lineal_pasos(estados, columnas=2):
    for mitad, nombre in ((estados[:4], "p4_pasos_a.png"), (estados[4:], "p4_pasos_b.png")):
        alturas = [max(len(mitad[fila * columnas + columna][1]) for columna in range(columnas)
                       if fila * columnas + columna < len(mitad))
                   for fila in range((len(mitad) + columnas - 1) // columnas)]
        figura = plt.figure(figsize=(9.8, 0.66 * sum(alturas) + 0.75 * len(alturas)))
        rejilla = figura.add_gridspec(len(alturas), columnas, height_ratios=alturas,
                                      hspace=0.45, wspace=0.08)
        for indice, (titulo, buckets, nivel, puntero) in enumerate(mitad):
            eje = figura.add_subplot(rejilla[indice // columnas, indice % columnas])
            panel_lineal(eje, titulo, buckets, puntero, alturas[indice // columnas])
        figura.savefig(os.path.join(RESULTADOS, nombre), dpi=170, bbox_inches="tight")
        plt.close(figura)


# ---------------------------------------------------------- experimentos (P1)

def experimentos_p1():
    empleados = leer_csv(os.path.join("data", "employee.csv"), 3200)
    rng = random.Random(21)
    carga, efecto_m = [], []
    for cantidad in (200, 400, 800, 1200, 1600, 2000, 2400):
        archivo = construir(os.path.join("data", "exp_hash.dat"), empleados[:cantidad], 101, 8)
        resumen = archivo.estadisticas()
        claves = rng.sample([e.employee_id for e in empleados[:cantidad]], min(200, cantidad))
        archivo.reiniciar_contadores()
        for clave in claves:
            archivo.search(clave)
        resumen["lecturas_busqueda"] = archivo.lecturas / len(claves)
        archivo.reiniciar_contadores()
        for clave in claves:
            archivo.search(clave + 500000)
        resumen["lecturas_fallida"] = archivo.lecturas / len(claves)
        carga.append(resumen)
        archivo.cerrar()
    for buckets in (53, 101, 211, 401, 809):
        archivo = construir(os.path.join("data", "exp_hash.dat"), empleados[:2000], buckets, 8)
        resumen = archivo.estadisticas()
        claves = rng.sample([e.employee_id for e in empleados[:2000]], 200)
        archivo.reiniciar_contadores()
        for clave in claves:
            archivo.search(clave)
        resumen["lecturas_busqueda"] = archivo.lecturas / len(claves)
        efecto_m.append(resumen)
        archivo.cerrar()
    os.remove(os.path.join("data", "exp_hash.dat"))
    return carga, efecto_m


def figura_p1(carga, efecto_m):
    figura, (izquierda, derecha) = plt.subplots(1, 2, figsize=(9.6, 3.8))
    factores = [fila["factor_carga"] for fila in carga]
    izquierda.plot(factores, [fila["lecturas_busqueda"] for fila in carga], marker="o",
                   color=AZUL, label="búsqueda con éxito")
    izquierda.plot(factores, [fila["lecturas_fallida"] for fila in carga], marker="s",
                   color=NARANJA, label="búsqueda fallida")
    izquierda.plot(factores, [fila["cadena_maxima"] for fila in carga], marker="^",
                   color="#5b8c5a", linestyle="--", label="cadena más larga")
    izquierda.set_xlabel("factor de carga (registros / capacidad primaria)")
    izquierda.set_ylabel("bloques leídos")
    izquierda.set_title("M = 101, FB = 8: el costo sube con la carga", fontsize=9.5)
    izquierda.axvline(1.0, color="#9aa4ae", linewidth=0.8, linestyle=":")
    izquierda.legend(fontsize=8)

    ms = [fila["buckets_primarios"] for fila in efecto_m]
    derecha.plot(ms, [fila["lecturas_busqueda"] for fila in efecto_m], marker="o", color=AZUL,
                 label="lecturas por búsqueda")
    derecha.plot(ms, [fila["cadena_maxima"] for fila in efecto_m], marker="^", color="#5b8c5a",
                 linestyle="--", label="cadena más larga")
    derecha.set_xscale("log")
    derecha.set_xticks(ms)
    derecha.set_xticklabels(ms)
    derecha.minorticks_off()
    derecha.set_xlabel("número de buckets primarios M")
    derecha.set_ylabel("bloques")
    derecha.set_title("2000 registros fijos: elegir M lo es todo", fontsize=9.5)
    derecha.legend(fontsize=8)
    for eje in (izquierda, derecha):
        eje.grid(True, linestyle=":", alpha=0.6)
        eje.spines["top"].set_visible(False)
        eje.spines["right"].set_visible(False)
    figura.tight_layout()
    figura.savefig(os.path.join(RESULTADOS, "p1_carga.png"), dpi=170)
    plt.close(figura)


def main():
    os.makedirs(RESULTADOS, exist_ok=True)
    fases = extendible(CLAVES)
    figura_extendible(fases)
    figura_trie(fases[1])
    traza_lineal, buckets_lineal, nivel, puntero = lineal(CLAVES)
    figura_lineal(buckets_lineal, nivel, puntero, 2 * 2 ** nivel)
    figura_lineal_pasos(estados_lineales(CLAVES))
    carga, efecto_m = experimentos_p1()
    figura_p1(carga, efecto_m)

    with open(os.path.join(RESULTADOS, "trazas.json"), "w") as destino:
        json.dump({"extendible": [{"D": fase["D"], "traza": fase["traza"],
                                   "directorio": fase["directorio"],
                                   "buckets": {str(k): v for k, v in fase["buckets"].items()}}
                                  for fase in fases],
                   "lineal": {"traza": traza_lineal,
                              "buckets": {str(k): v for k, v in buckets_lineal.items()},
                              "nivel": nivel, "puntero": puntero},
                   "p1_carga": carga, "p1_buckets": efecto_m}, destino, indent=2)
    print(f"figuras y trazas en {RESULTADOS}/")
    for fase in fases:
        print(f"  fase D={fase['D']}: {len(fase['traza'])} pasos, "
              f"{len(fase['directorio'])} entradas de directorio")
    print(f"  lineal: nivel {nivel}, p {puntero}, {len(buckets_lineal)} buckets")
    print(f"  P1: factor de carga de {carga[0]['factor_carga']:.2f} a "
          f"{carga[-1]['factor_carga']:.2f}")


if __name__ == "__main__":
    main()
