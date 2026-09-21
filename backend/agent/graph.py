"""Task 3: the LangGraph prescriptive agent.

    ingest -> diagnose -> simulate -> decide -> narrate -> validate

Each node is a pure function over the shared state, so any step can be unit
tested on its own and the whole graph runs offline. The LLM appears in exactly
one node (narrate) and only ever writes prose; every number in the payload is
produced by the model, the physics rules or the cost model.

Entry point: run(telemetry, asset_id, hours_to_window) -> PrescriptiveRecommendation
"""

from __future__ import annotations

from typing import Annotated, Any, TypedDict

from langgraph.graph import END, START, StateGraph

from backend import physics
from backend.agent import economics
from backend.agent.counterfactual import Candidate, select, simulate
from backend.agent.llm import llm_narration
from backend.agent.schema import (Economics, Narrative, ParameterAdjustment,
                                  PrescriptiveRecommendation, Projection, RiskAssessment,
                                  RootCause, RootCauseFactor, TelemetrySnapshot)
from backend.ml.predict import MODE_NAMES, Prediction, load_bundle, predict

# Below this probability there is nothing worth prescribing.
ACTION_THRESHOLD = 0.10
# Above this, a derate is no longer a responsible answer on its own.
STOP_THRESHOLD = 0.95


class AgentState(TypedDict, total=False):
    asset_id: str
    hours_to_window: float
    operating_point: physics.OperatingPoint
    bundle: Any
    prediction: Prediction
    candidates: list[Candidate]
    chosen: Candidate | None
    alternatives: list[Candidate]
    unresolved: list[str]
    action_type: str
    context: dict
    narrative: Narrative
    recommendation: PrescriptiveRecommendation
    trace: Annotated[list[str], lambda a, b: a + b]


# ---------------------------------------------------------------- nodes

def ingest(state: AgentState) -> dict:
    """Bind the trained bundle and normalise the incoming telemetry."""
    bundle = state.get("bundle") or load_bundle()
    return {"bundle": bundle, "trace": ["ingest"]}


def diagnose(state: AgentState) -> dict:
    """Task 1 and 2 combined: risk, RUL proxy, SHAP root cause, physical margins."""
    pred = predict(state["operating_point"], bundle=state["bundle"], explain=True)
    return {"prediction": pred, "trace": [f"diagnose p={pred.failure_probability:.3f}"]}


def simulate_node(state: AgentState) -> dict:
    """Run the counterfactual grid, unless the asset is already healthy."""
    pred = state["prediction"]
    # A breached limit always earns a simulation, however low the model reads.
    if pred.failure_probability < ACTION_THRESHOLD and not pred.rule_violations:
        return {"candidates": [], "trace": ["simulate skipped, risk below action threshold"]}
    cands = simulate(state["operating_point"], bundle=state["bundle"])
    return {"candidates": cands, "trace": [f"simulate {len(cands)} candidates"]}


def decide(state: AgentState) -> dict:
    """Pick the smallest intervention that carries the asset to the window."""
    pred = state["prediction"]
    if not state.get("candidates"):
        return {"chosen": None, "alternatives": [], "action_type": "no_action",
                "trace": ["decide no_action"]}

    chosen, alts = select(state["candidates"], state["hours_to_window"], pred.rul_hours,
                          baseline_violations=pred.rule_violations)
    unresolved = set(pred.rule_violations) & set(chosen.remaining_violations) if chosen else set()
    if chosen is None:
        action = "stop_now"
    elif unresolved:
        # A limit is genuinely breached and no setpoint inside the drive's range
        # clears it. Probability is beside the point here: the fault is real, so
        # a derate would only dress it up.
        action = "stop_now"
    elif pred.failure_probability >= STOP_THRESHOLD and chosen.rul_hours < state["hours_to_window"]:
        action = "stop_now"
    elif chosen.action_type == "schedule_maintenance":
        action = "schedule_maintenance"
    elif chosen.speed_pct > 0:
        # Raising speed is a reconfiguration, not a derate, and costs no output.
        action = "reconfigure"
    else:
        action = "derate"
    if action == "stop_now" and chosen is not None:
        # Nothing on the drive is a prescription any more. The best candidate is
        # demoted to a palliative option so the card cannot claim hours it will
        # not deliver, but the operator can still see it.
        alts = [chosen, *alts][:4]
        chosen = None

    return {"chosen": chosen, "alternatives": alts, "action_type": action,
            "unresolved": sorted(unresolved), "trace": [f"decide {action}"]}


def _adjustments(op: physics.OperatingPoint, chosen: Candidate | None) -> list[ParameterAdjustment]:
    if chosen is None:
        return []
    out = []
    new = chosen.operating_point
    if chosen.torque_pct:
        out.append(ParameterAdjustment(
            parameter="torque", label="VFD torque setpoint",
            current_value=round(op.torque, 2), recommended_value=round(new.torque, 2),
            unit="Nm", change_pct=round(chosen.torque_pct, 2)))
    if chosen.speed_pct:
        out.append(ParameterAdjustment(
            parameter="rotational_speed", label="VFD speed setpoint",
            current_value=round(op.rotational_speed, 1), recommended_value=round(new.rotational_speed, 1),
            unit="rpm", change_pct=round(chosen.speed_pct, 2)))
    if chosen.action_type == "schedule_maintenance":
        out.append(ParameterAdjustment(
            parameter="tool_wear", label="Tool wear at next line stop",
            current_value=round(op.tool_wear, 1), recommended_value=0.0,
            unit="min", change_pct=-100.0))
    return out


def narrate(state: AgentState) -> dict:
    """The only node that touches an LLM, and it only writes prose."""
    pred, chosen = state["prediction"], state.get("chosen")
    pushing = [a for a in pred.attributions if a.shap_value > 0]
    top = pushing[0] if pushing else None
    binding = pred.margins[physics.binding_mode(state["operating_point"])]

    ctx = {
        "asset_id": state["asset_id"],
        "action_type": state["action_type"],
        "risk_band": pred.risk_band,
        "failure_probability_pct": f"{pred.failure_probability * 100:.1f} percent",
        "mode_name": pred.likely_mode_name,
        "baseline_rul_hours": pred.rul_hours,
        "hours_to_window": state["hours_to_window"],
        "primary_driver": top.label if top else "no single dominant driver",
        "primary_driver_share_pct": f"{(top.share_of_risk * 100 if top else 0):.0f} percent",
        "physical_margin": (f"{binding.label} has {binding.margin:.1f} {binding.unit} of headroom"
                            if not binding.violated else
                            f"{binding.label} is past the limit by {abs(binding.margin):.1f} {binding.unit}"),
        "rule_violations": ", ".join(pred.rule_violations) or "none",
        "adjustment_summary": chosen.description if chosen else "Hold current setpoints",
        "projected_rul_hours": chosen.rul_hours if chosen else pred.rul_hours,
        "rul_extension_hours": round(chosen.rul_gain_hours, 1) if chosen else 0.0,
        "throughput_loss_pct": round(chosen.throughput_loss_pct, 1) if chosen else 0.0,
        "unresolved": ", ".join(state.get("unresolved", [])) or "the fault",
    }
    narration, source = llm_narration(ctx)
    return {"context": ctx,
            "narrative": Narrative(**narration.model_dump(), generated_by=source),
            "trace": [f"narrate via {source}"]}


def _confidence(pred: Prediction, chosen: Candidate | None) -> float:
    """How much to trust this card: sharp model output plus rule agreement."""
    p = pred.failure_probability
    sharpness = abs(p - 0.5) * 2                       # 0 at the decision boundary
    agreement = 1.0 if (bool(pred.rule_violations) == (p >= 0.5)) else 0.55
    coverage = 1.0 if chosen else 0.8
    return round(min(0.99, max(0.2, sharpness * 0.5 + 0.4 * agreement + 0.1 * coverage)), 2)


def _caveats(state: AgentState, chosen: Candidate | None) -> list[str]:
    pred = state["prediction"]
    out = ["Remaining useful life is a proxy derived from failure probability through a "
           "constant hazard model. AI4I 2020 carries no run to failure timeline."]
    if chosen and chosen.rul_hours >= 719.9:
        out.append("Projected life is reported at the 720 hour cap, not an extrapolated value.")
    if "TWF" in pred.rule_violations:
        out.append("Tool wear is inside the 200 to 240 minute change window. No VFD trim "
                   "removes wear, so a tool change is the only durable fix.")
    if chosen and chosen.throughput_loss_pct > 10:
        out.append(f"This action gives up {chosen.throughput_loss_pct:.1f} percent of shaft output. "
                   "Confirm the line can absorb it before applying.")
    if state.get("unresolved"):
        out.append(f"No available setpoint change clears {', '.join(state['unresolved'])}. "
                   "The action below buys time, it does not remove the fault.")
    if pred.rule_violations and pred.failure_probability < ACTION_THRESHOLD:
        out.append(f"The model reads this asset as low risk, but "
                   f"{', '.join(pred.rule_violations)} is breached on the telemetry. "
                   "The breached limit is the fact, the score is the estimate.")
    if pred.likely_mode == "TWF":
        out.append("The tool wear head is weak on this dataset (PR AUC 0.07) because the "
                   "failure point inside the wear window is random by construction.")
    return out


def validate(state: AgentState) -> dict:
    """Task 4: assemble and enforce the strict output contract."""
    op, pred, chosen = state["operating_point"], state["prediction"], state.get("chosen")
    binding = pred.margins[physics.binding_mode(op)]

    projection = Projection(
        baseline_rul_hours=pred.rul_hours,
        projected_rul_hours=chosen.rul_hours if chosen else pred.rul_hours,
        rul_extension_hours=round(chosen.rul_gain_hours, 1) if chosen else 0.0,
        baseline_failure_probability=round(pred.failure_probability, 4),
        projected_failure_probability=round(chosen.failure_probability if chosen
                                            else pred.failure_probability, 4),
        risk_reduction=round(chosen.risk_reduction if chosen else 0.0, 4),
        throughput_loss_pct=round(chosen.throughput_loss_pct if chosen else 0.0, 2),
        reaches_maintenance_window=bool(
            (chosen.rul_hours if chosen else pred.rul_hours) >= state["hours_to_window"]),
        hours_to_maintenance_window=state["hours_to_window"],
    )
    econ = economics.value_of_action(
        risk_reduction=projection.risk_reduction,
        throughput_loss_pct=projection.throughput_loss_pct,
        hours_to_window=state["hours_to_window"],
    )
    # Only a feature pushing risk UP can be a root cause. On a healthy asset every
    # attribution is negative, so there is nothing to blame.
    pushing = [a for a in pred.attributions if a.shap_value > 0]
    top = pushing[0] if pushing else None

    rec = PrescriptiveRecommendation(
        asset_id=state["asset_id"],
        model_trained_at=getattr(state["bundle"], "trained_at", ""),
        telemetry=TelemetrySnapshot(
            type=op.type, air_temperature=op.air_temperature,
            process_temperature=op.process_temperature, rotational_speed=op.rotational_speed,
            torque=op.torque, tool_wear=op.tool_wear,
            shaft_power_w=round(op.power_w, 1), temp_diff_k=round(op.temp_diff, 2)),
        risk=RiskAssessment(
            failure_probability=round(pred.failure_probability, 4),
            risk_band=pred.risk_band, rul_hours=pred.rul_hours,
            likely_failure_mode=pred.likely_mode if pred.likely_mode in MODE_NAMES else "none",
            likely_failure_mode_name=pred.likely_mode_name,
            mode_probabilities={k: round(v, 4) for k, v in pred.mode_probabilities.items()},
            rule_violations=pred.rule_violations),
        root_cause=RootCause(
            summary=(f"{top.label} is the dominant contributor at "
                     f"{top.share_of_risk * 100:.0f} percent of the upward risk push"
                     if top else "No feature is pushing this asset toward failure"),
            primary_driver=top.label if top else "none",
            primary_driver_share=round(top.share_of_risk, 4) if top else 0.0,
            controllable_lever=(pred.dominant_lever if top and pred.dominant_lever in
                                ("torque", "speed", "ambient", "maintenance", "fixed") else "none"),
            physical_margin=state["context"]["physical_margin"],
            factors=[RootCauseFactor(
                feature=a.feature, label=a.label, value=a.value, unit=a.unit,
                shap_value=a.shap_value, direction=a.direction,
                share_of_risk=a.share_of_risk) for a in pred.attributions]),
        action_type=state["action_type"],
        adjustments=_adjustments(op, chosen),
        projection=projection,
        economics=Economics(**econ),
        narrative=state["narrative"],
        alternatives=[c.as_dict() for c in state.get("alternatives", [])],
        confidence=_confidence(pred, chosen),
        caveats=_caveats(state, chosen),
    )
    return {"recommendation": rec, "trace": ["validate ok"]}


# ---------------------------------------------------------------- graph

def build_graph():
    g = StateGraph(AgentState)
    g.add_node("ingest", ingest)
    g.add_node("diagnose", diagnose)
    g.add_node("simulate", simulate_node)
    g.add_node("decide", decide)
    g.add_node("narrate", narrate)
    g.add_node("validate", validate)

    g.add_edge(START, "ingest")
    g.add_edge("ingest", "diagnose")
    g.add_edge("diagnose", "simulate")
    g.add_edge("simulate", "decide")
    g.add_edge("decide", "narrate")
    g.add_edge("narrate", "validate")
    g.add_edge("validate", END)
    return g.compile()


_GRAPH = None


def get_graph():
    global _GRAPH
    if _GRAPH is None:
        _GRAPH = build_graph()
    return _GRAPH


def run(telemetry: dict | physics.OperatingPoint, asset_id: str = "MOTOR-01",
        hours_to_window: float = 48.0, bundle=None,
        return_trace: bool = False):
    """Run the full prescriptive pipeline for one operating point."""
    op = telemetry if isinstance(telemetry, physics.OperatingPoint) else physics.OperatingPoint(
        type=str(telemetry["type"]).upper(),
        air_temperature=float(telemetry["air_temperature"]),
        process_temperature=float(telemetry["process_temperature"]),
        rotational_speed=float(telemetry["rotational_speed"]),
        torque=float(telemetry["torque"]),
        tool_wear=float(telemetry["tool_wear"]))

    final = get_graph().invoke({
        "asset_id": asset_id, "hours_to_window": float(hours_to_window),
        "operating_point": op, "bundle": bundle, "trace": [],
    })
    if return_trace:
        return final["recommendation"], final["trace"]
    return final["recommendation"]
