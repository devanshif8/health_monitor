"""Forecaster: risk classification (pure) + a guarded Prophet smoke test."""

import numpy as np
import pandas as pd
import pytest

from app.services.forecaster import HEALTHY, classify_risk


# ── Pure logic: risk classification ──────────────────────────────────

def test_value_inside_range_is_low():
    assert classify_risk(70, 60, 100) == "Low"
    assert classify_risk(60, 60, 100) == "Low"   # boundary inclusive
    assert classify_risk(100, 60, 100) == "Low"


def test_slight_breach_is_medium():
    # 10% over the high bound (110 vs 100) → Medium.
    assert classify_risk(110, 60, 100) == "Medium"


def test_large_breach_is_high():
    # >20% over the high bound (130 vs 100) → High.
    assert classify_risk(130, 60, 100) == "High"


def test_low_breach_is_high_when_far_below():
    # 40 vs low bound 60 → 33% below → High.
    assert classify_risk(40, 60, 100) == "High"


def test_healthy_bands_are_consistent_with_generator():
    assert HEALTHY["glucose_mg_dl"] == (70, 140)
    assert HEALTHY["heart_rate_bpm"] == (60, 100)


# ── ML smoke test (heavy; auto-skips without Prophet) ────────────────

@pytest.mark.ml
def test_refit_patient_forecast_writes_valid_csv(tmp_path, monkeypatch):
    pytest.importorskip("prophet")
    from app.services import forecaster

    # Point the forecaster at a temp patients dir.
    monkeypatch.setattr(forecaster, "PATIENTS_DIR", str(tmp_path))

    pid = "11111111-1111-1111-1111-111111111111"
    n = 20 * 24  # 20 days hourly is enough for daily+weekly seasonality
    ts = pd.date_range("2026-01-01", periods=n, freq="h")
    hod = ts.hour.to_numpy()
    rng = np.random.default_rng(0)
    pd.DataFrame({
        "timestamp": ts,
        "heart_rate_bpm": 72 + 8 * np.sin((hod - 10) * np.pi / 12) + rng.normal(0, 2, n),
        "systolic_bp_mmhg": 115 + 6 * np.sin((hod - 10) * np.pi / 12) + rng.normal(0, 2, n),
        "diastolic_bp_mmhg": 75 + rng.normal(0, 2, n),
        "glucose_mg_dl": 100 + rng.normal(0, 5, n),
    }).to_csv(tmp_path / f"{pid}_readings.csv", index=False)

    ok = forecaster.refit_patient_forecast(pid)
    assert ok is True

    out = pd.read_csv(tmp_path / f"{pid}_forecast.csv")
    assert set(["timestamp", "predicted", "lower_bound", "upper_bound",
                "risk_level", "metric"]).issubset(out.columns)
    assert len(out) > 0
    assert set(out["metric"].unique()).issubset(set(HEALTHY.keys()))


def test_refit_missing_patient_returns_false(tmp_path, monkeypatch):
    from app.services import forecaster

    monkeypatch.setattr(forecaster, "PATIENTS_DIR", str(tmp_path))
    assert forecaster.refit_patient_forecast("does-not-exist") is False
