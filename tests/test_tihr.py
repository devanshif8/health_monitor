"""Unit tests for the Time-in-Healthy-Range calculator (pure, no DB)."""

import numpy as np
import pandas as pd
import pytest

from app.services.tihr import DEFAULT_RANGES, calculate_tihr


def _frame(rows):
    return pd.DataFrame(rows)


def test_all_readings_in_range_is_100pct():
    df = _frame([
        {"timestamp": "2026-01-01 00:00", "heart_rate_bpm": 70,
         "systolic_bp_mmhg": 110, "glucose_mg_dl": 100},
        {"timestamp": "2026-01-01 01:00", "heart_rate_bpm": 80,
         "systolic_bp_mmhg": 115, "glucose_mg_dl": 120},
    ])
    res = calculate_tihr(df)
    assert res["total_readings"] == 2
    assert res["simultaneous_tihr_pct"] == 100.0
    for metric in ("heart_rate_bpm", "systolic_bp_mmhg", "glucose_mg_dl"):
        assert res["per_metric"][metric]["tihr_pct"] == 100.0


def test_per_metric_counts_are_correct():
    # HR: one high (150) out of range; glucose all fine; systolic one low (60).
    df = _frame([
        {"timestamp": "2026-01-01 00:00", "heart_rate_bpm": 70,
         "systolic_bp_mmhg": 60, "glucose_mg_dl": 100},   # sys out
        {"timestamp": "2026-01-01 01:00", "heart_rate_bpm": 150,
         "systolic_bp_mmhg": 110, "glucose_mg_dl": 100},  # hr out
    ])
    res = calculate_tihr(df)
    assert res["per_metric"]["heart_rate_bpm"]["in_range_count"] == 1
    assert res["per_metric"]["systolic_bp_mmhg"]["in_range_count"] == 1
    assert res["per_metric"]["glucose_mg_dl"]["in_range_count"] == 2


def test_simultaneous_requires_all_metrics_in_range():
    # Neither row has ALL three simultaneously in range.
    df = _frame([
        {"timestamp": "2026-01-01 00:00", "heart_rate_bpm": 150,
         "systolic_bp_mmhg": 110, "glucose_mg_dl": 100},
        {"timestamp": "2026-01-01 01:00", "heart_rate_bpm": 70,
         "systolic_bp_mmhg": 110, "glucose_mg_dl": 300},
    ])
    res = calculate_tihr(df)
    assert res["simultaneous_in_range"] == 0
    assert res["simultaneous_tihr_pct"] == 0.0


def test_empty_dataframe_does_not_crash():
    df = pd.DataFrame(columns=["timestamp", "heart_rate_bpm"])
    res = calculate_tihr(df)
    assert res["total_readings"] == 0
    assert res["simultaneous_tihr_pct"] == 0.0
    assert res["per_metric"] == {}


def test_nan_values_from_sensor_dropout_do_not_crash():
    """Dirty-data resilience: NaNs must not raise and must count as out-of-range."""
    df = _frame([
        {"timestamp": "2026-01-01 00:00", "heart_rate_bpm": np.nan,
         "systolic_bp_mmhg": 110, "glucose_mg_dl": 100},
        {"timestamp": "2026-01-01 01:00", "heart_rate_bpm": 70,
         "systolic_bp_mmhg": 110, "glucose_mg_dl": 100},
    ])
    res = calculate_tihr(df)  # must not raise
    # NaN comparison is False → that reading is not "in range".
    assert res["per_metric"]["heart_rate_bpm"]["in_range_count"] == 1
    assert res["simultaneous_in_range"] == 1


def test_custom_ranges_override_defaults():
    df = _frame([
        {"timestamp": "2026-01-01 00:00", "heart_rate_bpm": 105,
         "systolic_bp_mmhg": 110, "glucose_mg_dl": 100},
    ])
    # Default HR max is 100 → out of range. Widen it to 110 → in range.
    res = calculate_tihr(df, ranges={"heart_rate_bpm": (60, 110)})
    assert res["per_metric"]["heart_rate_bpm"]["tihr_pct"] == 100.0


def test_time_window_filtering():
    df = _frame([
        {"timestamp": "2026-01-01 00:00", "heart_rate_bpm": 70,
         "systolic_bp_mmhg": 110, "glucose_mg_dl": 100},
        {"timestamp": "2026-01-05 00:00", "heart_rate_bpm": 80,
         "systolic_bp_mmhg": 110, "glucose_mg_dl": 100},
    ])
    res = calculate_tihr(df, start="2026-01-03", end="2026-01-06")
    assert res["total_readings"] == 1


def test_glucose_default_is_70_to_140():
    """Guards the consistency fix — must match forecaster / generator bands."""
    assert DEFAULT_RANGES["glucose_mg_dl"] == (70, 140)
