"""Central configuration and filesystem paths for Drive-Saver Copilot."""

from __future__ import annotations

import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
RAW_DIR = DATA_DIR / "raw"
MODEL_DIR = ROOT / "models"

RAW_CSV = RAW_DIR / "ai4i2020.csv"
MODEL_BUNDLE = MODEL_DIR / "drive_saver_model.joblib"
METRICS_JSON = MODEL_DIR / "metrics.json"

UCI_DATASET_ID = 601
RANDOM_STATE = 42
TEST_SIZE = 0.2

# Reference horizon used by the RUL proxy. The AI4I dataset carries no run-to-failure
# timeline, so failure probability is converted to hours through a constant-hazard
# model anchored on this horizon. See backend/ml/rul.py.
RUL_REFERENCE_HORIZON_H = 72.0
RUL_MIN_H = 1.0
RUL_MAX_H = 720.0  # 30 days. Beyond this a single snapshot carries no signal,
                   # so the proxy is capped and flagged rather than extrapolated.

# Risk banding on the machine-failure probability.
RISK_BANDS = ((0.60, "critical"), (0.30, "high"), (0.10, "elevated"), (0.0, "normal"))

# Economics used by the prescriptive value calculation. Override via env for a demo.
UNPLANNED_DOWNTIME_HOURS = float(os.getenv("DSC_UNPLANNED_DOWNTIME_HOURS", "8"))
DOWNTIME_COST_PER_HOUR = float(os.getenv("DSC_DOWNTIME_COST_PER_HOUR", "1800"))
EMERGENCY_CALLOUT_COST = float(os.getenv("DSC_EMERGENCY_CALLOUT_COST", "2500"))
PRODUCTION_VALUE_PER_HOUR = float(os.getenv("DSC_PRODUCTION_VALUE_PER_HOUR", "950"))

# Serving. PORT is what most platforms inject, so it is read rather than fixed.
# CORS origins are comma separated; the default covers local dashboard dev and
# has to be set explicitly once a real frontend has a domain.
PORT = int(os.getenv("PORT", "8000"))
DEFAULT_CORS_ORIGINS = (
    "http://localhost:3000,http://127.0.0.1:3000,"      # Next.js
    "http://localhost:5173,http://127.0.0.1:5173,"      # Vite
    "http://localhost:8501,http://127.0.0.1:8501"       # Streamlit
)
CORS_ORIGINS = [o.strip() for o in
                os.getenv("DSC_CORS_ORIGINS", DEFAULT_CORS_ORIGINS).split(",") if o.strip()]

# Seeding the bundled AI4I sample costs a few seconds of startup and about 10,000
# scored rows of memory. Turn it off on a deployment that only serves uploads.
SEED_SAMPLE_DATASET = os.getenv("DSC_SEED_SAMPLE", "1").lower() not in ("0", "false", "no")

# LLM narration. When no key is present the agent falls back to a deterministic
# narrator so the prototype runs fully offline.
LLM_MODEL = os.getenv("DSC_LLM_MODEL", "claude-sonnet-5")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY")


def ensure_dirs() -> None:
    for d in (RAW_DIR, MODEL_DIR):
        d.mkdir(parents=True, exist_ok=True)
