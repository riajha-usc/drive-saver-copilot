"""Task 4: the output contract the API and the dashboard code against."""

import pytest
from pydantic import ValidationError

from backend.agent.schema import (PrescriptiveRecommendation, RiskAssessment,
                                  TelemetrySnapshot)


def _risk(**overrides):
    base = dict(failure_probability=0.9, risk_band="critical", rul_hours=16.3,
                likely_failure_mode="OSF", likely_failure_mode_name="Overstrain Failure",
                mode_probabilities={"OSF": 0.9})
    base.update(overrides)
    return base


def test_probabilities_are_bounded():
    with pytest.raises(ValidationError):
        RiskAssessment(**_risk(failure_probability=1.4))


def test_risk_band_is_a_closed_set():
    with pytest.raises(ValidationError):
        RiskAssessment(**_risk(risk_band="spicy"))


def test_failure_mode_is_a_closed_set():
    with pytest.raises(ValidationError):
        RiskAssessment(**_risk(likely_failure_mode="GREMLINS"))


def test_unknown_fields_are_rejected():
    with pytest.raises(ValidationError):
        RiskAssessment(**_risk(), extra_field=1)


def test_telemetry_rejects_impossible_physics():
    with pytest.raises(ValidationError):
        TelemetrySnapshot(type="L", air_temperature=298.0, process_temperature=308.0,
                          rotational_speed=0, torque=40.0, tool_wear=10.0,
                          shaft_power_w=0.0, temp_diff_k=10.0)


def test_schema_version_is_pinned():
    assert PrescriptiveRecommendation.model_fields["schema_version"].default == "1.0"
