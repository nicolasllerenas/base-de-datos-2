import csv
import os
import re
import struct
from dataclasses import dataclass

PAGE_SIZE = 4096
MAGIC = b"HEAP01"
FILE_HEADER_FORMAT = "<6sIIIQ"
FILE_HEADER_SIZE = struct.calcsize(FILE_HEADER_FORMAT)
PAGE_HEADER_FORMAT = "<I"
PAGE_HEADER_SIZE = struct.calcsize(PAGE_HEADER_FORMAT)
TOKEN = re.compile(r"(\d*)([xcbB?hHiIlLqQnNefdspP])")

SCHEMAS = {
    "employee": {
        "record_format": "<q10s14s16s1s10s",
        "fields": ["id", "birth_date", "first_name", "last_name", "gender", "hire_date"],
    },
    "department_employee": {
        "record_format": "<q4s10s10s",
        "fields": ["employee_id", "department_id", "from_date", "to_date"],
    },
}


@dataclass
class IOStats:
    pages_read: int = 0
    pages_written: int = 0

    def merge(self, other):
        self.pages_read += other.pages_read
        self.pages_written += other.pages_written


def field_kinds(record_format):
    kinds = []
    for count, code in TOKEN.findall(record_format):
        kinds.extend("s" if code == "s" else code * int(count or 1))
    return kinds


def encode_field(value, kind):
    if kind == "s":
        return value.encode("utf-8") if isinstance(value, str) else value
    if kind in "efd":
        return float(value)
    return int(value)


def decode_field(value, kind):
    if kind == "s":
        return value.split(b"\x00", 1)[0].decode("utf-8", "ignore")
    return value


def pack_text(buffer, offset, text):
    raw = text.encode("utf-8")
    struct.pack_into("<H", buffer, offset, len(raw))
    offset += 2
    buffer[offset:offset + len(raw)] = raw
    return offset + len(raw)


def unpack_text(buffer, offset):
    size = struct.unpack_from("<H", buffer, offset)[0]
    offset += 2
    return buffer[offset:offset + size].decode("utf-8"), offset + size


class HeapFile:
    def __init__(self, path, page_size=PAGE_SIZE):
        self.path = path
        self.stats = IOStats()
        self.stream = open(path, "r+b")
        head = self.stream.read(page_size)
        magic, stored_page_size, self.record_size, self.page_count, self.record_count = \
            struct.unpack_from(FILE_HEADER_FORMAT, head)
        if magic != MAGIC:
            raise ValueError(f"{path} no es un heap file valido")
        if stored_page_size != page_size:
            raise ValueError(f"{path} usa paginas de {stored_page_size} bytes")
        self.page_size = page_size
        self.record_format, offset = unpack_text(head, FILE_HEADER_SIZE)
        names, _ = unpack_text(head, offset)
        self.fields = names.split(",")
        self.record = struct.Struct(self.record_format)
        self.kinds = field_kinds(self.record_format)
        self.capacity = (page_size - PAGE_HEADER_SIZE) // self.record_size

    @classmethod
    def create(cls, path, record_format, fields, page_size=PAGE_SIZE):
        blob = bytearray(page_size)
        struct.pack_into(FILE_HEADER_FORMAT, blob, 0, MAGIC, page_size,
                         struct.calcsize(record_format), 0, 0)
        offset = pack_text(blob, FILE_HEADER_SIZE, record_format)
        pack_text(blob, offset, ",".join(fields))
        with open(path, "wb") as stream:
            stream.write(blob)
        return cls(path, page_size)

    @classmethod
    def like(cls, source, path):
        return cls.create(path, source.record_format, source.fields, source.page_size)

    def close(self):
        self.flush_header()
        self.stream.close()

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def field_index(self, name):
        return self.fields.index(name)

    def page_offset(self, page_id):
        return (page_id + 1) * self.page_size

    def flush_header(self):
        self.stream.seek(0)
        self.stream.write(struct.pack(FILE_HEADER_FORMAT, MAGIC, self.page_size,
                                      self.record_size, self.page_count, self.record_count))

    def read_page(self, page_id):
        if page_id < 0 or page_id >= self.page_count:
            raise IndexError(f"pagina {page_id} fuera de {self.path}")
        self.stream.seek(self.page_offset(page_id))
        blob = self.stream.read(self.page_size)
        self.stats.pages_read += 1
        count = struct.unpack_from(PAGE_HEADER_FORMAT, blob)[0]
        end = PAGE_HEADER_SIZE + count * self.record_size
        kinds = self.kinds
        return [tuple(decode_field(value, kind) for value, kind in zip(raw, kinds))
                for raw in self.record.iter_unpack(blob[PAGE_HEADER_SIZE:end])]

    def write_page(self, page_id, records):
        if len(records) > self.capacity:
            raise ValueError(f"{len(records)} registros exceden la capacidad de la pagina")
        blob = bytearray(self.page_size)
        struct.pack_into(PAGE_HEADER_FORMAT, blob, 0, len(records))
        offset = PAGE_HEADER_SIZE
        kinds = self.kinds
        for record in records:
            self.record.pack_into(blob, offset,
                                  *[encode_field(value, kind) for value, kind in zip(record, kinds)])
            offset += self.record_size
        self.stream.seek(self.page_offset(page_id))
        self.stream.write(blob)
        self.stats.pages_written += 1
        if page_id >= self.page_count:
            self.record_count += len(records)
            self.page_count = page_id + 1
        self.flush_header()

    def append_page(self, records):
        self.write_page(self.page_count, records)
        return self.page_count - 1

    def pages(self):
        for page_id in range(self.page_count):
            yield self.read_page(page_id)

    def records(self):
        for page in self.pages():
            yield from page


def export_to_heap(csv_path, heap_path, record_format, page_size=PAGE_SIZE):
    with open(csv_path, newline="") as source:
        reader = csv.reader(source)
        fields = next(reader)
        heap = HeapFile.create(heap_path, record_format, fields, page_size)
        buffer = []
        for row in reader:
            buffer.append(tuple(row))
            if len(buffer) == heap.capacity:
                heap.append_page(buffer)
                buffer = []
        if buffer:
            heap.append_page(buffer)
    stats = heap.stats
    info = {
        "heap_path": heap_path,
        "page_size": page_size,
        "record_format": record_format,
        "record_size": heap.record_size,
        "fields": heap.fields,
        "records_per_page": heap.capacity,
        "records": heap.record_count,
        "pages": heap.page_count,
        "bytes": os.path.getsize(heap_path),
        "pages_written": stats.pages_written,
    }
    heap.close()
    return info


def read_page(heap_path, page_id, page_size=PAGE_SIZE):
    heap = HeapFile(heap_path, page_size)
    try:
        return heap.read_page(page_id)
    finally:
        heap.close()


def write_page(heap_path, page_id, records, record_format, page_size=PAGE_SIZE):
    heap = HeapFile(heap_path, page_size)
    try:
        if record_format != heap.record_format:
            raise ValueError(f"{heap_path} usa el formato {heap.record_format}")
        heap.write_page(page_id, records)
    finally:
        heap.close()


def count_pages(heap_path, page_size=PAGE_SIZE):
    heap = HeapFile(heap_path, page_size)
    try:
        return heap.page_count
    finally:
        heap.close()


def heap_info(heap_path, page_size=PAGE_SIZE):
    heap = HeapFile(heap_path, page_size)
    try:
        return {
            "heap_path": heap_path,
            "page_size": heap.page_size,
            "record_format": heap.record_format,
            "record_size": heap.record_size,
            "fields": heap.fields,
            "records_per_page": heap.capacity,
            "records": heap.record_count,
            "pages": heap.page_count,
            "bytes": os.path.getsize(heap_path),
        }
    finally:
        heap.close()


def main():
    for name, schema in SCHEMAS.items():
        heap_path = os.path.join("data", f"{name}.bin")
        if not os.path.exists(heap_path):
            print(f"{heap_path} no existe: ejecutar export_data.py")
            continue
        info = heap_info(heap_path)
        print(f"{name}")
        for key, value in info.items():
            print(f"  {key:16s}: {value}")
        primera = read_page(heap_path, 0)
        ultima = read_page(heap_path, count_pages(heap_path) - 1)
        print(f"  primer registro : {primera[0]}")
        print(f"  ultimo registro : {ultima[-1]}")
        print(f"  paginas         : {count_pages(heap_path)}")


if __name__ == "__main__":
    main()
