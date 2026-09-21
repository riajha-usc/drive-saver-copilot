"""Phase 1 walkthrough. Runs the whole pipeline on real AI4I rows.

  python -m backend.demo            representative asset per failure mode
  python -m backend.demo --json     full payloads, for wiring up the API or UI
  python -m backend.demo --row 42   one specific dataset row
"""

from __future__ import annotations

import argparse
import json

from backend.agent.graph import run
from backend.ml.dataset import FAILURE_MODES, load_dataset
from backend.ml.predict import load_bundle
from backend.physics import OperatingPoint

BAR = "=" * 78


def _operating_point(row) -> OperatingPoint:
    return OperatingPoint(
        type=row["type"], air_temperature=float(row["air_temperature"]),
        process_temperature=float(row["process_temperature"]),
        rotational_speed=float(row["rotational_speed"]),
        torque=float(row["torque"]), tool_wear=float(row["tool_wear"]))


def _card(rec) -> str:
    t, r, p, e = rec.telemetry, rec.risk, rec.projection, rec.economics
    lines = [
        BAR,
        f"{rec.asset_id}   {r.risk_band.upper()}   {r.failure_probability * 100:.1f} percent "
        + (f"risk of {r.likely_failure_mode_name}" if r.likely_failure_mode != "none"
           else "risk, no failure mode at issue"),
        BAR,
        f"  telemetry     {t.torque:.1f} Nm at {t.rotational_speed:.0f} rpm, "
        f"{t.shaft_power_w:.0f} W, spread {t.temp_diff_k:.1f} K, wear {t.tool_wear:.0f} min",
        f"  limits hit    {', '.join(r.rule_violations) or 'none'}",
        f"  root cause    {rec.root_cause.summary}",
        f"                {rec.root_cause.physical_margin}",
        "",
        f"  ACTION        {rec.action_type}",
    ]
    for a in rec.adjustments:
        lines.append(f"                {a.label}: {a.current_value} -> "
                     f"{a.recommended_value} {a.unit} ({a.change_pct:+.1f} percent)")
    if not rec.adjustments:
        lines.append("                hold current setpoints")
    lines += [
        "",
        f"  life          {p.baseline_rul_hours} h -> {p.projected_rul_hours} h "
        f"({p.rul_extension_hours:+.1f} h), window at {p.hours_to_maintenance_window} h "
        f"{'reached' if p.reaches_maintenance_window else 'NOT reached'}",
        f"  risk          {p.baseline_failure_probability:.3f} -> "
        f"{p.projected_failure_probability:.3f}",
        f"  output cost   {p.throughput_loss_pct:.1f} percent",
        f"  net benefit   ${e.net_benefit_usd:,.0f} "
        f"(${e.avoided_downtime_cost_usd:,.0f} avoided less ${e.throughput_cost_usd:,.0f} output)",
        f"  confidence    {rec.confidence}",
        "",
        f"  {rec.narrative.headline}",
        f"  {rec.narrative.operator_instruction}",
    ]
    if rec.alternatives:
        lines.append("")
        lines.append("  alternatives")
        for alt in rec.alternatives:
            lines.append(f"                {alt['description']} "
                         f"({alt['throughput_loss_pct']:.1f} percent output loss)")
    return "\n".join(lines)


def pick_scenarios(df) -> list[tuple[str, object]]:
    """One real row per failure mode, plus a healthy baseline."""
    picks = []
    healthy = df[df["machine_failure"] == 0].sort_values("osf_utilisation").iloc[0]
    picks.append(("VFD-MOTOR-00 healthy baseline", healthy))
    for i, mode in enumerate(FAILURE_MODES, start=1):
        hits = df[df[mode] == 1]
        if len(hits):
            picks.append((f"VFD-MOTOR-{i:02d} {mode}", hits.iloc[0]))
    return picks


def main() -> None:
    ap = argparse.ArgumentParser(description="Drive-Saver Copilot phase 1 demo")
    ap.add_argument("--json", action="store_true", help="print full JSON payloads")
    ap.add_argument("--row", type=int, help="run one dataset row by index")
    ap.add_argument("--window", type=float, default=48.0,
                    help="hours until the planned maintenance window")
    args = ap.parse_args()

    bundle = load_bundle()
    df = load_dataset()

    if args.row is not None:
        scenarios = [(f"VFD-MOTOR-ROW{args.row}", df.iloc[args.row])]
    else:
        scenarios = pick_scenarios(df)

    payloads = []
    for asset_id, row in scenarios:
        rec = run(_operating_point(row), asset_id=asset_id,
                  hours_to_window=args.window, bundle=bundle)
        payloads.append(json.loads(rec.model_dump_json()))
        if not args.json:
            print(_card(rec))
            print()

    if args.json:
        print(json.dumps(payloads, indent=2))


if __name__ == "__main__":
    main()
