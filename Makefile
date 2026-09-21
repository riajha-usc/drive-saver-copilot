VENV := .venv
PY := $(VENV)/bin/python

setup:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements.txt

train:
	$(PY) -m backend.ml.train

demo:
	$(PY) -m backend.demo

test:
	$(PY) -m pytest tests/ -q

all: train test demo

.PHONY: setup train demo test all
