"""The AI4I failure rules are the ground truth the agent reasons against."""

import pytest

from backend import physics
from backend.physics import OperatingPoint


def test_derived_quantities(healthy_point):
    assert healthy_point.temp_diff == pytest.approx(10.5)
    assert healthy_point.power_w == pytest.approx(42.8 * 1551 * physics.RPM_TO_RAD_S)
    assert healthy_point.wear_torque == pytest.approx(20 * 42.8)
    assert healthy_point.osf_limit == 12000.0


def test_healthy_point_violates_nothing(healthy_point):
    assert physics.rule_failures(healthy_point) == []
    assert all(not m.violated for m in physics.margins(healthy_point).values())


def test_osf_rule_fires_on_the_limit(overstrain_point):
    assert "OSF" in physics.rule_failures(overstrain_point)
    assert physics.margins(overstrain_point)["OSF"].margin == pytest.approx(11000 - 13120)


def test_hdf_needs_both_conditions(heat_point):
    assert "HDF" in physics.rule_failures(heat_point)
    # Same low temperature spread but a fast drive is safe, which is why the fix
    # for HDF is to speed up rather than slow down.
    faster = heat_point.replace(rotational_speed=1600)
    assert "HDF" not in physics.rule_failures(faster)


def test_pwf_is_a_two_sided_band():
    low = OperatingPoint("L", 298.0, 308.0, 1200, 20.0, 10)
    high = OperatingPoint("L", 298.0, 308.0, 2500, 45.0, 10)
    assert low.power_w < physics.PWF_POWER_MIN_W
    assert high.power_w > physics.PWF_POWER_MAX_W
    assert "PWF" in physics.rule_failures(low)
    assert "PWF" in physics.rule_failures(high)


def test_scaled_applies_percentage_deltas(healthy_point):
    trimmed = healthy_point.scaled(torque_pct=-10, speed_pct=5)
    assert trimmed.torque == pytest.approx(42.8 * 0.9)
    assert trimmed.rotational_speed == pytest.approx(1551 * 1.05)
    assert trimmed.type == healthy_point.type


def test_invalid_operating_points_are_rejected():
    with pytest.raises(ValueError):
        OperatingPoint("X", 298.0, 308.0, 1500, 40.0, 10)
    with pytest.raises(ValueError):
        OperatingPoint("L", 298.0, 308.0, 0, 40.0, 10)


def test_binding_mode_names_the_tightest_limit(overstrain_point, heat_point):
    assert physics.binding_mode(overstrain_point) in {"OSF", "TWF"}
    assert physics.binding_mode(heat_point) == "HDF"
