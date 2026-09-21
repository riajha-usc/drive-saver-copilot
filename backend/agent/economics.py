"""Cost model behind the savings figure on the recommendation card.

Deliberately simple and fully explicit: every constant is surfaced in the payload
under economics.assumptions so an operator can see what the number rests on.
"""

from __future__ import annotations

from backend import config


def value_of_action(risk_reduction: float, throughput_loss_pct: float,
                    hours_to_window: float) -> dict:
    """Expected dollars avoided minus the production given up to get there."""
    unplanned_event_cost = (config.UNPLANNED_DOWNTIME_HOURS * config.DOWNTIME_COST_PER_HOUR
                            + config.EMERGENCY_CALLOUT_COST)
    avoided = max(0.0, risk_reduction) * unplanned_event_cost
    throughput_cost = (config.PRODUCTION_VALUE_PER_HOUR
                       * (throughput_loss_pct / 100.0) * max(0.0, hours_to_window))
    return {
        "avoided_downtime_cost_usd": round(avoided, 2),
        "throughput_cost_usd": round(throughput_cost, 2),
        "net_benefit_usd": round(avoided - throughput_cost, 2),
        "assumptions": {
            "unplanned_downtime_hours": config.UNPLANNED_DOWNTIME_HOURS,
            "downtime_cost_per_hour_usd": config.DOWNTIME_COST_PER_HOUR,
            "emergency_callout_usd": config.EMERGENCY_CALLOUT_COST,
            "production_value_per_hour_usd": config.PRODUCTION_VALUE_PER_HOUR,
            "unplanned_event_cost_usd": round(unplanned_event_cost, 2),
        },
    }
