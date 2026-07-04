"""
Prophet-based per-patient forecaster.

Fits a Prophet model per metric on a patient's full readings history and
writes a 28-day hourly forecast to data/patients/{id}_forecast.csv.

Used both by:
  - scripts/train_real_forecasts.py (bulk train all 1000 patients)
  - app/routers/patients.py         (refit a single patient via FastAPI
                                     BackgroundTasks whenever new readings
                                     come in, so forecasts never go stale)
"""

import logging
import os
import uuid
import warnings

import pandas as pd

# NOTE: prophet is imported lazily inside _fit_and_predict, not here. It's a
# heavy dependency (pulls in cmdstan) and only the forecast-fitting path needs
# it - keeping it out of module import lets the API, the CLI scripts, and the
# unit tests load this module without the ML stack installed.

logging.getLogger("cmdstanpy").setLevel(logging.ERROR)
logging.getLogger("prophet").setLevel(logging.ERROR)
warnings.filterwarnings("ignore")

DATA_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "data")
PATIENTS_DIR = os.path.join(DATA_DIR, "patients")

DAYS_FORECAST = 28
FREQ = "h"

METRICS = [
    "heart_rate_bpm",
    "systolic_bp_mmhg",
    "diastolic_bp_mmhg",
    "glucose_mg_dl",
]

HEALTHY = {
    "heart_rate_bpm":     (60, 100),
    "systolic_bp_mmhg":   (90, 120),
    "diastolic_bp_mmhg":  (60, 80),
    "glucose_mg_dl":      (70, 140),
}

log = logging.getLogger("forecaster")


def classify_risk(value: float, low: float, high: float) -> str:
    if low <= value <= high:
        return "Low"
    pct_low = (low - value) / low if low > 0 else 0
    pct_high = (value - high) / high if high > 0 else 0
    breach = max(pct_low, pct_high)
    return "High" if breach > 0.20 else "Medium"


def _fit_and_predict(history: pd.DataFrame, metric: str) -> pd.DataFrame:
    from prophet import Prophet

    df = history[["timestamp", metric]].rename(
        columns={"timestamp": "ds", metric: "y"}
    ).dropna()

    model = Prophet(
        daily_seasonality=True,
        weekly_seasonality=True,
        yearly_seasonality=False,
        interval_width=0.95,
        changepoint_prior_scale=0.05,
    )
    model.fit(df)
    future = model.make_future_dataframe(
        periods=DAYS_FORECAST * 24, freq=FREQ, include_history=False
    )
    fc = model.predict(future)
    return fc[["ds", "yhat", "yhat_lower", "yhat_upper"]]


def refit_patient_forecast(patient_id: uuid.UUID | str) -> bool:
    """Refit Prophet for one patient and overwrite their forecast CSV.

    Safe to call from FastAPI BackgroundTasks - never raises. Returns True
    on success, False if there's no readings file or Prophet failed.
    """
    pid = str(patient_id)
    readings_path = os.path.join(PATIENTS_DIR, f"{pid}_readings.csv")
    forecast_path = os.path.join(PATIENTS_DIR, f"{pid}_forecast.csv")

    if not os.path.exists(readings_path):
        log.warning("forecaster: no readings file for %s", pid)
        return False

    try:
        history = pd.read_csv(readings_path)
        history["timestamp"] = pd.to_datetime(history["timestamp"])
    except Exception as exc:
        log.warning("forecaster: could not load readings for %s: %s", pid, exc)
        return False

    rows: list[dict] = []
    for metric in METRICS:
        try:
            fc = _fit_and_predict(history, metric)
        except Exception as exc:
            log.warning("forecaster: %s failed for %s: %s", metric, pid, exc)
            continue
        low, high = HEALTHY[metric]
        for _, r in fc.iterrows():
            rows.append({
                "timestamp": r["ds"],
                "predicted": round(float(r["yhat"]), 2),
                "lower_bound": round(float(r["yhat_lower"]), 2),
                "upper_bound": round(float(r["yhat_upper"]), 2),
                "risk_level": classify_risk(float(r["yhat"]), low, high),
                "metric": metric,
            })

    if not rows:
        return False

    try:
        pd.DataFrame(rows).to_csv(forecast_path, index=False)
    except Exception as exc:
        log.warning("forecaster: could not write forecast for %s: %s", pid, exc)
        return False

    log.info("forecaster: refit %s (%d rows)", pid, len(rows))
    return True
