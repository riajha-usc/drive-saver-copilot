"""Request and response models for the HTTP layer.

The prescriptive payload itself is not redefined here. It is
backend.agent.schema.PrescriptiveRecommendation, served unchanged, so the
dashboard codes against one contract whether it reads it from the API or from
`python -m backend.demo --json`.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from backend.agent.schema import RiskBand, TelemetrySnapshot


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid")


class HealthResponse(Strict):
    status: Literal["ok", "degraded"]
    model_loaded: bool
    model_trained_at: str = ""
    datasets_loaded: int = 0
    detail: str = ""


class ModelInfo(Strict):
    trained_at: str
    feature_columns: list[str]
    heads: list[str]
    thresholds: dict[str, float]
    metrics: dict
    rul_reference_horizon_hours: float
    rul_cap_hours: float
    rul_is_proxy: bool = True
    rul_note: str


class TelemetryInput(Strict):
    """One operating point, the minimum the model needs."""

    type: Literal["L", "M", "H"] = Field(description="Product quality class")
    air_temperature: float = Field(description="K")
    process_temperature: float = Field(description="K")
    rotational_speed: float = Field(gt=0, description="rpm")
    torque: float = Field(ge=0, description="Nm")
    tool_wear: float = Field(ge=0, description="min")


class AssetRow(Strict):
    """A scored telemetry sample, for the asset selector and the charts."""

    asset_id: str
    row_index: int
    type: str
    air_temperature: float
    process_temperature: float
    rotational_speed: float
    torque: float
    tool_wear: float
    shaft_power_w: float
    temp_diff_k: float
    failure_probability: float
    risk_band: RiskBand
    rul_hours: float
    likely_failure_mode: str
    rule_violations: list[str]


class DatasetSummary(Strict):
    dataset_id: str
    name: str
    uploaded_at: datetime
    row_count: int
    rows_rejected: int
    at_risk_count: int
    risk_band_counts: dict[str, int]
    highest_risk_asset: str | None


class AssetPage(Strict):
    dataset_id: str
    total: int
    returned: int
    offset: int
    assets: list[AssetRow]


class MarginOut(Strict):
    mode: str
    label: str
    value: float
    limit: float
    margin: float
    unit: str
    violated: bool


class FactorOut(Strict):
    feature: str
    label: str
    value: float
    unit: str
    shap_value: float
    direction: str
    share_of_risk: float


class AssetDetail(Strict):
    """Everything the alert box and the root cause panel need for one asset."""

    dataset_id: str
    asset: AssetRow
    mode_probabilities: dict[str, float]
    likely_failure_mode_name: str
    dominant_lever: str
    margins: list[MarginOut]
    factors: list[FactorOut]


class HistoryPoint(Strict):
    row_index: int
    asset_id: str
    air_temperature: float
    process_temperature: float
    rotational_speed: float
    torque: float
    shaft_power_w: float
    tool_wear: float
    failure_probability: float
    risk_band: RiskBand


class HistoryResponse(Strict):
    dataset_id: str
    asset_id: str
    window: int
    note: str
    points: list[HistoryPoint]


class ScoreRequest(Strict):
    rows: list[TelemetryInput] = Field(min_length=1, max_length=5000)


class ScoreResponse(Strict):
    count: int
    results: list[AssetRow]


class RecommendationRequest(Strict):
    telemetry: TelemetryInput
    asset_id: str = "MOTOR-01"
    hours_to_window: float = Field(default=48.0, gt=0, le=2000)


class ApplyRequest(Strict):
    """Records the operator accepting a prescription. The prototype does not
    talk to a real drive, so this reports the resulting operating point rather
    than claiming the setpoint was written."""

    hours_to_window: float = Field(default=48.0, gt=0, le=2000)
    note: str = ""


class ApplyResponse(Strict):
    asset_id: str
    accepted_at: datetime
    applied: bool = False
    applied_note: str
    adjustments: list[dict]
    before: TelemetrySnapshot
    after: TelemetrySnapshot
    failure_probability_before: float
    failure_probability_after: float
    rul_hours_before: float
    rul_hours_after: float
