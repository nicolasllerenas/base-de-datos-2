<div style="background: #86d1f1ff; border-radius: 5px; padding: 1rem; margin-bottom: 1rem">
<img src="https://store.utec.edu.pe/files/Recursos/logo-utec-h.png" alt="Banner" width="150" />   
 <div style="font-weight: bold; color: #434549ff; float: right "><u style="font-size: 28px;">Base de Datos II</u> <br />
<span style="float:right"> Profesor Percy Lovon</span> <br /> 
<span style="float:right">  2026 - 2 </span>   
 </div>
 </div>
 

 
# Laboratorio 04.5: Indexación con Árbol B+ en Memoria Secundaria (B+ Tree File)

## **1. Introducción**

El propósito de este laboratorio es diseñar e implementar un índice/archivo multinivel basado en **Árbol B+ (B+ Tree)** persistente en memoria secundaria para la gestión eficiente de grandes volúmenes de datos, utilizando el dataset de empleados.


Se debe implementar la estructura y evaluar las operaciones fundamentales utilizando como clave de búsqueda el **ID de empleado** (`Employee_ID`):
- `insert(record)`: Inserción de registros con división de nodos (*split*) cuando se supera la capacidad.
- `search(key)`: Búsqueda exacta navegando desde la raíz hasta la hoja correspondiente.
- `rangeSearch(init_key, end_key)`: Búsqueda por rango explotando la lista enlazada entre nodos hoja.
- `remove(key)`: Eliminación lógica o física de registros.

---

### **Requerimientos de implementación:**
- Implementación completa en **Python** (usando `struct` y archivos binarios).
- Representación en disco mediante **bloques / páginas de tamaño fijo** (un bloque físico por nodo del árbol).
- Cada nodo interno almacena claves separadoras y punteros (offsets en bytes o IDs de bloque) a nodos hijos.
- Los **nodos hoja** almacenan las claves con los registros (o apuntadores al archivo de datos) y un puntero `next_leaf` (y opcionalmente `prev_leaf`) hacia el siguiente bloque hoja.
- Estructura de registro de longitud fija (**112 bytes**):

| Campo           | Tipo de Dato           | Formato `struct` | Tamaño (bytes) |
|:----------------|:-----------------------|:-----------------|:---------------|
| `Employee_ID`   | `int`                  | `i`              | 4              |
| `Employee_Name` | `string`               | `30s`            | 30             |
| `Country`       | `string`               | `20s`            | 20             |
| `Department`    | `string`               | `20s`            | 20             |
| `Salary`        | `float`                | `f`              | 4              |
| `Joining_Date`  | `string (DD/MM/YYYY)`  | `10s`            | 10             |

---

## **2. Desarrollo**

### **P1 (7 puntos): Estructura Física y Serialización del Árbol B+ en Disco**
1. **Definición de Bloques/Nodos:** Diseñar el formato binario de los nodos internos y nodos hoja con un orden $M$ definido (o capacidad máxima $B$ por nodo).
   - Cabecera del bloque: tipo de nodo (hoja/interno), número actual de claves, punteros/enlaces entre hojas.
2. **Persistencia y Punteros a Disco:** Implementar lectura (`read_node`) y escritura (`write_node`) en disco utilizando `seek` y `struct.pack` / `struct.unpack`.
3. **Carga Inicial / Inserción con Split:**
   - Carga de datos desde `employee.csv`.
   - Inserción ordenada en nodos hoja.
   - Algoritmo de **división (*split*)** en caso de sobreflujo (overflow), propagando la clave promotora hacia el nodo padre de forma ascendente y creando una nueva raíz si es necesario.

### **P2 (6 puntos): Búsquedas Puntuales y por Rango**
1. **Búsqueda Puntual (`search(key)`):**
   - Descender desde la raíz hasta la hoja adecuada mediante búsqueda binaria o lineal dentro de cada nodo interno.
   - Retornar el registro completo correspondiente al `Employee_ID` (o indicar si no existe).
2. **Búsqueda por Rango (`rangeSearch(init_key, end_key)`):**
   - Localizar el nodo hoja donde reside `init_key`.
   - Recorrer secuencialmente las hojas adyacentes usando los punteros de enlace (`next_leaf`) sin volver a consultar los niveles superiores del árbol.
   - Retornar todos los registros cuyos IDs se encuentren en el intervalo `[init_key, end_key]`.
3. **Eliminación (`remove(key)`):**
   - Eliminación por `Employee_ID` (marcado lógico en la hoja o rebalanceo/redistribución básica).

### **P3 (7 puntos): Evaluación Experimental y Análisis de Desempeño**
1. **Métricas a registrar:**
   - **Tiempo de ejecución (ms)** para inserciones masivas, búsquedas individuales y búsquedas por rango.
   - **Accesos a Disco (Disk I/O):** Contar el número de lecturas (`reads`) y escrituras (`writes`) de bloques realizadas por cada operación.
2. **Experimentos y Gráficos:**
   - Variar el tamaño del dataset ($N = 10^3, 10^4, 10^5, \dots$) y graficar el costo I/O y tiempo vs $N$.
   - Evaluar el impacto del orden del árbol $M$ (probar con diferentes capacidades por nodo).
   - Comparar el rendimiento de la búsqueda por rango del Árbol B+ frente a un escaneo secuencial (o frente al AVL del Laboratorio 03).
3. **Discusión:**
   - Justificar por qué el Árbol B+ minimiza los accesos a disco respecto a árboles binarios (AVL/BST) en arquitecturas de memoria secundaria.

---

## **3. Entregable**
- **Código fuente en Python** debidamente comentado y modularizado.
- **Informe técnico (PDF)** que contenga:
  - Diagrama de la estructura binaria de los nodos en disco.
  - Tablas y gráficos comparativos de tiempo y número de lecturas/escrituras (I/O).
  - Análisis crítico y conclusiones.


