"""Task 1: ingestion, cleaning and feature engineering."""

import pandas as pd
import pytest

from backend.ml import dataset


def test_column_normalisation_handles_both_uci_spellings():
    assert dataset._normalise_column("Air temperature [K]") == "air_temperature"
    assert dataset._normalise_column("Air temperature") == "air_temperature"
    assert dataset._normalise_column("Rotational speed [rpm]") == "rotational_speed"
    assert dataset._normalise_column("Machine failure") == "machine_failure"


def test_clean_drops_identifiers_and_bad_rows():
    raw = pd.DataFrame({
        "UDI": [1, 2, 3],
        "Product ID": ["L1", "L2", "L3"],
        "Type": ["L", "Z", "m"],               # Z is not a valid quality class
        "Air temperature [K]": [298.0, 298.0, 299.0],
        "Process temperature [K]": [308.0, 308.0, 309.0],
        "Rotational speed [rpm]": [1500, 1500, 0],   # 0 rpm is unusable
        "Torque [Nm]": [40.0, 40.0, 40.0],
        "Tool wear [min]": [10, 10, 10],
        "Machine failure": [0, 0, 1],
    })
    out = dataset.clean(raw)
    assert "udi" not in out.columns and "product_id" not in out.columns
    assert list(out["type"]) == ["L"]          # Z filtered, 0 rpm row dropped
    assert out["machine_failure"].dtype.kind == "i"


def test_clean_requires_the_core_telemetry_columns():
    with pytest.raises(ValueError, match="missing required columns"):
        dataset.clean(pd.DataFrame({"Type": ["L"], "Torque [Nm]": [40.0]}))


def test_add_features_matches_the_physics_module():
    df = dataset.add_features(pd.DataFrame({
        "type": ["L"], "air_temperature": [298.0], "process_temperature": [308.5],
        "rotational_speed": [1500.0], "torque": [40.0], "tool_wear": [100.0]}))
    assert df.loc[0, "temp_diff"] == pytest.approx(10.5)
    assert df.loc[0, "wear_torque"] == pytest.approx(4000.0)
    assert df.loc[0, "osf_utilisation"] == pytest.approx(4000.0 / 11000.0)
    assert df.loc[0, "type_ordinal"] == 0


def test_loaded_dataset_shape_and_labels():
    df = dataset.load_dataset()
    assert len(df) == 10000
    assert set(dataset.FEATURE_COLUMNS).issubset(df.columns)
    assert df["machine_failure"].sum() == 339
    assert "RNF" not in dataset.FAILURE_MODES     # injected noise stays out


def test_frame_from_records_round_trips_an_operating_point(healthy_point):
    X = dataset.frame_from_records([healthy_point])
    assert list(X.columns) == dataset.FEATURE_COLUMNS
    assert X.loc[0, "power_w"] == pytest.approx(healthy_point.power_w)
