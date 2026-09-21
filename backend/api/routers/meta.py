"""Health and model metadata. The dashboard calls these on load."""

from __future__ import annotations

from fastapi import APIRouter

from backend import config
from backend.api.schemas import HealthResponse, ModelInfo
from backend.api.store import store
from backend.ml.predict import ModelNotTrained, load_bundle
from backend.ml.train import HEADS

router = APIRouter(tags=["meta"])

RUL_NOTE = (
    "Remaining useful life is a proxy. AI4I 2020 carries no run to failure "
    "timeline, so failure probability is converted to hours through a constant "
    "hazard model anchored on the reference horizon and capped. Render it as an "
    "estimate, not a measurement.")


@router.get("/health", response_model=HealthResponse)
def health() -> HealthResponse:
    """Liveness plus whether a trained model is actually available."""
    try:
        bundle = load_bundle()
    except ModelNotTrained as exc:
        return HealthResponse(status="degraded", model_loaded=False, detail=str(exc))
    return HealthResponse(
        status="ok", model_loaded=True,
        model_trained_at=bundle.trained_at,
        datasets_loaded=len(store.list()))


@router.get("/model", response_model=ModelInfo)
def model_info() -> ModelInfo:
    """Feature list, thresholds and test metrics, so the UI can show provenance."""
    bundle = load_bundle()
    return ModelInfo(
        trained_at=bundle.trained_at,
        feature_columns=list(bundle.feature_columns),
        heads=[h for h in HEADS if h in bundle.models],
        thresholds={k: round(float(v), 3) for k, v in bundle.thresholds.items()},
        metrics=bundle.metrics,
        rul_reference_horizon_hours=config.RUL_REFERENCE_HORIZON_H,
        rul_cap_hours=config.RUL_MAX_H,
        rul_note=RUL_NOTE)
