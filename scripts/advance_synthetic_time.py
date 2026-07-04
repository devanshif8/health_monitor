"""
Advance synthetic patient histories forward in time.

Reads each patient's `_forecast.csv`, takes the next N days of predicted
values, adds measurement noise so they look like real readings, and appends
them to `_readings.csv`. Then regenerates `_forecast.csv` so the 28-day
forecast horizon starts fresh from the new last reading.

Usage:
    python scripts/advance_synthetic_time.py            # default: 14 days
    python scripts/advance_synthetic_time.py --days 30
    python scripts/advance_synthetic_time.py --patient <uuid> --days 7
    python scripts/advance_synthetic_time.py --no-regenerate-forecast
"""

import argparse
import os
import sys

import numpy as np
import pandas as pd

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
PATIENTS_DIR = os.path.join(DATA_DIR, "patients")
MANIFEST_FILE = os.path.join(DATA_DIR, "patients_manifest.csv")

READINGS_PER_DAY = 24
DAYS_FORECAST = 28
TREND_FIT_HOURS = 30 * 24  # use last 30 days to estimate trend

NOISE_STD = {
    "heart_rate_bpm":    2.5,
    "systolic_bp_mmhg":  3.5,
    "diastolic_bp_mmhg": 2.5,
    "glucose_mg_dl":     6.0,
}
CLIP = {
    "heart_rate_bpm":    (45, 150),
    "systolic_bp_mmhg":  (80, 200),
    "diastolic_bp_mmhg": (50, 130),
    "glucose_mg_dl":     (50, 300),
}
# Healthy bands - must match scripts/generate_synthetic_patients.py
HEALTHY = {
    "heart_rate_bpm":     (60, 100),
    "systolic_bp_mmhg":   (90, 120),
    "diastolic_bp_mmhg":  (60, 80),
    "glucose_mg_dl":      (70, 140),
}
# Forecast amplitude (circadian) and prediction-interval sigma per metric
FORECAST_AMP = {
    "heart_rate_bpm":    5,
    "systolic_bp_mmhg":  6,
    "diastolic_bp_mmhg": 4,
    "glucose_mg_dl":     15,
}
FORECAST_SIGMA = {
    "heart_rate_bpm":    3.0,
    "systolic_bp_mmhg":  4.0,
    "diastolic_bp_mmhg": 3.0,
    "glucose_mg_dl":     6.0,
}

# Ongoing telemetry is dirty too: inject light corruption into appended readings,
# but never into the final row so "current vitals" always render.
MISSING_CELL_RATE = 0.015
OUTLIER_RATE = 0.002
OUTLIER_RANGES = {
    "heart_rate_bpm":    ((30, 44), (155, 230)),
    "systolic_bp_mmhg":  ((60, 78), (185, 235)),
    "diastolic_bp_mmhg": ((38, 48), (115, 140)),
    "glucose_mg_dl":     ((40, 55), (320, 480)),
}


def _dirty_new_rows(new_rows: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Inject isolated NaNs and rare motion-artifact outliers into freshly
    appended readings, leaving the last row clean."""
    n = len(new_rows)
    if n == 0:
        return new_rows
    protect_from = n - 1  # keep the newest reading pristine
    for col in NOISE_STD.keys():
        if col not in new_rows.columns:
            continue
        pos = new_rows.columns.get_loc(col)
        miss = rng.random(n) < MISSING_CELL_RATE
        miss[protect_from:] = False
        new_rows.iloc[miss, pos] = np.nan
        lo_band, hi_band = OUTLIER_RANGES[col]
        out = rng.random(n) < OUTLIER_RATE
        out[protect_from:] = False
        for i in np.where(out)[0]:
            band = lo_band if rng.random() < 0.5 else hi_band
            new_rows.iat[i, pos] = round(float(rng.uniform(*band)), 1)
    return new_rows


def _circadian(hour: int) -> float:
    return float(np.sin((hour - 10) * np.pi / 12))


def _classify_risk(value: float, low: float, high: float) -> str:
    if low <= value <= high:
        return "Low"
    pct_low = (low - value) / low if low > 0 else 0
    pct_high = (value - high) / high if high > 0 else 0
    breach = max(pct_low, pct_high)
    return "High" if breach > 0.20 else "Medium"


def _advance_readings(
    readings: pd.DataFrame, forecast: pd.DataFrame, days: int, rng: np.random.Generator
) -> pd.DataFrame | None:
    """Return the new rows to append, or None if nothing to add."""
    last_ts = readings["timestamp"].max()

    wide = forecast.pivot_table(
        index="timestamp", columns="metric", values="predicted"
    ).reset_index()

    wide = wide[wide["timestamp"] > last_ts].sort_values("timestamp")
    n_take = days * READINGS_PER_DAY
    wide = wide.head(n_take)

    if wide.empty:
        return None

    new_rows = pd.DataFrame({"timestamp": wide["timestamp"]})
    for col, sigma in NOISE_STD.items():
        if col not in wide.columns:
            new_rows[col] = readings[col].iloc[-1]
            continue
        noisy = wide[col].to_numpy() + rng.normal(0, sigma, len(wide))
        lo, hi = CLIP[col]
        new_rows[col] = np.round(np.clip(noisy, lo, hi), 1)

    return new_rows[readings.columns.tolist()]


def _regenerate_forecast(readings: pd.DataFrame, rng: np.random.Generator) -> pd.DataFrame:
    """Build a fresh long-format forecast DataFrame from the updated readings."""
    n_fcst = DAYS_FORECAST * READINGS_PER_DAY
    last_ts = readings["timestamp"].max()
    fcst_ts = pd.date_range(last_ts + pd.Timedelta(hours=1), periods=n_fcst, freq="h")
    fcst_hour_of_day = fcst_ts.hour.to_numpy()
    fcst_idx = np.arange(n_fcst)

    rows = []
    for metric in NOISE_STD.keys():
        series = readings[metric].to_numpy()
        # Use last week as the forecast intercept, last 30 days for trend slope.
        intercept = float(series[-168:].mean())
        recent = series[-TREND_FIT_HOURS:]
        if len(recent) >= 2:
            slope, _ = np.polyfit(np.arange(len(recent)), recent, 1)
        else:
            slope = 0.0

        amp = FORECAST_AMP[metric]
        sigma = FORECAST_SIGMA[metric]
        circ = np.sin((fcst_hour_of_day - 10) * np.pi / 12)
        preds = intercept + slope * fcst_idx + amp * circ + rng.normal(0, sigma * 0.3, n_fcst)

        low, high = HEALTHY[metric]
        for ts, p in zip(fcst_ts, preds):
            rows.append({
                "timestamp": ts,
                "predicted": round(float(p), 2),
                "lower_bound": round(float(p - 1.96 * sigma), 2),
                "upper_bound": round(float(p + 1.96 * sigma), 2),
                "risk_level": _classify_risk(float(p), low, high),
                "metric": metric,
            })
    return pd.DataFrame(rows)


def advance_patient(
    patient_id: str, days: int, regenerate_forecast: bool, rng: np.random.Generator
) -> int:
    readings_path = os.path.join(PATIENTS_DIR, f"{patient_id}_readings.csv")
    forecast_path = os.path.join(PATIENTS_DIR, f"{patient_id}_forecast.csv")

    if not (os.path.exists(readings_path) and os.path.exists(forecast_path)):
        return 0

    readings = pd.read_csv(readings_path)
    readings["timestamp"] = pd.to_datetime(readings["timestamp"])

    forecast = pd.read_csv(forecast_path)
    forecast["timestamp"] = pd.to_datetime(forecast["timestamp"])

    new_rows = _advance_readings(readings, forecast, days, rng)
    if new_rows is None:
        return 0

    # Dirty a copy for disk; keep the clean version for forecast regeneration.
    dirty = _dirty_new_rows(new_rows.copy(), rng)
    out = dirty.copy()
    out["timestamp"] = out["timestamp"].dt.strftime("%Y-%m-%d %H:%M:%S")
    out.to_csv(readings_path, mode="a", header=False, index=False)

    if regenerate_forecast:
        updated = pd.concat([readings, new_rows], ignore_index=True)
        updated["timestamp"] = pd.to_datetime(updated["timestamp"])
        new_forecast = _regenerate_forecast(updated, rng)
        new_forecast["timestamp"] = pd.to_datetime(new_forecast["timestamp"]).dt.strftime(
            "%Y-%m-%d %H:%M:%S"
        )
        new_forecast.to_csv(forecast_path, index=False)

    return len(new_rows)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--days", type=int, default=14, help="How many days to advance (default 14)")
    parser.add_argument("--patient", type=str, default=None, help="Single patient UUID (default: all)")
    parser.add_argument("--seed", type=int, default=None, help="RNG seed for reproducibility")
    parser.add_argument(
        "--no-regenerate-forecast",
        dest="regenerate_forecast",
        action="store_false",
        help="Skip rewriting _forecast.csv after appending new readings.",
    )
    parser.set_defaults(regenerate_forecast=True)
    args = parser.parse_args()

    rng = np.random.default_rng(args.seed)

    if args.patient:
        patient_ids = [args.patient]
    else:
        if not os.path.exists(MANIFEST_FILE):
            print(f"Manifest not found: {MANIFEST_FILE}", file=sys.stderr)
            sys.exit(1)
        patient_ids = pd.read_csv(MANIFEST_FILE)["id"].astype(str).tolist()

    total_rows = 0
    touched = 0
    for i, pid in enumerate(patient_ids, start=1):
        added = advance_patient(pid, args.days, args.regenerate_forecast, rng)
        total_rows += added
        if added > 0:
            touched += 1
        if i % 100 == 0:
            print(f"  processed {i}/{len(patient_ids)}")

    fcst_note = "regenerated forecasts" if args.regenerate_forecast else "left forecasts unchanged"
    print(f"\nAdvanced {touched}/{len(patient_ids)} patients by up to {args.days} days "
          f"({total_rows} total new rows); {fcst_note}.")
    if touched < len(patient_ids):
        print("Patients with no rows added had already exhausted their forecast window.")


if __name__ == "__main__":
    main()
