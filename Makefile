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

api:
	$(VENV)/bin/uvicorn backend.api.main:app --reload --port 8000

all: train test demo

.PHONY: setup train demo test api all
