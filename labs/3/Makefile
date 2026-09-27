PYTHON ?= .venv/bin/python
DB ?= employees
USUARIO ?= postgres
EVIDENCIA = evidencia

all: datos planes pruebas bench capturas informe

datos:
	$(PYTHON) export_data.py $(DB) $(USUARIO)

planes:
	./capturar_planes.sh $(DB) $(USUARIO)

pruebas:
	mkdir -p $(EVIDENCIA)
	$(PYTHON) heap_file.py | tee $(EVIDENCIA)/p2_1_heap_file.txt
	$(PYTHON) external_sort.py | tee $(EVIDENCIA)/p2_2_external_sort.txt
	$(PYTHON) external_hashing.py | tee $(EVIDENCIA)/p2_3_external_hashing.txt

bench:
	$(PYTHON) benchmark.py | tee $(EVIDENCIA)/p2_4_benchmark.txt

capturas:
	$(PYTHON) capturas.py

informe: capturas
	$(PYTHON) informe.py

limpiar:
	rm -rf data/runs data/particiones data/employee_sorted.bin

.PHONY: all datos planes pruebas bench capturas informe limpiar
