# Drive-Saver Copilot

Agentic prescriptive maintenance for variable frequency drives (VFDs) and electric motors.

## Idea

Most maintenance tooling stops at prediction. It tells you a motor will fail in 20 hours and leaves the rest to the operator. Drive-Saver Copilot goes one step further: it calculates counterfactual parameter adjustments, for example reducing VFD torque by 10 percent, so the failure is pushed past the next planned maintenance window instead of landing in the middle of a production run.

## Core Objective

Move from *predictive* maintenance (a failure is coming) to *prescriptive* maintenance (here is the exact parameter change, the projected hours gained, and the estimated cost avoided).

## Prototype Need

A functional, end-to-end proof of concept covering:

1. Data ingestion
2. Automated failure prediction
3. SHAP-driven root cause extraction
4. Agentic recommendation generation
5. An intuitive UI that surfaces the prescriptive action

## Primary Dataset

**AI4I 2020 Predictive Maintenance Dataset** (UCI Machine Learning Repository)

Simulates industrial machinery operating conditions and carries the exact VFD and motor metrics the agent needs.

| Feature | Notes |
| --- | --- |
| Rotational Speed (RPM) | Drive output speed |
| Torque (Nm) | Primary throttling lever |
| Air Temperature (K) | Ambient condition |
| Process Temperature (K) | Thermal load indicator |
| Machine Failure | Binary target |
| HDF | Heat Dissipation Failure |
| OSF | Overstrain Failure |
| PWF | Power Failure |

**Why it fits:** torque, RPM, and heat are all present and directly manipulable, so the LangGraph agent can simulate parameter throttling (for instance lowering torque 10 percent to avoid an Overstrain or Heat Dissipation Failure) and re-score the model on the modified point.

## Tech Stack

| Technology | Role in the prototype |
| --- | --- |
| Python | Primary language for ML, agents, and backend logic |
| XGBoost / LightGBM | Lightweight, high-accuracy failure prediction and RUL estimation |
| SHAP | Feature attribution to identify the specific failure driver (temperature vs torque) |
| LangGraph + LLM (OpenAI / Anthropic) | Agentic reasoning, counterfactual simulation, structured JSON output |
| FastAPI | REST endpoints for telemetry analysis and agent recommendations |
| Streamlit or React / Next.js | Dashboard for telemetry charts, failure alerts, and prescriptive actions |
| Sample telemetry CSV | AI4I 2020, with NASA C-MAPSS or synthetic VFD telemetry as a fallback |

## Implementation Tasks

### Phase 1: Core ML and Agent Logic (Backend)

1. **Dataset pipeline and model training.** Clean the motor/VFD telemetry CSV and train an XGBoost or LightGBM model to predict failure risk or Remaining Useful Life.
2. **SHAP feature attribution.** Extract the top failure-contributing features for any high-risk data point, such as high winding temperature or excessive torque spikes.
3. **LangGraph prescriptive agent engine.** Take the model output plus SHAP values, run a counterfactual simulation (if torque drops 10 percent, projected life increases by 48 hours), and generate plain-English prescriptive advice.
4. **Structured JSON output schema.** Enforce a strict response schema carrying failure risk, root cause, prescribed adjustments, and projected hour extension so the API can consume it directly.

### Phase 2: Backend API Layer

5. **FastAPI setup and ingestion endpoint.** Routes that accept telemetry uploads and return model predictions.
6. **Prescriptive agent endpoint.** Trigger the LangGraph agent for a selected high-risk motor and serve the structured recommendation payload.

### Phase 3: Dashboard UI

7. **Telemetry and failure alert interface.** Asset selector, telemetry line charts for temperature, RPM, and torque, plus a prominent red alert box showing health status.
8. **Prescriptive recommendation panel.** An interactive card showing the prescribed parameter change, projected RUL extension in hours, estimated cost savings, and an "Implement Adjustment" button.
9. **End-to-end flow integration.** Wire the UI to the FastAPI endpoints so uploading a dataset triggers live predictions and populates the recommendation panel.

## Repository Layout

```
drive-saver-copilot/
  backend/
    config.py     paths, thresholds, cost constants, LLM settings
    physics.py    AI4I failure rules, operating point, margins to each limit
    ml/           dataset, training, RUL proxy, SHAP, inference
    agent/        counterfactual simulation, LangGraph graph, output schema
  tests/
  data/raw/       cached AI4I CSV, fetched on first run
  models/         trained bundle and metrics
```

## Quickstart

macOS needs the OpenMP runtime before XGBoost will load:

```bash
brew install libomp
```

Then:

```bash
make setup
make train
make test
```

An Anthropic API key is optional. Copy `.env.example` to `.env` and set
`ANTHROPIC_API_KEY` to have the LLM write the operator card. Without it the
deterministic narrator runs and every number is unchanged.

## Status

Scaffolding in place: configuration, the AI4I failure rules as a shared physics
module, and the test harness. The nine implementation tasks follow.
