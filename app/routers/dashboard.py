"""Dashboard endpoints: per-patient history, forecasts, and TIHR stats,
read straight from the generated CSV files."""

import os
import uuid

from fastapi import APIRouter, Depends, HTTPException, Query
import pandas as pd
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.healthy_range import HealthyRange
from app.models.reading import MetricType
from app.services.tihr import calculate_tihr

router = APIRouter(prefix="/dashboard", tags=["dashboard"])

# DB MetricType -> the column name tihr.calculate_tihr expects
_METRIC_TO_COLUMN = {
    MetricType.HEART_RATE: "heart_rate_bpm",
    MetricType.BLOOD_PRESSURE: "systolic_bp_mmhg",
    MetricType.GLUCOSE: "glucose_mg_dl",
}


async def _load_user_ranges(
    db: AsyncSession, patient_id: uuid.UUID
) -> dict[str, tuple[float, float]]:
    rows = await db.execute(
        select(HealthyRange).where(HealthyRange.user_id == patient_id)
    )
    out: dict[str, tuple[float, float]] = {}
    for r in rows.scalars().all():
        col = _METRIC_TO_COLUMN.get(r.metric_type)
        if col:
            out[col] = (float(r.min_value), float(r.max_value))
    return out

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
PATIENTS_DIR = os.path.join(DATA_DIR, "patients")
EVAL_SUMMARY_FILE = os.path.join(DATA_DIR, "forecast_eval_summary.csv")

_METRIC_DISPLAY = {
    "heart_rate_bpm":     {"label": "Heart Rate",    "unit": "bpm"},
    "systolic_bp_mmhg":   {"label": "Systolic BP",   "unit": "mmHg"},
    "diastolic_bp_mmhg":  {"label": "Diastolic BP",  "unit": "mmHg"},
    "glucose_mg_dl":      {"label": "Glucose",       "unit": "mg/dL"},
}


def _readings_path(patient_id: uuid.UUID) -> str:
    return os.path.join(PATIENTS_DIR, f"{patient_id}_readings.csv")


def _forecast_path(patient_id: uuid.UUID) -> str:
    return os.path.join(PATIENTS_DIR, f"{patient_id}_forecast.csv")


def _load_readings(patient_id: uuid.UUID) -> pd.DataFrame:
    path = _readings_path(patient_id)
    if not os.path.exists(path):
        raise HTTPException(status_code=404, detail="No readings for this patient")
    df = pd.read_csv(path)
    df["timestamp"] = pd.to_datetime(df["timestamp"])
    return df


@router.get("/historical")
def get_historical(
    patient_id: uuid.UUID = Query(...),
    last_days: int = Query(30, ge=1, le=90),
):
    df = _load_readings(patient_id)

    cutoff = df["timestamp"].max() - pd.Timedelta(days=last_days)
    df = df[df["timestamp"] >= cutoff]

    # Resample to every 6 hours for cleaner charts
    df = df.set_index("timestamp").resample("6h").mean().reset_index()
    df = df.dropna()

    records = []
    for _, row in df.iterrows():
        records.append({
            "timestamp": row["timestamp"].isoformat(),
            "heart_rate": round(row["heart_rate_bpm"], 1),
            "systolic_bp": round(row["systolic_bp_mmhg"], 1),
            "diastolic_bp": round(row["diastolic_bp_mmhg"], 1),
            "glucose": round(row["glucose_mg_dl"], 1),
        })
    return records


@router.get("/forecast-data")
def get_forecast_data(patient_id: uuid.UUID = Query(...)):
    forecast_file = _forecast_path(patient_id)
    if not os.path.exists(forecast_file):
        return []

    df = pd.read_csv(forecast_file)
    df["timestamp"] = pd.to_datetime(df["timestamp"])

    metrics = df["metric"].unique()
    result = None
    for metric in metrics:
        mdf = df[df["metric"] == metric][["timestamp", "predicted", "risk_level"]].copy()
        mdf = mdf.rename(columns={"predicted": metric, "risk_level": f"{metric}_risk"})
        if result is None:
            result = mdf
        else:
            result = pd.merge(result, mdf, on="timestamp", how="outer")

    if result is None:
        return []

    numeric_cols = [c for c in result.columns if c not in ["timestamp"] and "_risk" not in c]
    result = result.set_index("timestamp")
    resampled = result[numeric_cols].resample("6h").mean().reset_index().dropna()

    records = []
    for _, row in resampled.iterrows():
        entry = {"timestamp": row["timestamp"].isoformat()}
        if "heart_rate_bpm" in row:
            entry["heart_rate"] = round(row["heart_rate_bpm"], 1)
        if "systolic_bp_mmhg" in row:
            entry["systolic_bp"] = round(row["systolic_bp_mmhg"], 1)
        if "diastolic_bp_mmhg" in row:
            entry["diastolic_bp"] = round(row["diastolic_bp_mmhg"], 1)
        if "glucose_mg_dl" in row:
            entry["glucose"] = round(row["glucose_mg_dl"], 1)
        records.append(entry)

    return records


@router.get("/model-performance")
def get_model_performance():
    """Return backtest accuracy metrics for the Prophet forecaster.

    Reads scripts/evaluate_forecast.py's output CSV. If the file does not
    exist (forecaster never validated), returns an empty object so the
    frontend can hide the card gracefully.
    """
    if not os.path.exists(EVAL_SUMMARY_FILE):
        return {"validated": False}

    df = pd.read_csv(EVAL_SUMMARY_FILE)
    metrics = []
    n_patients = 0
    for _, r in df.iterrows():
        meta = _METRIC_DISPLAY.get(r["metric"], {"label": r["metric"], "unit": ""})
        metrics.append({
            "metric": r["metric"],
            "label": meta["label"],
            "unit": meta["unit"],
            "mae":  round(float(r["prophet_mae"]), 2),
            "rmse": round(float(r["prophet_rmse"]), 2),
            "mape": round(float(r["prophet_mape"]), 2),
            "naive_mape": round(float(r["naive_mape"]), 2),
            "improvement_pct": round(float(r["improvement_vs_naive_%"]), 1),
        })
        n_patients = max(n_patients, int(r["n"]))

    return {
        "validated": True,
        "n_patients": n_patients,
        "horizon_days": 10,
        "model": "Prophet",
        "metrics": metrics,
    }


@router.get("/tihr")
async def get_tihr(
    patient_id: uuid.UUID = Query(...),
    last_days: int = Query(30, ge=1, le=90),
    db: AsyncSession = Depends(get_db),
):
    df = _load_readings(patient_id)

    end = str(df["timestamp"].max())
    start = str(df["timestamp"].max() - pd.Timedelta(days=last_days))

    ranges = await _load_user_ranges(db, patient_id)
    result = calculate_tihr(df, ranges=ranges or None, start=start, end=end)
    result.pop("breakdown", None)
    return result
