"""Task 2: SHAP feature attribution.

TreeExplainer runs against the trained boosted heads and returns the features
pushing a given operating point toward failure. Attributions are in log odds, so
they are reported both raw and as a share of the total positive push, which is
what the recommendation card shows as root cause confidence.
"""

from __future__ import annotations

from dataclasses import dataclass, asdict

import numpy as np
import pandas as pd
import shap

# Feature names as an operator would read them, plus the lever each one responds to.
FEATURE_LABELS = {
    "air_temperature": ("Air temperature", "K", "ambient"),
    "process_temperature": ("Process temperature", "K", "ambient"),
    "rotational_speed": ("Rotational speed", "rpm", "speed"),
    "torque": ("Torque", "Nm", "torque"),
    "tool_wear": ("Tool wear", "min", "maintenance"),
    "temp_diff": ("Temperature spread", "K", "ambient"),
    "power_w": ("Shaft power", "W", "torque"),
    "wear_torque": ("Wear times torque", "min Nm", "torque"),
    "osf_utilisation": ("Overstrain utilisation", "fraction of limit", "torque"),
    "type_ordinal": ("Product quality class", "L/M/H", "fixed"),
}


@dataclass
class Attribution:
    feature: str
    label: str
    unit: str
    lever: str
    value: float
    shap_value: float
    direction: str          # "raises risk" or "lowers risk"
    share_of_risk: float    # fraction of the total upward push, 0 when downward

    def as_dict(self) -> dict:
        return asdict(self)


class Explainer:
    """SHAP wrapper bound to one trained bundle."""

    def __init__(self, bundle):
        self.bundle = bundle
        self._explainers: dict = {}

    def _explainer(self, head: str):
        if head not in self._explainers:
            self._explainers[head] = shap.TreeExplainer(self.bundle.models[head])
        return self._explainers[head]

    def attributions(self, X: pd.DataFrame, head: str = "machine_failure",
                     top_k: int = 4) -> list[Attribution]:
        """Top contributors for a single row frame."""
        if len(X) != 1:
            raise ValueError("attributions expects exactly one row")
        values = self._explainer(head).shap_values(X)
        values = np.asarray(values).reshape(-1)

        total_up = float(values[values > 0].sum()) or 1.0
        out = []
        for name, sv in zip(X.columns, values):
            label, unit, lever = FEATURE_LABELS.get(name, (name, "", "unknown"))
            out.append(Attribution(
                feature=name, label=label, unit=unit, lever=lever,
                value=round(float(X.iloc[0][name]), 3),
                shap_value=round(float(sv), 4),
                direction="raises risk" if sv > 0 else "lowers risk",
                share_of_risk=round(max(float(sv), 0.0) / total_up, 4),
            ))
        out.sort(key=lambda a: abs(a.shap_value), reverse=True)
        return out[:top_k]

    def dominant_lever(self, X: pd.DataFrame, head: str = "machine_failure") -> str:
        """Which control lever carries the most upward attribution."""
        totals: dict[str, float] = {}
        for a in self.attributions(X, head=head, top_k=len(X.columns)):
            if a.shap_value > 0:
                totals[a.lever] = totals.get(a.lever, 0.0) + a.shap_value
        if not totals:
            return "none"
        return max(totals, key=totals.get)


_EXPLAINER_CACHE: dict[int, Explainer] = {}


def get_explainer(bundle) -> Explainer:
    """One Explainer per loaded bundle. TreeExplainer construction is not free."""
    key = id(bundle)
    if key not in _EXPLAINER_CACHE:
        _EXPLAINER_CACHE[key] = Explainer(bundle)
    return _EXPLAINER_CACHE[key]
