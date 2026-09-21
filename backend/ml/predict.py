"""Inference facade: one operating point in, risk plus RUL proxy plus root cause out."""

from __future__ import annotations

from dataclasses import dataclass, field
from functools import lru_cache

import joblib
import pandas as pd

from backend import config, physics
from backend.ml.dataset import FAILURE_MODES, frame_from_records
from backend.ml.explain import Attribution, get_explainer
from backend.ml.rul import probability_to_rul_hours, risk_band

MODE_NAMES = {
    "HDF": "Heat Dissipation Failure",
    "PWF": "Power Failure",
    "OSF": "Overstrain Failure",
    "TWF": "Tool Wear Failure",
}


class ModelNotTrained(RuntimeError):
    pass


@lru_cache(maxsize=1)
def load_bundle(path: str | None = None):
    p = config.MODEL_BUNDLE if path is None else path
    try:
        return joblib.load(p)
    except FileNotFoundError as exc:
        raise ModelNotTrained(
            "No trained model found. Run: python -m backend.ml.train") from exc


@dataclass
class Prediction:
    operating_point: physics.OperatingPoint
    failure_probability: float
    risk_band: str
    rul_hours: float
    mode_probabilities: dict
    likely_mode: str
    likely_mode_name: str
    rule_violations: list
    margins: dict
    attributions: list[Attribution] = field(default_factory=list)
    dominant_lever: str = "none"

    def as_dict(self) -> dict:
        return {
            "failure_probability": round(self.failure_probability, 4),
            "risk_band": self.risk_band,
            "rul_hours": self.rul_hours,
            "mode_probabilities": {k: round(v, 4) for k, v in self.mode_probabilities.items()},
            "likely_mode": self.likely_mode,
            "likely_mode_name": self.likely_mode_name,
            "rule_violations": self.rule_violations,
            "margins": {k: {"label": m.label, "value": round(m.value, 2),
                            "limit": m.limit, "margin": round(m.margin, 2),
                            "unit": m.unit, "violated": m.violated}
                        for k, m in self.margins.items()},
            "attributions": [a.as_dict() for a in self.attributions],
            "dominant_lever": self.dominant_lever,
        }


def score_frame(X: pd.DataFrame, bundle=None) -> pd.DataFrame:
    """Batch scoring. Returns probabilities, RUL proxy and risk band per row."""
    bundle = bundle or load_bundle()
    X = X[bundle.feature_columns]
    out = pd.DataFrame(index=X.index)
    for head, model in bundle.models.items():
        out[f"p_{head}"] = model.predict_proba(X)[:, 1]
    out["risk_band"] = out["p_machine_failure"].map(risk_band)
    out["rul_hours"] = out["p_machine_failure"].map(probability_to_rul_hours)
    mode_cols = [f"p_{m}" for m in FAILURE_MODES if f"p_{m}" in out.columns]
    out["likely_mode"] = out[mode_cols].idxmax(axis=1).str.removeprefix("p_")
    return out


def failure_probability(op: physics.OperatingPoint, bundle=None, head: str = "machine_failure") -> float:
    """Single probability lookup, used heavily by the counterfactual search."""
    bundle = bundle or load_bundle()
    X = frame_from_records([op])[bundle.feature_columns]
    return float(bundle.models[head].predict_proba(X)[:, 1][0])


def predict(op: physics.OperatingPoint, bundle=None, explain: bool = True) -> Prediction:
    bundle = bundle or load_bundle()
    X = frame_from_records([op])[bundle.feature_columns]

    probs = {h: float(m.predict_proba(X)[:, 1][0]) for h, m in bundle.models.items()}
    p_fail = probs["machine_failure"]
    mode_probs = {m: probs[m] for m in FAILURE_MODES if m in probs}

    violations = physics.rule_failures(op)
    band = risk_band(p_fail, violations)
    # Trust an actual rule violation over the learned head when naming the mechanism,
    # and name no mechanism at all on an asset that is not at risk.
    if violations:
        likely = max(violations, key=lambda m: mode_probs.get(m, 0.0))
    elif band == "normal" or not mode_probs:
        likely = "none"
    else:
        likely = max(mode_probs, key=mode_probs.get)

    attributions, lever = [], "none"
    if explain:
        ex = get_explainer(bundle)
        attributions = ex.attributions(X, head="machine_failure")
        lever = ex.dominant_lever(X, head="machine_failure")

    return Prediction(
        operating_point=op,
        failure_probability=p_fail,
        risk_band=band,
        rul_hours=probability_to_rul_hours(p_fail),
        mode_probabilities=mode_probs,
        likely_mode=likely,
        likely_mode_name=MODE_NAMES.get(likely, "no mode at risk"),
        rule_violations=violations,
        margins=physics.margins(op),
        attributions=attributions,
        dominant_lever=lever,
    )
