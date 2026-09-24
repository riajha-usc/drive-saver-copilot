"""Task 4: the strict output contract.

Everything the agent emits is validated against PrescriptiveRecommendation before
it leaves the process, so the API layer and the dashboard can rely on the shape.
Numbers are rounded at the boundary; the UI should render them as given.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

RiskBand = Literal["normal", "elevated", "high", "critical"]
FailureMode = Literal["HDF", "PWF", "OSF", "TWF", "none"]
ActionType = Literal["derate", "reconfigure", "schedule_maintenance", "no_action", "stop_now"]


class Strict(BaseModel):
    model_config = ConfigDict(extra="forbid", validate_assignment=True)


class TelemetrySnapshot(Strict):
    type: Literal["L", "M", "H"] = Field(description="Product quality class")
    air_temperature: float = Field(description="K")
    process_temperature: float = Field(description="K")
    rotational_speed: float = Field(gt=0, description="rpm")
    torque: float = Field(ge=0, description="Nm")
    tool_wear: float = Field(ge=0, description="min")
    shaft_power_w: float = Field(description="Derived mechanical power, W")
    temp_diff_k: float = Field(description="Process minus air temperature, K")


class RiskAssessment(Strict):
    failure_probability: float = Field(ge=0, le=1)
    risk_band: RiskBand
    rul_hours: float = Field(ge=0, description="Proxy RUL, see backend/ml/rul.py")
    rul_is_proxy: bool = True
    likely_failure_mode: FailureMode
    likely_failure_mode_name: str
    mode_probabilities: dict[str, float]
    rule_violations: list[str] = Field(default_factory=list)


class RootCauseFactor(Strict):
    feature: str
    label: str
    value: float
    unit: str
    shap_value: float
    direction: Literal["raises risk", "lowers risk"]
    share_of_risk: float = Field(ge=0, le=1)


class RootCause(Strict):
    summary: str
    primary_driver: str
    primary_driver_share: float = Field(ge=0, le=1)
    controllable_lever: Literal["torque", "speed", "ambient", "maintenance", "fixed", "none"]
    physical_margin: str = Field(description="Distance to the binding physical limit")
    factors: list[RootCauseFactor]


class ParameterAdjustment(Strict):
    parameter: Literal["torque", "rotational_speed", "tool_wear"]
    label: str
    current_value: float
    recommended_value: float
    unit: str
    change_pct: float


class Projection(Strict):
    baseline_rul_hours: float
    projected_rul_hours: float
    rul_extension_hours: float
    baseline_failure_probability: float = Field(ge=0, le=1)
    projected_failure_probability: float = Field(ge=0, le=1)
    risk_reduction: float
    throughput_loss_pct: float = Field(ge=0, le=100)
    reaches_maintenance_window: bool
    hours_to_maintenance_window: float


class Economics(Strict):
    avoided_downtime_cost_usd: float
    throughput_cost_usd: float
    net_benefit_usd: float
    assumptions: dict[str, float]


class Narrative(Strict):
    headline: str
    explanation: str
    operator_instruction: str
    generated_by: Literal["llm", "deterministic"]


class ReasoningStep(Strict):
    """One node of the agent, as an operator would read it."""

    node: Literal["ingest", "diagnose", "simulate", "decide", "narrate", "validate"]
    title: str
    detail: str
    duration_ms: float = Field(ge=0)


class PrescriptiveRecommendation(Strict):
    """Top level payload served to the dashboard."""

    schema_version: Literal["1.0"] = "1.0"
    asset_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    model_trained_at: str = ""

    telemetry: TelemetrySnapshot
    risk: RiskAssessment
    root_cause: RootCause
    action_type: ActionType
    adjustments: list[ParameterAdjustment]
    projection: Projection
    economics: Economics
    narrative: Narrative

    alternatives: list[dict] = Field(default_factory=list,
                                     description="Other simulated options, best first")
    confidence: float = Field(ge=0, le=1)
    caveats: list[str] = Field(default_factory=list)
    reasoning: list[ReasoningStep] = Field(
        default_factory=list,
        description="The agent's steps in order, with what each one found")
