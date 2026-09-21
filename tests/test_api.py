"""Phase 2: the HTTP layer.

Exercised through TestClient against the real app, real model and real agent.
Nothing is mocked, so a green run here means the dashboard can be built against
these endpoints as they stand.
"""

from __future__ import annotations

import io

import pytest
from fastapi.testclient import TestClient

from backend.agent.schema import PrescriptiveRecommendation
from backend.api.main import create_app
from backend.api.store import DEFAULT_DATASET_ID, store


@pytest.fixture(scope="module")
def client():
    with TestClient(create_app()) as c:
        yield c


@pytest.fixture(scope="module")
def sample_csv():
    """A small upload covering a healthy row and two breached limits."""
    return (
        "Type,Air temperature [K],Process temperature [K],Rotational speed [rpm],"
        "Torque [Nm],Tool wear [min]\n"
        "M,298.1,308.6,1551,42.8,20\n"        # healthy
        "L,298.4,308.9,1330,64.0,205\n"       # OSF and TWF breached
        "L,302.0,310.0,1345,42.0,110\n"       # HDF breached
    ).encode()


def _upload(client, csv_bytes, name="telemetry.csv"):
    return client.post("/datasets", files={"file": (name, io.BytesIO(csv_bytes), "text/csv")})


# --------------------------------------------------------------------- meta

def test_health_reports_a_loaded_model(client):
    body = client.get("/health").json()
    assert body["status"] == "ok"
    assert body["model_loaded"] is True
    assert body["model_trained_at"]


def test_model_endpoint_exposes_provenance_and_the_rul_caveat(client):
    body = client.get("/model").json()
    assert "machine_failure" in body["heads"]
    assert body["metrics"]["heads"]["machine_failure"]["pr_auc"] > 0.8
    assert body["rul_is_proxy"] is True
    assert "proxy" in body["rul_note"].lower()


def test_the_sample_dataset_is_seeded_on_startup(client):
    """The dashboard should never open to an empty asset list."""
    body = client.get(f"/datasets/{DEFAULT_DATASET_ID}").json()
    assert body["row_count"] == 10000
    assert body["at_risk_count"] > 0
    assert body["highest_risk_asset"]


# ---------------------------------------------------------------- ingestion

def test_upload_cleans_scores_and_summarises(client, sample_csv):
    r = _upload(client, sample_csv)
    assert r.status_code == 201
    body = r.json()
    assert body["row_count"] == 3
    assert body["rows_rejected"] == 0
    assert body["at_risk_count"] == 2
    assert body["dataset_id"] != DEFAULT_DATASET_ID


def test_upload_accepts_the_stripped_column_spelling_too(client):
    csv = ("Type,Air temperature,Process temperature,Rotational speed,Torque,Tool wear\n"
           "M,298.1,308.6,1551,42.8,20\n").encode()
    assert _upload(client, csv).status_code == 201


def test_upload_drops_unusable_rows_without_failing_the_batch(client):
    csv = ("Type,Air temperature [K],Process temperature [K],Rotational speed [rpm],"
           "Torque [Nm],Tool wear [min]\n"
           "M,298.1,308.6,1551,42.8,20\n"
           "M,298.1,308.6,0,42.8,20\n"          # 0 rpm is not usable
           "Z,298.1,308.6,1500,42.8,20\n").encode()   # not a quality class
    body = _upload(client, csv).json()
    assert body["row_count"] == 1
    assert body["rows_rejected"] == 2


def test_upload_rejects_a_file_missing_required_columns(client):
    csv = b"Type,Torque [Nm]\nM,42.8\n"
    r = _upload(client, csv)
    assert r.status_code == 422
    assert "missing required columns" in r.json()["detail"]


def test_upload_rejects_an_empty_file(client):
    r = _upload(client, b"")
    assert r.status_code == 400


def test_upload_rejects_a_file_that_is_not_csv(client):
    r = _upload(client, b"\x89PNG\r\n\x1a\n not a spreadsheet", name="image.png")
    assert r.status_code == 422


def test_inline_scoring_needs_no_upload(client):
    r = client.post("/telemetry/score", json={"rows": [
        {"type": "M", "air_temperature": 298.1, "process_temperature": 308.6,
         "rotational_speed": 1551, "torque": 42.8, "tool_wear": 20},
        {"type": "L", "air_temperature": 298.4, "process_temperature": 308.9,
         "rotational_speed": 1330, "torque": 64.0, "tool_wear": 205},
    ]})
    body = r.json()
    assert body["count"] == 2
    assert body["results"][0]["risk_band"] == "normal"
    assert body["results"][1]["risk_band"] == "critical"
    assert "OSF" in body["results"][1]["rule_violations"]


def test_inline_scoring_validates_physics(client):
    r = client.post("/telemetry/score", json={"rows": [
        {"type": "M", "air_temperature": 298.1, "process_temperature": 308.6,
         "rotational_speed": 0, "torque": 42.8, "tool_wear": 20}]})
    assert r.status_code == 422
