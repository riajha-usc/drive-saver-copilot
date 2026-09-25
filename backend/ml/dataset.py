"""Task 1a: ingest and clean the AI4I 2020 telemetry.

Source of truth is the UCI repository (id 601) pulled through ucimlrepo. The raw
frame is cached to data/raw/ai4i2020.csv so training and the API can run offline
after the first fetch.
"""

from __future__ import annotations

import re

import numpy as np
import pandas as pd

from backend import config
from backend.physics import RPM_TO_RAD_S, QUALITY_TYPES

# Canonical internal names. The UCI CSV and the ucimlrepo frame label the same
# columns differently (units in brackets vs stripped), so both are mapped here.
CANONICAL = {
    "type": "type",
    "air temperature": "air_temperature",
    "process temperature": "process_temperature",
    "rotational speed": "rotational_speed",
    "torque": "torque",
    "tool wear": "tool_wear",
    "machine failure": "machine_failure",
    "twf": "TWF",
    "hdf": "HDF",
    "pwf": "PWF",
    "osf": "OSF",
    "rnf": "RNF",
}

BASE_FEATURES = ["air_temperature", "process_temperature", "rotational_speed", "torque", "tool_wear"]
DERIVED_FEATURES = ["temp_diff", "power_w", "wear_torque", "osf_utilisation", "type_ordinal"]
FEATURE_COLUMNS = BASE_FEATURES + DERIVED_FEATURES

# RNF is injected noise (0.1 percent random) with no physical driver, so it is
# excluded from the modelled failure modes.
FAILURE_MODES = ["HDF", "PWF", "OSF", "TWF"]
TARGET_COLUMNS = ["machine_failure"] + FAILURE_MODES

TYPE_ORDINAL = {"L": 0, "M": 1, "H": 2}
OSF_LIMITS = {"L": 11000.0, "M": 12000.0, "H": 13000.0}


def _normalise_column(name: str) -> str:
    key = re.sub(r"\[.*?\]", "", str(name)).strip().lower()
    key = re.sub(r"\s+", " ", key)
    return CANONICAL.get(key, key.replace(" ", "_"))


def fetch_raw(force: bool = False) -> pd.DataFrame:
    """Return the raw AI4I frame, fetching from UCI on first use."""
    config.ensure_dirs()
    if config.RAW_CSV.exists() and not force:
        return pd.read_csv(config.RAW_CSV)

    from ucimlrepo import fetch_ucirepo  # imported lazily so offline runs work

    ai4i_data = fetch_ucirepo(id=config.UCI_DATASET_ID)
    X = ai4i_data.data.features
    y = ai4i_data.data.targets
    raw = pd.concat([X, y], axis=1)
    raw.to_csv(config.RAW_CSV, index=False)
    return raw


def clean(raw: pd.DataFrame) -> pd.DataFrame:
    """Normalise names, drop identifiers, coerce dtypes, drop unusable rows."""
    df = raw.copy()
    df.columns = [_normalise_column(c) for c in df.columns]
    df = df.drop(columns=[c for c in ("udi", "product_id", "productid") if c in df.columns])

    missing = [c for c in ["type", *BASE_FEATURES] if c not in df.columns]
    if missing:
        raise ValueError(f"telemetry is missing required columns: {missing}")

    received = len(df)
    rejections: dict[str, int] = {}

    def keep(mask, reason: str) -> None:
        """Drop the rows failing a check and count them under that reason."""
        nonlocal df
        dropped = int((~mask).sum())
        if dropped:
            rejections[reason] = rejections.get(reason, 0) + dropped
        df = df[mask]

    df["type"] = df["type"].astype(str).str.strip().str.upper()
    keep(df["type"].isin(QUALITY_TYPES), "unknown_type")

    for col in BASE_FEATURES:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    for col in TARGET_COLUMNS + ["RNF"]:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce").fillna(0).astype(int)

    keep(df[BASE_FEATURES].notna().all(axis=1), "missing_or_non_numeric")
    keep(df["rotational_speed"] > 0, "non_positive_speed")
    keep(df["torque"] >= 0, "negative_torque")
    keep(df["tool_wear"] >= 0, "negative_tool_wear")
    keep(~df.duplicated(), "duplicate_row")

    df = df.reset_index(drop=True)
    # Read by the dataset quality report. Checks run in the order above, so a row
    # is counted under the first check it fails.
    df.attrs["rows_received"] = received
    df.attrs["rejections"] = rejections
    df.attrs["rows_dropped"] = received - len(df)
    return df


def add_features(df: pd.DataFrame) -> pd.DataFrame:
    """Attach the physically meaningful derived features the agent reasons over."""
    out = df.copy()
    out["temp_diff"] = out["process_temperature"] - out["air_temperature"]
    out["power_w"] = out["torque"] * out["rotational_speed"] * RPM_TO_RAD_S
    out["wear_torque"] = out["tool_wear"] * out["torque"]
    limits = out["type"].map(OSF_LIMITS).astype(float)
    out["osf_utilisation"] = out["wear_torque"] / limits
    out["type_ordinal"] = out["type"].map(TYPE_ORDINAL).astype(int)
    return out


def load_dataset(force_fetch: bool = False) -> pd.DataFrame:
    """Cleaned, feature engineered AI4I frame ready for training."""
    return add_features(clean(fetch_raw(force=force_fetch)))


def split(df: pd.DataFrame, test_size: float | None = None, seed: int | None = None):
    """Stratified train/test split on the machine failure label."""
    from sklearn.model_selection import train_test_split

    test_size = config.TEST_SIZE if test_size is None else test_size
    seed = config.RANDOM_STATE if seed is None else seed
    X = df[FEATURE_COLUMNS]
    y = df[[c for c in TARGET_COLUMNS if c in df.columns]]
    return train_test_split(X, y, test_size=test_size, random_state=seed, stratify=y["machine_failure"])


def frame_from_records(records) -> pd.DataFrame:
    """Build a feature frame from raw telemetry dicts or OperatingPoint objects."""
    rows = []
    for r in records:
        d = r if isinstance(r, dict) else {
            "type": r.type,
            "air_temperature": r.air_temperature,
            "process_temperature": r.process_temperature,
            "rotational_speed": r.rotational_speed,
            "torque": r.torque,
            "tool_wear": r.tool_wear,
        }
        rows.append({_normalise_column(k): v for k, v in d.items()})
    df = pd.DataFrame(rows)
    df["type"] = df["type"].astype(str).str.upper()
    for col in BASE_FEATURES:
        df[col] = pd.to_numeric(df[col], errors="raise").astype(np.float64)
    return add_features(df)[FEATURE_COLUMNS]
