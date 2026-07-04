import os
import uuid

import pandas as pd
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.doctor import Doctor
from app.models.healthy_range import DEFAULT_HEALTHY_RANGES, HealthyRange
from app.models.reading import HealthReading, MetricType
from app.models.user import User
from app.schemas.healthy_range import HealthyRangesIn, HealthyRangesOut
from app.schemas.quick_reading import QuickReadingIn, QuickReadingOut
from app.schemas.user import UserOut
from app.services.auth import get_current_doctor
from app.services.forecaster import refit_patient_forecast

router = APIRouter(prefix="/patients", tags=["patients"])

PATIENTS_DIR = os.path.join(
    os.path.dirname(__file__), "..", "..", "data", "patients"
)


@router.get("/", response_model=list[UserOut])
async def list_patients(
    db: AsyncSession = Depends(get_db),
    _: Doctor = Depends(get_current_doctor),
):
    result = await db.execute(select(User).order_by(User.full_name))
    return result.scalars().all()


def _append_to_readings_csv(
    patient_id: uuid.UUID,
    recorded_at: pd.Timestamp,
    hr: float | None,
    sbp: float | None,
    dbp: float | None,
    glu: float | None,
) -> None:
    """Append a row to the patient's _readings.csv so the chart picks it up.

    Missing metrics are forward-filled from the patient's most recent CSV row
    so the dashboard's resampling-then-dropna does not drop the entry.
    """
    path = os.path.join(PATIENTS_DIR, f"{patient_id}_readings.csv")
    if not os.path.exists(path):
        return  # no CSV for this patient (e.g. a manually-created user), skip silently

    df = pd.read_csv(path)
    last = df.iloc[-1]

    row = {
        "timestamp": recorded_at.isoformat(sep=" "),
        "heart_rate_bpm":     round(hr if hr is not None else float(last["heart_rate_bpm"]), 1),
        "systolic_bp_mmhg":   round(sbp if sbp is not None else float(last["systolic_bp_mmhg"]), 1),
        "diastolic_bp_mmhg":  round(dbp if dbp is not None else float(last["diastolic_bp_mmhg"]), 1),
        "glucose_mg_dl":      round(glu if glu is not None else float(last["glucose_mg_dl"]), 1),
    }

    pd.DataFrame([row]).to_csv(path, mode="a", header=False, index=False)


@router.post(
    "/{patient_id}/readings/quick",
    response_model=QuickReadingOut,
    status_code=201,
)
async def quick_record_reading(
    patient_id: uuid.UUID,
    body: QuickReadingIn,
    background_tasks: BackgroundTasks,
    db: AsyncSession = Depends(get_db),
    _doctor: Doctor = Depends(get_current_doctor),
):
    user = await db.get(User, patient_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    saved: list[str] = []

    if body.heart_rate_bpm is not None:
        db.add(HealthReading(
            user_id=patient_id,
            metric_type=MetricType.HEART_RATE,
            value=body.heart_rate_bpm,
            unit="bpm",
            source="manual",
            notes=body.notes,
            recorded_at=body.recorded_at,
        ))
        saved.append("heart_rate")

    if body.systolic_bp_mmhg is not None:
        # Schema validation guarantees diastolic is present too
        db.add(HealthReading(
            user_id=patient_id,
            metric_type=MetricType.BLOOD_PRESSURE,
            value=body.systolic_bp_mmhg,
            value_secondary=body.diastolic_bp_mmhg,
            unit="mmHg",
            source="manual",
            notes=body.notes,
            recorded_at=body.recorded_at,
        ))
        saved.append("blood_pressure")

    if body.glucose_mg_dl is not None:
        db.add(HealthReading(
            user_id=patient_id,
            metric_type=MetricType.GLUCOSE,
            value=body.glucose_mg_dl,
            unit="mg/dL",
            source="manual",
            notes=body.notes,
            recorded_at=body.recorded_at,
        ))
        saved.append("glucose")

    await db.flush()

    _append_to_readings_csv(
        patient_id,
        pd.Timestamp(body.recorded_at).tz_localize(None),
        body.heart_rate_bpm,
        body.systolic_bp_mmhg,
        body.diastolic_bp_mmhg,
        body.glucose_mg_dl,
    )

    # Refit Prophet for this patient in the background so the forecast
    # reflects the new reading on the next dashboard load (~5s after this
    # response returns). Doesn't block the API response.
    background_tasks.add_task(refit_patient_forecast, patient_id)

    return QuickReadingOut(saved_metrics=saved, recorded_at=body.recorded_at)


def _ranges_dict_to_response(ranges: list[HealthyRange]) -> HealthyRangesOut:
    by_metric = {r.metric_type: r for r in ranges}

    def fallback(metric: MetricType) -> dict:
        return DEFAULT_HEALTHY_RANGES[metric]

    hr = by_metric.get(MetricType.HEART_RATE)
    bp = by_metric.get(MetricType.BLOOD_PRESSURE)
    glu = by_metric.get(MetricType.GLUCOSE)

    hr_d = fallback(MetricType.HEART_RATE)
    bp_d = fallback(MetricType.BLOOD_PRESSURE)
    glu_d = fallback(MetricType.GLUCOSE)

    return HealthyRangesOut(
        heart_rate={
            "min": hr.min_value if hr else hr_d["min_value"],
            "max": hr.max_value if hr else hr_d["max_value"],
        },
        blood_pressure={
            "min": bp.min_value if bp else bp_d["min_value"],
            "max": bp.max_value if bp else bp_d["max_value"],
            "min_secondary": (bp.min_value_secondary if bp else bp_d["min_value_secondary"]),
            "max_secondary": (bp.max_value_secondary if bp else bp_d["max_value_secondary"]),
        },
        glucose={
            "min": glu.min_value if glu else glu_d["min_value"],
            "max": glu.max_value if glu else glu_d["max_value"],
        },
    )


@router.get("/{patient_id}/healthy-ranges", response_model=HealthyRangesOut)
async def get_healthy_ranges(
    patient_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
    _doctor: Doctor = Depends(get_current_doctor),
):
    user = await db.get(User, patient_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    rows = await db.execute(
        select(HealthyRange).where(HealthyRange.user_id == patient_id)
    )
    return _ranges_dict_to_response(list(rows.scalars().all()))


@router.put("/{patient_id}/healthy-ranges", response_model=HealthyRangesOut)
async def update_healthy_ranges(
    patient_id: uuid.UUID,
    body: HealthyRangesIn,
    db: AsyncSession = Depends(get_db),
    _doctor: Doctor = Depends(get_current_doctor),
):
    user = await db.get(User, patient_id)
    if user is None:
        raise HTTPException(status_code=404, detail="Patient not found")

    rows = await db.execute(
        select(HealthyRange).where(HealthyRange.user_id == patient_id)
    )
    existing = {r.metric_type: r for r in rows.scalars().all()}

    updates = {
        MetricType.HEART_RATE: dict(
            min_value=body.heart_rate.min, max_value=body.heart_rate.max,
            min_value_secondary=None, max_value_secondary=None,
        ),
        MetricType.BLOOD_PRESSURE: dict(
            min_value=body.blood_pressure.min, max_value=body.blood_pressure.max,
            min_value_secondary=body.blood_pressure.min_secondary,
            max_value_secondary=body.blood_pressure.max_secondary,
        ),
        MetricType.GLUCOSE: dict(
            min_value=body.glucose.min, max_value=body.glucose.max,
            min_value_secondary=None, max_value_secondary=None,
        ),
    }

    for metric, fields in updates.items():
        if metric in existing:
            row = existing[metric]
            for k, v in fields.items():
                setattr(row, k, v)
        else:
            db.add(HealthyRange(user_id=patient_id, metric_type=metric, **fields))

    await db.flush()

    rows = await db.execute(
        select(HealthyRange).where(HealthyRange.user_id == patient_id)
    )
    return _ranges_dict_to_response(list(rows.scalars().all()))
