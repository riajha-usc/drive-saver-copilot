"""Task 3a: the counterfactual simulator.

For a motor at risk, enumerate realistic VFD adjustments, rebuild the operating
point, re-score it with the trained model, and convert the probability change
into hours of life gained. Two guards keep the answers honest:

  1. A candidate is rejected if it trips a physical limit that the current point
     respects. Cutting torque 10 percent is the obvious move against overstrain,
     but on a lightly loaded drive it pushes shaft power under the 3500 W floor
     and buys a Power Failure instead.
  2. Every candidate carries its throughput cost, so the selector can prefer the
     smallest intervention that still reaches the maintenance window.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from backend import physics
from backend.ml.predict import failure_probability
from backend.ml.rul import probability_to_rul_hours

# Torque and speed trims a VFD can hold indefinitely. Positive speed steps matter
# because Heat Dissipation Failure needs speed BELOW 1380 rpm, so the fix there
# is to speed up, not slow down.
TORQUE_STEPS = (0.0, -2.5, -5.0, -7.5, -10.0, -12.5, -15.0, -17.5, -20.0, 5.0, 10.0, 20.0)
SPEED_STEPS = (0.0, -5.0, -2.5, 2.5, 5.0, 10.0, 20.0)

MAX_DERATE_PCT = 25.0          # refuse to propose losing more than this much output
MAX_UPRATE_PCT = 30.0          # and do not propose loading the drive up without limit
MIN_TORQUE_NM = 3.8            # observed floor in AI4I
SPEED_LIMITS_RPM = (1100.0, 2900.0)


@dataclass
class Candidate:
    """One simulated adjustment and its consequences."""

    torque_pct: float
    speed_pct: float
    action_type: str
    description: str
    operating_point: physics.OperatingPoint
    failure_probability: float
    rul_hours: float
    rul_gain_hours: float
    risk_reduction: float
    throughput_loss_pct: float
    feasible: bool
    rejection: str = ""
    new_violations: list = field(default_factory=list)
    remaining_violations: list = field(default_factory=list)
    resolved_violations: list = field(default_factory=list)

    @property
    def magnitude(self) -> float:
        """How large an intervention this is, for the minimal action preference."""
        return abs(self.torque_pct) + abs(self.speed_pct)

    def as_dict(self) -> dict:
        return {
            "description": self.description,
            "action_type": self.action_type,
            "torque_pct": self.torque_pct,
            "speed_pct": self.speed_pct,
            "projected_failure_probability": round(self.failure_probability, 4),
            "projected_rul_hours": self.rul_hours,
            "rul_extension_hours": round(self.rul_gain_hours, 1),
            "throughput_loss_pct": round(self.throughput_loss_pct, 2),
            "feasible": self.feasible,
            "rejection": self.rejection,
            "resolves": self.resolved_violations,
            "still_violating": self.remaining_violations,
        }


def _describe(torque_pct: float, speed_pct: float) -> str:
    parts = []
    if torque_pct:
        parts.append(f"{'reduce' if torque_pct < 0 else 'raise'} torque by {abs(torque_pct):.1f} percent")
    if speed_pct:
        parts.append(f"{'reduce' if speed_pct < 0 else 'raise'} speed by {abs(speed_pct):.1f} percent")
    return " and ".join(parts).capitalize() if parts else "Hold current setpoints"


def _check_feasible(base: physics.OperatingPoint, cand: physics.OperatingPoint,
                    throughput_loss_pct: float) -> tuple[bool, str, list]:
    if cand.torque < MIN_TORQUE_NM:
        return False, f"torque would fall below {MIN_TORQUE_NM} Nm", []
    if not SPEED_LIMITS_RPM[0] <= cand.rotational_speed <= SPEED_LIMITS_RPM[1]:
        return False, "speed would leave the drive operating range", []
    if throughput_loss_pct > MAX_DERATE_PCT:
        return False, f"output loss above the {MAX_DERATE_PCT:.0f} percent derate ceiling", []
    uprate = (cand.power_w - base.power_w) / base.power_w * 100.0
    if uprate > MAX_UPRATE_PCT:
        return False, f"output rise above the {MAX_UPRATE_PCT:.0f} percent uprate ceiling", []

    before = set(physics.rule_failures(base))
    after = set(physics.rule_failures(cand))
    introduced = sorted(after - before)
    if introduced:
        return False, f"would introduce {', '.join(introduced)}", introduced
    return True, "", []


def simulate(base: physics.OperatingPoint, bundle=None,
             include_tool_change: bool = True) -> list[Candidate]:
    """Score the full adjustment grid. Returns every candidate, feasible or not."""
    p_base = failure_probability(base, bundle=bundle)
    rul_base = probability_to_rul_hours(p_base)
    power_base = base.power_w
    base_violations = set(physics.rule_failures(base))

    out: list[Candidate] = []
    for t_pct in TORQUE_STEPS:
        for s_pct in SPEED_STEPS:
            if t_pct == 0.0 and s_pct == 0.0:
                continue
            cand_op = base.scaled(torque_pct=t_pct, speed_pct=s_pct)
            loss = max(0.0, (power_base - cand_op.power_w) / power_base * 100.0)
            feasible, rejection, introduced = _check_feasible(base, cand_op, loss)

            p_new = failure_probability(cand_op, bundle=bundle)
            rul_new = probability_to_rul_hours(p_new)
            after = set(physics.rule_failures(cand_op))
            out.append(Candidate(
                torque_pct=t_pct, speed_pct=s_pct, action_type="derate",
                description=_describe(t_pct, s_pct), operating_point=cand_op,
                failure_probability=p_new, rul_hours=rul_new,
                rul_gain_hours=rul_new - rul_base, risk_reduction=p_base - p_new,
                throughput_loss_pct=loss, feasible=feasible,
                rejection=rejection, new_violations=introduced,
                remaining_violations=sorted(after),
                resolved_violations=sorted(base_violations - after),
            ))

    # A tool change is not a VFD trim, but when wear is the driver it is the only
    # honest prescription, so it competes in the same ranking.
    if include_tool_change and base.tool_wear > 0:
        cand_op = base.replace(tool_wear=0.0)
        p_new = failure_probability(cand_op, bundle=bundle)
        rul_new = probability_to_rul_hours(p_new)
        after = set(physics.rule_failures(cand_op))
        out.append(Candidate(
            torque_pct=0.0, speed_pct=0.0, action_type="schedule_maintenance",
            description="Replace the tool at the next line stop",
            operating_point=cand_op, failure_probability=p_new, rul_hours=rul_new,
            rul_gain_hours=rul_new - rul_base, risk_reduction=p_base - p_new,
            throughput_loss_pct=0.0, feasible=True,
            remaining_violations=sorted(after),
            resolved_violations=sorted(base_violations - after),
        ))

    # Rank on risk reduction rather than hours: the RUL proxy saturates at its
    # cap, so hours tie for every genuinely safe candidate.
    out.sort(key=lambda c: (-c.risk_reduction, c.throughput_loss_pct))
    return out


def select(candidates: list[Candidate], hours_to_window: float,
           baseline_rul_hours: float,
           baseline_violations: list | None = None) -> tuple[Candidate | None, list[Candidate]]:
    """Cheapest feasible action that carries the asset to the maintenance window.

    Candidates are tiered by whether they actually fix the mechanism that is
    failing before cost is considered. Without this a tool change wins on cost
    against a heat dissipation fault it does nothing about: the learned model
    still scores it lower because wear correlates with risk across the dataset,
    but the physical fault is untouched.

    Falls back to the largest risk reduction when nothing clears the window.
    Returns (chosen, runner up alternatives).
    """
    feasible = [c for c in candidates if c.feasible and c.risk_reduction > 0]
    if not feasible:
        return None, []

    n_base = len(baseline_violations) if baseline_violations is not None else 0
    if n_base:
        tiers = [
            [c for c in feasible if not c.remaining_violations],
            [c for c in feasible if 0 < len(c.remaining_violations) < n_base],
            feasible,
        ]
        feasible = next(t for t in tiers if t)

    clears = [c for c in feasible if c.rul_hours >= hours_to_window]
    if clears:
        # Minimal intervention: least output given up, then the smallest setpoint
        # move that still clears the window, then the biggest risk reduction.
        clears.sort(key=lambda c: (round(c.throughput_loss_pct, 2), c.magnitude, -c.risk_reduction))
        chosen = clears[0]
    else:
        chosen = max(feasible, key=lambda c: c.risk_reduction)

    # Surface the cheapest other options that also clear the window, so the
    # operator can trade output against margin rather than take one answer.
    pool = clears if clears else feasible
    alternatives = sorted((c for c in pool if c is not chosen),
                          key=lambda c: (round(c.throughput_loss_pct, 2), c.magnitude,
                                         -c.risk_reduction))[:3]
    return chosen, alternatives
