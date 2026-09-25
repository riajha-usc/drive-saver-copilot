"""In-memory telemetry registry.

A prototype store, deliberately. Uploaded datasets live in process and vanish on
restart, which is the right trade for a demo: no database to stand up, no
migration to write, and the shape of the data is the same one a real store would
hand back. Swapping this for Postgres later touches this file and nothing else.

One dataset is seeded at startup from the bundled AI4I sample so the dashboard
has assets to show before anyone uploads anything.
"""

from __future__ import annotations

import io
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone

import pandas as pd

from backend.ml.dataset import FEATURE_COLUMNS, add_features, clean, load_dataset
from backend.ml.predict import load_bundle, score_frame
from backend.ml.quality import build_report
from backend.physics import OperatingPoint, rule_failures

DEFAULT_DATASET_ID = "ai4i-sample"
ASSET_PREFIX = "VFD"


def asset_id_for(index: int) -> str:
    """Stable asset id for a dataset row.

    Each AI4I row is an independent snapshot of a machine, so a row is an asset.
    """
    return f"{ASSET_PREFIX}-{index:04d}"


@dataclass
class Dataset:
    id: str
    name: str
    uploaded_at: datetime
    frame: pd.DataFrame          # cleaned telemetry plus derived features
    scores: pd.DataFrame         # per row probabilities, band, RUL proxy, mode
    rows_rejected: int = 0
    quality: dict = field(default_factory=dict)
    _index_by_asset: dict = field(default_factory=dict)

    def __post_init__(self) -> None:
        self._index_by_asset = {asset_id_for(i): i for i in range(len(self.frame))}

    def row_index(self, asset_id: str) -> int | None:
        return self._index_by_asset.get(asset_id)

    def operating_point(self, index: int) -> OperatingPoint:
        r = self.frame.iloc[index]
        return OperatingPoint(
            type=str(r["type"]), air_temperature=float(r["air_temperature"]),
            process_temperature=float(r["process_temperature"]),
            rotational_speed=float(r["rotational_speed"]),
            torque=float(r["torque"]), tool_wear=float(r["tool_wear"]))

    @property
    def at_risk_count(self) -> int:
        return int((self.scores["risk_band"] != "normal").sum())

    def summary(self) -> dict:
        bands = self.scores["risk_band"].value_counts().to_dict()
        return {
            "dataset_id": self.id,
            "name": self.name,
            "uploaded_at": self.uploaded_at,
            "row_count": int(len(self.frame)),
            "rows_rejected": self.rows_rejected,
            "at_risk_count": self.at_risk_count,
            "risk_band_counts": {k: int(v) for k, v in bands.items()},
            "highest_risk_asset": self.highest_risk_asset(),
            "quality_verdict": self.quality.get("verdict"),
        }

    def highest_risk_asset(self) -> str | None:
        if self.scores.empty:
            return None
        return asset_id_for(int(self.scores["p_machine_failure"].idxmax()))


def _quality(frame) -> dict:
    """Quality report against the ranges the loaded model was trained on."""
    ranges = load_bundle().metrics.get("training_ranges")
    return build_report(frame, ranges)


class TelemetryStore:
    def __init__(self) -> None:
        self._datasets: dict[str, Dataset] = {}

    # ------------------------------------------------------------- lifecycle

    def seed_default(self) -> None:
        """Load the bundled AI4I sample so the dashboard is never empty."""
        if DEFAULT_DATASET_ID in self._datasets:
            return
        frame = load_dataset()
        self._datasets[DEFAULT_DATASET_ID] = Dataset(
            id=DEFAULT_DATASET_ID, name="AI4I 2020 sample",
            uploaded_at=datetime.now(timezone.utc),
            frame=frame, scores=score_frame(frame[FEATURE_COLUMNS]),
            rows_rejected=int(frame.attrs.get("rows_dropped", 0)),
            quality=_quality(frame))

    def ingest_csv(self, raw_bytes: bytes, name: str) -> Dataset:
        """Clean, feature engineer and score an uploaded CSV."""
        try:
            raw = pd.read_csv(io.BytesIO(raw_bytes))
        except Exception as exc:
            raise ValueError(f"could not parse the file as CSV: {exc}") from exc
        if raw.empty:
            raise ValueError("the uploaded file has no rows")

        cleaned = clean(raw)                    # raises ValueError on missing columns
        if cleaned.empty:
            raise ValueError("no usable telemetry rows survived cleaning")
        frame = add_features(cleaned)

        ds = Dataset(
            id=uuid.uuid4().hex[:12], name=name,
            uploaded_at=datetime.now(timezone.utc), frame=frame,
            scores=score_frame(frame[FEATURE_COLUMNS]),
            rows_rejected=int(len(raw) - len(cleaned)),
            quality=_quality(frame))
        self._datasets[ds.id] = ds
        return ds

    # ---------------------------------------------------------------- access

    def get(self, dataset_id: str) -> Dataset | None:
        return self._datasets.get(dataset_id)

    def list(self) -> list[Dataset]:
        return sorted(self._datasets.values(), key=lambda d: d.uploaded_at, reverse=True)

    def clear(self) -> None:
        self._datasets.clear()


def asset_row(ds: Dataset, index: int) -> dict:
    """One row rendered for the asset list and the telemetry chart."""
    tel = ds.frame.iloc[index]
    sc = ds.scores.iloc[index]
    op = ds.operating_point(index)
    return {
        "asset_id": asset_id_for(index),
        "row_index": index,
        "type": str(tel["type"]),
        "air_temperature": float(tel["air_temperature"]),
        "process_temperature": float(tel["process_temperature"]),
        "rotational_speed": float(tel["rotational_speed"]),
        "torque": float(tel["torque"]),
        "tool_wear": float(tel["tool_wear"]),
        "shaft_power_w": round(op.power_w, 1),
        "temp_diff_k": round(op.temp_diff, 2),
        "failure_probability": round(float(sc["p_machine_failure"]), 4),
        "risk_band": str(sc["risk_band"]),
        "rul_hours": float(sc["rul_hours"]),
        "likely_failure_mode": str(sc["likely_mode"]),
        "rule_violations": rule_failures(op),
    }


store = TelemetryStore()
