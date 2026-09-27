#include <algorithm>
#include <array>
#include <cstdint>
#include <cstdio>
#include <cmath>
#include <cstring>
#include <fstream>
#include <iomanip>
#include <iostream>
#include <random>
#include <stdexcept>
#include <string>
#include <vector>

constexpr int PAGE_SIZE = 4096;
constexpr int32_t NONE = -1;

struct Matricula {
    std::string codigo;
    int32_t ciclo = 0;
    double mensualidad = 0.0;
    std::string observaciones;

    bool operator==(const Matricula& other) const {
        return codigo == other.codigo && ciclo == other.ciclo &&
               mensualidad == other.mensualidad && observaciones == other.observaciones;
    }
};

struct RID {
    int32_t page = NONE;
    int32_t slot = NONE;

    bool operator==(const RID& other) const {
        return page == other.page && slot == other.slot;
    }
    bool operator<(const RID& other) const {
        return page != other.page ? page < other.page : slot < other.slot;
    }
};

std::ostream& operator<<(std::ostream& out, const RID& rid) {
    return out << "(" << rid.page << "," << rid.slot << ")";
}

#pragma pack(push, 1)
struct FileHeader {
    int32_t pageCount = 0;
    int32_t recordCount = 0;
    int32_t freePageHead = NONE;
    float fillFactor = 1.0f;
};

struct PageHeader {
    int32_t slotCount = 0;
    int32_t freePtr = PAGE_SIZE;
    int32_t liveCount = 0;
    int32_t freeSlot = NONE;
    int32_t nextFreePage = NONE;
    int32_t inFreeList = 0;
};

struct Slot {
    int32_t offset = NONE;
    int32_t length = 0;
};
#pragma pack(pop)

template <typename T>
void writeAt(char* base, int offset, const T& value) {
    std::memcpy(base + offset, &value, sizeof(T));
}

template <typename T>
T readAt(const char* base, int offset) {
    T value;
    std::memcpy(&value, base + offset, sizeof(T));
    return value;
}

template <typename T>
void appendPod(std::vector<char>& buffer, const T& value) {
    const char* raw = reinterpret_cast<const char*>(&value);
    buffer.insert(buffer.end(), raw, raw + sizeof(T));
}

std::vector<char> serialize(const Matricula& record) {
    std::vector<char> buffer;
    uint16_t sizeCodigo = static_cast<uint16_t>(record.codigo.size());
    uint16_t sizeObs = static_cast<uint16_t>(record.observaciones.size());
    appendPod(buffer, sizeCodigo);
    buffer.insert(buffer.end(), record.codigo.begin(), record.codigo.end());
    appendPod(buffer, record.ciclo);
    appendPod(buffer, record.mensualidad);
    appendPod(buffer, sizeObs);
    buffer.insert(buffer.end(), record.observaciones.begin(), record.observaciones.end());
    return buffer;
}

Matricula deserialize(const std::vector<char>& buffer) {
    Matricula record;
    int cursor = 0;
    uint16_t sizeCodigo = readAt<uint16_t>(buffer.data(), cursor);
    cursor += static_cast<int>(sizeof(uint16_t));
    record.codigo.assign(buffer.data() + cursor, sizeCodigo);
    cursor += sizeCodigo;
    record.ciclo = readAt<int32_t>(buffer.data(), cursor);
    cursor += static_cast<int>(sizeof(int32_t));
    record.mensualidad = readAt<double>(buffer.data(), cursor);
    cursor += static_cast<int>(sizeof(double));
    uint16_t sizeObs = readAt<uint16_t>(buffer.data(), cursor);
    cursor += static_cast<int>(sizeof(uint16_t));
    record.observaciones.assign(buffer.data() + cursor, sizeObs);
    return record;
}

class SlottedPage {
public:
    static constexpr int DIRECTORY = static_cast<int>(sizeof(PageHeader));
    static constexpr int SLOT_SIZE = static_cast<int>(sizeof(Slot));

    SlottedPage() { clear(); }

    void clear() {
        bytes_.fill(0);
        setHeader(PageHeader{});
    }

    char* data() { return bytes_.data(); }
    const char* data() const { return bytes_.data(); }

    PageHeader header() const { return readAt<PageHeader>(bytes_.data(), 0); }
    void setHeader(const PageHeader& value) { writeAt(bytes_.data(), 0, value); }

    Slot slot(int id) const { return readAt<Slot>(bytes_.data(), DIRECTORY + id * SLOT_SIZE); }
    void setSlot(int id, const Slot& value) { writeAt(bytes_.data(), DIRECTORY + id * SLOT_SIZE, value); }

    int directoryEnd() const { return DIRECTORY + header().slotCount * SLOT_SIZE; }
    int freeSpace() const { return header().freePtr - directoryEnd(); }
    int usedSpace() const { return PAGE_SIZE - freeSpace(); }

    int available(int usableLimit) const {
        return std::min(freeSpace(), usableLimit - usedSpace());
    }

    bool live(int id) const {
        return id >= 0 && id < header().slotCount && slot(id).offset >= 0;
    }

    int insert(const std::vector<char>& payload, int usableLimit) {
        PageHeader head = header();
        int payloadSize = static_cast<int>(payload.size());
        int needed = payloadSize + (head.freeSlot == NONE ? SLOT_SIZE : 0);
        if (needed > available(usableLimit)) return NONE;
        int id = head.freeSlot;
        if (id == NONE) {
            id = head.slotCount;
            head.slotCount += 1;
        } else {
            head.freeSlot = slot(id).length;
        }
        head.freePtr -= payloadSize;
        head.liveCount += 1;
        std::memcpy(bytes_.data() + head.freePtr, payload.data(), payload.size());
        setHeader(head);
        setSlot(id, Slot{head.freePtr, payloadSize});
        return id;
    }

    bool read(int id, std::vector<char>& out) const {
        if (!live(id)) return false;
        Slot target = slot(id);
        out.assign(bytes_.data() + target.offset, bytes_.data() + target.offset + target.length);
        return true;
    }

    bool erase(int id) {
        if (!live(id)) return false;
        PageHeader head = header();
        setSlot(id, Slot{NONE, head.freeSlot});
        head.freeSlot = id;
        head.liveCount -= 1;
        setHeader(head);
        compact();
        return true;
    }

    void compact() {
        PageHeader head = header();
        std::vector<int> ids;
        for (int id = 0; id < head.slotCount; ++id) {
            if (slot(id).offset >= 0) ids.push_back(id);
        }
        std::sort(ids.begin(), ids.end(), [this](int a, int b) {
            return slot(a).offset > slot(b).offset;
        });
        int cursor = PAGE_SIZE;
        for (int id : ids) {
            Slot target = slot(id);
            int destination = cursor - target.length;
            if (destination != target.offset) {
                std::memmove(bytes_.data() + destination, bytes_.data() + target.offset,
                             static_cast<size_t>(target.length));
            }
            setSlot(id, Slot{destination, target.length});
            cursor = destination;
        }
        std::memset(bytes_.data() + directoryEnd(), 0,
                    static_cast<size_t>(cursor - directoryEnd()));
        head.freePtr = cursor;
        setHeader(head);
    }

    bool contiguous() const {
        PageHeader head = header();
        int bytes = 0;
        for (int id = 0; id < head.slotCount; ++id) {
            if (slot(id).offset >= 0) bytes += slot(id).length;
        }
        return head.freePtr == PAGE_SIZE - bytes;
    }

private:
    std::array<char, PAGE_SIZE> bytes_{};
};

class VariableRecordFile {
public:
    VariableRecordFile(const std::string& filename, float fillFactor = 1.0f)
        : filename_(filename) {
        std::ifstream probe(filename, std::ios::binary);
        bool exists = probe.good();
        probe.close();
        if (!exists) {
            std::ofstream create(filename, std::ios::binary);
            FileHeader head;
            head.fillFactor = fillFactor;
            create.write(reinterpret_cast<const char*>(&head), sizeof(head));
        }
        file_.open(filename, std::ios::in | std::ios::out | std::ios::binary);
        if (!file_) throw std::runtime_error("no se pudo abrir " + filename);
        readFileHeader();
    }

    ~VariableRecordFile() {
        if (file_.is_open()) file_.close();
    }

    int usableLimit() const {
        return std::max(1, static_cast<int>(PAGE_SIZE * header_.fillFactor));
    }

    int pageCount() const { return header_.pageCount; }
    int size() const { return header_.recordCount; }

    RID add(const Matricula& record) {
        std::vector<char> payload = serialize(record);
        if (header_.freePageHead != NONE) {
            int pageId = header_.freePageHead;
            SlottedPage page = readPage(pageId);
            int id = page.insert(payload, usableLimit());
            if (id != NONE) return commitInsert(pageId, page, id);
            PageHeader head = page.header();
            header_.freePageHead = head.nextFreePage;
            head.nextFreePage = NONE;
            head.inFreeList = 0;
            page.setHeader(head);
            writePage(pageId, page);
            writeFileHeader();
        }
        if (header_.pageCount > 0) {
            int pageId = header_.pageCount - 1;
            SlottedPage page = readPage(pageId);
            int id = page.insert(payload, usableLimit());
            if (id != NONE) return commitInsert(pageId, page, id);
        }
        SlottedPage page;
        int pageId = appendPage(page);
        int id = page.insert(payload, usableLimit());
        if (id == NONE) throw std::runtime_error("el registro excede el tamano de pagina");
        return commitInsert(pageId, page, id);
    }

    bool readRecord(const RID& pos, Matricula& out) {
        if (pos.page < 0 || pos.page >= header_.pageCount) return false;
        SlottedPage page = readPage(pos.page);
        std::vector<char> payload;
        if (!page.read(pos.slot, payload)) return false;
        out = deserialize(payload);
        return true;
    }

    bool remove(const RID& pos) {
        if (pos.page < 0 || pos.page >= header_.pageCount) return false;
        SlottedPage page = readPage(pos.page);
        if (!page.erase(pos.slot)) return false;
        PageHeader head = page.header();
        if (head.inFreeList == 0) {
            head.nextFreePage = header_.freePageHead;
            head.inFreeList = 1;
            header_.freePageHead = pos.page;
            page.setHeader(head);
        }
        writePage(pos.page, page);
        header_.recordCount -= 1;
        writeFileHeader();
        return true;
    }

    std::vector<Matricula> load() {
        std::vector<Matricula> records;
        std::vector<char> payload;
        for (int pageId = 0; pageId < header_.pageCount; ++pageId) {
            SlottedPage page = readPage(pageId);
            int slotCount = page.header().slotCount;
            for (int id = 0; id < slotCount; ++id) {
                if (page.read(id, payload)) records.push_back(deserialize(payload));
            }
        }
        return records;
    }

    std::vector<RID> positions() {
        std::vector<RID> ids;
        for (int pageId = 0; pageId < header_.pageCount; ++pageId) {
            SlottedPage page = readPage(pageId);
            int slotCount = page.header().slotCount;
            for (int id = 0; id < slotCount; ++id) {
                if (page.live(id)) ids.push_back(RID{pageId, id});
            }
        }
        return ids;
    }

    SlottedPage readPage(int pageId) {
        SlottedPage page;
        file_.seekg(pageOffset(pageId));
        file_.read(page.data(), PAGE_SIZE);
        if (!file_) throw std::runtime_error("lectura de pagina fallida");
        return page;
    }

private:
    static int pageOffset(int pageId) {
        return static_cast<int>(sizeof(FileHeader)) + pageId * PAGE_SIZE;
    }

    void readFileHeader() {
        file_.seekg(0);
        file_.read(reinterpret_cast<char*>(&header_), sizeof(FileHeader));
    }

    void writeFileHeader() {
        file_.seekp(0);
        file_.write(reinterpret_cast<const char*>(&header_), sizeof(FileHeader));
        file_.flush();
    }

    void writePage(int pageId, const SlottedPage& page) {
        file_.seekp(pageOffset(pageId));
        file_.write(page.data(), PAGE_SIZE);
        file_.flush();
    }

    int appendPage(SlottedPage& page) {
        int pageId = header_.pageCount;
        page.clear();
        writePage(pageId, page);
        header_.pageCount += 1;
        writeFileHeader();
        return pageId;
    }

    RID commitInsert(int pageId, SlottedPage& page, int slotId) {
        writePage(pageId, page);
        header_.recordCount += 1;
        writeFileHeader();
        return RID{pageId, slotId};
    }

    std::string filename_;
    std::fstream file_;
    FileHeader header_;
};

const std::vector<std::string> CODIGOS = {"A", "B", "C", "MAT", "INF", "CS", "BIO"};
const std::vector<std::string> NOTAS = {
    "matricula regular",
    "alumno con beca parcial otorgada por rendimiento academico",
    "pendiente de pago",
    "cruce de horarios autorizado por el coordinador de la carrera",
    "reingreso",
    "matricula extemporanea con recargo administrativo aplicado al ciclo",
};

std::vector<Matricula> generarMatriculas(int n, unsigned seed = 2026) {
    std::mt19937 rng(seed);
    std::uniform_int_distribution<int> codigoDist(0, static_cast<int>(CODIGOS.size()) - 1);
    std::uniform_int_distribution<int> notaDist(0, static_cast<int>(NOTAS.size()) - 1);
    std::uniform_int_distribution<int> cicloDist(1, 10);
    std::uniform_real_distribution<double> montoDist(950.0, 4200.0);
    std::vector<Matricula> records;
    records.reserve(n);
    for (int i = 0; i < n; ++i) {
        Matricula record;
        record.codigo = CODIGOS[codigoDist(rng)] + std::to_string(1000 + i);
        record.ciclo = cicloDist(rng);
        record.mensualidad = std::round(montoDist(rng) * 100.0) / 100.0;
        record.observaciones = NOTAS[notaDist(rng)];
        records.push_back(record);
    }
    return records;
}

int fallos = 0;

void check(bool condition, const std::string& mensaje) {
    if (!condition) {
        ++fallos;
        std::cout << "  FALLO: " << mensaje << "\n";
    }
}

void titulo(const std::string& texto) {
    std::cout << "\n" << std::string(70, '=') << "\n" << texto << "\n"
              << std::string(70, '=') << "\n";
}

void mostrarPaginas(VariableRecordFile& heap, const std::string& etiqueta) {
    std::cout << etiqueta << ": paginas=" << heap.pageCount()
              << " registros=" << heap.size() << "\n";
    for (int pageId = 0; pageId < heap.pageCount(); ++pageId) {
        SlottedPage page = heap.readPage(pageId);
        PageHeader head = page.header();
        std::cout << "  pagina " << pageId << ": slots=" << std::setw(3) << head.slotCount
                  << " vivos=" << std::setw(3) << head.liveCount
                  << " free_ptr=" << std::setw(5) << head.freePtr
                  << " libre=" << std::setw(5) << page.freeSpace()
                  << " slot_libre=" << std::setw(3) << head.freeSlot << "\n";
    }
}

void mostrarDirectorio(SlottedPage& page, const std::string& etiqueta, int limite) {
    PageHeader head = page.header();
    std::cout << etiqueta << " -> free_ptr=" << head.freePtr
              << " espacio_libre=" << page.freeSpace() << "\n  directorio:";
    for (int id = 0; id < std::min(limite, head.slotCount); ++id) {
        Slot target = page.slot(id);
        if (target.offset < 0) {
            std::cout << " [" << id << ":libre]";
        } else {
            std::cout << " [" << id << ":" << target.offset << "+" << target.length << "]";
        }
    }
    std::cout << " ...\n";
}

void pruebaSlottedPage(const std::vector<Matricula>& matriculas) {
    titulo("P2.A - INSERCION, LECTURA Y RECORRIDO");
    std::remove("matriculas.dat");
    VariableRecordFile heap("matriculas.dat");

    std::vector<RID> posiciones;
    for (const Matricula& record : matriculas) posiciones.push_back(heap.add(record));
    check(heap.size() == static_cast<int>(matriculas.size()), "conteo de registros");
    check(heap.load() == matriculas, "load() devuelve los registros en orden de insercion");
    mostrarPaginas(heap, "luego de insertar");

    Matricula leido;
    check(heap.readRecord(posiciones[0], leido) && leido == matriculas[0], "readRecord del primero");
    check(heap.readRecord(posiciones[137], leido) && leido == matriculas[137], "readRecord intermedio");
    std::cout << "readRecord" << posiciones[137] << " -> " << leido.codigo << " | ciclo "
              << leido.ciclo << " | " << std::fixed << std::setprecision(2) << leido.mensualidad
              << " | " << leido.observaciones << "\n";
    check(!heap.readRecord(RID{99, 0}, leido), "pagina inexistente");
    check(!heap.readRecord(RID{0, 9999}, leido), "slot inexistente");
}

void pruebaCompactacion(const std::vector<Matricula>& matriculas) {
    titulo("P2.B - ELIMINACION CON COMPACTACION");
    VariableRecordFile heap("matriculas.dat");

    SlottedPage antes = heap.readPage(0);
    mostrarDirectorio(antes, "pagina 0 antes de eliminar", 8);

    std::vector<RID> vivos = heap.positions();
    std::vector<RID> eliminadas;
    for (size_t i = 0; i < vivos.size(); i += 4) eliminadas.push_back(vivos[i]);
    for (const RID& pos : eliminadas) check(heap.remove(pos), "remove valido");
    std::cout << "registros eliminados: " << eliminadas.size() << "\n";

    SlottedPage despues = heap.readPage(0);
    mostrarDirectorio(despues, "pagina 0 luego de eliminar", 8);

    for (int pageId = 0; pageId < heap.pageCount(); ++pageId) {
        SlottedPage page = heap.readPage(pageId);
        check(page.contiguous(), "pagina compactada sin fragmentacion");
    }
    std::cout << "todas las paginas quedan compactadas: los datos vivos son contiguos "
              << "y el espacio libre es un unico bloque\n";

    check(despues.header().slotCount == antes.header().slotCount,
          "la compactacion conserva los ids de slot");
    std::cout << "ids de slot conservados: slotCount " << antes.header().slotCount
              << " -> " << despues.header().slotCount << "\n";

    Matricula leido;
    for (const RID& pos : eliminadas) check(!heap.readRecord(pos, leido), "el eliminado no se lee");
    for (const RID& pos : eliminadas) check(!heap.remove(pos), "no se elimina dos veces");

    std::vector<RID> restantes = heap.positions();
    check(restantes.size() == vivos.size() - eliminadas.size(), "conteo luego de eliminar");
    for (const RID& pos : restantes) {
        check(heap.readRecord(pos, leido), "los sobrevivientes siguen legibles tras compactar");
    }
    std::vector<Matricula> esperados;
    for (size_t i = 0; i < matriculas.size(); ++i) {
        if (i % 4 != 0) esperados.push_back(matriculas[i]);
    }
    check(heap.load() == esperados, "load() coincide con los registros no eliminados");
    mostrarPaginas(heap, "luego de eliminar");
}

void pruebaReuso() {
    titulo("P2.C - REUSO DE SLOTS Y ESPACIO LIBERADO");
    VariableRecordFile heap("matriculas.dat");
    int paginasAntes = heap.pageCount();
    int vivosAntes = heap.size();

    std::vector<Matricula> nuevos = generarMatriculas(40, 77);
    std::vector<RID> destinos;
    for (const Matricula& record : nuevos) destinos.push_back(heap.add(record));

    Matricula leido;
    for (size_t i = 0; i < nuevos.size(); ++i) {
        check(heap.readRecord(destinos[i], leido) && leido == nuevos[i], "lectura del reinsertado");
    }
    check(heap.size() == vivosAntes + static_cast<int>(nuevos.size()), "conteo luego de reinsertar");
    check(heap.pageCount() == paginasAntes, "las inserciones reusan el espacio compactado");
    std::cout << "reinsertados " << nuevos.size() << " registros sin crear paginas nuevas ("
              << paginasAntes << " paginas)\n";
    mostrarPaginas(heap, "luego de reinsertar");

    std::vector<Matricula> vigentes = heap.load();
    VariableRecordFile relectura("matriculas.dat");
    check(relectura.load() == vigentes, "el archivo se relee correctamente");
    std::cout << "relectura del archivo -> " << relectura.load().size() << " registros\n";
}

void pruebaFillFactor(const std::vector<Matricula>& matriculas) {
    titulo("P3 - FILL FACTOR 80% (registros de longitud variable)");
    std::remove("matriculas_fillfactor.dat");
    VariableRecordFile heap("matriculas_fillfactor.dat", 0.8f);
    std::cout << "limite de ocupacion por pagina: " << heap.usableLimit() << " de "
              << PAGE_SIZE << " bytes\n";
    for (const Matricula& record : matriculas) heap.add(record);
    mostrarPaginas(heap, "luego de insertar");
    for (int pageId = 0; pageId < heap.pageCount(); ++pageId) {
        SlottedPage page = heap.readPage(pageId);
        check(page.usedSpace() <= heap.usableLimit(), "la pagina respeta el fill factor");
    }
    check(heap.load() == matriculas, "load() con fill factor");
}

int main() {
    titulo("LABORATORIO 02 - P2: SLOTTED PAGE DE LONGITUD VARIABLE");
    std::cout << "tamano de pagina     : " << PAGE_SIZE << " bytes\n";
    std::cout << "header de archivo    : " << sizeof(FileHeader) << " bytes\n";
    std::cout << "header de pagina     : " << sizeof(PageHeader) << " bytes\n";
    std::cout << "entrada de directorio: " << sizeof(Slot) << " bytes\n";

    std::vector<Matricula> matriculas = generarMatriculas(300);
    std::cout << "registros generados  : " << matriculas.size() << "\n";
    std::cout << "tamano serializado   : "
              << serialize(*std::min_element(matriculas.begin(), matriculas.end(),
                                             [](const Matricula& a, const Matricula& b) {
                                                 return serialize(a).size() < serialize(b).size();
                                             })).size()
              << " a "
              << serialize(*std::max_element(matriculas.begin(), matriculas.end(),
                                             [](const Matricula& a, const Matricula& b) {
                                                 return serialize(a).size() < serialize(b).size();
                                             })).size()
              << " bytes\n";

    pruebaSlottedPage(matriculas);
    pruebaCompactacion(matriculas);
    pruebaReuso();
    pruebaFillFactor(matriculas);

    titulo(fallos == 0 ? "Todas Las Pruebas Funcionales Pasaron"
                       : "PRUEBAS CON FALLOS: " + std::to_string(fallos));
    return fallos == 0 ? 0 : 1;
}
