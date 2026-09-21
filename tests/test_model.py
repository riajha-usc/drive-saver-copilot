"""Task 1 and 2: the trained heads and their SHAP attributions."""

import json

import pytest

from backend import config
from backend.ml.explain import get_explainer
from backend.ml.dataset import frame_from_records
from backend.ml.predict import predict, failure_probability, score_frame


def test_metrics_meet_the_bar_recorded_at_training_time():
    metrics = json.loads(config.METRICS_JSON.read_text())["heads"]
    assert metrics["machine_failure"]["pr_auc"] > 0.80
    assert metrics["machine_failure"]["roc_auc"] > 0.95
    for mode in ("HDF", "PWF", "OSF"):
        assert metrics[mode]["pr_auc"] > 0.80, mode
    # TWF is deliberately left weak: the failure point inside the 200 to 240
    # minute wear window is random by construction, so it is not learnable.
    assert metrics["TWF"]["pr_auc"] < 0.5


def test_risk_separates_healthy_from_failing(bundle, healthy_point, overstrain_point, heat_point):
    p_ok = failure_probability(healthy_point, bundle=bundle)
    assert p_ok < 0.10
    for bad in (overstrain_point, heat_point):
        assert failure_probability(bad, bundle=bundle) > 0.5


def test_prediction_names_the_right_mechanism(bundle, overstrain_point, heat_point):
    assert predict(overstrain_point, bundle=bundle).likely_mode == "OSF"
    assert predict(heat_point, bundle=bundle).likely_mode == "HDF"


def test_rul_moves_opposite_to_risk(bundle, healthy_point, overstrain_point):
    assert (predict(healthy_point, bundle=bundle, explain=False).rul_hours
            > predict(overstrain_point, bundle=bundle, explain=False).rul_hours)


def test_shap_blames_the_overstrain_features(bundle, overstrain_point):
    pred = predict(overstrain_point, bundle=bundle)
    top = pred.attributions[0]
    assert top.feature in {"osf_utilisation", "wear_torque", "torque", "tool_wear"}
    assert top.direction == "raises risk"
    assert 0.0 <= top.share_of_risk <= 1.0
    assert pred.dominant_lever in {"torque", "maintenance"}


def test_shap_shares_of_upward_push_sum_to_one(bundle, overstrain_point):
    X = frame_from_records([overstrain_point])[bundle.feature_columns]
    attrs = get_explainer(bundle).attributions(X, top_k=len(bundle.feature_columns))
    assert sum(a.share_of_risk for a in attrs) == pytest.approx(1.0, abs=1e-3)


def test_batch_scoring_returns_one_row_per_input(bundle, healthy_point, overstrain_point):
    X = frame_from_records([healthy_point, overstrain_point])
    out = score_frame(X, bundle=bundle)
    assert len(out) == 2
    assert {"p_machine_failure", "risk_band", "rul_hours", "likely_mode"} <= set(out.columns)
    assert out.loc[0, "p_machine_failure"] < out.loc[1, "p_machine_failure"]
