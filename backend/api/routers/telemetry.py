"""Task 5: ingestion.

Upload a telemetry CSV, get it cleaned, feature engineered, scored and held for
the dashboard to browse. Also serves ad hoc JSON scoring for callers that have
rows in hand and no file.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, HTTPException, Query, UploadFile, status

from backend.api.deps import get_bundle, get_dataset
from backend.api.schemas import (AssetPage, AssetRow, DatasetSummary, ScoreRequest,
                                 ScoreResponse)
from backend.api.store import Dataset, asset_row, store
from backend.ml.dataset import FEATURE_COLUMNS, frame_from_records
from backend.ml.predict import score_frame
from backend.physics import rule_failures, OperatingPoint

router = APIRouter(tags=["telemetry"])

MAX_UPLOAD_BYTES = 16 * 1024 * 1024


@router.post("/datasets", response_model=DatasetSummary,
             status_code=status.HTTP_201_CREATED)
async def upload_dataset(file: UploadFile = File(..., description="Telemetry CSV"),
                         _bundle=Depends(get_bundle)) -> DatasetSummary:
    """Ingest a telemetry CSV and return prediction results for it.

    Accepts either column spelling the AI4I source ships with, bracketed units
    or stripped. Rows that are not physically usable are dropped and counted in
    rows_rejected rather than failing the whole upload.
    """
    raw = await file.read()
    if not raw:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "the uploaded file is empty")
    if len(raw) > MAX_UPLOAD_BYTES:
        raise HTTPException(413,
                            f"file exceeds {MAX_UPLOAD_BYTES // (1024 * 1024)} MB")
    try:
        ds = store.ingest_csv(raw, name=file.filename or "upload.csv")
    except ValueError as exc:
        # Bad telemetry is the caller's problem to fix, so say exactly what broke.
        # 422 by number: starlette renamed the constant, and the status code is
        # the part the dashboard actually branches on.
        raise HTTPException(422, str(exc)) from exc
    return DatasetSummary(**ds.summary())


@router.get("/datasets", response_model=list[DatasetSummary])
def list_datasets() -> list[DatasetSummary]:
    return [DatasetSummary(**d.summary()) for d in store.list()]


@router.get("/datasets/{dataset_id}", response_model=DatasetSummary)
def get_dataset_summary(ds: Dataset = Depends(get_dataset)) -> DatasetSummary:
    return DatasetSummary(**ds.summary())


@router.get("/datasets/{dataset_id}/assets", response_model=AssetPage)
def list_assets(ds: Dataset = Depends(get_dataset),
                limit: int = Query(50, ge=1, le=500),
                offset: int = Query(0, ge=0),
                sort: str = Query("risk", pattern="^(risk|index)$"),
                min_risk: float = Query(0.0, ge=0.0, le=1.0),
                band: str | None = Query(None, pattern="^(normal|elevated|high|critical)$"),
                ) -> AssetPage:
    """The asset selector feed. Sorted by risk so the ones that matter lead."""
    scores = ds.scores
    mask = scores["p_machine_failure"] >= min_risk
    if band:
        mask &= scores["risk_band"] == band
    selected = scores[mask]

    order = (selected["p_machine_failure"].sort_values(ascending=False).index
             if sort == "risk" else selected.index)
    page = list(order)[offset:offset + limit]
    return AssetPage(
        dataset_id=ds.id, total=int(len(selected)), returned=len(page), offset=offset,
        assets=[AssetRow(**asset_row(ds, int(i))) for i in page])


@router.post("/telemetry/score", response_model=ScoreResponse)
def score_rows(req: ScoreRequest, bundle=Depends(get_bundle)) -> ScoreResponse:
    """Score telemetry supplied inline, with no upload and nothing retained."""
    points = [OperatingPoint(**r.model_dump()) for r in req.rows]
    X = frame_from_records(points)
    scored = score_frame(X[FEATURE_COLUMNS], bundle=bundle)

    results = []
    for i, op in enumerate(points):
        sc = scored.iloc[i]
        results.append(AssetRow(
            asset_id=f"ROW-{i:04d}", row_index=i, type=op.type,
            air_temperature=op.air_temperature,
            process_temperature=op.process_temperature,
            rotational_speed=op.rotational_speed, torque=op.torque,
            tool_wear=op.tool_wear, shaft_power_w=round(op.power_w, 1),
            temp_diff_k=round(op.temp_diff, 2),
            failure_probability=round(float(sc["p_machine_failure"]), 4),
            risk_band=str(sc["risk_band"]), rul_hours=float(sc["rul_hours"]),
            likely_failure_mode=str(sc["likely_mode"]),
            rule_violations=rule_failures(op)))
    return ScoreResponse(count=len(results), results=results)
