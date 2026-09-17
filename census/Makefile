VENV ?= .venv
PY   := $(VENV)/bin/python

.PHONY: setup test fetch build report explorer all clean

$(VENV)/bin/activate:
	python3 -m venv $(VENV)
	$(PY) -m pip install --upgrade pip
	$(PY) -m pip install -r requirements-dev.txt

setup: $(VENV)/bin/activate

test: setup
	$(PY) -m pytest tests/ -q

fetch: setup
	$(PY) -m cohort_trace fetch

build: setup
	$(PY) -m cohort_trace build

report: setup
	$(PY) -m cohort_trace report

explorer: setup
	$(PY) explorer/build_explorer.py

all: setup test
	$(PY) -m cohort_trace all
	$(PY) explorer/build_explorer.py

clean:
	rm -rf data/raw/*.json data/processed/*.csv output/*.csv output/*.md \
		output/explorer.html
