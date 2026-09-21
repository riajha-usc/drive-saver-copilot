"""Task 6: the prescriptive endpoint.

Runs the LangGraph agent for one asset and serves PrescriptiveRecommendation
unchanged, so the dashboard reads the same contract the agent validates against.
"""

from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter, Body, Depends, Query

from backend.agent.graph import run
from backend.agent.schema import PrescriptiveRecommendation, TelemetrySnapshot
from backend.api.deps import get_asset_index, get_bundle
from backend.api.schemas import ApplyRequest, ApplyResponse, RecommendationRequest
from backend.api.store import Dataset, asset_id_for
from backend.ml.predict import predict
from backend.physics import OperatingPoint

router = APIRouter(tags=["recommendations"])

APPLIED_NOTE = (
    "Recorded, not written to the drive. This prototype has no connection to a "
    "VFD, so the figures below are the model's view of the adjusted operating "
    "point, not a confirmation that any setpoint changed.")


def _snapshot(op: OperatingPoint) -> TelemetrySnapshot:
    return TelemetrySnapshot(
        type=op.type, air_temperature=op.air_temperature,
        process_temperature=op.process_temperature,
        rotational_speed=op.rotational_speed, torque=op.torque,
        tool_wear=op.tool_wear, shaft_power_w=round(op.power_w, 1),
        temp_diff_k=round(op.temp_diff, 2))


@router.post("/datasets/{dataset_id}/assets/{asset_id}/recommendation",
             response_model=PrescriptiveRecommendation)
def asset_recommendation(
        pair: tuple[Dataset, int] = Depends(get_asset_index),
        hours_to_window: float = Query(48.0, gt=0, le=2000,
                                       description="Hours until the planned window"),
        bundle=Depends(get_bundle)) -> PrescriptiveRecommendation:
    """Run the agent for a selected asset and return the full prescription."""
    ds, index = pair
    return run(ds.operating_point(index), asset_id=asset_id_for(index),
               hours_to_window=hours_to_window, bundle=bundle)


@router.post("/recommendations", response_model=PrescriptiveRecommendation)
def ad_hoc_recommendation(req: RecommendationRequest = Body(...),
                          bundle=Depends(get_bundle)) -> PrescriptiveRecommendation:
    """Same agent, for telemetry supplied inline with no upload."""
    return run(OperatingPoint(**req.telemetry.model_dump()), asset_id=req.asset_id,
               hours_to_window=req.hours_to_window, bundle=bundle)


@router.post("/datasets/{dataset_id}/assets/{asset_id}/apply",
             response_model=ApplyResponse)
def apply_adjustment(req: ApplyRequest = Body(default=ApplyRequest()),
                     pair: tuple[Dataset, int] = Depends(get_asset_index),
                     bundle=Depends(get_bundle)) -> ApplyResponse:
    """Back the Implement Adjustment button.

    Recomputes the prescription, applies it to a copy of the operating point and
    reports the before and after. It does not claim to have changed anything on
    a real drive, and says so in applied_note.
    """
    ds, index = pair
    op = ds.operating_point(index)
    rec = run(op, asset_id=asset_id_for(index),
              hours_to_window=req.hours_to_window, bundle=bundle)

    changes = {a.parameter: a.recommended_value for a in rec.adjustments
               if a.parameter in ("torque", "rotational_speed", "tool_wear")}
    after = op.replace(**changes) if changes else op

    before_pred = predict(op, bundle=bundle, explain=False)
    after_pred = predict(after, bundle=bundle, explain=False)

    return ApplyResponse(
        asset_id=asset_id_for(index),
        accepted_at=datetime.now(timezone.utc),
        applied=False, applied_note=APPLIED_NOTE,
        adjustments=[a.model_dump() for a in rec.adjustments],
        before=_snapshot(op), after=_snapshot(after),
        failure_probability_before=round(before_pred.failure_probability, 4),
        failure_probability_after=round(after_pred.failure_probability, 4),
        rul_hours_before=before_pred.rul_hours,
        rul_hours_after=after_pred.rul_hours)
