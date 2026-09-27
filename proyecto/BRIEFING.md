# Proyecto CS2042 — Gestor de Bases de Datos Multimodal

> **Qué es este documento.** Un briefing autocontenido para poner en contexto a cualquier
> persona (o agente) que se sume al proyecto sin haber leído el enunciado. Resume qué hay que
> construir, con qué restricciones, qué ya está hecho y cómo está repartido el trabajo.
> Fuente original: `proyecto/Proyecto_Enunciado.pdf` (7 páginas).

**Curso:** Base de Datos II (CS2042) · UTEC · 2026-II · Docente: Percy Lovon Ramos
**Modalidad:** grupal, máximo **4 integrantes** según el enunciado — *ver nota al final, somos 5*.

---

## 1. El proyecto en una frase

Implementar **desde cero** un mini-gestor de bases de datos que opera directamente sobre
memoria secundaria: páginas y bloques físicos binarios, punteros, serialización a bajo nivel
(`seek`, `read`, `write`, `struct`), índices propios, un parser SQL, un planificador de
consultas y un cliente web que muestra el costo real de I/O de cada consulta.

Se entrega en dos partes:

| | Entregable 1 (P1) | Entregable 2 (P2) |
|---|---|---|
| **Semana** | 7 | 16 |
| **Peso** | 15 % | 15 % |
| **Tema** | Núcleo del motor relacional en disco | Extensión multimodal + aplicación de IA |

**Este documento se concentra en el P1**, que es lo inmediato. El P2 está resumido en §7.

---

## 2. Restricciones arquitectónicas (lo más importante)

Estas son las reglas que invalidan el proyecto si se rompen:

1. **Prohibido usar cualquier motor de base de datos existente** — SQLite, PostgreSQL, MySQL,
   DuckDB — y prohibido usar ORMs. Toda estructura física la codifica el equipo.
2. **Prohibido `pickle`** ni ningún serializador de alto nivel en memoria.
3. **Prohibido leer el archivo completo con `.read()`.** Toda interacción con disco es por
   desplazamiento de puntero: `seek(offset)` + lectura/escritura del bloque exacto.
4. **Empaquetamiento con `struct`** (Python) o memoria binaria (C++).
5. **Todo archivo de datos e índice reside en disco** organizado en bloques de tamaño fijo
   homogéneo: `B = 4096` bytes u `8192` bytes.

El criterio de diseño que atraviesa todo el proyecto es **minimizar el número de transferencias
de bloque entre disco y RAM**. Cada estructura se justifica por su costo de I/O, no por su
elegancia en memoria.

---

## 3. Entregable 1 — especificación por componente

### 3.1 Capa de almacenamiento físico

**Layout de página.** Cada bloque lleva una cabecera (*Page Header*) con:

| Campo | Significado |
|---|---|
| `page_id` | Identificador único del bloque dentro del archivo |
| `record_count` | Cantidad de registros activos en la página |
| `free_space_offset` | Puntero al inicio del espacio contiguo libre (o cabecera de la lista de slots) |
| `next_page_id` / `prev_page_id` | Punteros de encadenamiento entre páginas |

Se puede elegir entre dos organizaciones:
- **Registros de longitud fija con bitmap de presencia**, o
- **Página ranurada** (*Slotted-Page Architecture*) — la estándar.

**RID (Record Identifier).** Cada tupla se referencia unívocamente por la tupla lógica
`RID = ⟨page_id, slot_number⟩`. Es lo que guardan los índices no agrupados.

**DiskCounter — obligatorio.** Un monitor que registra exactamente dos variables:

```
disk_reads  : bloques físicos leídos
disk_writes : bloques físicos escritos
```

Estas cifras son las que se reportan en la API, en el frontend y en los cuatro experimentos.
Sin este contador no hay proyecto: es la evidencia de todo lo demás.

### 3.2 Métodos de organización de archivos

Hay que soportar **dos** organizaciones de tabla, seleccionables desde SQL:

**Heap File**
- *Inserción:* costo O(1) de I/O — se ubica la primera página con espacio libre vía
  **free-list**, o se anexa al final del archivo.
- *Búsqueda:* escaneo secuencial completo (*Full Table Scan*), costo `P` lecturas, donde `P`
  es el número total de páginas.
- *Eliminación:* lógica con encadenamiento de espacios en la free-list, **o** compactación
  inmediata con la técnica *move-the-last*.

**Sequential File**
- *Estructura dual:* un **Área de Datos Principal**, con páginas ordenadas físicamente por
  clave primaria (admite búsqueda binaria), y un **Área de Desbordamiento** (*overflow*) donde
  van las tuplas que ya no entran en su bloque, manteniendo el orden lógico mediante punteros
  binarios encadenados.
- *`reorganize()`:* proceso periódico que recorre ordenadamente ambos archivos, fusiona los
  registros y reescribe un archivo principal limpio y balanceado con un **fill factor de
  70–80 %**, vaciando el área de overflow.

### 3.3 Capa de indexación

Dos técnicas, ambas sobre páginas de tamaño fijo en disco:

**Árbol B+ multinivel**
- *Nodos internos:* arreglo ordenado de claves separadoras y punteros a bloques hijos
  `⟨P₀, K₁, P₁, …, Kₘ, Pₘ⟩`.
- *Nodos hoja:* pares ordenados `⟨Keyᵢ, RIDᵢ⟩` (o el registro completo si el índice es
  agrupado), más punteros de enlace continuo `next_leaf_id` y `prev_leaf_id`.
- *Operaciones:*
  - Inserción con **división recursiva (split) al 50 %**, propagación hacia el nodo padre y
    creación de nueva raíz ante sobreflujo.
  - Búsqueda puntual con costo acotado a la altura `h = O(log_M N)` transferencias.
  - Búsqueda por rango: descender a la primera hoja y recorrer horizontalmente por
    `next_leaf`, **sin volver a bajar por el árbol**.

**Hashing dinámico**
- Implementar **Extendible Hashing** *o* **Linear Hashing**. Lo esencial es que sea dinámico:
  el número de buckets crece con los datos, no se fija al crear el archivo.

### 3.4 Motor de consultas y parser SQL

El sistema expone una interfaz declarativa. La gramática mínima a soportar:

```sql
-- Creación de tablas con motor de almacenamiento específico
CREATE TABLE empleados (id INT PRIMARY KEY, nombre CHAR(30), dept CHAR(20), salario FLOAT)
  USING [HEAP | SEQUENTIAL];

-- Inserción y creación de índices en disco
INSERT INTO empleados VALUES (101, 'Ada Lovelace', 'Analytics', 5200.0);
CREATE INDEX idx_emp_id ON empleados(id) USING [BTREE | HASH];

-- Consultas de selección puntual y por rango
SELECT * FROM empleados WHERE id = 101;
SELECT * FROM empleados WHERE id >= 100 AND id <= 500;

-- Eliminación
DELETE FROM empleados WHERE id = 101;
```

**Planificador y telemetría.** El motor inspecciona la cláusula `WHERE` y elige la ruta óptima:

| Condición | Ruta |
|---|---|
| Existe índice `BTREE` o `HASH` aplicable a una igualdad | **IndexScan** |
| Se evalúa un rango y existe índice `BTREE` | **IndexRangeScan** |
| Cualquier otro caso | **SeqScan** |

Cada ejecución debe reportar el desglose exacto: **bloques leídos, bloques escritos, tiempo de
parseo y tiempo de ejecución en milisegundos**.

### 3.5 Backend API REST

Backend en **FastAPI / Flask / C++**, exponiendo al menos:

| Endpoint | Función |
|---|---|
| `POST /api/query` | Procesa la consulta y retorna las tuplas **más las métricas de I/O y tiempo** |
| `GET /api/tables` | Lista las tablas y sus índices activos |
| `POST /api/tables/reorganize` | Dispara la reorganización del Sequential File |

### 3.6 Frontend web (cliente SQL)

Cuatro secciones visibles:

1. **Explorador de tablas** — visualización de tablas y tipos de índices activos.
2. **Editor SQL** — entrada de consultas con resaltado y botón de ejecución.
3. **Visor de resultados** — tabla paginada con los registros recuperados.
4. **Plan de ejecución y métricas** — panel con el número exacto de transferencias de disco
   (I/O reads / writes) y la latencia en milisegundos.

### 3.7 Conjuntos de datos de prueba

- **Volumen mínimo obligatorio: 100 000 a 500 000 registros.** Datasets reales o sintéticos.
- *"No se admitirán proyectos validados únicamente con muestras triviales de 10 a 50 filas."*

---

## 4. Los cuatro experimentos obligatorios

El informe debe incluir estos cuatro, con datos tabulados y gráficas comparativas analizadas
a la luz de la teoría:

**1 · Costo de inserción masiva.**
Tiempo total y escrituras de I/O al insertar lotes crecientes
`N ∈ [10³, 10⁴, 5×10⁴, 10⁵, 2.5×10⁵, 5×10⁵]`
en Heap File, Sequential File (con y sin reorganización), Árbol B+ y Hash dinámico.

**2 · Búsquedas puntuales de igualdad.**
1000 consultas aleatorias de igualdad sobre `N = 100 000` registros. Comparar **promedio y
desviación estándar** de I/O reads y latencia entre:
Full Scan (Heap) · Búsqueda binaria (Sequential) · Árbol B+ · Hash dinámico.

**3 · Búsquedas por rango con selectividad variable.**
Costo de I/O y tiempo para rangos que representan **0.1 %, 1 %, 5 %, 10 % y 25 %** del total de
tuplas. Contrastar Árbol B+ frente a Sequential File y Full Scan.

**4 · Sensibilidad al tamaño de bloque.**
Variar `B ∈ [1024, 2048, 4096, 8192]` bytes y analizar el efecto en el **factor de ramificación
(fan-out)**, la **altura `h`** del árbol B+ y el **número total de I/Os** transferidos.

---

## 5. Qué hay que entregar (Semana 7)

1. **Repositorio GitHub** con acceso otorgado al docente, con esta estructura:
   ```
   backend/     frontend/     data/     benchmarks/     README.md
   ```
   El `README.md` debe traer instrucciones precisas para levantar el sistema **en un solo paso**.
2. **Informe** en PDF **compilado desde LaTeX**: descripción del diseño físico, decisiones de
   arquitectura y el reporte experimental detallado.
3. **Video demostrativo de 5 a 10 minutos**: el equipo inspecciona los archivos binarios en
   disco, demuestra la ejecución de consultas en el cliente web observando el plan de ejecución,
   y presenta los resultados del benchmark automatizado.

---

## 6. Código ya existente y reutilizable (los labs)

**Esto es clave: buena parte del P1 ya está escrita en los laboratorios del curso.** Están en
`labs/`. No hay que empezar de cero — hay que portar, unificar y completar.

### `labs/2/P1.py` — página física de 4 KB
Ya implementa el page layout completo que pide §3.1.
```
PAGE_SIZE = 4096
FILE_HEADER_FORMAT = "<iiif"   # page_count, active_count, free_page_head, fill_factor
PAGE_HEADER_FORMAT = "<iiiii"
class HeapFile              → _page_offset, _record_offset, _page_header, _new_page,
                              _read_slot, _write_slot, scan, add, remove
class FixedRecordMoveLast   → estrategia move-the-last
class FixedRecordFreeList   → estrategia free-list
```
*Lo que falta:* convertirlo a **página ranurada** con slots y exponer el **RID ⟨page_id, slot⟩**.

### `labs/3/heap_file.py` — heap con contador de I/O
```
class IOStats:  pages_read, pages_written, merge()     ← ESTE ES EL DiskCounter
class HeapFile: create(), read_page(), write_page(), append_page(), pages(), records()
SCHEMAS = {...}   # formatos struct por tabla, p.ej. "<q10s14s16s1s10s"
```
*Lo que falta:* nada estructural. `IOStats` ya es el monitor obligatorio; hay que centralizarlo
para que **todas** las estructuras lo compartan.

### `labs/4/sequential_file.py` — archivo secuencial con área auxiliar
```
class SequentialFile:
    build(), insert(), search(), remove(), range_search(), load(), _reconstruir()
    K_AUXILIAR = 32    # umbral de reconstrucción
```
*Lo que falta:* encadenar los punteros binarios en el área de overflow y aplicar el
**fill factor de 70–80 %** en `_reconstruir()`, que hoy no lo hace.

### `labs/4 1:2/bplus_tree.py` — árbol B+ en disco (509 líneas, el más completo)
```
class BPlusTreeFile:
    read_node(), write_node(), search(), range_search(), insert(), remove(), validar()
    _dividir_hoja(), _dividir_interno(), _fusionar(), _prestar_de_izquierda/derecha()
    ORDEN = 64         # un nodo = un bloque físico
```
*Lo que falta:* parametrizar el tamaño de bloque para el Experimento 4, y guardar **RIDs** en
las hojas en vez del registro completo si se quiere índice no agrupado.

### `labs/5/static_hash.py` — hash en disco
```
class StaticHashFile:
    insert(), search(), remove(), cadena(), estadisticas()
    BUCKETS = 101, FACTOR_BLOQUE = 8    # buckets + overflow encadenado
```
*Lo que falta:* **es estático**. Hay que convertirlo en Extendible o Linear Hashing — esta es
la única estructura que requiere trabajo algorítmico real de cero.

### `labs/3/external_sort.py` — ordenamiento externo
```
generate_runs(), merge_group(), multiway_merge(), external_sort(), verify_sorted()
class PageReader / PageWriter
```
*Útil para:* el merge ordenado dentro de `reorganize()`, y más adelante para SPIMI en el P2.

### `labs/4/registro.py` — serialización de registros
```
FORMATO = "<i30si20s20s20sf10s"
empaquetar() / desempaquetar() / texto_fijo() / leer_csv()
```
Es el patrón de serialización que ya usan todas las estructuras. El motor final necesita
generalizarlo para que el `CREATE TABLE` construya el formato `struct` dinámicamente.

### Además
`labs/{3,4,5}/benchmark.py` e `informe.py` ya son un arnés de benchmarks con generación de
gráficas y tablas. Los cuatro experimentos salen de ahí con adaptaciones.

**Resumen de lo que hay que escribir realmente desde cero:**
página ranurada con RID · hashing dinámico · parser SQL · planificador · API REST · frontend.

---

## 7. Entregable 2 (Semana 16) — resumen

Para contexto, porque condiciona la elección del dataset:

- **Módulo espacial:** R-Tree / GiST — indexación 2D en disco por cajas envolventes mínimas
  (MBR), consultas de proximidad y visor en mapa cartográfico (Leaflet / OpenLayers).
- **Módulo de texto:** índices invertidos construidos con el algoritmo **SPIMI**, ranking por
  **TF-IDF** y **BM25**.
- **Módulo multimedia y vectorial:** indexación de *embeddings* de alta dimensión con **IVF** o
  grafos navegables **HNSW**.
- **Aplicación de IA — obligatoria**, una de cuatro:
  - **A:** RAG sobre literatura científica (ArXiv / NeurIPS)
  - **B:** Recomendador multimodal para e-commerce (imágenes similares + metadatos)
  - **C:** Detección de huellas acústicas y derechos de autor en audio
  - **D:** Reconocimiento e identificación facial (LFW / CelebA)

SQL extendido con distancias geográficas, búsqueda por relevancia textual (`MATCH`) y similitud
de embeddings (`COSINE`).

---

## 8. Dataset — estado de la decisión

Se verificaron los tamaños reales de los candidatos contra el mínimo de 100 000–500 000 filas:

| Dataset | Filas | ¿Cumple? | Notas |
|---|---|---|---|
| Flipkart Products (PromptCloudHQ) | 20 000 | ❌ | No llega al mínimo. Descartado. |
| Amazon Products 2023 (asaniczka) | 1 400 000 | ✅ | Solo `title`, sin descripción larga → BM25 flojo |
| NYC Taxi Trip Duration | 1 458 644 | ✅ | Tiene coordenadas, pero **sin texto ni imágenes** → inservible para el P2 |
| NYC Yellow Taxi (TLC) | millones | ⚠️ | **Sin lat/lon desde julio 2016** (solo `PULocationID`) |
| Olist `order_items` | 112 650 | ✅ | Justo por encima del mínimo |
| **Olist `geolocation`** | **1 000 163** | ✅ | Numérico y limpio; alimenta también el R-Tree |
| Olist `order_reviews` | 99 224 (≈41 000 con texto) | ✅ | Sirve para BM25 |

**Propuesta del equipo (pendiente de confirmación):** usar el
**Brazilian E-Commerce Public Dataset by Olist** (`olistbr/brazilian-ecommerce`) como columna
vertebral, con `olist_geolocation_dataset.csv` como tabla de estrés del P1.

Motivo: su esquema es `(zip_code_prefix INT, lat FLOAT, lng FLOAT, city CHAR, state CHAR(2))` —
numérico, sin strings problemáticos que corrompan el empaquetado binario — cubre con holgura el
`N = 5×10⁵` del Experimento 1, y **las mismas coordenadas alimentan el R-Tree y el visor de
mapas del P2** sin cargar un segundo dataset. Las tablas `order_items`, `products` y `reviews`
quedan como dominio para las demos de SQL y el índice invertido.

*Limitación conocida:* Olist no tiene imágenes de producto. Si se elige la Opción B
(recomendador multimodal), el módulo vectorial tendría que trabajar sobre embeddings de texto,
o complementarse con un dataset de Amazon que sí traiga `imgUrl`.

---

## 9. Reparto del trabajo

El P1 está dividido en seis bloques. Somos cinco, así que a alguien le tocan dos.

| # | Bloque | Alcance | Punto de partida |
|---|---|---|---|
| **01** | **Núcleo de almacenamiento** ⚠️ *bloqueante* | Página ranurada de 4 KB, cabecera, RID ⟨page_id, slot⟩, DiskCounter, file manager sobre `seek/read/write` | `labs/2/P1.py` + `labs/3/heap_file.py` |
| **02** | **Heap + Sequential File** | Free-list o move-the-last; área principal + overflow encadenado; `reorganize()` con fill factor 70–80 % | `labs/4/sequential_file.py` |
| **03** | **Árbol B+ multinivel** | Split recursivo al 50 %, búsqueda puntual, rango por `next_leaf` | `labs/4 1:2/bplus_tree.py` |
| **04** | **Hashing dinámico** | Extendible o Linear Hashing: directorio, buckets, split de bucket | `labs/5/static_hash.py` |
| **05** | **Parser SQL + planner** | Tokenizer, AST, selección de ruta de acceso, telemetría | desde cero |
| **06** | **API REST + frontend** | Los 3 endpoints y los 4 paneles | desde cero |

**Fuera del reparto — lo hacen los cinco:** informe LaTeX, video de 5–10 min, los cuatro
experimentos, y la preparación del dataset.

> **El bloque 01 bloquea a todos los demás.** Nadie puede avanzar en serio hasta que exista el
> page layout, el RID y el DiskCounter, porque las cinco estructuras restantes se construyen
> encima. Debe arrancar el día 1 y cerrarse rápido.

---

## 10. Avisos

1. **Tamaño del equipo.** El enunciado dice textualmente *"equipos de máximo 04 integrantes"* y
   el equipo es de 5. Hay que confirmarlo con el docente antes de avanzar — afecta la
   conformación y potencialmente la nota.
2. **Un solo DiskCounter.** El error clásico es que cada estructura lleve su propio contador y
   las cifras del informe no cuadren. Debe ser una única instancia compartida, inyectada en el
   file manager, y nadie toca el archivo sin pasar por ahí.
3. **El tamaño de bloque tiene que ser un parámetro**, no una constante. El Experimento 4 exige
   correr todo con `B ∈ [1024, 2048, 4096, 8192]`.
4. **El frontend no se deja para el final.** Es lo que se graba en el video y lo que demuestra
   el plan de ejecución; sin él no hay evidencia de nada.
