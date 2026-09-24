"""Model comparison: every head is chosen from several algorithms, fairly."""

from __future__ import annotations

import pytest

from backend.ml import train as T
from backend.ml.dataset import BASE_FEATURES


def test_every_head_records_a_full_comparison(bundle):
    selection = bundle.metrics["selection"]
    assert set(selection) == set(bundle.models)
    names = [c.name for c in T.CANDIDATES]
    for head, entry in selection.items():
        assert [c["name"] for c in entry["candidates"]] == names, head
        assert entry["criterion"] == "validation PR AUC"


def test_the_chosen_model_is_the_one_in_use(bundle):
    for head, entry in bundle.metrics["selection"].items():
        model = bundle.models[head]
        expected = {"xgboost": "XGBClassifier", "lightgbm": "LGBMClassifier"}[entry["chosen"]]
        assert type(model).__name__ == expected, head
        assert bundle.metrics["heads"][head]["algorithm"] == entry["chosen"]


def test_the_winner_is_the_best_eligible_on_validation(bundle):
    for head, entry in bundle.metrics["selection"].items():
        eligible = [c for c in entry["candidates"] if c["eligible"]]
        best = max(c["val_pr_auc"] for c in eligible)
        chosen = next(c for c in entry["candidates"] if c["name"] == entry["chosen"])
        assert chosen["eligible"]
        assert chosen["val_pr_auc"] >= best - T.TIE_TOLERANCE, head


def test_the_baseline_is_measured_but_never_chosen(bundle):
    for entry in bundle.metrics["selection"].values():
        baseline = next(c for c in entry["candidates"] if c["name"] == "logistic_regression")
        assert not baseline["eligible"]
        assert baseline["val_pr_auc"] is not None
        assert entry["chosen"] != "logistic_regression"


def test_choose_prefers_the_earlier_candidate_on_a_tie():
    results = [
        {"name": "xgboost", "eligible": True, "val_pr_auc": 0.900},
        {"name": "lightgbm", "eligible": True, "val_pr_auc": 0.901},
        {"name": "logistic_regression", "eligible": False, "val_pr_auc": 0.990},
    ]
    assert T._choose(results)["name"] == "xgboost"      # within tolerance
    results[1]["val_pr_auc"] = 0.95
    assert T._choose(results)["name"] == "lightgbm"     # a real improvement wins


def test_training_ranges_cover_every_raw_signal(bundle):
    ranges = bundle.metrics["training_ranges"]
    assert set(ranges) == set(BASE_FEATURES)
    for col, r in ranges.items():
        assert r["min"] <= r["mean"] <= r["max"], col


def test_candidates_are_logged_to_mlflow(tmp_path, monkeypatch):
    pytest.importorskip("mlflow")
    import mlflow
    monkeypatch.setattr("backend.config.MLFLOW_TRACKING_URI", f"sqlite:///{tmp_path}/t.db")
    tracker = T._Tracker(enabled=True, verbose=False)
    result = {"val_pr_auc": 0.9, "test_pr_auc": 0.88, "fit_seconds": 0.1, "val_roc_auc": None}
    with tracker.parent("test run"):
        tracker.log_candidate("machine_failure", T.CANDIDATES[0], result, chosen=True)
    runs = mlflow.search_runs(experiment_names=["drive-saver-copilot"])
    child = runs[runs["tags.mlflow.runName"] == "machine_failure / XGBoost"].iloc[0]
    assert child["metrics.val_pr_auc"] == pytest.approx(0.9)
    assert child["tags.selected"] == "true"
    assert child["params.algorithm"] == "xgboost"


def test_training_runs_without_mlflow_tracking():
    tracker = T._Tracker(enabled=False, verbose=False)
    assert tracker.mlflow is None
    with tracker.parent("noop"):
        tracker.log_candidate("machine_failure", T.CANDIDATES[0], {}, chosen=False)
