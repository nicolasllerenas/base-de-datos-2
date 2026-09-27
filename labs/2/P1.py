import os
import random
import struct
from dataclasses import dataclass

PAGE_SIZE = 4096
NULL = -1
ACTIVE = -2

FILE_HEADER_FORMAT = "<iiif"
FILE_HEADER_SIZE = struct.calcsize(FILE_HEADER_FORMAT)
PAGE_HEADER_FORMAT = "<iiiii"
PAGE_HEADER_SIZE = struct.calcsize(PAGE_HEADER_FORMAT)
RECORD_FORMAT = "<5s11s20s15sidi"
RECORD_SIZE = struct.calcsize(RECORD_FORMAT)
PAGE_CAPACITY = (PAGE_SIZE - PAGE_HEADER_SIZE) // RECORD_SIZE


class RecordNotFound(Exception):
    pass


@dataclass
class Alumno:
    codigo: str = ""
    nombre: str = ""
    apellidos: str = ""
    carrera: str = ""
    ciclo: int = 0
    mensualidad: float = 0.0


@dataclass
class FileHeader:
    page_count: int = 0
    active_count: int = 0
    free_page_head: int = NULL
    fill_factor: float = 1.0


@dataclass
class PageHeader:
    n_records: int = 0
    n_active: int = 0
    first_free: int = NULL
    next_free_page: int = NULL
    in_free_list: int = 0


def _decode(raw):
    return raw.split(b"\x00", 1)[0].decode("utf-8", "ignore")


def _encode(text, size):
    return text.encode("utf-8")[:size]


def pack_record(alumno, link):
    return struct.pack(
        RECORD_FORMAT,
        _encode(alumno.codigo, 5),
        _encode(alumno.nombre, 11),
        _encode(alumno.apellidos, 20),
        _encode(alumno.carrera, 15),
        alumno.ciclo,
        alumno.mensualidad,
        link,
    )


def unpack_record(raw):
    codigo, nombre, apellidos, carrera, ciclo, mensualidad, link = struct.unpack(RECORD_FORMAT, raw)
    alumno = Alumno(
        _decode(codigo),
        _decode(nombre),
        _decode(apellidos),
        _decode(carrera),
        ciclo,
        mensualidad,
    )
    return alumno, link


class HeapFile:
    def __init__(self, filename, fill_factor=1.0):
        self.filename = filename
        if not os.path.exists(filename) or os.path.getsize(filename) < FILE_HEADER_SIZE:
            with open(filename, "wb") as stream:
                stream.write(struct.pack(FILE_HEADER_FORMAT, 0, 0, NULL, fill_factor))
        self.file = open(filename, "r+b")
        self.fill_factor = self._file_header().fill_factor
        self.page_limit = max(1, int(PAGE_CAPACITY * self.fill_factor))

    def close(self):
        self.file.close()

    def _file_header(self):
        self.file.seek(0)
        return FileHeader(*struct.unpack(FILE_HEADER_FORMAT, self.file.read(FILE_HEADER_SIZE)))

    def _write_file_header(self, header):
        self.file.seek(0)
        self.file.write(struct.pack(
            FILE_HEADER_FORMAT,
            header.page_count,
            header.active_count,
            header.free_page_head,
            header.fill_factor,
        ))
        self.file.flush()

    def _page_offset(self, page_id):
        return FILE_HEADER_SIZE + page_id * PAGE_SIZE

    def _record_offset(self, page_id, slot):
        return self._page_offset(page_id) + PAGE_HEADER_SIZE + slot * RECORD_SIZE

    def _page_header(self, page_id):
        self.file.seek(self._page_offset(page_id))
        return PageHeader(*struct.unpack(PAGE_HEADER_FORMAT, self.file.read(PAGE_HEADER_SIZE)))

    def _write_page_header(self, page_id, header):
        self.file.seek(self._page_offset(page_id))
        self.file.write(struct.pack(
            PAGE_HEADER_FORMAT,
            header.n_records,
            header.n_active,
            header.first_free,
            header.next_free_page,
            header.in_free_list,
        ))
        self.file.flush()

    def _new_page(self):
        header = self._file_header()
        page_id = header.page_count
        self.file.seek(self._page_offset(page_id))
        self.file.write(struct.pack(PAGE_HEADER_FORMAT, 0, 0, NULL, NULL, 0))
        self.file.write(bytes(PAGE_SIZE - PAGE_HEADER_SIZE))
        header.page_count += 1
        self._write_file_header(header)
        return page_id

    def _read_slot(self, page_id, slot):
        self.file.seek(self._record_offset(page_id, slot))
        return unpack_record(self.file.read(RECORD_SIZE))

    def _write_slot(self, page_id, slot, alumno, link):
        self.file.seek(self._record_offset(page_id, slot))
        self.file.write(pack_record(alumno, link))
        self.file.flush()

    def _append_slot(self, alumno):
        header = self._file_header()
        page_id = header.page_count - 1
        if header.page_count == 0:
            page_id = self._new_page()
        page = self._page_header(page_id)
        if page.n_records >= self.page_limit:
            page_id = self._new_page()
            page = PageHeader()
        slot = page.n_records
        self._write_slot(page_id, slot, alumno, ACTIVE)
        page.n_records += 1
        page.n_active += 1
        self._write_page_header(page_id, page)
        header = self._file_header()
        header.active_count += 1
        self._write_file_header(header)
        return page_id * PAGE_CAPACITY + slot

    def size(self):
        return self._file_header().active_count

    def page_count(self):
        return self._file_header().page_count

    def pages(self):
        return [self._page_header(page_id) for page_id in range(self.page_count())]

    def scan(self):
        for page_id in range(self.page_count()):
            page = self._page_header(page_id)
            for slot in range(page.n_records):
                alumno, link = self._read_slot(page_id, slot)
                if link == ACTIVE:
                    yield page_id * PAGE_CAPACITY + slot, alumno

    def load(self):
        return [alumno for _, alumno in self.scan()]

    def positions(self):
        return [pos for pos, _ in self.scan()]

    def readRecord(self, pos):
        if pos < 0:
            raise RecordNotFound(f"posicion invalida: {pos}")
        page_id, slot = divmod(pos, PAGE_CAPACITY)
        if page_id >= self.page_count():
            raise RecordNotFound(f"posicion fuera del archivo: {pos}")
        page = self._page_header(page_id)
        if slot >= page.n_records:
            raise RecordNotFound(f"posicion fuera de la pagina: {pos}")
        alumno, link = self._read_slot(page_id, slot)
        if link != ACTIVE:
            raise RecordNotFound(f"registro eliminado: {pos}")
        return alumno

    def add(self, record):
        raise NotImplementedError

    def remove(self, pos):
        raise NotImplementedError


class FixedRecordMoveLast(HeapFile):
    def add(self, record):
        return self._append_slot(record)

    def remove(self, pos):
        self.readRecord(pos)
        page_id, slot = divmod(pos, PAGE_CAPACITY)
        header = self._file_header()
        last_id = header.page_count - 1
        last_page = self._page_header(last_id)
        last_slot = last_page.n_records - 1
        moved_from = None
        if (page_id, slot) != (last_id, last_slot):
            alumno, _ = self._read_slot(last_id, last_slot)
            self._write_slot(page_id, slot, alumno, ACTIVE)
            moved_from = last_id * PAGE_CAPACITY + last_slot
        self._write_slot(last_id, last_slot, Alumno(), NULL)
        last_page.n_records -= 1
        last_page.n_active -= 1
        self._write_page_header(last_id, last_page)
        header.active_count -= 1
        if last_page.n_records == 0:
            header.page_count -= 1
            self.file.truncate(self._page_offset(header.page_count))
        self._write_file_header(header)
        return moved_from


class FixedRecordFreeList(HeapFile):
    def add(self, record):
        header = self._file_header()
        if header.free_page_head == NULL:
            return self._append_slot(record)
        page_id = header.free_page_head
        page = self._page_header(page_id)
        slot = page.first_free
        _, next_free = self._read_slot(page_id, slot)
        self._write_slot(page_id, slot, record, ACTIVE)
        page.first_free = next_free
        page.n_active += 1
        if page.first_free == NULL:
            header.free_page_head = page.next_free_page
            page.next_free_page = NULL
            page.in_free_list = 0
        self._write_page_header(page_id, page)
        header.active_count += 1
        self._write_file_header(header)
        return page_id * PAGE_CAPACITY + slot

    def remove(self, pos):
        alumno = self.readRecord(pos)
        page_id, slot = divmod(pos, PAGE_CAPACITY)
        header = self._file_header()
        page = self._page_header(page_id)
        self._write_slot(page_id, slot, Alumno(), page.first_free)
        page.first_free = slot
        page.n_active -= 1
        if page.in_free_list == 0:
            page.next_free_page = header.free_page_head
            page.in_free_list = 1
            header.free_page_head = page_id
        self._write_page_header(page_id, page)
        header.active_count -= 1
        self._write_file_header(header)
        return alumno


NOMBRES = ["Ana", "Luis", "Maria", "Carlos", "Jose", "Lucia", "Diego",
           "Valeria", "Fernando", "Rodrigo", "Camila", "Sebastian"]
APELLIDOS = ["Perez Diaz", "Gomez Rojas", "Torres Vega", "Ramirez Luna",
             "Castillo Soto", "Fernandez Paz", "Quispe Mamani", "Silva Cordova"]
CARRERAS = ["Ciencia Comp.", "Ing. Software", "Ing. Mecanica", "Ing. Civil",
            "Bioingenieria", "Ing. Ambiental", "Adm. y Negocios"]


def generar_alumnos(n, seed=2026):
    rng = random.Random(seed)
    return [
        Alumno(
            f"A{i:04d}",
            rng.choice(NOMBRES),
            rng.choice(APELLIDOS),
            rng.choice(CARRERAS),
            rng.randint(1, 10),
            round(rng.uniform(950.0, 4200.0), 2),
        )
        for i in range(n)
    ]


def titulo(texto):
    print()
    print("=" * 70)
    print(texto)
    print("=" * 70)


def mostrar_paginas(heap, etiqueta):
    print(f"{etiqueta}: paginas={heap.page_count()} activos={heap.size()}")
    for page_id, page in enumerate(heap.pages()):
        print(f"  pagina {page_id}: total={page.n_records:3d} activos={page.n_active:3d} "
              f"primer_libre={page.first_free:3d} sig_pagina_libre={page.next_free_page:3d}")


def nuevo_archivo(nombre):
    ruta = os.path.join(os.path.dirname(os.path.abspath(__file__)), nombre)
    if os.path.exists(ruta):
        os.remove(ruta)
    return ruta


def prueba_move_the_last(alumnos):
    titulo("P1.A - MOVE THE LAST")
    ruta = nuevo_archivo("alumnos_movelast.dat")
    heap = FixedRecordMoveLast(ruta)

    posiciones = [heap.add(a) for a in alumnos]
    assert heap.size() == len(alumnos)
    assert heap.load() == alumnos
    mostrar_paginas(heap, "luego de insertar")

    assert heap.readRecord(posiciones[0]) == alumnos[0]
    assert heap.readRecord(posiciones[137]) == alumnos[137]
    print(f"readRecord({posiciones[137]}) -> {heap.readRecord(posiciones[137])}")

    ultimo = posiciones[-1]
    movido = heap.remove(posiciones[10])
    assert movido == ultimo
    assert heap.readRecord(posiciones[10]) == alumnos[-1]
    print(f"remove({posiciones[10]}) movio el registro de la posicion {movido}")
    try:
        heap.readRecord(ultimo)
        raise AssertionError("la ultima posicion deberia quedar libre")
    except RecordNotFound as error:
        print(f"readRecord({ultimo}) -> {error}")

    assert heap.remove(heap.positions()[-1]) is None
    assert heap.size() == len(alumnos) - 2

    for _ in range(190):
        heap.remove(heap.positions()[0])
    mostrar_paginas(heap, "luego de 192 eliminaciones")
    assert heap.size() == len(alumnos) - 192
    assert len(heap.load()) == heap.size()
    assert heap.page_count() == 1
    tam_esperado = FILE_HEADER_SIZE + heap.page_count() * PAGE_SIZE
    assert os.path.getsize(ruta) == tam_esperado
    print(f"archivo truncado a {tam_esperado} bytes")

    vigentes = heap.load()
    heap.close()
    relectura = FixedRecordMoveLast(ruta)
    assert relectura.load() == vigentes
    print(f"relectura del archivo -> {len(relectura.load())} registros validos")
    relectura.close()


def prueba_free_list(alumnos):
    titulo("P1.B - FREE LIST")
    ruta = nuevo_archivo("alumnos_freelist.dat")
    heap = FixedRecordFreeList(ruta)

    posiciones = [heap.add(a) for a in alumnos]
    assert heap.load() == alumnos
    mostrar_paginas(heap, "luego de insertar")

    eliminadas = [posiciones[3], posiciones[7], posiciones[11]]
    for pos in eliminadas:
        heap.remove(pos)
    mostrar_paginas(heap, "luego de eliminar 3 registros de la pagina 0")
    assert heap.size() == len(alumnos) - 3
    assert len(heap.load()) == heap.size()

    for pos in eliminadas:
        try:
            heap.readRecord(pos)
            raise AssertionError("el registro deberia estar eliminado")
        except RecordNotFound as error:
            print(f"readRecord({pos}) -> {error}")

    nuevos = generar_alumnos(3, seed=7)
    reusadas = [heap.add(a) for a in nuevos]
    assert reusadas == list(reversed(eliminadas))
    print(f"free list reutiliza en orden LIFO: {reusadas}")
    for pos, alumno in zip(reusadas, nuevos):
        assert heap.readRecord(pos) == alumno
    assert heap.size() == len(alumnos)
    assert heap.page_count() == (len(alumnos) + PAGE_CAPACITY - 1) // PAGE_CAPACITY

    borradas = [posiciones[i] for i in range(60, 130)]
    for pos in borradas:
        heap.remove(pos)
    mostrar_paginas(heap, "luego de eliminar 70 registros de varias paginas")
    assert heap.size() == len(alumnos) - 70

    try:
        heap.remove(borradas[0])
        raise AssertionError("no se puede eliminar dos veces")
    except RecordNotFound as error:
        print(f"remove({borradas[0]}) -> {error}")
    try:
        heap.readRecord(99999)
        raise AssertionError("posicion inexistente")
    except RecordNotFound as error:
        print(f"readRecord(99999) -> {error}")

    reinsertados = generar_alumnos(70, seed=99)
    destinos = [heap.add(a) for a in reinsertados]
    assert sorted(destinos) == sorted(borradas)
    assert heap.page_count() == (len(alumnos) + PAGE_CAPACITY - 1) // PAGE_CAPACITY
    print(f"las 70 inserciones reusaron los huecos sin crecer el archivo "
          f"({os.path.getsize(ruta)} bytes)")

    vigentes = heap.load()
    heap.close()
    relectura = FixedRecordFreeList(ruta)
    assert relectura.load() == vigentes
    print(f"relectura del archivo -> {len(relectura.load())} registros validos")
    relectura.close()


def prueba_fill_factor(alumnos):
    titulo("P3 - FILL FACTOR 80% (registros de longitud fija)")
    ruta = nuevo_archivo("alumnos_fillfactor.dat")
    heap = FixedRecordFreeList(ruta, fill_factor=0.8)
    print(f"capacidad teorica={PAGE_CAPACITY} registros/pagina, "
          f"limite con fill factor={heap.page_limit}")
    for alumno in alumnos:
        heap.add(alumno)
    mostrar_paginas(heap, "luego de insertar")
    assert all(page.n_records <= heap.page_limit for page in heap.pages())
    assert heap.load() == alumnos
    esperado = (len(alumnos) + heap.page_limit - 1) // heap.page_limit
    assert heap.page_count() == esperado
    heap.close()


def main():
    titulo("LABORATORIO 02 - P1: HEAP FILE DE LONGITUD FIJA")
    print(f"tamano de registro   : {RECORD_SIZE} bytes")
    print(f"tamano de pagina     : {PAGE_SIZE} bytes")
    print(f"header de archivo    : {FILE_HEADER_SIZE} bytes")
    print(f"header de pagina     : {PAGE_HEADER_SIZE} bytes")
    print(f"registros por pagina : {PAGE_CAPACITY}")

    alumnos = generar_alumnos(250)
    print(f"registros generados  : {len(alumnos)}")
    print(f"ejemplo              : {alumnos[0]}")

    prueba_move_the_last(alumnos)
    prueba_free_list(alumnos)
    prueba_fill_factor(alumnos)

    titulo("Todas las pruebas funcionales pasaron")


if __name__ == "__main__":
    main()
