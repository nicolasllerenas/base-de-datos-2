import csv
import os
import shutil
import sys
import time
import zlib

from external_sort import PageWriter, buffer_pages, temp_dir_for
from heap_file import PAGE_SIZE, HeapFile, IOStats

BUFFER_SIZE = 64 * 1024
SEED_PARTICION = 0x00000000
SEED_RESIDENTE = 0x9E3779B9
BUCKETS_INICIALES = 1021


def h_p(value, buckets):
    return zlib.crc32(value.encode("utf-8"), SEED_PARTICION) % buckets


def h_r(value, buckets):
    return zlib.crc32(value.encode("utf-8"), SEED_RESIDENTE) % buckets


class CountingHashTable:
    def __init__(self, buckets=BUCKETS_INICIALES):
        self.buckets = [[] for _ in range(buckets)]
        self.entries = 0

    def add(self, key):
        bucket = self.buckets[h_r(key, len(self.buckets))]
        for entry in bucket:
            if entry[0] == key:
                entry[1] += 1
                return
        bucket.append([key, 1])
        self.entries += 1
        if self.entries > 2 * len(self.buckets):
            self.grow()

    def grow(self):
        anteriores = self.buckets
        self.buckets = [[] for _ in range(2 * len(anteriores) + 1)]
        for bucket in anteriores:
            for entry in bucket:
                self.buckets[h_r(entry[0], len(self.buckets))].append(entry)

    def items(self):
        for bucket in self.buckets:
            for key, count in bucket:
                yield key, count


def partition_data(heap_path, page_size, buffer_size, group_key, temp_dir=None, stats=None):
    source = HeapFile(heap_path, page_size)
    key = source.field_index(group_key)
    particiones = buffer_pages(buffer_size, page_size) - 1
    directory = temp_dir or temp_dir_for(heap_path, "particiones")
    paths = [os.path.join(directory, f"particion_{indice:05d}.bin") for indice in range(particiones)]
    salidas = [HeapFile.like(source, path) for path in paths]
    writers = [PageWriter(salida) for salida in salidas]
    for page_id in range(source.page_count):
        for record in source.read_page(page_id):
            writers[h_p(record[key], particiones)].append(record)
    for writer in writers:
        writer.flush()
    if stats is not None:
        stats.merge(source.stats)
        for salida in salidas:
            stats.merge(salida.stats)
    for salida in salidas:
        salida.close()
    source.close()
    return paths


def aggregate_partitions(partition_paths, page_size, buffer_size, group_key, stats=None, tablas=None):
    resultado = {}
    for path in partition_paths:
        particion = HeapFile(path, page_size)
        key = particion.field_index(group_key)
        tabla = CountingHashTable()
        for page_id in range(particion.page_count):
            for record in particion.read_page(page_id):
                tabla.add(record[key])
        if tablas is not None:
            tablas.append(tabla.entries)
        for valor, conteo in tabla.items():
            resultado[valor] = conteo
        if stats is not None:
            stats.merge(particion.stats)
        particion.close()
    return resultado


def external_hash_group_by(heap_path, page_size, buffer_size, group_key):
    stats = IOStats()
    pages_in_ram = buffer_pages(buffer_size, page_size)

    inicio = time.perf_counter()
    partition_paths = partition_data(heap_path, page_size, buffer_size, group_key, stats=stats)
    fase1 = time.perf_counter() - inicio

    tablas = []
    inicio = time.perf_counter()
    resultado = aggregate_partitions(partition_paths, page_size, buffer_size, group_key,
                                     stats, tablas)
    fase2 = time.perf_counter() - inicio

    paginas_particion = [HeapFile(path, page_size) for path in partition_paths]
    reparto = [heap.page_count for heap in paginas_particion]
    for heap in paginas_particion:
        heap.close()
    shutil.rmtree(os.path.join(os.path.dirname(os.path.abspath(heap_path)), "particiones"),
                  ignore_errors=True)
    return {
        "result": resultado,
        "buffer_size": buffer_size,
        "buffer_pages": pages_in_ram,
        "partitions_created": len(partition_paths),
        "groups": len(resultado),
        "max_groups_in_partition": max(tablas),
        "partition_pages_min": min(reparto),
        "partition_pages_max": max(reparto),
        "pages_read": stats.pages_read,
        "pages_written": stats.pages_written,
        "time_phase1_sec": fase1,
        "time_phase2_sec": fase2,
        "time_total_sec": fase1 + fase2,
    }


def load_reference(csv_path):
    with open(csv_path, newline="") as source:
        reader = csv.reader(source)
        next(reader)
        return {fila[0]: int(fila[1]) for fila in reader}


def main():
    heap_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join("data", "department_employee.bin")
    group_key = sys.argv[2] if len(sys.argv) > 2 else "from_date"
    buffer_size = int(sys.argv[3]) if len(sys.argv) > 3 else BUFFER_SIZE
    referencia_path = os.path.join("data", "group_by_referencia.csv")

    metricas = external_hash_group_by(heap_path, PAGE_SIZE, buffer_size, group_key)
    resultado = metricas.pop("result")

    print(f"External hashing GROUP BY {group_key} sobre {heap_path}")
    for clave, valor in metricas.items():
        print(f"  {clave:24s}: {valor:.4f}" if isinstance(valor, float) else f"  {clave:24s}: {valor}")
    print(f"  suma de conteos         : {sum(resultado.values())}")

    muestra = sorted(resultado.items())[:5]
    for valor, conteo in muestra:
        print(f"  {valor} -> {conteo}")

    if os.path.exists(referencia_path):
        referencia = load_reference(referencia_path)
        assert resultado == referencia, "el resultado no coincide con PostgreSQL"
        print(f"  verificacion            : identico a PostgreSQL ({len(referencia)} grupos)")
    else:
        print(f"  verificacion            : falta {referencia_path}")


if __name__ == "__main__":
    main()
