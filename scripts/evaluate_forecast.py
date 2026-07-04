"""
Backtest the Prophet forecaster against ground truth.

For each patient:
  1. Split 90 days of history -> train (first 80 days) + test (last 10 days)
  2. Fit Prophet on the train slice
  3. Predict the 10-day test window
  4. Also compute a "naive last-value" baseline (predict = last train value)
  5. Compute MAE, RMSE, MAPE for both

Aggregate across all patients and print one row per metric.

Usage:
  python scripts/evaluate_forecast.py                # all patients
  python scripts/evaluate_forecast.py --limit 20     # first 20 patients (fast)
"""

import argparse
import logging
import os
import sys
import time
import warnings

import numpy as np
import pandas as pd
from prophet import Prophet

logging.getLogger("cmdstanpy").setLevel(logging.ERROR)
logging.getLogger("prophet").setLevel(logging.ERROR)
warnings.filterwarnings("ignore")

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "data")
PATIENTS_DIR = os.path.join(DATA_DIR, "patients")
MANIFEST_FILE = os.path.join(DATA_DIR, "patients_manifest.csv")

TRAIN_DAYS = 80
TEST_DAYS = 10
FREQ = "h"

METRICS = [
    "heart_rate_bpm",
    "systolic_bp_mmhg",
    "diastolic_bp_mmhg",
    "glucose_mg_dl",
]


def mae(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.mean(np.abs(y_true - y_pred)))


def rmse(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    return float(np.sqrt(np.mean((y_true - y_pred) ** 2)))


def mape(y_true: np.ndarray, y_pred: np.ndarray) -> float:
    mask = y_true != 0
    if not mask.any():
        return float("nan")
    return float(np.mean(np.abs((y_true[mask] - y_pred[mask]) / y_true[mask])) * 100)


def prophet_forecast(train_df: pd.DataFrame, horizon_hours: int) -> np.ndarray:
    model = Prophet(
        daily_seasonality=True,
        weekly_seasonality=True,
        yearly_seasonality=False,
        interval_width=0.95,
        changepoint_prior_scale=0.05,
    )
    model.fit(train_df)
    future = model.make_future_dataframe(
        periods=horizon_hours, freq=FREQ, include_history=False
    )
    fc = model.predict(future)
    return fc["yhat"].to_numpy()


def evaluate_one_patient(patient_id: str) -> dict | None:
    readings_path = os.path.join(PATIENTS_DIR, f"{patient_id}_readings.csv")
    if not os.path.exists(readings_path):
        return None

    df = pd.read_csv(readings_path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    df = df.sort_values("timestamp").reset_index(drop=True)

    train_hours = TRAIN_DAYS * 24
    test_hours = TEST_DAYS * 24
    if len(df) < train_hours + test_hours:
        return None

    train = df.iloc[:train_hours]
    test = df.iloc[train_hours: train_hours + test_hours]

    out: dict[str, dict] = {}
    for metric in METRICS:
        train_m = train[["timestamp", metric]].rename(
            columns={"timestamp": "ds", metric: "y"}
        ).dropna()
        y_true = test[metric].to_numpy()

        try:
            y_prophet = prophet_forecast(train_m, test_hours)
        except Exception as exc:
            print(f"  [warn] prophet failed for {patient_id}/{metric}: {exc}")
            continue

        # Naive last-value baseline
        last_value = float(train_m["y"].iloc[-1])
        y_naive = np.full_like(y_true, last_value, dtype=float)

        out[metric] = {
            "prophet_mae":  mae(y_true, y_prophet),
            "prophet_rmse": rmse(y_true, y_prophet),
            "prophet_mape": mape(y_true, y_prophet),
            "naive_mae":    mae(y_true, y_naive),
            "naive_rmse":   rmse(y_true, y_naive),
            "naive_mape":   mape(y_true, y_naive),
        }

    return out if out else None


def aggregate(per_patient: list[dict]) -> pd.DataFrame:
    rows = []
    for metric in METRICS:
        vals = [p[metric] for p in per_patient if metric in p]
        if not vals:
            continue
        rows.append({
            "metric": metric,
            "n": len(vals),
            "prophet_mae":  np.mean([v["prophet_mae"]  for v in vals]),
            "prophet_rmse": np.mean([v["prophet_rmse"] for v in vals]),
            "prophet_mape": np.mean([v["prophet_mape"] for v in vals]),
            "naive_mae":    np.mean([v["naive_mae"]    for v in vals]),
            "naive_mape":   np.mean([v["naive_mape"]   for v in vals]),
        })
    df = pd.DataFrame(rows)
    df["improvement_vs_naive_%"] = (
        (df["naive_mape"] - df["prophet_mape"]) / df["naive_mape"] * 100
    ).round(1)
    return df


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None,
                        help="Only evaluate the first N patients.")
    args = parser.parse_args()

    if not os.path.exists(MANIFEST_FILE):
        print(f"Manifest not found at {MANIFEST_FILE}")
        return 1

    manifest = pd.read_csv(MANIFEST_FILE)
    if args.limit:
        manifest = manifest.head(args.limit)

    total = len(manifest)
    print(f"Backtest: train={TRAIN_DAYS}d / test={TEST_DAYS}d, "
          f"{total} patient(s), {len(METRICS)} metrics each.\n")

    t0 = time.time()
    per_patient: list[dict] = []
    for i, (_, row) in enumerate(manifest.iterrows(), start=1):
        pid = row["id"]
        t = time.time()
        res = evaluate_one_patient(pid)
        if res is not None:
            per_patient.append(res)
            print(f"  [{i}/{total}] {pid}  ({time.time() - t:.1f}s)")
        else:
            print(f"  [{i}/{total}] {pid}  SKIP")

    elapsed = time.time() - t0
    print(f"\nEvaluated {len(per_patient)}/{total} patients in {elapsed:.1f}s\n")

    if not per_patient:
        print("Nothing to summarise.")
        return 1

    summary = aggregate(per_patient)

    print("=" * 78)
    print(f"{'Metric':<20} {'MAE':>8} {'RMSE':>8} {'MAPE':>8} "
          f"{'NaiveMAPE':>10} {'Better by':>10}")
    print("-" * 78)
    for _, r in summary.iterrows():
        print(f"{r['metric']:<20} "
              f"{r['prophet_mae']:>8.2f} {r['prophet_rmse']:>8.2f} "
              f"{r['prophet_mape']:>7.2f}% "
              f"{r['naive_mape']:>9.2f}% "
              f"{r['improvement_vs_naive_%']:>9.1f}%")
    print("=" * 78)

    summary_path = os.path.join(DATA_DIR, "forecast_eval_summary.csv")
    summary.to_csv(summary_path, index=False)
    print(f"\nSaved summary to {summary_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
