"""The synthetic generator injects realistic 'dirty data'. These tests prove the
corruption is present (so the dataset isn't a suspiciously-clean red flag) yet
still safe for the downstream pipeline to consume."""

import importlib.util
import os

import numpy as np
import pandas as pd
import pytest

from app.services.tihr import calculate_tihr

# Import the standalone generator script by path (scripts/ is not a package).
_GEN_PATH = os.path.join(
    os.path.dirname(__file__), "..", "scripts", "generate_synthetic_patients.py"
)
_spec = importlib.util.spec_from_file_location("gen", _GEN_PATH)
gen = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(gen)


def _clean_frame(n=2160):
    ts = pd.date_range("2026-01-01", periods=n, freq="h")
    return pd.DataFrame({
        "timestamp": ts,
        "heart_rate_bpm": np.full(n, 72.0),
        "systolic_bp_mmhg": np.full(n, 115.0),
        "diastolic_bp_mmhg": np.full(n, 75.0),
        "glucose_mg_dl": np.full(n, 100.0),
    })


def test_injection_introduces_missing_values():
    rng = np.random.default_rng(0)
    dirty = gen._inject_dirty_data(_clean_frame(), rng)
    total_nan = dirty[gen.METRICS].isna().sum().sum()
    assert total_nan > 0, "expected some NaNs from dropouts / missing cells"


def test_timestamps_never_corrupted():
    rng = np.random.default_rng(1)
    dirty = gen._inject_dirty_data(_clean_frame(), rng)
    assert dirty["timestamp"].isna().sum() == 0


def test_recent_tail_is_kept_clean():
    """The last CLEAN_TAIL_HOURS must be pristine so 'current vitals' render."""
    rng = np.random.default_rng(2)
    dirty = gen._inject_dirty_data(_clean_frame(), rng)
    tail = dirty[gen.METRICS].iloc[-gen.CLEAN_TAIL_HOURS:]
    assert tail.isna().sum().sum() == 0
    # untouched baseline values, so no outlier/typo landed in the tail
    assert (tail["heart_rate_bpm"] == 72.0).all()


def test_downstream_tihr_survives_dirty_data():
    rng = np.random.default_rng(3)
    dirty = gen._inject_dirty_data(_clean_frame(), rng)
    res = calculate_tihr(dirty)  # must not raise on NaNs / outliers
    assert res["total_readings"] == len(dirty)


def test_missing_rate_is_realistic_not_overwhelming():
    """Dirty, but not so dirty the data is unusable — a few percent, not half."""
    rng = np.random.default_rng(4)
    dirty = gen._inject_dirty_data(_clean_frame(), rng)
    frac = dirty[gen.METRICS].isna().sum().sum() / dirty[gen.METRICS].size
    assert 0.0 < frac < 0.15


def test_sample_age_correlates_with_profile():
    rng = np.random.default_rng(5)
    healthy = [gen._sample_age(rng, "healthy") for _ in range(300)]
    chronic = [gen._sample_age(rng, "chronic") for _ in range(300)]
    assert np.mean(healthy) < np.mean(chronic)  # healthy skews younger
    assert min(healthy) >= 20 and max(chronic) <= 90
