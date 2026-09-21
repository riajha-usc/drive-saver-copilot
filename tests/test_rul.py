"""The RUL proxy is the bridge from probability to the hours the UI shows."""

import pytest

from backend import config
from backend.ml.rul import probability_to_rul_hours, risk_band


def test_mapping_is_strictly_decreasing():
    hours = [probability_to_rul_hours(p) for p in (0.01, 0.1, 0.3, 0.6, 0.9, 0.99)]
    assert hours == sorted(hours, reverse=True)


def test_mapping_stays_inside_the_declared_bounds():
    # Certainty is clamped before the log, so p = 1 reports a small number of
    # hours rather than zero. Both ends stay inside the declared range.
    assert probability_to_rul_hours(0.0) == config.RUL_MAX_H
    assert probability_to_rul_hours(1.0) < 10.0
    for p in (0.0, 0.25, 0.5, 0.75, 1.0):
        assert config.RUL_MIN_H <= probability_to_rul_hours(p) <= config.RUL_MAX_H


def test_hazard_model_matches_its_closed_form():
    # p = 0.5 over the reference horizon implies RUL = H / ln(2).
    import math
    expected = config.RUL_REFERENCE_HORIZON_H / math.log(2)
    assert probability_to_rul_hours(0.5) == pytest.approx(expected, rel=1e-3)


def test_risk_bands():
    assert risk_band(0.02) == "normal"
    assert risk_band(0.15) == "elevated"
    assert risk_band(0.45) == "high"
    assert risk_band(0.97) == "critical"
