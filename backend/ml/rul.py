"""Remaining Useful Life proxy.

AI4I 2020 is a snapshot dataset: every row is an independent operating point with
no run-to-failure timeline, so a true RUL label does not exist. Rather than invent
one, the prototype converts the model's failure probability into hours through an
explicit constant hazard model, and labels the result a proxy everywhere it is
surfaced.

Read p as the probability that this operating point fails within the reference
horizon H. Under a constant hazard rate lambda,

    p = 1 - exp(-lambda * H)   =>   lambda = -ln(1 - p) / H
    RUL = E[time to failure] = 1 / lambda

The mapping is strictly decreasing in p, which is the property the prescriptive
layer needs: any adjustment that lowers risk shows up as hours gained.
"""

from __future__ import annotations

import math

from backend import config


def probability_to_rul_hours(p: float, horizon_h: float | None = None) -> float:
    """Map a failure probability to a proxy RUL in hours."""
    h = config.RUL_REFERENCE_HORIZON_H if horizon_h is None else horizon_h
    p = min(max(float(p), 1e-6), 1.0 - 1e-6)
    lam = -math.log(1.0 - p) / h
    return round(min(max(1.0 / lam, config.RUL_MIN_H), config.RUL_MAX_H), 1)


def risk_band(p: float, violations=()) -> str:
    """Band the failure probability, with a floor for breached physical limits.

    The band is probability derived, but it never reports normal while a
    deterministic AI4I limit is actually breached. The TWF head is the case that
    forces this: the failure point inside the tool wear window is random by
    construction, so the model reads low on a machine whose wear window is
    demonstrably open. Reporting that as normal hides a fact we know for certain.
    """
    band = "normal"
    for threshold, label in config.RISK_BANDS:
        if p >= threshold:
            band = label
            break
    if violations and band == "normal":
        return "elevated"
    return band
