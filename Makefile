PYTHON ?= python
PIP ?= $(PYTHON) -m pip

.PHONY: install init collect facts entities chunks qa index graph eval demo validate stats export-hf test lint all

install:
	$(PIP) install -e ".[dev]"

init:
	$(PYTHON) scripts/00_init_registry.py

collect:
	$(PYTHON) scripts/01_collect_sources.py --resume

facts:
	$(PYTHON) scripts/02_extract_facts.py --resume

entities:
	$(PYTHON) scripts/03_build_entities.py --resume

chunks:
	$(PYTHON) scripts/04_build_chunks.py --resume

qa:
	$(PYTHON) scripts/05_build_qa_eval.py --minimum 300 --resume

index:
	$(PYTHON) scripts/06_build_vector_index.py --resume

graph:
	$(PYTHON) scripts/07_build_graph.py --resume

eval:
	$(PYTHON) -m qinghai_rag.rag.evaluate

demo:
	$(PYTHON) scripts/08_run_rag_demo.py

validate:
	$(PYTHON) scripts/09_validate_release.py

stats:
	$(PYTHON) scripts/11_dataset_stats.py

export-hf:
	$(PYTHON) scripts/10_export_hf_dataset.py

test:
	pytest

lint:
	ruff check src scripts tests

all: init collect facts entities chunks qa index graph eval validate stats
