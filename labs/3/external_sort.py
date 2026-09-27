import heapq
import math
import os
import shutil
import sys
import time

from heap_file import PAGE_SIZE, HeapFile, IOStats

BUFFER_SIZE = 64 * 1024


class PageReader:
    def __init__(self, heap):
        self.heap = heap
        self.page_id = 0
        self.buffer = []
        self.cursor = 0

    def next(self):
        if self.cursor == len(self.buffer):
            if self.page_id == self.heap.page_count:
                return None
            self.buffer = self.heap.read_page(self.page_id)
            self.page_id += 1
            self.cursor = 0
            if not self.buffer:
                return None
        record = self.buffer[self.cursor]
        self.cursor += 1
        return record


class PageWriter:
    def __init__(self, heap):
        self.heap = heap
        self.buffer = []

    def append(self, record):
        self.buffer.append(record)
        if len(self.buffer) == self.heap.capacity:
            self.flush()

    def flush(self):
        if self.buffer:
            self.heap.append_page(self.buffer)
            self.buffer = []


def buffer_pages(buffer_size, page_size):
    pages = buffer_size // page_size
    if pages < 3:
        raise ValueError("el buffer debe admitir al menos 3 paginas")
    return pages


def temp_dir_for(path, nombre):
    directory = os.path.join(os.path.dirname(os.path.abspath(path)), nombre)
    shutil.rmtree(directory, ignore_errors=True)
    os.makedirs(directory)
    return directory


def generate_runs(heap_path, page_size, buffer_size, sort_key, temp_dir=None, stats=None):
    source = HeapFile(heap_path, page_size)
    key = source.field_index(sort_key)
    pages_in_ram = buffer_pages(buffer_size, page_size)
    directory = temp_dir or temp_dir_for(heap_path, "runs")
    run_paths = []
    page_id = 0
    while page_id < source.page_count:
        buffer = []
        for offset in range(min(pages_in_ram, source.page_count - page_id)):
            buffer.extend(source.read_page(page_id + offset))
        page_id += pages_in_ram
        buffer.sort(key=lambda record: record[key])
        run_path = os.path.join(directory, f"run_{len(run_paths):05d}.bin")
        run = HeapFile.like(source, run_path)
        writer = PageWriter(run)
        for record in buffer:
            writer.append(record)
        writer.flush()
        if stats is not None:
            stats.merge(run.stats)
        run.close()
        run_paths.append(run_path)
    if stats is not None:
        stats.merge(source.stats)
    source.close()
    return run_paths


def merge_group(run_paths, output_path, page_size, sort_key, stats=None):
    runs = [HeapFile(path, page_size) for path in run_paths]
    key = runs[0].field_index(sort_key)
    output = HeapFile.like(runs[0], output_path)
    writer = PageWriter(output)
    readers = [PageReader(run) for run in runs]
    frontier = []
    for index, reader in enumerate(readers):
        record = reader.next()
        if record is not None:
            frontier.append((record[key], index, record))
    heapq.heapify(frontier)
    while frontier:
        _, index, record = heapq.heappop(frontier)
        writer.append(record)
        siguiente = readers[index].next()
        if siguiente is not None:
            heapq.heappush(frontier, (siguiente[key], index, siguiente))
    writer.flush()
    if stats is not None:
        stats.merge(output.stats)
        for run in runs:
            stats.merge(run.stats)
    output.close()
    for run in runs:
        run.close()


def multiway_merge(run_paths, output_path, page_size, buffer_size, sort_key, stats=None):
    fan_in = buffer_pages(buffer_size, page_size) - 1
    directory = os.path.dirname(os.path.abspath(run_paths[0]))
    nivel = 0
    actuales = list(run_paths)
    while len(actuales) > fan_in:
        siguientes = []
        for indice, inicio in enumerate(range(0, len(actuales), fan_in)):
            grupo = actuales[inicio:inicio + fan_in]
            destino = os.path.join(directory, f"merge_{nivel}_{indice:05d}.bin")
            merge_group(grupo, destino, page_size, sort_key, stats)
            siguientes.append(destino)
        for path in actuales:
            os.remove(path)
        actuales = siguientes
        nivel += 1
    merge_group(actuales, output_path, page_size, sort_key, stats)
    for path in actuales:
        os.remove(path)
    return nivel + 1


def external_sort(heap_path, output_path, page_size, buffer_size, sort_key):
    stats = IOStats()
    pages_in_ram = buffer_pages(buffer_size, page_size)
    total_pages = HeapFile(heap_path, page_size).page_count

    inicio = time.perf_counter()
    run_paths = generate_runs(heap_path, page_size, buffer_size, sort_key, stats=stats)
    fase1 = time.perf_counter() - inicio

    inicio = time.perf_counter()
    merge_passes = multiway_merge(run_paths, output_path, page_size, buffer_size, sort_key, stats)
    fase2 = time.perf_counter() - inicio

    shutil.rmtree(os.path.join(os.path.dirname(os.path.abspath(heap_path)), "runs"),
                  ignore_errors=True)
    return {
        "buffer_size": buffer_size,
        "buffer_pages": pages_in_ram,
        "fan_in": pages_in_ram - 1,
        "input_pages": total_pages,
        "runs_generated": len(run_paths),
        "merge_passes": merge_passes,
        "pages_read": stats.pages_read,
        "pages_written": stats.pages_written,
        "time_phase1_sec": fase1,
        "time_phase2_sec": fase2,
        "time_total_sec": fase1 + fase2,
    }


def verify_sorted(output_path, page_size, sort_key, expected_records):
    heap = HeapFile(output_path, page_size)
    key = heap.field_index(sort_key)
    anterior = None
    total = 0
    for record in heap.records():
        actual = record[key]
        if anterior is not None and actual < anterior:
            heap.close()
            raise AssertionError(f"orden roto en el registro {total}")
        anterior = actual
        total += 1
    heap.close()
    if total != expected_records:
        raise AssertionError(f"se esperaban {expected_records} registros y hay {total}")
    return total


def main():
    heap_path = sys.argv[1] if len(sys.argv) > 1 else os.path.join("data", "employee.bin")
    sort_key = sys.argv[2] if len(sys.argv) > 2 else "hire_date"
    buffer_size = int(sys.argv[3]) if len(sys.argv) > 3 else BUFFER_SIZE
    output_path = os.path.join("data", "employee_sorted.bin")

    origen = HeapFile(heap_path, PAGE_SIZE)
    total_registros = origen.record_count
    total_paginas = origen.page_count
    origen.close()

    esperados = math.ceil(total_paginas / (buffer_size // PAGE_SIZE))
    metricas = external_sort(heap_path, output_path, PAGE_SIZE, buffer_size, sort_key)
    assert metricas["runs_generated"] == esperados
    verify_sorted(output_path, PAGE_SIZE, sort_key, total_registros)

    print(f"TPMMS sobre {heap_path} ordenando por {sort_key}")
    for clave, valor in metricas.items():
        print(f"  {clave:18s}: {valor:.4f}" if isinstance(valor, float) else f"  {clave:18s}: {valor}")
    print(f"  runs esperados    : ceil({total_paginas}/{metricas['buffer_pages']}) = {esperados}")
    print(f"  salida ordenada   : {output_path} ({total_registros} registros verificados)")
    muestra = HeapFile(output_path, PAGE_SIZE)
    print(f"  primer registro   : {muestra.read_page(0)[0]}")
    print(f"  ultimo registro   : {muestra.read_page(muestra.page_count - 1)[-1]}")
    muestra.close()


if __name__ == "__main__":
    main()
