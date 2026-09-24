"""Task 3a: the counterfactual simulator and its safety guards."""

import pytest

from backend import physics
from backend.agent.counterfactual import MAX_DERATE_PCT, select, simulate
from backend.ml.predict import failure_probability, predict


def test_torque_cut_relieves_overstrain(bundle, overstrain_point):
    cands = simulate(overstrain_point, bundle=bundle)
    cuts = [c for c in cands
            if c.torque_pct == -20.0 and c.speed_pct == 0.0 and not c.tool_change]
    assert len(cuts) == 1
    cut = cuts[0]
    assert cut.feasible
    assert cut.risk_reduction > 0.5
    assert "OSF" not in physics.rule_failures(cut.operating_point)


def test_a_torque_cut_near_the_power_floor_is_rejected(bundle, low_power_point):
    """The headline case for the guard: the obvious fix buys a different failure."""
    assert low_power_point.power_w > physics.PWF_POWER_MIN_W
    cands = simulate(low_power_point, bundle=bundle)
    deep_cut = next(c for c in cands if c.torque_pct == -20.0 and c.speed_pct == 0.0)
    assert not deep_cut.feasible
    assert "PWF" in deep_cut.rejection
    assert "PWF" in deep_cut.new_violations


def test_no_candidate_exceeds_the_derate_ceiling(bundle, overstrain_point):
    for c in simulate(overstrain_point, bundle=bundle):
        if c.feasible:
            assert c.throughput_loss_pct <= MAX_DERATE_PCT + 1e-9


def test_heat_dissipation_is_fixed_by_speeding_up(bundle, heat_point):
    cands = simulate(heat_point, bundle=bundle)
    chosen, _ = select(cands, hours_to_window=48.0,
                       baseline_rul_hours=predict(heat_point, bundle=bundle, explain=False).rul_hours)
    assert chosen is not None
    assert chosen.speed_pct > 0
    assert chosen.throughput_loss_pct == 0.0


def test_selector_prefers_the_cheapest_option_that_clears_the_window(bundle, overstrain_point):
    base = predict(overstrain_point, bundle=bundle, explain=False)
    cands = simulate(overstrain_point, bundle=bundle)
    chosen, alts = select(cands, hours_to_window=48.0, baseline_rul_hours=base.rul_hours)
    assert chosen.rul_hours >= 48.0
    for alt in alts:
        assert alt.throughput_loss_pct >= chosen.throughput_loss_pct


def test_tool_change_is_offered_when_wear_is_present(bundle, overstrain_point):
    cands = simulate(overstrain_point, bundle=bundle)
    tool_only = [c for c in cands if c.tool_change and c.action_count == 1]
    assert len(tool_only) == 1
    assert tool_only[0].operating_point.tool_wear == 0.0
    assert tool_only[0].throughput_loss_pct == 0.0
    # And paired with every setpoint change, for faults that need both.
    paired = [c for c in cands if c.combined]
    assert len(paired) == len([c for c in cands if not c.tool_change])
    assert all(c.operating_point.tool_wear == 0.0 for c in paired)


def test_selector_returns_nothing_when_no_candidate_helps(bundle, healthy_point):
    # A healthy point has nothing to gain, so there is no action to prescribe.
    cands = simulate(healthy_point, bundle=bundle)
    chosen, alts = select([c for c in cands if c.risk_reduction <= 0], 48.0, 720.0)
    assert chosen is None and alts == []


def test_selector_will_not_prescribe_an_action_that_ignores_the_fault(bundle, heat_point):
    """A tool change scores well on the model but does nothing about heat.

    Tiering by resolved violations is what stops the cheap wrong answer winning.
    """
    base = predict(heat_point, bundle=bundle, explain=False)
    cands = simulate(heat_point, bundle=bundle)
    tool_only = next(c for c in cands if c.tool_change and c.action_count == 1)
    assert "HDF" in tool_only.remaining_violations, "fixture assumption: a tool change leaves HDF"

    chosen, _ = select(cands, 48.0, base.rul_hours, baseline_violations=base.rule_violations)
    assert not chosen.tool_change
    assert "HDF" not in chosen.remaining_violations


def test_minimal_intervention_wins_among_equally_cheap_options(bundle, heat_point):
    base = predict(heat_point, bundle=bundle, explain=False)
    cands = simulate(heat_point, bundle=bundle)
    chosen, _ = select(cands, 48.0, base.rul_hours, baseline_violations=base.rule_violations)
    same_cost = [c for c in cands
                 if c.feasible and not c.remaining_violations and c.risk_reduction > 0
                 and c.rul_hours >= 48.0
                 and round(c.throughput_loss_pct, 2) == round(chosen.throughput_loss_pct, 2)]
    assert chosen.magnitude == min(c.magnitude for c in same_cost)


def test_uprating_is_offered_when_the_drive_is_under_loaded(bundle, unfixable_point):
    cands = simulate(unfixable_point, bundle=bundle)
    assert any(c.torque_pct > 0 for c in cands), "grid must include torque increases"
    # But not without bound.
    for c in cands:
        if c.feasible:
            rise = (c.operating_point.power_w - unfixable_point.power_w) / unfixable_point.power_w * 100
            assert rise <= 30.0 + 1e-9



# ------------------------------------------------------------ combined fixes

def test_a_fault_needing_two_kinds_of_fix_gets_both(bundle, two_kind_point):
    base = predict(two_kind_point, bundle=bundle, explain=False)
    assert set(base.rule_violations) == {"HDF", "TWF"}, "fixture assumption"

    cands = simulate(two_kind_point, bundle=bundle)
    # No single kind of fix can clear both limits...
    singles = [c for c in cands if c.feasible and c.action_count == 1]
    assert all(c.remaining_violations for c in singles)

    # ...so the selector reaches for a pair, and the pair clears everything.
    chosen, _ = select(cands, 48.0, base.rul_hours, baseline_violations=base.rule_violations)
    assert chosen.combined
    assert chosen.speed_pct > 0
    assert not chosen.remaining_violations


def test_a_single_fix_is_never_padded_with_a_tool_change(bundle, heat_point, overstrain_point):
    for op in (heat_point, overstrain_point):
        base = predict(op, bundle=bundle, explain=False)
        chosen, _ = select(simulate(op, bundle=bundle), 48.0, base.rul_hours,
                           baseline_violations=base.rule_violations)
        assert chosen.action_count == 1


def test_batch_scoring_matches_one_at_a_time(bundle, overstrain_point, heat_point,
                                            two_kind_point):
    from backend.ml.predict import failure_probabilities
    ops = [overstrain_point, heat_point, two_kind_point]
    batch = failure_probabilities(ops, bundle=bundle)
    for op, p in zip(ops, batch):
        assert p == pytest.approx(failure_probability(op, bundle=bundle), abs=1e-9)
