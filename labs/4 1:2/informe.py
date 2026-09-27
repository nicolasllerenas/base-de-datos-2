import json
import os
import re

from docx import Document
from docx.enum.style import WD_STYLE_TYPE
from docx.enum.text import WD_ALIGN_PARAGRAPH, WD_BREAK
from docx.shared import Cm, Pt, RGBColor

RESULTADOS = "resultados"
CAPTURAS = "capturas"
SALIDA = "Informe_Laboratorio04_5.docx"
LOGO = "utec.png"


def metricas():
    with open(os.path.join(RESULTADOS, "metricas.json")) as fuente:
        return json.load(fuente)


def por_tamano(filas, tamano):
    return next(fila for fila in filas if fila["tamano"] == tamano)


def por_orden(filas, orden):
    return next(fila for fila in filas if fila["orden"] == orden)


def coma(valor, decimales=2):
    return f"{valor:.{decimales}f}".replace(".", ",")


def mil(valor):
    return f"{int(valor):,}".replace(",", "\u00a0")


def documento():
    doc = Document()
    seccion = doc.sections[0]
    seccion.page_width = Cm(21.0)
    seccion.page_height = Cm(29.7)
    seccion.top_margin = Cm(2.5)
    seccion.bottom_margin = Cm(2.5)
    seccion.left_margin = Cm(3.0)
    seccion.right_margin = Cm(3.0)

    normal = doc.styles["Normal"]
    normal.font.name = "Arial"
    normal.font.size = Pt(12)
    normal.paragraph_format.line_spacing = 1.5
    normal.paragraph_format.space_after = Pt(6)
    normal.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.JUSTIFY

    for nombre, tamano in (("Heading 1", 14), ("Heading 2", 12), ("Heading 3", 12)):
        estilo = doc.styles[nombre]
        estilo.font.name = "Arial"
        estilo.font.size = Pt(tamano)
        estilo.font.bold = True
        estilo.font.italic = nombre == "Heading 3"
        estilo.font.color.rgb = RGBColor(0, 0, 0)
        estilo.paragraph_format.line_spacing = 1.5
        estilo.paragraph_format.space_before = Pt(12)
        estilo.paragraph_format.space_after = Pt(6)
        estilo.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.LEFT

    pie = doc.styles.add_style("Pie", WD_STYLE_TYPE.PARAGRAPH)
    pie.font.name = "Arial"
    pie.font.size = Pt(10)
    pie.font.italic = True
    pie.paragraph_format.line_spacing = 1.0
    pie.paragraph_format.space_after = Pt(10)
    pie.paragraph_format.alignment = WD_ALIGN_PARAGRAPH.CENTER
    return doc


def parrafo(doc, texto, estilo=None):
    parrafo_actual = doc.add_paragraph(style=estilo)
    for indice, fragmento in enumerate(re.split(r"</?b>", texto)):
        if fragmento:
            parrafo_actual.add_run(fragmento).font.bold = indice % 2 == 1
    return parrafo_actual


def captura(doc, nombre, pie):
    figura(doc, os.path.join(CAPTURAS, nombre), pie, ancho=15.0)


def figura(doc, ruta, pie, ancho=14.0):
    doc.add_picture(ruta, width=Cm(ancho))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph(pie, style="Pie")


def tabla(doc, cabeceras, filas, izquierda=(0,)):
    tabla = doc.add_table(rows=1, cols=len(cabeceras))
    tabla.style = "Table Grid"
    for celda, texto in zip(tabla.rows[0].cells, cabeceras):
        celda.text = texto
        for parrafo_celda in celda.paragraphs:
            parrafo_celda.alignment = WD_ALIGN_PARAGRAPH.CENTER
            for corrida in parrafo_celda.runs:
                corrida.font.bold = True
    for fila in filas:
        celdas = tabla.add_row().cells
        for indice, (celda, texto) in enumerate(zip(celdas, fila)):
            celda.text = str(texto)
            for parrafo_celda in celda.paragraphs:
                parrafo_celda.alignment = (WD_ALIGN_PARAGRAPH.LEFT if indice in izquierda
                                           else WD_ALIGN_PARAGRAPH.CENTER)
    for fila in tabla.rows:
        for celda in fila.cells:
            for parrafo_celda in celda.paragraphs:
                parrafo_celda.paragraph_format.line_spacing = 1.0
                parrafo_celda.paragraph_format.space_after = Pt(2)
                for corrida in parrafo_celda.runs:
                    corrida.font.name = "Arial"
                    corrida.font.size = Pt(9)
    doc.add_paragraph()
    return tabla


def agrupar(cuadro, pares, columna_inicial=0):
    for izquierda, derecha in pares:
        cuadro.cell(0, izquierda).merge(cuadro.cell(0, derecha))
    for columna in range(columna_inicial + 1):
        cuadro.cell(0, columna).merge(cuadro.cell(1, columna))


def portada(doc):
    def centrado(texto, tamano=12, negrita=False, espacio=6):
        parrafo_actual = doc.add_paragraph()
        parrafo_actual.alignment = WD_ALIGN_PARAGRAPH.CENTER
        parrafo_actual.paragraph_format.space_after = Pt(espacio)
        corrida = parrafo_actual.add_run(texto)
        corrida.font.size = Pt(tamano)
        corrida.font.bold = negrita
        return parrafo_actual

    centrado("UNIVERSIDAD DE INGENIERÍA Y TECNOLOGÍA", 14, True, 24)
    doc.add_picture(LOGO, width=Cm(6))
    doc.paragraphs[-1].alignment = WD_ALIGN_PARAGRAPH.CENTER
    doc.add_paragraph().paragraph_format.space_after = Pt(24)
    centrado("Curso:", 14, True, 2)
    centrado("Base de Datos II", 14, False, 36)
    centrado("Laboratorio 04.5: Indexación con Árbol B+", 18, True, 6)
    centrado("en Memoria Secundaria", 18, True, 48)
    centrado("Alumno:", 12, True, 2)
    centrado("Llerena Silva, Nicolás Alejandro (202110190)", 12, False, 24)
    centrado("Profesor:", 12, True, 2)
    centrado("Lovon, Percy", 12, False, 36)
    centrado("Lima, setiembre de 2026", 12, False, 0)
    doc.add_paragraph().add_run().add_break(WD_BREAK.PAGE)


def introduccion(doc):
    doc.add_heading("Introducción", level=1)
    parrafo(doc, "El laboratorio pide construir un índice de árbol B+ que viva en disco y evaluarlo "
                 "sobre el dataset de empleados, usando el Employee_ID como clave. La diferencia con "
                 "las estructuras de los laboratorios anteriores es el grano: acá la unidad de "
                 "trabajo no es el registro sino el bloque, y cada nodo del árbol ocupa exactamente "
                 "un bloque del archivo. Esa decisión es la que hace que el árbol sea plano y que una "
                 "búsqueda cueste tres lecturas incluso con cien mil registros.")
    parrafo(doc, "Están implementadas las cuatro operaciones que pide el enunciado (insert con "
                 "split, search, rangeSearch aprovechando el enlace entre hojas y remove con "
                 "rebalanceo real), más un validador de invariantes que se usa como red de seguridad "
                 "en todas las pruebas. Todo el código es Python con struct y archivos binarios; "
                 "matplotlib solo aparece para las gráficas.")

    doc.add_heading("Los datos y el registro", level=2)
    parrafo(doc, "El employee.csv se construye desde la base employees del Laboratorio 01 con "
                 "exportar_csv.py, que toma 100 000 empleados vigentes con sus datos reales de "
                 "nombre, departamento, sueldo y fecha de ingreso. Country es el único campo que la "
                 "base no tiene y se asigna de forma determinista a partir del id. Los 100 000 "
                 "registros permiten llegar al N = 10⁵ que sugiere el enunciado para los "
                 "experimentos.")
    parrafo(doc, "Sobre el tamaño del registro hay que hacer una precisión. El enunciado anuncia "
                 "112 bytes, pero la tabla de campos que da a continuación lista seis campos que "
                 "suman 88: 4 de Employee_ID, 30 de Employee_Name, 20 de Country, 20 de Department, "
                 "4 de Salary y 10 de Joining_Date. Los 112 corresponden al registro del laboratorio "
                 "anterior, que además tenía Age y Position. Implementé lo que dice la tabla, con los "
                 "formatos de struct que ella misma indica, así que el registro ocupa 88 bytes y el "
                 "formato completo es <i30s20s20sf10s.")
    captura(doc, "cap_datos.png", "Exportación del CSV desde la base employees.")


def parte1(doc, datos):
    grande = por_tamano(datos["tamanos"], 100000)
    doc.add_heading("P1: estructura física y serialización", level=1)
    parrafo(doc, "Un nodo es un bloque y un bloque es un nodo. El tamaño del bloque no se fija a "
                 "mano sino que se deriva del orden M, porque lo que tiene que entrar en el bloque "
                 "son M−1 registros de 88 bytes más la cabecera: BLOQUE(M) = 12 + (M−1)×88. Con el "
                 "orden 64 que uso por defecto eso da bloques de 5556 bytes. El nodo interno entra "
                 "holgado en ese mismo bloque, porque sus M−1 claves de 4 bytes y sus M punteros de "
                 "4 bytes ocupan mucho menos que los registros de una hoja; la diferencia queda como "
                 "relleno, que es el precio de tener un único tamaño de bloque para los dos tipos de "
                 "nodo.")
    figura(doc, os.path.join(RESULTADOS, "diagrama_nodos.png"),
           "Estructura binaria de los bloques en disco, con el orden M = 64.", ancho=15.0)
    parrafo(doc, "La cabecera de 12 bytes lleva el tipo de nodo, un byte reservado para alinear, el "
                 "número de claves ocupadas y los dos punteros de la lista de hojas. En un nodo "
                 "interno esos dos punteros valen −1. Después de la cabecera, un nodo interno guarda "
                 "sus claves seguidas de sus punteros a bloque, y una hoja guarda los registros "
                 "completos uno detrás de otro. Los punteros son números de bloque, no "
                 "desplazamientos en bytes, así que el offset físico se calcula como cabecera del "
                 "archivo más número de bloque por tamaño de bloque.")
    parrafo(doc, "read_node hace un seek al bloque, lee sus bytes de una vez y los interpreta con "
                 "struct.unpack_from según el tipo; write_node arma un bytearray del tamaño exacto "
                 "del bloque, lo rellena con struct.pack_into y lo escribe de un solo write. Las dos "
                 "funciones incrementan los contadores de lecturas y escrituras, que son los que "
                 "alimentan todas las mediciones de la tercera parte. El archivo empieza con una "
                 "cabecera propia de 24 bytes que guarda la raíz, la cantidad de bloques, la altura, "
                 "el número de registros, el orden y la cabeza de la lista de bloques libres.")
    parrafo(doc, "La inserción baja hasta la hoja que corresponde, mete el registro en su posición "
                 "ordenada y, si la hoja se pasa de M−1, la parte en dos y devuelve hacia arriba la "
                 "primera clave de la mitad derecha. En una hoja esa clave se copia al padre y en un "
                 "nodo interno la clave del medio sube y desaparece del hijo, que es la diferencia "
                 "clásica entre el split de hoja y el de nodo interno en un B+. Si la promoción llega "
                 "hasta la raíz se crea una raíz nueva y el árbol gana un nivel. Con 100 000 "
                 f"registros el árbol terminó con altura {grande['altura']} y "
                 f"{grande['hojas']} hojas.")


def parte2(doc):
    doc.add_heading("P2: búsquedas y eliminación", level=1)
    parrafo(doc, "search desciende de la raíz a la hoja resolviendo cada nodo interno con búsqueda "
                 "binaria sobre sus claves separadoras, así que hace exactamente una lectura por "
                 "nivel. rangeSearch hace ese mismo descenso una sola vez, para ubicar la hoja donde "
                 "empieza el rango, y a partir de ahí avanza por el puntero next_leaf leyendo hojas "
                 "consecutivas hasta pasarse de la clave final. Es la operación donde el B+ se "
                 "separa del resto: los niveles superiores del árbol no se vuelven a tocar.")
    parrafo(doc, "remove elimina físicamente y rebalancea. Se quita el registro de la hoja y, si "
                 "queda por debajo del mínimo, se intenta primero pedirle un registro al hermano "
                 "izquierdo y después al derecho, actualizando la clave separadora del padre. Si "
                 "ningún hermano puede prestar sin quedar corto, los dos se fusionan en uno y la "
                 "clave separadora baja o desaparece según el nodo sea interno u hoja. La fusión "
                 "puede dejar corto al padre, y eso lo resuelve la vuelta de la recursión; si la raíz "
                 "se queda sin claves, el árbol pierde un nivel. Los bloques que quedan vacíos por "
                 "una fusión se encadenan en una lista de libres y se reutilizan en la siguiente "
                 "inserción, para que el archivo no crezca indefinidamente.")
    parrafo(doc, "Como la eliminación es la parte donde estos árboles se rompen en silencio, el "
                 "módulo trae un validador que recorre el árbol entero y comprueba cinco cosas: que "
                 "las claves de cada nodo estén ordenadas, que caigan dentro del rango que impone el "
                 "padre, que todas las hojas estén a la misma profundidad, que ningún nodo distinto "
                 "de la raíz esté por debajo del mínimo de ocupación y que el recorrido por la lista "
                 "de hojas devuelva exactamente los registros esperados en orden. La prueba que "
                 "aparece abajo inserta 3000 registros y borra 2500 con tres órdenes distintos, "
                 "validando cada 500 bajas.")
    captura(doc, "cap_bplus.png", "Operaciones sobre 5000 registros y prueba de estrés de la "
                                  "eliminación. Entre corchetes van los accesos a disco.")


def parte3(doc, datos):
    filas = datos["tamanos"]
    ordenes = datos["ordenes"]
    rango = datos["rango"]
    chico = por_tamano(filas, 1000)
    grande = por_tamano(filas, 100000)
    m4 = por_orden(ordenes, 4)
    m64 = por_orden(ordenes, 64)
    m256 = por_orden(ordenes, 256)

    doc.add_heading("P3: evaluación experimental", level=1)
    parrafo(doc, "Las mediciones se hacen con benchmark.py sobre el CSV barajado con una semilla "
                 "fija, para que las claves no entren ordenadas y el árbol se comporte como en un "
                 "caso real. Cada tanda cronometra la operación y lee los contadores de bloques "
                 "leídos y escritos que llevan read_node y write_node. Después de construir y "
                 "después de eliminar se corre el validador, así que los números que siguen "
                 "corresponden a árboles verificados.")

    cuadro = tabla(doc,
          ["N", "Altura", "Hojas", "Ocupación", "Construcción", "", "Búsqueda", "", "Rango", ""],
          [["", "", "", "", "seg", "I/O", "lecturas", "ms", "lecturas", "ms"]] +
          [[f"{fila['tamano']:,}".replace(",", "\u00a0"), fila["altura"],
            f"{fila['hojas']:,}".replace(",", "\u00a0"), f"{fila['ocupacion_hojas']:.0%}",
            coma(fila["construccion"]["total_seg"]),
            mil(fila["construccion"]["lecturas"] + fila["construccion"]["escrituras"]),
            f"{fila['busqueda']['lecturas_promedio']:.1f}",
            coma(fila["busqueda"]["promedio_ms"], 3),
            f"{fila['rango']['lecturas_promedio']:.1f}",
            coma(fila["rango"]["promedio_ms"], 3)] for fila in filas])
    agrupar(cuadro, [(4, 5), (6, 7), (8, 9)], columna_inicial=3)
    doc.add_paragraph("Escalamiento con M = 64. La búsqueda y el rango son promedios de 500 y 100 "
                      "operaciones.", style="Pie")
    figura(doc, os.path.join(RESULTADOS, "escalamiento.png"),
           "Costo de construcción, búsqueda y rango al crecer N.", ancho=15.0)

    parrafo(doc, f"El resultado que más importa está en el panel de abajo a la izquierda: la "
                 f"búsqueda puntual cuesta {chico['busqueda']['lecturas_promedio']:.0f} lecturas con "
                 f"mil registros y {grande['busqueda']['lecturas_promedio']:.0f} con cien mil, y esas "
                 f"lecturas son exactamente la altura del árbol. Entre 10⁴ y 10⁵ el número no se "
                 f"mueve porque un árbol de altura 3 con orden 64 admite hasta 64 × 64 × 63 = 258 048 "
                 f"registros; para pasar a cuatro lecturas habría que superar ese techo. La "
                 f"construcción, en cambio, crece de forma lineal, que es lo esperable: son N "
                 f"inserciones y cada una cuesta del orden de la altura.")
    parrafo(doc, f"El costo del rango crece de "
                 f"{chico['rango']['lecturas_promedio']:.1f} a "
                 f"{grande['rango']['lecturas_promedio']:.1f} lecturas, pero no porque el árbol "
                 f"empeore: el rango tiene ancho fijo de 500 claves y, al haber más registros en el "
                 f"mismo tramo de identificadores, la respuesta trae más filas y hacen falta más "
                 f"hojas para devolverlas. El descenso sigue costando 3 lecturas; el resto es "
                 f"recorrido secuencial por next_leaf.")

    doc.add_heading("Impacto del orden M", level=2)
    tabla(doc,
          ["M", "Bloque (B)", "Altura", "Hojas", "Archivo (MB)", "Búsqueda (lecturas)",
           "Rango (lecturas)", "I/O construcción"],
          [[fila["orden"], mil(fila["bloque"]), fila["altura"],
            f"{fila['hojas']:,}".replace(",", "\u00a0"), coma(fila["bytes"] / 1e6),
            f"{fila['busqueda_lecturas']:.1f}", f"{fila['rango_lecturas']:.1f}",
            mil(fila["construccion_io"])] for fila in ordenes])
    doc.add_paragraph("Efecto del orden con 20 000 registros.", style="Pie")
    figura(doc, os.path.join(RESULTADOS, "orden_m.png"),
           "Altura y costo de búsqueda frente al orden, y precio de un M grande.", ancho=15.0)
    parrafo(doc, f"Subir el orden aplana el árbol y eso se traduce directamente en menos lecturas: "
                 f"con M = {m4['orden']} el árbol tiene altura {m4['altura']} y cada búsqueda cuesta "
                 f"{m4['busqueda_lecturas']:.0f} lecturas, mientras que con M = {m256['orden']} "
                 f"bastan {m256['busqueda_lecturas']:.0f}. La ganancia no es gratis y se nota en dos "
                 f"lugares. El primero es el bloque: con M = {m256['orden']} pesa "
                 f"{mil(m256['bloque'])} bytes, de modo que cada lectura mueve 22 KB para responder "
                 f"por un registro de 88 bytes, y el sistema de archivos termina haciendo varias "
                 f"operaciones físicas por cada lectura lógica. El segundo es la escritura: cada "
                 f"inserción reescribe el bloque entero, así que un bloque grande encarece la "
                 f"construcción. En un motor real M se elige para que el bloque coincida con la "
                 f"página del disco, típicamente 4 u 8 KB, que en este diseño cae entre M = 32 y "
                 f"M = 64.")
    parrafo(doc, f"El tamaño del archivo se comporta al revés de lo que uno esperaría: baja de "
                 f"{coma(m4['bytes'] / 1e6)} MB con M = 4 a {coma(m64['bytes'] / 1e6)} MB con "
                 f"M = 64. Con órdenes chicos hay muchísimos nodos internos, y cada uno gasta una "
                 f"cabecera y punteros; además el relleno del bloque interno se paga tantas veces "
                 f"como nodos internos haya. Con M = 256 vuelve a subir un poco porque las hojas "
                 f"quedan medio vacías y cada hoja desperdicia media página.")

    doc.add_heading("Rango: B+ contra escaneo secuencial y contra el AVL", level=2)
    tabla(doc,
          ["Estructura", "Lecturas por rango", "Tiempo por rango (ms)", "Veces más lecturas"],
          [["Árbol B+ (M = 64)", f"{rango['bplus']['lecturas_promedio']:.1f}",
            coma(rango["bplus"]["promedio_ms"], 3), "1,0"],
           ["Árbol AVL (laboratorio 04)", f"{rango['avl']['lecturas_promedio']:.1f}",
            coma(rango["avl"]["promedio_ms"], 3),
            coma(rango["avl"]["lecturas_promedio"] / rango["bplus"]["lecturas_promedio"], 1)],
           ["Escaneo secuencial", f"{rango['secuencial']['lecturas_promedio']:.1f}",
            coma(rango["secuencial"]["promedio_ms"], 3),
            coma(rango["secuencial"]["lecturas_promedio"] / rango["bplus"]["lecturas_promedio"], 1)]],
          izquierda=(0,))
    doc.add_paragraph(f"Rangos de 500 claves sobre 20 000 registros, que devuelven "
                      f"{rango['registros_por_rango']:.0f} registros en promedio. Los tres métodos "
                      f"devuelven exactamente los mismos registros, lo verifica el benchmark.",
                      style="Pie")
    figura(doc, os.path.join(RESULTADOS, "rango_comparacion.png"),
           "Costo de una búsqueda por rango según la organización del archivo.")
    parrafo(doc, f"El escaneo secuencial lee el archivo completo, "
                 f"{rango['secuencial']['lecturas_promedio']:.0f} bloques, para devolver "
                 f"{rango['registros_por_rango']:.0f} registros; tarda "
                 f"{coma(rango['secuencial']['promedio_ms'], 1)} ms, unas "
                 f"{coma(rango['secuencial']['promedio_ms'] / rango['bplus']['promedio_ms'], 0)} "
                 f"veces más que el B+. El AVL es mucho mejor que eso porque no lee lo que no "
                 f"necesita, pero igual gasta {rango['avl']['lecturas_promedio']:.0f} lecturas "
                 f"contra las {rango['bplus']['lecturas_promedio']:.1f} del B+: como cada nodo del "
                 f"AVL guarda un solo registro, devolver "
                 f"{rango['registros_por_rango']:.0f} filas exige visitar al menos "
                 f"{rango['registros_por_rango']:.0f} nodos, más el camino de bajada. El B+ resuelve "
                 f"lo mismo con tres lecturas de descenso y menos de dos hojas.")

    doc.add_heading("Por qué el B+ minimiza los accesos a disco", level=2)
    parrafo(doc, "La razón de fondo es que en memoria secundaria el costo se paga por bloque y no "
                 "por comparación. Traer un bloque cuesta un posicionamiento del disco, y ese "
                 "posicionamiento es órdenes de magnitud más caro que cualquier trabajo que se haga "
                 "después en RAM con los bytes traídos. Un árbol binario gasta ese acceso completo "
                 "para leer un solo registro y dos punteros; el B+ lo gasta para traer hasta 63 "
                 "claves de una vez y decidir con ellas por dónde seguir.")
    parrafo(doc, "Eso se ve en la altura, que es lo único que se paga en una búsqueda. Un AVL tiene "
                 "altura de hasta 1,44·log₂(N), que con 100 000 registros son unos 24 niveles; el B+ "
                 "tiene altura log_M(N), que con M = 64 son 3. Medido sobre 20 000 registros, la "
                 "construcción del AVL del laboratorio anterior gastó 527 000 accesos y la del B+ "
                 "unos 38 000 para 10 000 registros, es decir un orden de magnitud menos por "
                 "registro insertado.")
    parrafo(doc, "A eso se suma la segunda decisión de diseño del B+: los registros viven solo en "
                 "las hojas y las hojas están enlazadas. Un árbol binario mezcla datos y estructura "
                 "en todos los niveles, así que un recorrido ordenado obliga a subir y bajar por el "
                 "árbol saltando entre bloques dispersos. En el B+ el recorrido ordenado es leer "
                 "hojas consecutivas, que además es el patrón que mejor aprovecha la lectura "
                 "anticipada del sistema operativo. Por eso el B+ es la estructura que usan "
                 "PostgreSQL, MySQL y prácticamente cualquier motor para sus índices, y no un AVL.")


def conclusiones(doc, datos):
    grande = por_tamano(datos["tamanos"], 100000)
    rango = datos["rango"]
    doc.add_heading("Conclusiones", level=1)
    parrafo(doc, f"El árbol B+ quedó implementado con bloques de tamaño fijo, un nodo por bloque, "
                 f"split en la inserción, eliminación con préstamo y fusión, y lista enlazada entre "
                 f"hojas. Con 100 000 registros el árbol tiene altura {grande['altura']} y una "
                 f"búsqueda cuesta {grande['busqueda']['lecturas_promedio']:.0f} lecturas, un número "
                 f"que se mantiene constante en dos órdenes de magnitud de N. Es la propiedad que "
                 f"justifica la estructura: el costo de acceso deja de depender del tamaño de los "
                 f"datos en cualquier rango de tamaños práctico.")
    parrafo(doc, f"En la búsqueda por rango la ventaja es todavía más marcada, porque el enlace "
                 f"entre hojas convierte la consulta en una lectura secuencial: "
                 f"{rango['bplus']['lecturas_promedio']:.1f} bloques contra "
                 f"{rango['avl']['lecturas_promedio']:.0f} del AVL y "
                 f"{rango['secuencial']['lecturas_promedio']:.0f} del escaneo completo. El orden M "
                 f"es la perilla que gobierna todo el comportamiento, y conviene elegirlo de modo "
                 f"que el bloque coincida con la página física del disco: más chico deja el árbol "
                 f"innecesariamente alto y más grande hace que cada acceso mueva datos que no se "
                 f"usan.")


def anexo(doc):
    doc.add_heading("Anexo: archivos entregados", level=1)
    parrafo(doc, "registro.py define el registro de 88 bytes, su serialización con struct y la "
                 "lectura del CSV. bplus_tree.py contiene la clase BPlusTreeFile con read_node, "
                 "write_node, insert con split, search, range_search, remove con préstamo y fusión, "
                 "y el validador de invariantes; ejecutado directamente corre la demostración y la "
                 "prueba de estrés de este informe. avl_file.py es el árbol AVL del laboratorio "
                 "anterior, incluido porque benchmark.py lo usa como línea base de la comparación "
                 "por rango. benchmark.py ejecuta los tres experimentos y genera las gráficas y el "
                 "diagrama de bloques. Los datos van en data/employee.csv, exportado de la base "
                 "employees del Laboratorio 01 tal como se describe al inicio del informe.")


def main():
    datos = metricas()
    doc = documento()
    portada(doc)
    introduccion(doc)
    parte1(doc, datos)
    parte2(doc)
    parte3(doc, datos)
    conclusiones(doc, datos)
    anexo(doc)
    doc.save(SALIDA)
    print(f"{SALIDA} ({os.path.getsize(SALIDA) // 1024} KB)")


if __name__ == "__main__":
    main()
