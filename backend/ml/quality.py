"""Dataset quality report.

Before anyone trusts a prediction on uploaded telemetry, the report answers four
questions: how many rows were usable and why the rest were not, whether the
readings sit inside the range the model was trained on, what the product and
failure mix looks like, and how many rows already breach a physical limit.

It ends in a plain verdict: ready, use with care, or not usable.
"""

from __future__ import annotations

import pandas as pd

from backend.ml.dataset import BASE_FEATURES, FAILURE_MODES
from backend.physics import QUALITY_TYPES

REJECTION_LABELS = {
    "unknown_type": "Product type not L, M or H",
    "missing_or_non_numeric": "Missing or non numeric reading",
    "non_positive_speed": "Rotational speed of zero or less",
    "negative_torque": "Negative torque",
    "negative_tool_wear": "Negative tool wear",
    "duplicate_row": "Exact duplicate of another row",
}

COLUMN_LABELS = {
    "air_temperature": ("Air temperature", "K"),
    "process_temperature": ("Process temperature", "K"),
    "rotational_speed": ("Rotational speed", "rpm"),
    "torque": ("Torque", "Nm"),
    "tool_wear": ("Tool wear", "min"),
}

# Thresholds for a warning. Deliberately simple and stated in the report.
REJECTED_WARN_SHARE = 0.05       # more than 5 percent of rows unusable
OUT_OF_RANGE_WARN_SHARE = 0.01   # more than 1 percent of a column outside training
SMALL_DATASET_ROWS = 20


def _lower_first(text: str) -> str:
    """Lower case only the first letter, so "L, M or H" keeps its capitals."""
    return text[:1].lower() + text[1:]


def _check(status: str, title: str, detail: str) -> dict:
    return {"status": status, "title": title, "detail": detail}


def build_report(frame: pd.DataFrame, training_ranges: dict | None) -> dict:
    """Profile a cleaned, feature engineered frame.

    `frame.attrs` carries what cleaning recorded: rows received and the count
    rejected under each reason. `training_ranges` comes from the model bundle;
    without it the out of range check is skipped and says so.
    """
    received = int(frame.attrs.get("rows_received", len(frame)))
    accepted = int(len(frame))
    rejected = received - accepted
    rejections = frame.attrs.get("rejections", {})

    columns, out_of_range = [], {}
    for col in BASE_FEATURES:
        label, unit = COLUMN_LABELS[col]
        values = frame[col] if accepted else pd.Series(dtype=float)
        entry = {
            "column": col, "label": label, "unit": unit,
            "min": round(float(values.min()), 2) if accepted else None,
            "max": round(float(values.max()), 2) if accepted else None,
            "mean": round(float(values.mean()), 2) if accepted else None,
            "training_min": None, "training_max": None, "out_of_range": 0,
        }
        if training_ranges and col in training_ranges and accepted:
            lo, hi = training_ranges[col]["min"], training_ranges[col]["max"]
            outside = int(((values < lo) | (values > hi)).sum())
            entry.update(training_min=lo, training_max=hi, out_of_range=outside)
            if outside:
                out_of_range[label] = outside
        columns.append(entry)

    type_counts = frame["type"].value_counts() if accepted else pd.Series(dtype=int)
    type_mix = {t: int(type_counts.get(t, 0)) for t in QUALITY_TYPES}

    has_labels = "machine_failure" in frame.columns
    labels = None
    if has_labels and accepted:
        labels = {
            "failure_rate": round(float(frame["machine_failure"].mean()), 4),
            "failures": int(frame["machine_failure"].sum()),
            "by_mode": {m: int(frame[m].sum()) for m in FAILURE_MODES if m in frame.columns},
        }

    # Rows already past a physical limit, whatever the model says about them.
    breaches = {}
    if accepted:
        from backend.ml.predict import _violation_masks   # avoid a circular import
        masks = _violation_masks(frame)
        breaches = {mode: int(masks[mode].sum()) for mode in masks.columns}

    # ---------------------------------------------------------------- checks
    checks = [_check("pass", "Required columns present",
                     "Type, both temperatures, rotational speed, torque and tool wear.")]

    if accepted == 0:
        checks.append(_check("fail", "No usable rows",
                             f"All {received:,} rows failed validation."))
    elif rejected == 0:
        checks.append(_check("pass", "Every row usable",
                             f"All {received:,} rows passed validation."))
    else:
        share = rejected / received
        # List the reasons with their counts rather than calling one "mostly":
        # with several reasons at one row each, no single reason dominates.
        reasons = sorted(rejections.items(), key=lambda kv: -kv[1])[:3]
        listed = ", ".join(f"{_lower_first(REJECTION_LABELS.get(r, r))} ({n:,})"
                           for r, n in reasons)
        detail = (f"{rejected:,} of {received:,} rows ({share:.1%}) were skipped"
                  + (f": {listed}." if listed else "."))
        checks.append(_check("warn" if share > REJECTED_WARN_SHARE else "pass",
                             "Some rows skipped", detail))

    if accepted and accepted < SMALL_DATASET_ROWS:
        checks.append(_check("warn", "Small dataset",
                             f"Only {accepted} usable rows; fleet level figures will be noisy."))

    if not training_ranges:
        checks.append(_check("warn", "Training range unknown",
                             "The model build carries no training ranges; retrain to enable this check."))
    elif accepted:
        worst = {k: v for k, v in out_of_range.items() if v / accepted > OUT_OF_RANGE_WARN_SHARE}
        if worst:
            listed = ", ".join(f"{k} ({v:,} row{'' if v == 1 else 's'})"
                               for k, v in worst.items())
            checks.append(_check("warn", "Readings outside the training range",
                                 f"{listed}. Predictions there are extrapolation; treat them with care."))
        elif out_of_range:
            checks.append(_check("pass", "Readings within the training range",
                                 f"A handful of readings sit just outside it "
                                 f"({sum(out_of_range.values())} in total), under 1 percent of rows."))
        else:
            checks.append(_check("pass", "Readings within the training range",
                                 "Every reading sits inside the range the model learned from."))

    if labels:
        checks.append(_check("pass", "Failure labels present",
                             f"{labels['failures']:,} recorded failures ({labels['failure_rate']:.1%}); "
                             f"predictions can be checked against them."))
    elif accepted:
        checks.append(_check("info", "No failure labels",
                             "Predictions only; there is nothing recorded to check them against."))

    statuses = {c["status"] for c in checks}
    if "fail" in statuses:
        verdict = "not_usable"
    elif "warn" in statuses:
        verdict = "use_with_care"
    else:
        verdict = "ready"

    return {
        "verdict": verdict,
        "rows_received": received,
        "rows_accepted": accepted,
        "rows_rejected": rejected,
        "rejections": [{"reason": r, "label": REJECTION_LABELS.get(r, r), "count": n}
                       for r, n in sorted(rejections.items(), key=lambda kv: -kv[1])],
        "columns": columns,
        "type_mix": type_mix,
        "labels": labels,
        "limit_breaches": breaches,
        "checks": checks,
    }


def verdict_label(verdict: str) -> str:
    return {"ready": "Ready", "use_with_care": "Use with care",
            "not_usable": "Not usable"}.get(verdict, verdict)

