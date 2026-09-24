"""Whole pipeline regression harness.

The other test modules pin one unit each against a hand built operating point.
This one runs the real dataset through the full graph and asserts the invariants
that have to hold for every row, not just the ones someone thought to write a
fixture for. It is the test that catches a prescription that looks reasonable in
isolation and is wrong in the field.
"""

from __future__ import annotations

import json

import pytest

from backend import physics
from backend.agent.graph import run
from backend.agent.schema import PrescriptiveRecommendation
from backend.ml.dataset import frame_from_records, load_dataset
from backend.ml.predict import predict, score_frame

SAMPLE_SIZE = 12


@pytest.fixture(scope="module")
def df():
    return load_dataset()


@pytest.fixture(scope="module")
def failing_rows(df):
    """A spread of genuinely failing rows, one batch across all modes."""
    return df[df["machine_failure"] == 1].sample(
        n=SAMPLE_SIZE, random_state=7).to_dict("records")


@pytest.fixture(scope="module")
def healthy_rows(df):
    return df[df["machine_failure"] == 0].sample(
        n=SAMPLE_SIZE, random_state=7).to_dict("records")


def _point(row) -> physics.OperatingPoint:
    return physics.OperatingPoint(
        type=row["type"], air_temperature=float(row["air_temperature"]),
        process_temperature=float(row["process_temperature"]),
        rotational_speed=float(row["rotational_speed"]),
        torque=float(row["torque"]), tool_wear=float(row["tool_wear"]))


@pytest.fixture(scope="module")
def failing_recommendations(bundle, failing_rows):
    return [(r, run(_point(r), asset_id=f"VFD-{i:03d}", hours_to_window=48, bundle=bundle))
            for i, r in enumerate(failing_rows)]


# ------------------------------------------------------------------ safety

def test_no_prescription_ever_introduces_a_new_failure(failing_recommendations):
    """The guard that matters most: a fix must not buy a different failure."""
    for row, rec in failing_recommendations:
        if not rec.adjustments:
            continue
        op = _point(row)
        moved = op.replace(**{a.parameter: a.recommended_value for a in rec.adjustments})
        introduced = set(physics.rule_failures(moved)) - set(physics.rule_failures(op))
        assert not introduced, f"{rec.asset_id} prescription introduces {introduced}"


def test_a_prescription_either_clears_the_fault_or_says_it_cannot(failing_recommendations):
    for row, rec in failing_recommendations:
        if not rec.risk.rule_violations:
            continue
        if rec.action_type == "stop_now":
            assert rec.adjustments == []
            assert any("still leaves" in c for c in rec.caveats)
        elif rec.adjustments:
            moved = _point(row).replace(
                **{a.parameter: a.recommended_value for a in rec.adjustments})
            assert not (set(rec.risk.rule_violations) & set(physics.rule_failures(moved))), \
                f"{rec.asset_id} prescribes a change that leaves the fault in place"


def test_derates_stay_inside_the_output_ceiling(failing_recommendations):
    for _, rec in failing_recommendations:
        assert rec.projection.throughput_loss_pct <= 25.0


# ------------------------------------------------------------ consistency

def test_projection_arithmetic_is_self_consistent(failing_recommendations):
    for _, rec in failing_recommendations:
        p = rec.projection
        assert p.rul_extension_hours == pytest.approx(
            p.projected_rul_hours - p.baseline_rul_hours, abs=0.15)
        assert p.risk_reduction == pytest.approx(
            p.baseline_failure_probability - p.projected_failure_probability, abs=1e-3)
        assert p.reaches_maintenance_window == (
            p.projected_rul_hours >= p.hours_to_maintenance_window)


def test_economics_arithmetic_is_self_consistent(failing_recommendations):
    for _, rec in failing_recommendations:
        e = rec.economics
        assert e.net_benefit_usd == pytest.approx(
            e.avoided_downtime_cost_usd - e.throughput_cost_usd, abs=0.02)
        assert set(e.assumptions), "every cost figure must show its assumptions"


def test_action_type_matches_the_payload_it_ships_with(failing_recommendations):
    for _, rec in failing_recommendations:
        if rec.action_type in ("no_action", "stop_now"):
            assert rec.adjustments == []
            assert rec.projection.rul_extension_hours == 0.0
            assert rec.economics.net_benefit_usd == 0.0
        else:
            assert rec.adjustments, f"{rec.action_type} must carry an adjustment"
            # A prescribed action has to buy something. Usually that is hours, but
            # when the baseline already sits at the 720 hour RUL cap there are no
            # hours left to show and the gain lands in the risk figure instead.
            assert (rec.projection.rul_extension_hours > 0
                    or rec.projection.risk_reduction > 0), \
                f"{rec.asset_id} prescribes an action that buys nothing"


def test_every_payload_round_trips_through_the_contract(failing_recommendations):
    for _, rec in failing_recommendations:
        PrescriptiveRecommendation.model_validate(json.loads(rec.model_dump_json()))


def test_every_payload_declares_the_rul_proxy(failing_recommendations):
    for _, rec in failing_recommendations:
        assert rec.risk.rul_is_proxy
        assert any("proxy" in c.lower() for c in rec.caveats)


# ------------------------------------------------------- behaviour at scale

def test_healthy_assets_are_not_alarmed(bundle, healthy_rows):
    """False alarms are the fastest way to get a tool like this switched off."""
    actions = [run(_point(r), asset_id=f"OK-{i:03d}", bundle=bundle).action_type
               for i, r in enumerate(healthy_rows)]
    assert actions.count("no_action") >= len(actions) - 1


def test_failing_assets_are_all_flagged(failing_recommendations):
    for _, rec in failing_recommendations:
        assert rec.risk.risk_band != "normal", f"{rec.asset_id} failed silently"


def test_batch_scoring_agrees_with_single_point_scoring(bundle, failing_rows):
    """The ingestion endpoint will use score_frame, the agent uses predict."""
    points = [_point(r) for r in failing_rows]
    batch = score_frame(frame_from_records(points), bundle=bundle)
    for i, op in enumerate(points):
        single = predict(op, bundle=bundle, explain=False)
        assert batch.iloc[i]["p_machine_failure"] == pytest.approx(
            single.failure_probability, abs=1e-6)
        assert batch.iloc[i]["rul_hours"] == pytest.approx(single.rul_hours, abs=0.05)
        # The band must match too: the asset list and the asset detail are the
        # same number to an operator, and they come from these two paths.
        assert batch.iloc[i]["risk_band"] == single.risk_band
        assert bool(batch.iloc[i]["rule_violated"]) == bool(single.rule_violations)
        assert batch.iloc[i]["likely_mode"] == single.likely_mode


def test_batch_scoring_names_no_mode_on_healthy_rows(bundle, healthy_rows):
    points = [_point(r) for r in healthy_rows]
    batch = score_frame(frame_from_records(points), bundle=bundle)
    healthy = batch[batch["risk_band"] == "normal"]
    assert not healthy.empty
    assert (healthy["likely_mode"] == "none").all(), \
        "an asset list must not name a failure mode on a healthy machine"


def test_the_agent_is_deterministic(bundle, overstrain_point):
    """Same telemetry in, same card out. A demo that drifts is not demoable."""
    a = run(overstrain_point, asset_id="VFD-07", hours_to_window=48, bundle=bundle)
    b = run(overstrain_point, asset_id="VFD-07", hours_to_window=48, bundle=bundle)
    # Step timings are wall clock, so they are the one part allowed to vary.
    volatile = {"generated_at", "reasoning"}
    assert a.model_dump(exclude=volatile) == b.model_dump(exclude=volatile)
    assert ([(s.node, s.title, s.detail) for s in a.reasoning]
            == [(s.node, s.title, s.detail) for s in b.reasoning])


def test_a_tighter_window_never_yields_a_weaker_action(bundle, overstrain_point):
    """Shrinking the window can only hold or raise the intervention."""
    loose = run(overstrain_point, hours_to_window=24, bundle=bundle)
    tight = run(overstrain_point, hours_to_window=120, bundle=bundle)
    assert tight.projection.projected_rul_hours >= loose.projection.projected_rul_hours
