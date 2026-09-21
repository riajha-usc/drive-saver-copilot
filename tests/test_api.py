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


# ------------------------------------------------------------------- assets

def test_asset_list_leads_with_the_riskiest(client):
    body = client.get(f"/datasets/{DEFAULT_DATASET_ID}/assets",
                      params={"limit": 20}).json()
    probs = [a["failure_probability"] for a in body["assets"]]
    assert probs == sorted(probs, reverse=True)
    assert body["assets"][0]["risk_band"] == "critical"


def test_asset_list_filters_by_band_and_risk_floor(client):
    body = client.get(f"/datasets/{DEFAULT_DATASET_ID}/assets",
                      params={"band": "critical", "limit": 200}).json()
    assert body["total"] > 0
    assert all(a["risk_band"] == "critical" for a in body["assets"])

    floored = client.get(f"/datasets/{DEFAULT_DATASET_ID}/assets",
                         params={"min_risk": 0.9, "limit": 200}).json()
    assert all(a["failure_probability"] >= 0.9 for a in floored["assets"])


def test_asset_list_pages(client):
    q = {"limit": 5, "offset": 0}
    first = client.get(f"/datasets/{DEFAULT_DATASET_ID}/assets", params=q).json()
    second = client.get(f"/datasets/{DEFAULT_DATASET_ID}/assets",
                        params={"limit": 5, "offset": 5}).json()
    assert first["returned"] == second["returned"] == 5
    assert {a["asset_id"] for a in first["assets"]}.isdisjoint(
        {a["asset_id"] for a in second["assets"]})


def test_asset_detail_carries_margins_and_shap_factors(client, sample_csv):
    ds_id = _upload(client, sample_csv).json()["dataset_id"]
    body = client.get(f"/datasets/{ds_id}/assets/VFD-0001").json()
    assert body["asset"]["risk_band"] == "critical"
    assert body["likely_failure_mode_name"] == "Overstrain Failure"
    assert {m["mode"] for m in body["margins"]} == {"PWF", "HDF", "OSF", "TWF"}
    assert any(m["violated"] for m in body["margins"])
    assert body["factors"] and body["factors"][0]["share_of_risk"] >= 0


def test_asset_history_returns_a_plottable_trace(client):
    body = client.get(f"/datasets/{DEFAULT_DATASET_ID}/assets/VFD-0100/history",
                      params={"window": 30}).json()
    assert body["window"] == 30
    assert body["points"][-1]["asset_id"] == "VFD-0100"
    assert [p["row_index"] for p in body["points"]] == list(range(71, 101))
    # The note has to travel with the data: these rows are not one machine's run.
    assert "not a time series" in body["note"]


def test_history_clamps_at_the_start_of_the_dataset(client):
    body = client.get(f"/datasets/{DEFAULT_DATASET_ID}/assets/VFD-0002/history",
                      params={"window": 60}).json()
    assert body["window"] == 3
    assert body["points"][0]["row_index"] == 0


def test_unknown_dataset_and_asset_give_actionable_404s(client):
    r = client.get("/datasets/nope/assets")
    assert r.status_code == 404 and "Upload one" in r.json()["detail"]

    r = client.get(f"/datasets/{DEFAULT_DATASET_ID}/assets/NOT-AN-ASSET")
    assert r.status_code == 404 and "VFD-0000" in r.json()["detail"]


# ----------------------------------------------------------- prescriptions

def test_recommendation_serves_the_agent_contract_unchanged(client, sample_csv):
    ds_id = _upload(client, sample_csv).json()["dataset_id"]
    r = client.post(f"/datasets/{ds_id}/assets/VFD-0001/recommendation",
                    params={"hours_to_window": 48})
    assert r.status_code == 200
    rec = PrescriptiveRecommendation.model_validate(r.json())
    assert rec.asset_id == "VFD-0001"
    assert rec.risk.likely_failure_mode == "OSF"
    assert rec.adjustments
    assert rec.projection.reaches_maintenance_window
    assert rec.narrative.headline


def test_recommendation_honours_the_maintenance_window(client, sample_csv):
    ds_id = _upload(client, sample_csv).json()["dataset_id"]
    tight = client.post(f"/datasets/{ds_id}/assets/VFD-0002/recommendation",
                        params={"hours_to_window": 24}).json()
    wide = client.post(f"/datasets/{ds_id}/assets/VFD-0002/recommendation",
                       params={"hours_to_window": 200}).json()
    assert tight["projection"]["hours_to_maintenance_window"] == 24
    assert (wide["projection"]["projected_rul_hours"]
            >= tight["projection"]["projected_rul_hours"])


def test_recommendation_rejects_a_nonsense_window(client, sample_csv):
    ds_id = _upload(client, sample_csv).json()["dataset_id"]
    r = client.post(f"/datasets/{ds_id}/assets/VFD-0000/recommendation",
                    params={"hours_to_window": -5})
    assert r.status_code == 422


def test_healthy_asset_returns_no_action(client, sample_csv):
    ds_id = _upload(client, sample_csv).json()["dataset_id"]
    rec = client.post(f"/datasets/{ds_id}/assets/VFD-0000/recommendation").json()
    assert rec["action_type"] == "no_action"
    assert rec["adjustments"] == []


def test_ad_hoc_recommendation_needs_no_dataset(client):
    r = client.post("/recommendations", json={
        "asset_id": "LINE-3-EXTRUDER",
        "hours_to_window": 48,
        "telemetry": {"type": "L", "air_temperature": 302.0,
                      "process_temperature": 310.0, "rotational_speed": 1345,
                      "torque": 42.0, "tool_wear": 110}})
    rec = PrescriptiveRecommendation.model_validate(r.json())
    assert rec.asset_id == "LINE-3-EXTRUDER"
    assert rec.risk.likely_failure_mode == "HDF"
    # The heat fix is to speed up, not throttle.
    speed = [a for a in rec.adjustments if a.parameter == "rotational_speed"]
    assert speed and speed[0].change_pct > 0


def test_apply_reports_the_adjusted_point_without_claiming_to_have_written_it(
        client, sample_csv):
    ds_id = _upload(client, sample_csv).json()["dataset_id"]
    body = client.post(f"/datasets/{ds_id}/assets/VFD-0002/apply",
                       json={"hours_to_window": 48}).json()
    assert body["applied"] is False
    assert "no connection to a VFD" in body["applied_note"]
    assert body["adjustments"]
    assert body["failure_probability_after"] < body["failure_probability_before"]
    assert body["rul_hours_after"] >= body["rul_hours_before"]
    assert body["after"]["shaft_power_w"] != body["before"]["shaft_power_w"]


# ------------------------------------------------------------------ contract

def test_openapi_documents_the_prescriptive_contract(client):
    schema = client.get("/openapi.json").json()
    assert "PrescriptiveRecommendation" in schema["components"]["schemas"]
    ref = schema["paths"]["/recommendations"]["post"]["responses"]["200"]
    body = ref["content"]["application/json"]["schema"]
    assert body["$ref"].endswith("PrescriptiveRecommendation")


# -------------------------------------------------------------- dashboard

@pytest.fixture(scope="module")
def built():
    """A client for a checkout where the dashboard has actually been built."""
    from backend.api.static import DIST_DIR
    if not (DIST_DIR / "index.html").is_file():
        pytest.skip("frontend not built; run npm run build in frontend/")
    with TestClient(create_app()) as c:
        yield c


class TestDashboardServing:
    """The dashboard and the API share one origin, so the mount must not eat
    API routes and an API typo must not quietly return HTML."""

    def test_root_serves_the_dashboard(self, built):
        r = built.get("/")
        assert r.status_code == 200
        assert "text/html" in r.headers["content-type"]
        assert "<div id=\"root\">" in r.text

    def test_client_routes_fall_back_to_the_app_shell(self, built):
        """A refresh on a client side route must not 404."""
        for route in ("/assets/VFD-0001", "/upload", "/assets/VFD-0001/detail"):
            r = built.get(route)
            assert r.status_code == 200, route
            assert "text/html" in r.headers["content-type"], route

    def test_built_files_are_served(self, built):
        """The hashed bundle the app shell references must actually resolve."""
        import re
        html = built.get("/").text
        for ref in re.findall(r'(?:src|href)="(/static/[^"]+)"', html):
            assert built.get(ref).status_code == 200, ref

    def test_api_routes_are_not_shadowed(self, built):
        assert built.get("/health").json()["status"] == "ok"
        assert built.get("/model").status_code == 200
        assert built.get(f"/datasets/{DEFAULT_DATASET_ID}").status_code == 200
        assert built.get("/openapi.json").status_code == 200
        assert built.get("/docs").status_code == 200

    def test_a_wrong_api_path_still_404s_as_an_api_path(self, built):
        """Returning the dashboard HTML for a mistyped endpoint would turn a
        clear 404 into a confusing 200 full of markup."""
        r = built.get("/datasets/ai4i-sample/assets/VFD-0001/recomendation")
        assert r.status_code == 404
        assert "text/html" not in r.headers.get("content-type", "")

    def test_the_api_runs_without_a_built_dashboard(self, monkeypatch, tmp_path):
        """Backend only checkouts and CI must not need a node build."""
        monkeypatch.setattr("backend.api.static.DIST_DIR", tmp_path / "nothing")
        with TestClient(create_app()) as c:
            assert c.get("/health").json()["status"] == "ok"
            assert c.get("/").status_code == 404
