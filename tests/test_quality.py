"""Dataset quality report: usable rows and why, training range, verdict."""

from __future__ import annotations

import io

import pandas as pd
import pytest

from backend.ml.dataset import add_features, clean
from backend.ml.quality import build_report

HEADER = ("Type,Air temperature [K],Process temperature [K],Rotational speed [rpm],"
          "Torque [Nm],Tool wear [min]")
RANGES = {
    "air_temperature": {"min": 295.3, "max": 304.5, "mean": 300.0},
    "process_temperature": {"min": 305.7, "max": 313.8, "mean": 310.0},
    "rotational_speed": {"min": 1168, "max": 2886, "mean": 1539},
    "torque": {"min": 3.8, "max": 76.6, "mean": 40.0},
    "tool_wear": {"min": 0, "max": 253, "mean": 108},
}


def frame(*rows):
    raw = pd.read_csv(io.StringIO("\n".join([HEADER, *rows])))
    return add_features(clean(raw))


GOOD = ["M,298.1,308.6,1551,42.8,20", "L,298.4,308.9,1330,64.0,205", "H,300.0,310.0,1600,35.0,90"]


def good_rows(n: int) -> list[str]:
    """n distinct, in range rows. Repeating one row would be rejected as a
    duplicate, which is the cleaner working, not a fixture."""
    return [f"{'LMH'[i % 3]},{298.0 + (i % 50) * 0.1:.1f},{308.0 + (i % 40) * 0.1:.1f},"
            f"{1400 + i * 7},{30.0 + (i % 30):.1f},{i % 200}" for i in range(n)]


def test_cleaning_records_why_each_row_was_rejected():
    df = frame(*GOOD,
               "Z,298.1,308.6,1551,42.8,20",      # unknown type
               "M,298.1,abc,1551,42.8,20",         # non numeric
               "M,298.1,308.6,0,42.8,20",          # zero speed
               "M,298.1,308.6,1551,-1,20",         # negative torque
               "M,298.1,308.6,1551,42.8,20")       # duplicate of the first good row
    assert len(df) == 3
    assert df.attrs["rows_received"] == 8
    assert df.attrs["rejections"] == {
        "unknown_type": 1, "missing_or_non_numeric": 1, "non_positive_speed": 1,
        "negative_torque": 1, "duplicate_row": 1}


def test_a_clean_in_range_dataset_is_ready():
    report = build_report(frame(*good_rows(24)), RANGES)
    assert report["verdict"] == "ready"
    assert report["rows_rejected"] == 0
    assert all(c["out_of_range"] == 0 for c in report["columns"])
    assert {c["status"] for c in report["checks"]} <= {"pass", "info"}


def test_many_skipped_rows_warn():
    bad = ["M,298.1,308.6,0,42.8,20"] * 3           # 3 of 27 rows, over 5 percent
    report = build_report(frame(*good_rows(24), *bad), RANGES)
    assert report["verdict"] == "use_with_care"
    assert report["rows_received"] == 27 and report["rows_accepted"] == 24
    assert report["rejections"][0]["reason"] == "non_positive_speed"
    warn = next(c for c in report["checks"] if c["title"] == "Some rows skipped")
    assert warn["status"] == "warn" and "rotational speed of zero or less (3)" in warn["detail"]


def test_skipped_row_reasons_keep_their_capitals_and_counts():
    report = build_report(frame(*good_rows(24), "Z,298.1,308.6,1551,42.8,20",
                                "M,298.1,308.6,0,42.8,20"), RANGES)
    detail = next(c for c in report["checks"] if c["title"] == "Some rows skipped")["detail"]
    assert "product type not L, M or H (1)" in detail
    assert "mostly" not in detail


def test_readings_outside_the_training_range_warn():
    report = build_report(frame(*good_rows(24), "M,299.0,309.5,1500,120.0,50"), RANGES)
    assert report["verdict"] == "use_with_care"
    torque = next(c for c in report["columns"] if c["column"] == "torque")
    assert torque["out_of_range"] == 1 and torque["training_max"] == 76.6
    warn = next(c for c in report["checks"] if "training range" in c["title"])
    assert warn["status"] == "warn" and "Torque (1 row)" in warn["detail"]


def test_a_handful_out_of_range_passes_with_a_note():
    report = build_report(frame(*good_rows(120), "M,299.0,309.5,1500,120.0,50"), RANGES)
    check = next(c for c in report["checks"] if "training range" in c["title"])
    assert check["status"] == "pass" and "handful" in check["detail"]


def test_missing_training_ranges_are_declared_not_assumed():
    report = build_report(frame(*good_rows(24)), None)
    assert report["verdict"] == "use_with_care"
    assert any(c["title"] == "Training range unknown" for c in report["checks"])


def test_small_datasets_warn_and_labels_are_reported():
    labelled = frame(*GOOD)
    labelled["machine_failure"] = [0, 1, 0]
    for mode in ("HDF", "PWF", "OSF", "TWF"):
        labelled[mode] = [0, 1 if mode == "OSF" else 0, 0]
    report = build_report(labelled, RANGES)
    assert any(c["title"] == "Small dataset" for c in report["checks"])
    assert report["labels"] == {"failure_rate": 0.3333, "failures": 1,
                                "by_mode": {"HDF": 0, "PWF": 0, "OSF": 1, "TWF": 0}}
    assert report["limit_breaches"]["OSF"] == 1 and report["limit_breaches"]["TWF"] == 1
    assert report["type_mix"] == {"L": 1, "M": 1, "H": 1}


def test_no_usable_rows_is_not_usable():
    df = frame("M,298.1,308.6,0,42.8,20")
    report = build_report(df, RANGES)
    assert report["verdict"] == "not_usable"
    assert report["rows_accepted"] == 0


# ------------------------------------------------------------------- API

@pytest.fixture(scope="module")
def client():
    from fastapi.testclient import TestClient
    from backend.api.main import create_app
    with TestClient(create_app()) as c:
        yield c


def test_the_sample_dataset_reports_ready(client):
    body = client.get("/datasets/ai4i-sample/quality").json()
    assert body["verdict"] == "ready"
    assert body["rows_accepted"] == 10000
    assert client.get("/datasets/ai4i-sample").json()["quality_verdict"] == "ready"


def test_an_upload_carries_its_verdict_and_report(client):
    csv = "\n".join([HEADER, *good_rows(24), "M,299.0,309.5,1500,120.0,50",
                     "X,299,309,1500,40,20"]).encode()
    summary = client.post("/datasets", files={"file": ("t.csv", io.BytesIO(csv), "text/csv")}).json()
    assert summary["quality_verdict"] == "use_with_care"
    report = client.get(f"/datasets/{summary['dataset_id']}/quality").json()
    assert report["rows_rejected"] == 1
    assert report["rejections"][0]["label"] == "Product type not L, M or H"
    assert client.get("/datasets/nope/quality").status_code == 404
