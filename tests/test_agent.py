"""Task 3 and 4 end to end: the LangGraph agent and its validated payload."""

import json

import pytest

from backend.agent import graph
from backend.agent.llm import deterministic_narration
from backend.agent.schema import PrescriptiveRecommendation


def test_graph_nodes_are_wired_in_order():
    nodes = set(graph.build_graph().get_graph().nodes)
    assert {"ingest", "diagnose", "simulate", "decide", "narrate", "validate"} <= nodes


def test_trace_records_every_stage(bundle, overstrain_point):
    _, trace = graph.run(overstrain_point, asset_id="VFD-01", bundle=bundle, return_trace=True)
    assert [t.split()[0] for t in trace] == ["ingest", "diagnose", "simulate", "decide",
                                             "narrate", "validate"]


def test_overstrain_asset_gets_an_actionable_prescription(bundle, overstrain_point):
    rec = graph.run(overstrain_point, asset_id="VFD-07", hours_to_window=48, bundle=bundle)
    assert isinstance(rec, PrescriptiveRecommendation)
    assert rec.risk.risk_band == "critical"
    assert rec.risk.likely_failure_mode == "OSF"
    assert rec.action_type in {"derate", "schedule_maintenance", "reconfigure"}
    assert rec.adjustments, "an at risk asset must carry at least one adjustment"
    assert rec.projection.rul_extension_hours > 0
    assert rec.projection.reaches_maintenance_window
    assert rec.economics.net_benefit_usd > 0
    assert rec.narrative.headline and rec.narrative.operator_instruction


def test_heat_case_prescribes_speeding_up_not_slowing_down(bundle, heat_point):
    rec = graph.run(heat_point, asset_id="VFD-09", hours_to_window=48, bundle=bundle)
    assert rec.risk.likely_failure_mode == "HDF"
    speed = [a for a in rec.adjustments if a.parameter == "rotational_speed"]
    assert speed and speed[0].change_pct > 0
    assert rec.projection.throughput_loss_pct == 0.0


def test_healthy_asset_gets_no_action(bundle, healthy_point):
    rec = graph.run(healthy_point, asset_id="VFD-02", bundle=bundle)
    assert rec.action_type == "no_action"
    assert rec.adjustments == []
    assert rec.projection.rul_extension_hours == 0.0
    assert rec.economics.net_benefit_usd == 0.0
    assert "No action needed" in rec.narrative.headline


def test_prescription_never_recommends_a_move_that_breaks_another_limit(bundle, low_power_point):
    from backend import physics
    rec = graph.run(low_power_point, asset_id="VFD-11", bundle=bundle)
    if rec.adjustments:
        new = low_power_point.replace(
            **{a.parameter: a.recommended_value for a in rec.adjustments
               if a.parameter in ("torque", "rotational_speed", "tool_wear")})
        introduced = set(physics.rule_failures(new)) - set(physics.rule_failures(low_power_point))
        assert not introduced, f"prescription introduced {introduced}"


def test_payload_is_json_serialisable_for_the_api(bundle, overstrain_point):
    rec = graph.run(overstrain_point, asset_id="VFD-07", bundle=bundle)
    payload = json.loads(rec.model_dump_json())
    assert payload["schema_version"] == "1.0"
    # Round trips cleanly, which is what the dashboard contract depends on.
    PrescriptiveRecommendation.model_validate(payload)


def test_caveats_always_flag_the_rul_proxy(bundle, overstrain_point, healthy_point):
    for op in (overstrain_point, healthy_point):
        rec = graph.run(op, bundle=bundle)
        assert any("proxy" in c.lower() for c in rec.caveats)


def test_narration_falls_back_to_the_template_without_a_key(monkeypatch, bundle, overstrain_point):
    monkeypatch.setattr("backend.config.ANTHROPIC_API_KEY", None)
    rec = graph.run(overstrain_point, bundle=bundle)
    assert rec.narrative.generated_by == "deterministic"


def test_deterministic_narrator_avoids_em_dashes(bundle, overstrain_point):
    rec = graph.run(overstrain_point, bundle=bundle)
    text = " ".join([rec.narrative.headline, rec.narrative.explanation,
                     rec.narrative.operator_instruction])
    assert "\u2014" not in text, "em dash found in operator facing text"


def test_unfixable_fault_stops_the_asset_rather_than_derating(bundle, unfixable_point):
    rec = graph.run(unfixable_point, asset_id="VFD-13", hours_to_window=48, bundle=bundle)
    assert rec.action_type == "stop_now"
    # The card must not promise hours it cannot deliver.
    assert rec.adjustments == []
    assert rec.projection.rul_extension_hours == 0.0
    assert rec.projection.projected_rul_hours == rec.projection.baseline_rul_hours
    assert rec.economics.net_benefit_usd == 0.0
    assert not rec.projection.reaches_maintenance_window
    assert any("still leaves PWF" in c for c in rec.caveats)
    # The palliative option is still visible, just not prescribed.
    assert rec.alternatives


def test_heat_prescription_actually_clears_the_heat_fault(bundle, heat_point):
    from backend import physics
    rec = graph.run(heat_point, asset_id="VFD-09", bundle=bundle)
    new = heat_point.replace(**{a.parameter: a.recommended_value for a in rec.adjustments})
    assert "HDF" not in physics.rule_failures(new)


def test_no_action_asset_reports_reaching_the_window(bundle, healthy_point):
    rec = graph.run(healthy_point, hours_to_window=48, bundle=bundle)
    assert rec.projection.reaches_maintenance_window
    assert rec.risk.likely_failure_mode == "none"
    assert rec.root_cause.primary_driver == "none"
    assert rec.root_cause.controllable_lever == "none"


# ------------------------------------------------------------ reasoning steps

NODES = ["ingest", "diagnose", "simulate", "decide", "narrate", "validate"]


def test_reasoning_lists_every_node_in_order(bundle, overstrain_point):
    rec = graph.run(overstrain_point, bundle=bundle)
    assert [s.node for s in rec.reasoning] == NODES
    assert all(s.title and s.detail and s.duration_ms >= 0 for s in rec.reasoning)


def test_reasoning_reports_what_the_simulation_rejected(bundle, overstrain_point):
    rec = graph.run(overstrain_point, bundle=bundle)
    simulate = next(s for s in rec.reasoning if s.node == "simulate")
    assert "Tested" in simulate.detail and "rejected" in simulate.detail
    # The overstrain point is near the power ceiling, so some speed increases
    # are thrown out for causing a Power Failure; the step should say so.
    assert "Power Failure" in simulate.detail


def test_reasoning_matches_the_decision(bundle, overstrain_point, healthy_point,
                                        unfixable_point):
    fix = graph.run(overstrain_point, hours_to_window=48, bundle=bundle)
    decide = next(s for s in fix.reasoning if s.node == "decide")
    assert "48 hour window" in decide.detail

    healthy = graph.run(healthy_point, bundle=bundle)
    assert next(s for s in healthy.reasoning if s.node == "simulate").title.startswith("Skipped")
    assert "no action" in next(s for s in healthy.reasoning if s.node == "decide").title

    stop = graph.run(unfixable_point, bundle=bundle)
    assert "PWF" in next(s for s in stop.reasoning if s.node == "decide").detail


def test_reasoning_says_who_wrote_the_explanation(monkeypatch, bundle, overstrain_point):
    monkeypatch.setattr("backend.config.ANTHROPIC_API_KEY", None)
    rec = graph.run(overstrain_point, bundle=bundle)
    narrate = next(s for s in rec.reasoning if s.node == "narrate")
    assert "template" in narrate.detail



def test_combined_fix_reaches_the_card_with_both_actions(bundle, two_kind_point):
    rec = graph.run(two_kind_point, hours_to_window=48, bundle=bundle)
    assert rec.action_type == "schedule_maintenance"
    params = {a.parameter for a in rec.adjustments}
    assert "tool_wear" in params and "rotational_speed" in params
    # Applying every adjustment clears every breached limit.
    from backend import physics
    moved = two_kind_point.replace(**{a.parameter: a.recommended_value for a in rec.adjustments})
    assert not physics.rule_failures(moved)
    # The card is honest that the tool change is not immediate.
    assert any("already done" in c for c in rec.caveats)
    assert "next line stop" in rec.narrative.operator_instruction


def test_headlines_never_exceed_the_schema_limit():
    from backend.agent.llm import HEADLINE_MAX, _fit
    long = "Reduce torque by 17.5 percent and raise speed by 20.0 percent " * 4
    fitted = _fit(long)
    assert len(fitted) <= HEADLINE_MAX
    assert fitted.endswith("...")
    assert _fit("short") == "short"
