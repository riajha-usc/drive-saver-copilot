"""FastAPI application for Drive-Saver Copilot.

  uvicorn backend.api.main:app --reload
  open http://127.0.0.1:8000/docs

The model is loaded once at startup and the AI4I sample is seeded as a dataset,
so the dashboard has assets to show before anyone uploads a file. A missing
model does not stop the app from starting: /health reports degraded and the
endpoints that need it return 503 with the command to fix it.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.api.routers import assets, meta, recommendations, telemetry
from backend.api.store import store
from backend.ml.predict import ModelNotTrained, load_bundle

log = logging.getLogger(__name__)

DESCRIPTION = """
Prescriptive maintenance for VFDs and motors.

Most tooling stops at "this motor will fail in 20 hours". These endpoints go one
step further and return the parameter change that pushes the failure past the
next planned maintenance window, with the projected hours gained and what the
derate costs in output.

Typical dashboard flow:

1. `GET /health` and `GET /model` on load
2. `POST /datasets` to upload a telemetry CSV, or use the seeded `ai4i-sample`
3. `GET /datasets/{id}/assets?sort=risk` for the asset selector
4. `GET /datasets/{id}/assets/{asset_id}` and `.../history` for the alert box
   and the charts
5. `POST /datasets/{id}/assets/{asset_id}/recommendation` for the prescription
6. `POST .../apply` behind the Implement Adjustment button

Remaining useful life is a proxy throughout. See `GET /model` for the note.
"""

# Local dev origins for the dashboard. Tighten before this goes anywhere real.
ALLOWED_ORIGINS = [
    "http://localhost:3000", "http://127.0.0.1:3000",      # Next.js
    "http://localhost:5173", "http://127.0.0.1:5173",      # Vite
    "http://localhost:8501", "http://127.0.0.1:8501",      # Streamlit
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        load_bundle()
        store.seed_default()
        log.info("model loaded, AI4I sample seeded")
    except ModelNotTrained:
        # Starting without a model is fine. /health says so and says how to fix it.
        log.warning("no trained model found, API starts degraded. "
                    "Run: python -m backend.ml.train")
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="Drive-Saver Copilot",
        description=DESCRIPTION,
        version="1.0.0",
        lifespan=lifespan)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=ALLOWED_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"])

    app.include_router(meta.router)
    app.include_router(telemetry.router)
    app.include_router(assets.router)
    app.include_router(recommendations.router)
    return app


app = create_app()
