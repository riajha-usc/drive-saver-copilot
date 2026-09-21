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

from backend import config
from backend.api.routers import assets, meta, recommendations, telemetry
from backend.api.static import mount_dashboard
from backend.api.store import store
from backend.ml.predict import ModelNotTrained, load_bundle

log = logging.getLogger(__name__)

DESCRIPTION = """
Prescriptive maintenance for VFDs and motors.

Most tooling stops at "this motor will fail in 20 hours". These endpoints go one
step further and return the parameter change that pushes the failure past the
next planned maintenance window, with the projected hours gained and what the
derate costs in output.

The dashboard is served from this same app at `/` when it has been built, so the
browser origin is already correct and there is no CORS to configure.

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


@asynccontextmanager
async def lifespan(app: FastAPI):
    try:
        load_bundle()
        if config.SEED_SAMPLE_DATASET:
            store.seed_default()
            log.info("model loaded, AI4I sample seeded")
        else:
            log.info("model loaded, sample seeding disabled")
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
        allow_origins=config.CORS_ORIGINS,
        allow_credentials=False,
        allow_methods=["GET", "POST"],
        allow_headers=["*"])

    app.include_router(meta.router)
    app.include_router(telemetry.router)
    app.include_router(assets.router)
    app.include_router(recommendations.router)

    # Last, so the single page app catch all cannot shadow an API route.
    mount_dashboard(app)
    return app


app = create_app()
