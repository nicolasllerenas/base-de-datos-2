import csv
import json
import os

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

from external_hashing import external_hash_group_by, load_reference
from external_sort import external_sort, verify_sorted
from heap_file import PAGE_SIZE, HeapFile

BUFFER_SIZES = [64 * 1024, 128 * 1024, 256 * 1024, 512 * 1024, 1024 * 1024]
EMPLOYEE = os.path.join("data", "employee.bin")
DEPARTMENT_EMPLOYEE = os.path.join("data", "department_employee.bin")
SORTED_OUTPUT = os.path.join("data", "employee_sorted.bin")
REFERENCIA = os.path.join("data", "group_by_referencia.csv")
RESULTADOS = "resultados"

COLOR_SORT = "#2f6f9f"
COLOR_HASH = "#c1622c"


def etiqueta(buffer_size):
    return f"{buffer_size // 1024} KB"


def medir_sort(buffer_size, total_registros):
    metricas = external_sort(EMPLOYEE, SORTED_OUTPUT, PAGE_SIZE, buffer_size, "hire_date")
    verify_sorted(SORTED_OUTPUT, PAGE_SIZE, "hire_date", total_registros)
    metricas["io_total"] = metricas["pages_read"] + metricas["pages_written"]
    return metricas


def medir_hash(buffer_size, referencia):
    metricas = external_hash_group_by(DEPARTMENT_EMPLOYEE, PAGE_SIZE, buffer_size, "from_date")
    resultado = metricas.pop("result")
    assert resultado == referencia, f"resultado incorrecto con buffer {buffer_size}"
    metricas["io_total"] = metricas["pages_read"] + metricas["pages_written"]
    return metricas


def grafica(x, series, titulo, ylabel, destino):
    figura, ejes = plt.subplots(figsize=(7.0, 4.0))
    for nombre, valores, color in series:
        ejes.plot(x, valores, marker="o", color=color, label=nombre)
        for xi, yi in zip(x, valores):
            ejes.annotate(f"{yi:.2f}", (xi, yi), textcoords="offset points",
                          xytext=(0, 7), ha="center", fontsize=8, color=color)
    ejes.set_title(titulo)
    ejes.set_xlabel("BUFFER_SIZE")
    ejes.set_ylabel(ylabel)
    ejes.set_xscale("log", base=2)
    ejes.set_xticks(x)
    ejes.set_xticklabels([etiqueta(valor) for valor in x])
    ejes.grid(True, linestyle=":", alpha=0.6)
    ejes.legend()
    ejes.spines["top"].set_visible(False)
    ejes.spines["right"].set_visible(False)
    figura.tight_layout()
    figura.savefig(destino, dpi=160)
    plt.close(figura)


def main():
    os.makedirs(RESULTADOS, exist_ok=True)
    employee = HeapFile(EMPLOYEE, PAGE_SIZE)
    total_registros = employee.record_count
    employee.close()
    referencia = load_reference(REFERENCIA)

    filas = []
    for buffer_size in BUFFER_SIZES:
        sort = medir_sort(buffer_size, total_registros)
        hashing = medir_hash(buffer_size, referencia)
        filas.append({"buffer_size": buffer_size, "sort": sort, "hash": hashing})
        print(f"{etiqueta(buffer_size):>7s}  B={sort['buffer_pages']:4d}  "
              f"runs={sort['runs_generated']:4d} passes={sort['merge_passes']} "
              f"sort={sort['time_total_sec']:6.2f}s io={sort['io_total']:6d}  |  "
              f"particiones={hashing['partitions_created']:4d} "
              f"hash={hashing['time_total_sec']:6.2f}s io={hashing['io_total']:6d}")

    with open(os.path.join(RESULTADOS, "metricas.json"), "w") as destino:
        json.dump(filas, destino, indent=2)

    with open(os.path.join(RESULTADOS, "metricas.csv"), "w", newline="") as destino:
        writer = csv.writer(destino)
        writer.writerow(["algoritmo", "buffer_size", "buffer_pages", "runs_o_particiones",
                         "merge_passes", "time_phase1_sec", "time_phase2_sec", "time_total_sec",
                         "pages_read", "pages_written", "io_total"])
        for fila in filas:
            sort, hashing = fila["sort"], fila["hash"]
            writer.writerow(["external_sort", fila["buffer_size"], sort["buffer_pages"],
                             sort["runs_generated"], sort["merge_passes"],
                             f"{sort['time_phase1_sec']:.4f}", f"{sort['time_phase2_sec']:.4f}",
                             f"{sort['time_total_sec']:.4f}", sort["pages_read"],
                             sort["pages_written"], sort["io_total"]])
            writer.writerow(["external_hashing", fila["buffer_size"], hashing["buffer_pages"],
                             hashing["partitions_created"], 1,
                             f"{hashing['time_phase1_sec']:.4f}", f"{hashing['time_phase2_sec']:.4f}",
                             f"{hashing['time_total_sec']:.4f}", hashing["pages_read"],
                             hashing["pages_written"], hashing["io_total"]])

    x = [fila["buffer_size"] for fila in filas]
    grafica(x,
            [("External sorting (employee)", [fila["sort"]["time_total_sec"] for fila in filas], COLOR_SORT),
             ("External hashing (department_employee)", [fila["hash"]["time_total_sec"] for fila in filas], COLOR_HASH)],
            "Tiempo total vs BUFFER_SIZE", "segundos",
            os.path.join(RESULTADOS, "tiempo_total.png"))

    grafica(x,
            [("Fase 1 (runs)", [fila["sort"]["time_phase1_sec"] for fila in filas], COLOR_SORT),
             ("Fase 2 (merge)", [fila["sort"]["time_phase2_sec"] for fila in filas], "#7aa8c9")],
            "External sorting: fases vs BUFFER_SIZE", "segundos",
            os.path.join(RESULTADOS, "sort_fases.png"))

    grafica(x,
            [("Fase 1 (particionamiento)", [fila["hash"]["time_phase1_sec"] for fila in filas], COLOR_HASH),
             ("Fase 2 (agregacion)", [fila["hash"]["time_phase2_sec"] for fila in filas], "#dda07a")],
            "External hashing: fases vs BUFFER_SIZE", "segundos",
            os.path.join(RESULTADOS, "hash_fases.png"))

    grafica(x,
            [("External sorting", [fila["sort"]["io_total"] for fila in filas], COLOR_SORT),
             ("External hashing", [fila["hash"]["io_total"] for fila in filas], COLOR_HASH)],
            "I/O total (paginas leidas + escritas) vs BUFFER_SIZE", "paginas",
            os.path.join(RESULTADOS, "io_total.png"))

    print(f"\nresultados en {RESULTADOS}/")


if __name__ == "__main__":
    main()
