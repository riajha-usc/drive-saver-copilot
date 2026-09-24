VENV := .venv
PY := $(VENV)/bin/python

setup:
	python3 -m venv $(VENV)
	$(VENV)/bin/pip install --upgrade pip
	$(VENV)/bin/pip install -r requirements-dev.txt

train:
	$(PY) -m backend.ml.train

demo:
	$(PY) -m backend.demo

test:
	$(PY) -m pytest tests/ -q

api:
	$(VENV)/bin/uvicorn backend.api.main:app --reload --port 8000

ui:
	cd frontend && npm install && npm run dev

ui-build:
	cd frontend && npm install && npm run build

mlflow:
	MLFLOW_DISABLE_TELEMETRY=true $(VENV)/bin/mlflow ui --backend-store-uri sqlite:///models/mlflow.db --port 5000

docker-build:
	docker build -t drive-saver-copilot .

docker-run: docker-build
	docker run --rm -p 8000:8000 --env-file .env.example drive-saver-copilot

all: train test demo

.PHONY: setup train demo test api ui ui-build mlflow docker-build docker-run all
