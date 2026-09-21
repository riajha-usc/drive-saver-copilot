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

Complete. `uvicorn backend.api.main:app --reload`, docs at `/docs`.

The prescriptive payload is not redefined at the HTTP boundary. It is
`PrescriptiveRecommendation` served unchanged, so the dashboard codes against one
contract whether it reads it from the API or from `python -m backend.demo --json`.

### Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| GET | `/health` | liveness and whether a trained model is loaded |
| GET | `/model` | features, thresholds, test metrics, the RUL proxy note |
| POST | `/datasets` | Task 5: upload a telemetry CSV, get it cleaned, scored and held |
| GET | `/datasets` | list loaded datasets |
| GET | `/datasets/{id}` | dataset summary with risk band counts |
| GET | `/datasets/{id}/assets` | asset selector feed, sorted by risk, filterable and paged |
| GET | `/datasets/{id}/assets/{asset_id}` | risk, per mode probabilities, margins, SHAP factors |
| GET | `/datasets/{id}/assets/{asset_id}/history` | telemetry trace for the charts |
| POST | `/datasets/{id}/assets/{asset_id}/recommendation` | Task 6: run the agent, return the prescription |
| POST | `/datasets/{id}/assets/{asset_id}/apply` | back the Implement Adjustment button |
| POST | `/telemetry/score` | score rows inline, no upload, nothing retained |
| POST | `/recommendations` | run the agent on inline telemetry, no upload |

### Notes for the dashboard

- The AI4I sample is seeded at startup as dataset `ai4i-sample`, so the UI never
  opens to an empty asset list.
- Uploads accept either column spelling the AI4I source ships with, bracketed
  units or stripped. Unusable rows are dropped and counted in `rows_rejected`
  rather than failing the whole upload.
- A missing model does not stop the app booting. `/health` reports `degraded` and
  the endpoints that need the model return 503 with the command to fix it.
- `/apply` records the operator accepting a prescription and reports the resulting
  operating point. It does not talk to a real drive and says so in
  `applied_note`. Do not render it as a confirmation that a setpoint changed.
- The history endpoint carries a `note` saying that AI4I rows are independent
  snapshots rather than one machine over time. Keep that note visible near the
  chart.
- CORS is open to localhost on ports 3000, 5173 and 8501.

## Phase 3: Dashboard UI

7. **Telemetry and failure alert interface.** Asset selector, telemetry line charts for temperature, RPM, and torque, plus a prominent red alert box showing health status.
8. **Prescriptive recommendation panel.** An interactive card showing the prescribed parameter change, projected RUL extension in hours, estimated cost savings, and an "Implement Adjustment" button.
9. **End-to-end flow integration.** Wire the UI to the FastAPI endpoints so uploading a dataset triggers live predictions and populates the recommendation panel.

## Repository Layout

```
drive-saver-copilot/
  backend/
    config.py            paths, thresholds, cost constants, LLM settings
    physics.py           AI4I failure rules, operating point, margins to each limit
    ml/
      dataset.py         Task 1a  fetch, clean, feature engineering, split
      train.py           Task 1b  five XGBoost heads, thresholds, metrics
      bundle.py          serialisable model artifact
      rul.py             probability to hours, the RUL proxy
      explain.py         Task 2   SHAP attributions and the controllable lever
      predict.py         inference facade: risk, RUL, root cause, margins
    agent/
      counterfactual.py  Task 3a  adjustment grid, feasibility guards, selector
      economics.py       cost model behind the savings figure
      llm.py             narration, LLM optional with a deterministic fallback
      graph.py           Task 3   the LangGraph state machine
      schema.py          Task 4   the strict Pydantic output contract
    api/
      main.py            Task 5   FastAPI app, CORS, startup model load
      store.py           in memory dataset registry, seeded with the AI4I sample
      schemas.py         request and response models for the HTTP layer
      deps.py            shared dependencies and error translation
      routers/           meta, telemetry ingestion, assets, recommendations
    demo.py              runnable Phase 1 walkthrough
  tests/                 93 tests, including a whole pipeline regression harness
  data/raw/              cached AI4I CSV
  models/                trained bundle and metrics.json
```

## Quickstart

macOS needs the OpenMP runtime before XGBoost will load:

```bash
brew install libomp
```

Then:

```bash
make setup      # venv plus requirements
make train      # fetches AI4I from UCI on first run, trains, writes models/
make test       # 93 tests
make demo       # one prescriptive card per failure mode, on real dataset rows
make api        # serve the API at http://127.0.0.1:8000, docs at /docs
```

`make demo --json` is available as `python -m backend.demo --json` and prints the
exact payloads Phase 2 will serve.

An Anthropic API key is optional. Copy `.env.example` to `.env` and set
`ANTHROPIC_API_KEY` to have the LLM write the operator card. Without it the
deterministic narrator runs and every number is unchanged.

## Phase 1 Status

All four Phase 1 tasks are complete and tested.

### Task 1: dataset pipeline and model training

10,000 rows, no rows dropped. Five gradient boosted heads on a shared feature
frame of the six raw signals plus four derived features (`temp_diff`, `power_w`,
`wear_torque`, `osf_utilisation`). Operating thresholds are picked on an inner
validation split so the test numbers below are clean.

| Head | PR AUC | ROC AUC | Precision | Recall |
| --- | --- | --- | --- | --- |
| machine_failure | 0.863 | 0.975 | 0.902 | 0.809 |
| HDF | 0.986 | 1.000 | 0.931 | 0.931 |
| PWF | 0.866 | 0.999 | 0.813 | 1.000 |
| OSF | 1.000 | 1.000 | 0.941 | 1.000 |
| TWF | 0.066 | 0.904 | 0.053 | 0.100 |

TWF is weak on purpose and the caveat is carried in the payload. The AI4I
generator places the tool wear failure at a random point inside the 200 to 240
minute window, so nothing in the feature set can time it. The agent handles TWF
by prescribing a tool change rather than a setpoint trim.

### Remaining Useful Life

AI4I is a snapshot dataset with no run to failure timeline, so a true RUL label
does not exist. Rather than invent one, failure probability is converted to hours
through an explicit constant hazard model anchored on a 72 hour reference horizon,
capped at 720 hours. Every payload flags `rul_is_proxy: true` and repeats the
caveat in plain English. The mapping is strictly decreasing, which is the only
property the prescriptive layer needs: any adjustment that lowers risk shows up
as hours gained.

### Task 2: SHAP attribution

TreeExplainer over the trained heads. Each factor carries its log odds value, its
direction, and its share of the total upward push, which is what the UI renders as
root cause confidence. Attributions are also rolled up to a controllable lever
(torque, speed, ambient, maintenance) so the agent knows which knob to reach for.
Features that hold risk down are never reported as a root cause.

### Task 3: LangGraph prescriptive agent

```
ingest -> diagnose -> simulate -> decide -> narrate -> validate
```

Every node is a pure function over shared state, so each is unit tested on its own
and the whole graph runs offline. The LLM appears in exactly one node and only
writes prose. Every number comes from the model, the physics rules or the cost
model, which keeps the prescription auditable.

The counterfactual engine sweeps a torque and speed grid, rebuilds the operating
point, rescores it, and converts the probability change into hours. Three things
keep the answers honest:

1. **Feasibility guard.** A candidate is rejected if it trips a limit the current
   point respects. Cutting torque 10 percent is the obvious move against
   overstrain, but on a lightly loaded drive it pushes shaft power under the
   3500 W floor and buys a Power Failure instead.
2. **Fault tiering.** Candidates that actually clear the breached limit are ranked
   above ones that merely score lower. Without this a tool change wins on cost
   against a heat dissipation fault it does nothing about, because wear correlates
   with risk across the dataset.
3. **Stop instead of dress up.** When a limit is genuinely breached and no setpoint
   inside the drive's range clears it, the agent returns `stop_now` with no
   adjustments rather than promising hours it cannot deliver. The best palliative
   is still listed under alternatives.

Among the candidates that survive, the selector takes the smallest intervention:
least output given up, then the smallest setpoint move, then the largest risk
reduction.

Heat Dissipation Failure is the case that shows the engine is reasoning about
physics rather than pattern matching. HDF needs the temperature spread below
8.6 K **and** speed below 1380 rpm, so the fix is to speed the drive up, not
throttle it. The agent prescribes a speed increase with zero output loss.

### Task 4: structured output

`PrescriptiveRecommendation` in `backend/agent/schema.py`. Strict Pydantic with
`extra="forbid"`, closed enums for risk band, failure mode and action type, and
bounded probabilities. Nothing leaves the agent unvalidated. Top level fields:

`asset_id`, `generated_at`, `model_trained_at`, `telemetry`, `risk`, `root_cause`,
`action_type`, `adjustments`, `projection`, `economics`, `narrative`,
`alternatives`, `confidence`, `caveats`, `schema_version`.

`action_type` is one of `derate`, `reconfigure`, `schedule_maintenance`,
`no_action`, `stop_now`.

## Sample Output

Real AI4I row, an overstrained L class drive:

```
VFD-MOTOR-03   CRITICAL   99.9 percent risk of Power Failure
  telemetry     65.7 Nm at 1410 rpm, 9701 W, spread 10.1 K, wear 191 min
  limits hit    PWF, OSF
  root cause    Shaft power is the dominant contributor at 40 percent of the upward risk push
                wear times torque against the overstrain limit is past the limit by 1548.7 min Nm

  ACTION        reconfigure
                VFD torque setpoint: 65.7 -> 57.49 Nm (-12.5 percent)
                VFD speed setpoint: 1410.0 -> 1480.5 rpm (+5.0 percent)

  life          10.6 h -> 96.4 h (+85.8 h), window at 48.0 h reached
  risk          0.999 -> 0.526
  output cost   8.1 percent
  net benefit   $4,284 ($7,987 avoided less $3,703 output)
  confidence    0.99
```

## Phase 2: Backend API Layer

Code completed and testing not started. Planned endpoints, both serving the schema above unchanged:

5. **Ingestion.** `POST /telemetry` accepts a CSV upload or a JSON batch, returns
   per row risk, RUL proxy and likely mode from `score_frame`.
6. **Prescription.** `POST /assets/{asset_id}/recommendation` runs the LangGraph
   agent for one operating point and a maintenance window, returns
   `PrescriptiveRecommendation`.

## Phase 3: Dashboard UI

Not Started. The contract is `PrescriptiveRecommendation`, served by
the endpoints above. Start the API with `make api` and browse `/docs` for a live,
executable reference. `python -m backend.demo --json` still prints example
payloads if you want them without a running server.

## Testing

93 tests. The unit modules pin one behaviour each against a hand built operating
point. `tests/test_integration.py` runs sampled real rows through the full graph
and asserts the invariants that must hold for every row rather than only the ones
someone wrote a fixture for:

- no prescription ever introduces a failure the asset did not already have
- a prescription either clears the breached limit or returns `stop_now` and says
  it cannot
- projection and economics arithmetic is self consistent
- `action_type` matches the payload it ships with
- every payload round trips through the schema
- healthy assets are not alarmed, failing assets are never silent
- batch scoring agrees with single point scoring
- the agent is deterministic, so a demo does not drift between runs

That harness caught a real bug on its first run. A row with tool wear inside the
200 to 240 minute change window scored 0.009 and was reported as `normal` with
`no_action`, because the TWF head cannot time a failure the generator places at
random. A breached limit is a fact and the score is only an estimate, so the risk
band now floors at `elevated` whenever a deterministic limit is breached, the
agent always simulates in that case, and the payload carries a caveat naming the
disagreement.

## Notes and Limitations

- The RUL figure is a proxy, not a measured time to failure. It is labelled as such
  in the payload and in every card.
- Economic figures rest on four configurable constants, all surfaced in the payload
  under `economics.assumptions`.
- Throughput loss is modelled as the drop in mechanical shaft power. A real line
  would map this to units per hour.
- RNF, the 0.1 percent random failure flag, is excluded from the modelled modes.
