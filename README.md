# Drive-Saver Copilot

Agentic prescriptive maintenance for variable frequency drives (VFDs) and electric motors.

Most maintenance tools stop at "this motor will fail in 20 hours". Drive-Saver
Copilot goes one step further: it finds the smallest change to the drive's torque
and speed setpoints that pushes the failure past your next planned maintenance
window, and tells you the hours gained, the risk removed and the money saved.

Built for the ABB Accelerator 2026 challenge, Theme 1: Agentic Predictive
Maintenance Studio.

**Live demo:** https://drive-saver-copilot-138499493256.us-central1.run.app
(the first visit after a quiet spell can take a few seconds while it starts up)

## How it works

```
telemetry -> failure risk model -> SHAP root cause -> counterfactual agent -> prescription
```

1. **Predict.** Five XGBoost models score failure risk overall and per failure mode.
2. **Explain.** SHAP shows which signals drive the risk and which control lever
   moves them.
3. **Prescribe.** A LangGraph agent simulates torque and speed adjustments, rejects
   any that would break another physical limit, and picks the smallest one that
   reaches the maintenance window. If nothing safe works, it says stop.

## Features

- Asset dashboard with risk filters, telemetry charts and root cause analysis
- Adjustable maintenance window that changes the prescription
- Before and after projection, economics, caveats and alternative options
- CSV upload scores new telemetry live
- Physics guards: a fix never trades one failure for another
- Runs fully offline; an LLM is optional and only writes the explanation

## Tech stack

| Area | Tools |
| --- | --- |
| Machine learning | Python, XGBoost, scikit-learn, pandas |
| Explainability | SHAP |
| Agent | LangGraph, optional Anthropic Claude for narration |
| API | FastAPI, Pydantic |
| Dashboard | React, Vite, Recharts |
| Deployment | Docker, Google Cloud Run |

## Quickstart

Requires Python 3.12 or newer and Node 20 or newer. macOS also needs the OpenMP
runtime for XGBoost:

```bash
brew install libomp
```

Then:

```bash
make setup      # virtual environment and dependencies
make train      # fetch the dataset and train the models
make test       # run the test suite
make ui-build   # build the dashboard
make api        # API and dashboard on http://127.0.0.1:8000, API docs at /docs
```

For dashboard development with hot reload, run `make ui` in a second terminal and
open http://127.0.0.1:5173.

An Anthropic API key is optional. Copy `.env.example` to `.env` and set
`ANTHROPIC_API_KEY` to have Claude write the operator card; without it a built in
template writes it and every number stays the same.

## Docker and deployment

```bash
make docker-build   # builds the dashboard and trains the model into the image
make docker-run     # dashboard and API together on http://127.0.0.1:8000
```

Deploy to Google Cloud Run, which builds the image in the cloud:

```bash
gcloud run deploy drive-saver-copilot --source . --region us-central1 --allow-unauthenticated --memory 1Gi --cpu 1 --min-instances 0 --max-instances 1
```

Keep `--max-instances 1`: uploaded datasets are held in memory, so a second
instance would not see them.

## API

Interactive docs are served at `/docs`. Main endpoints:

| Method | Path | Purpose |
| --- | --- | --- |
| POST | `/datasets` | upload a telemetry CSV |
| GET | `/datasets/{id}/assets` | assets sorted by risk, with filters and paging |
| GET | `/datasets/{id}/assets/{asset_id}` | risk, root cause and physical margins |
| POST | `/datasets/{id}/assets/{asset_id}/recommendation` | run the agent |
| POST | `/recommendations` | run the agent on inline telemetry |

## Project structure

```
backend/
  physics.py      failure rules and physical margins
  ml/             data pipeline, training, SHAP, inference
  agent/          counterfactual search, LangGraph graph, output schema
  api/            FastAPI app and routes
frontend/         React dashboard
tests/            unit, API and integration tests
data/raw/         AI4I 2020 dataset
```

## Limitations

- Remaining useful life is an estimate derived from failure probability; the
  dataset has no run to failure timeline.
- Uploaded datasets are kept in memory and cleared on restart.
- The prototype does not connect to real drives. Implement Adjustment records the
  change and shows its projected effect.

## Data and attribution

Trained on the [AI4I 2020 Predictive Maintenance Dataset](https://archive.ics.uci.edu/dataset/601/ai4i+2020+predictive+maintenance+dataset)
from the UCI Machine Learning Repository, licensed CC BY 4.0. Built with
open source libraries including XGBoost, SHAP, LangGraph, FastAPI, React and
Recharts.
