"""Asset detail and telemetry history, for the alert box and the charts."""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from backend.api.deps import get_asset_index, get_bundle
from backend.api.schemas import (AssetDetail, AssetRow, FactorOut, HistoryPoint,
                                 HistoryResponse, MarginOut)
from backend.api.store import Dataset, asset_id_for, asset_row
from backend.ml.predict import predict

router = APIRouter(tags=["assets"])

HISTORY_NOTE = (
    "AI4I 2020 rows are independent snapshots, not a time series. These are the "
    "dataset rows leading up to the selected one, presented in order so the "
    "dashboard has a telemetry trace to plot. Read it as recent samples from the "
    "line, not as this one machine over time.")


@router.get("/datasets/{dataset_id}/assets/{asset_id}", response_model=AssetDetail)
def asset_detail(pair: tuple[Dataset, int] = Depends(get_asset_index),
                 bundle=Depends(get_bundle)) -> AssetDetail:
    """Risk, per mode probabilities, physical margins and the SHAP root cause."""
    ds, index = pair
    op = ds.operating_point(index)
    pred = predict(op, bundle=bundle, explain=True)

    return AssetDetail(
        dataset_id=ds.id,
        asset=AssetRow(**asset_row(ds, index)),
        mode_probabilities={k: round(v, 4) for k, v in pred.mode_probabilities.items()},
        likely_failure_mode_name=pred.likely_mode_name,
        dominant_lever=pred.dominant_lever,
        margins=[MarginOut(mode=m.mode, label=m.label, value=round(m.value, 2),
                           limit=m.limit, margin=round(m.margin, 2), unit=m.unit,
                           violated=m.violated) for m in pred.margins.values()],
        factors=[FactorOut(feature=a.feature, label=a.label, value=a.value,
                           unit=a.unit, shap_value=a.shap_value,
                           direction=a.direction, share_of_risk=a.share_of_risk)
                 for a in pred.attributions])


@router.get("/datasets/{dataset_id}/assets/{asset_id}/history",
            response_model=HistoryResponse)
def asset_history(pair: tuple[Dataset, int] = Depends(get_asset_index),
                  window: int = Query(60, ge=2, le=500)) -> HistoryResponse:
    """Telemetry trace for the temperature, speed and torque charts."""
    ds, index = pair
    start = max(0, index - window + 1)

    points = []
    for i in range(start, index + 1):
        tel = ds.frame.iloc[i]
        sc = ds.scores.iloc[i]
        points.append(HistoryPoint(
            row_index=i, asset_id=asset_id_for(i),
            air_temperature=float(tel["air_temperature"]),
            process_temperature=float(tel["process_temperature"]),
            rotational_speed=float(tel["rotational_speed"]),
            torque=float(tel["torque"]),
            shaft_power_w=round(float(tel["power_w"]), 1),
            tool_wear=float(tel["tool_wear"]),
            failure_probability=round(float(sc["p_machine_failure"]), 4),
            risk_band=str(sc["risk_band"])))

    return HistoryResponse(dataset_id=ds.id, asset_id=asset_id_for(index),
                           window=len(points), note=HISTORY_NOTE, points=points)
