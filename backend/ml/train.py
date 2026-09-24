"""Task 1b: train the failure risk models, choosing the algorithm per head.

Five heads are trained on the same feature frame:
  machine_failure  overall risk, drives the RUL proxy
  HDF PWF OSF TWF  per mode heads, used to name the mechanism at risk

Heads are kept separate rather than multi-label so each one can carry its own
operating threshold and so the agent can query a single mode after a
counterfactual adjustment.

Model selection. For every head, three candidates are trained on the same split:
XGBoost, LightGBM, and a logistic regression baseline. The winner is the one with
the best PR AUC on the validation split; the test split is only ever used to
report results, never to choose. Only tree models are eligible, because the root
cause analysis uses SHAP's tree explainer; the baseline is there as a yardstick
for how much the trees add.

Experiment tracking. When MLflow is installed (it is a development dependency,
see requirements-dev.txt), every candidate is logged as a child run of one
training run, so `make mlflow` shows the whole comparison. Without MLflow the
comparison still runs and the leaderboard is saved in the model bundle.

Run:  python -m backend.ml.train
"""

from __future__ import annotations

import json
import os
import time
from dataclasses import dataclass
from typing import Callable

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (average_precision_score, brier_score_loss, f1_score,
                             precision_score, recall_score, roc_auc_score)
from lightgbm import LGBMClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.pipeline import make_pipeline
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

from backend import config
from backend.ml.bundle import ModelBundle
from backend.ml.dataset import (BASE_FEATURES, FAILURE_MODES, FEATURE_COLUMNS, load_dataset,
                                split)

HEADS = ["machine_failure", *FAILURE_MODES]

PARAMS = dict(
    n_estimators=400,
    max_depth=4,
    learning_rate=0.08,
    subsample=0.9,
    colsample_bytree=0.9,
    min_child_weight=1,
    reg_lambda=1.0,
    objective="binary:logistic",
    eval_metric="aucpr",
    tree_method="hist",
    n_jobs=-1,
    random_state=config.RANDOM_STATE,
)

LGBM_PARAMS = dict(
    n_estimators=400,
    learning_rate=0.05,
    num_leaves=15,
    subsample=0.9,
    subsample_freq=1,
    colsample_bytree=0.9,
    reg_lambda=1.0,
    n_jobs=-1,
    random_state=config.RANDOM_STATE,
    verbose=-1,
)

LOGREG_PARAMS = dict(max_iter=2000)


@dataclass(frozen=True)
class CandidateSpec:
    name: str
    label: str
    build: Callable
    params: dict
    eligible: bool
    note: str = ""


CANDIDATES = [
    CandidateSpec("xgboost", "XGBoost", lambda: XGBClassifier(**PARAMS), PARAMS, True),
    CandidateSpec("lightgbm", "LightGBM", lambda: LGBMClassifier(**LGBM_PARAMS), LGBM_PARAMS, True),
    CandidateSpec("logistic_regression", "Logistic regression",
                  lambda: make_pipeline(StandardScaler(), LogisticRegression(**LOGREG_PARAMS)),
                  LOGREG_PARAMS, False,
                  "Baseline only: root cause analysis needs a tree model"),
]

SELECTION_CRITERION = "validation PR AUC"
# Candidates within this much of the best validation score count as a tie, and a
# tie goes to the earlier entry in CANDIDATES. It keeps the choice from flipping
# on noise between runs.
TIE_TOLERANCE = 0.002


def _best_threshold(y_true, proba) -> float:
    """Threshold maximising F1 on a held out validation slice."""
    grid = np.unique(np.round(np.linspace(0.05, 0.95, 91), 3))
    scores = [f1_score(y_true, (proba >= t).astype(int), zero_division=0) for t in grid]
    return float(grid[int(np.argmax(scores))])


def _evaluate(y_true, proba, threshold) -> dict:
    pred = (proba >= threshold).astype(int)
    positives = int(y_true.sum())
    return {
        "positives": positives,
        "roc_auc": round(float(roc_auc_score(y_true, proba)), 4) if positives else None,
        "pr_auc": round(float(average_precision_score(y_true, proba)), 4) if positives else None,
        "precision": round(float(precision_score(y_true, pred, zero_division=0)), 4),
        "recall": round(float(recall_score(y_true, pred, zero_division=0)), 4),
        "f1": round(float(f1_score(y_true, pred, zero_division=0)), 4),
        "brier": round(float(brier_score_loss(y_true, proba)), 5),
        "threshold": round(float(threshold), 3),
    }


def _pr_auc(y_true, proba) -> float | None:
    return float(average_precision_score(y_true, proba)) if int(y_true.sum()) else None


def _roc_auc(y_true, proba) -> float | None:
    return float(roc_auc_score(y_true, proba)) if int(y_true.sum()) else None


def _choose(results: list[dict]) -> dict:
    """Best eligible candidate on validation PR AUC, ties to the earlier entry."""
    eligible = [r for r in results if r["eligible"] and r["val_pr_auc"] is not None]
    best = max(r["val_pr_auc"] for r in eligible)
    return next(r for r in eligible if r["val_pr_auc"] >= best - TIE_TOLERANCE)


def _training_ranges(X: pd.DataFrame) -> dict:
    """Value ranges of the raw signals the model was trained on, for the dataset
    quality report's out of range check."""
    out = {}
    for col in BASE_FEATURES:
        v = X[col]
        out[col] = {"min": round(float(v.min()), 3), "max": round(float(v.max()), 3),
                    "mean": round(float(v.mean()), 3)}
    return out


class _Tracker:
    """Thin MLflow wrapper that does nothing when MLflow is not installed."""

    def __init__(self, enabled: bool, verbose: bool):
        self.mlflow = None
        if not enabled:
            return
        os.environ.setdefault("MLFLOW_DISABLE_AGENT_HINT", "1")
        os.environ.setdefault("MLFLOW_DISABLE_TELEMETRY", "true")   # no usage reporting
        try:
            import mlflow
        except ImportError:
            if verbose:
                print("MLflow not installed, skipping experiment tracking "
                      "(pip install -r requirements-dev.txt)")
            return
        mlflow.set_tracking_uri(config.MLFLOW_TRACKING_URI)
        mlflow.set_experiment(config.MLFLOW_EXPERIMENT)
        self.mlflow = mlflow

    def parent(self, name: str):
        if self.mlflow is None:
            from contextlib import nullcontext
            return nullcontext()
        return self.mlflow.start_run(run_name=name)

    def log_candidate(self, head: str, spec: CandidateSpec, result: dict, chosen: bool) -> None:
        if self.mlflow is None:
            return
        with self.mlflow.start_run(run_name=f"{head} / {spec.label}", nested=True):
            self.mlflow.log_params({"head": head, "algorithm": spec.name,
                                    **{f"hp_{k}": v for k, v in spec.params.items()}})
            self.mlflow.log_metrics({k: v for k, v in result.items()
                                     if k.startswith(("val_", "test_", "fit_")) and v is not None})
            self.mlflow.set_tags({"eligible": str(spec.eligible).lower(),
                                  "selected": str(chosen).lower()})

    def log_summary(self, selection: dict, n_rows: int) -> None:
        if self.mlflow is None:
            return
        self.mlflow.log_params({"n_rows": n_rows, "criterion": SELECTION_CRITERION})
        self.mlflow.set_tags({f"selected_{h}": v["chosen"] for h, v in selection.items()})


def train(save: bool = True, verbose: bool = True, track: bool | None = None) -> ModelBundle:
    df = load_dataset()
    X_train_full, X_test, y_train_full, y_test = split(df)

    # Inner split so model choice and operating thresholds never touch the test set.
    X_train, X_val, y_train, y_val = train_test_split(
        X_train_full, y_train_full, test_size=0.2,
        random_state=config.RANDOM_STATE, stratify=y_train_full["machine_failure"])

    tracker = _Tracker(config.MLFLOW_ENABLED if track is None else track, verbose)
    trained_at = time.strftime("%Y-%m-%dT%H:%M:%S")

    models, thresholds, metrics, selection = {}, {}, {}, {}
    with tracker.parent(f"training {trained_at}"):
        for head in HEADS:
            if head not in y_train.columns:
                continue
            yv, yt = y_val[head].to_numpy(), y_test[head].to_numpy()

            fitted, results = {}, []
            for spec in CANDIDATES:
                model = spec.build()
                started = time.perf_counter()
                model.fit(X_train, y_train[head])
                fit_seconds = time.perf_counter() - started

                val_proba = model.predict_proba(X_val)[:, 1]
                test_proba = model.predict_proba(X_test)[:, 1]
                fitted[spec.name] = (model, val_proba, test_proba)
                results.append({
                    "name": spec.name, "label": spec.label, "eligible": spec.eligible,
                    "note": spec.note,
                    "val_pr_auc": _pr_auc(yv, val_proba), "val_roc_auc": _roc_auc(yv, val_proba),
                    "test_pr_auc": _pr_auc(yt, test_proba), "test_roc_auc": _roc_auc(yt, test_proba),
                    "fit_seconds": round(fit_seconds, 3),
                })

            winner = _choose(results)
            model, val_proba, test_proba = fitted[winner["name"]]
            thr = _best_threshold(yv, val_proba)

            models[head] = model
            thresholds[head] = thr
            metrics[head] = {**_evaluate(yt, test_proba, thr), "algorithm": winner["name"]}
            selection[head] = {
                "chosen": winner["name"],
                "criterion": SELECTION_CRITERION,
                "candidates": [{k: (round(v, 4) if isinstance(v, float) else v)
                                for k, v in r.items()} for r in results],
            }
            for spec, result in zip(CANDIDATES, results):
                tracker.log_candidate(head, spec, result, chosen=spec.name == winner["name"])

            if verbose:
                board = "  ".join(f"{r['label']} {r['val_pr_auc']:.3f}" for r in results
                                  if r["val_pr_auc"] is not None)
                m = metrics[head]
                print(f"{head:<16} chose {winner['label']:<10} | val PR AUC: {board}")
                print(f"{'':<16} test pr_auc={m['pr_auc']} roc_auc={m['roc_auc']} "
                      f"precision={m['precision']} recall={m['recall']} thr={m['threshold']}")

        tracker.log_summary(selection, int(len(df)))

    background = X_train.sample(n=min(200, len(X_train)), random_state=config.RANDOM_STATE)
    bundle = ModelBundle(
        models=models,
        thresholds=thresholds,
        feature_columns=list(FEATURE_COLUMNS),
        background=background,
        metrics={"heads": metrics, "selection": selection,
                 "training_ranges": _training_ranges(X_train_full),
                 "n_rows": int(len(df)), "n_train": int(len(X_train)),
                 "n_val": int(len(X_val)), "n_test": int(len(X_test))},
        trained_at=trained_at,
    )

    if save:
        config.ensure_dirs()
        joblib.dump(bundle, config.MODEL_BUNDLE)
        config.METRICS_JSON.write_text(json.dumps(bundle.metrics, indent=2))
        if verbose:
            print(f"\nsaved {config.MODEL_BUNDLE.relative_to(config.ROOT)}")
            if tracker.mlflow is not None:
                print(f"experiment tracked in MLflow: make mlflow")
    return bundle


if __name__ == "__main__":
    train()
