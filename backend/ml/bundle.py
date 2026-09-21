"""Serialisable container for the trained heads.

Kept in its own module so the pickled class always resolves to the same import
path, whether training ran via `python -m backend.ml.train` or the API imported it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

import pandas as pd

from backend.ml.dataset import FEATURE_COLUMNS


@dataclass
class ModelBundle:
    models: dict
    thresholds: dict
    feature_columns: list = field(default_factory=lambda: list(FEATURE_COLUMNS))
    background: pd.DataFrame | None = None   # SHAP reference sample
    metrics: dict = field(default_factory=dict)
    trained_at: str = ""
