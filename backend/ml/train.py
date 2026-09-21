"""Task 1b: train the failure risk models.

Five gradient boosted heads are trained on the same feature frame:
  machine_failure  overall risk, drives the RUL proxy
  HDF PWF OSF TWF  per mode heads, used to name the mechanism at risk

Heads are kept separate rather than multi-label so each one can carry its own
operating threshold and so the agent can query a single mode after a
counterfactual adjustment.

Run:  python -m backend.ml.train
"""

from __future__ import annotations

import json
import time
import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import (average_precision_score, brier_score_loss, f1_score,
                             precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

from backend import config
from backend.ml.bundle import ModelBundle
from backend.ml.dataset import FAILURE_MODES, FEATURE_COLUMNS, load_dataset, split

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


def train(save: bool = True, verbose: bool = True) -> ModelBundle:
    df = load_dataset()
    X_train_full, X_test, y_train_full, y_test = split(df)

    # Inner split so operating thresholds are chosen without touching the test set.
    X_train, X_val, y_train, y_val = train_test_split(
        X_train_full, y_train_full, test_size=0.2,
        random_state=config.RANDOM_STATE, stratify=y_train_full["machine_failure"])

    models, thresholds, metrics = {}, {}, {}
    for head in HEADS:
        if head not in y_train.columns:
            continue
        model = XGBClassifier(**PARAMS)
        model.fit(X_train, y_train[head], eval_set=[(X_val, y_val[head])], verbose=False)

        val_proba = model.predict_proba(X_val)[:, 1]
        thr = _best_threshold(y_val[head].to_numpy(), val_proba)
        test_proba = model.predict_proba(X_test)[:, 1]

        models[head] = model
        thresholds[head] = thr
        metrics[head] = _evaluate(y_test[head].to_numpy(), test_proba, thr)
        if verbose:
            m = metrics[head]
            print(f"{head:<16} pr_auc={m['pr_auc']} roc_auc={m['roc_auc']} "
                  f"precision={m['precision']} recall={m['recall']} f1={m['f1']} thr={m['threshold']}")

    background = X_train.sample(n=min(200, len(X_train)), random_state=config.RANDOM_STATE)
    bundle = ModelBundle(
        models=models,
        thresholds=thresholds,
        feature_columns=list(FEATURE_COLUMNS),
        background=background,
        metrics={"heads": metrics, "n_rows": int(len(df)),
                 "n_train": int(len(X_train)), "n_val": int(len(X_val)), "n_test": int(len(X_test))},
        trained_at=time.strftime("%Y-%m-%dT%H:%M:%S"),
    )

    if save:
        config.ensure_dirs()
        joblib.dump(bundle, config.MODEL_BUNDLE)
        config.METRICS_JSON.write_text(json.dumps(bundle.metrics, indent=2))
        if verbose:
            print(f"\nsaved {config.MODEL_BUNDLE.relative_to(config.ROOT)}")
    return bundle


if __name__ == "__main__":
    train()
