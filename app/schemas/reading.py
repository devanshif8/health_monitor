import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.models.reading import MetricType


class ReadingCreate(BaseModel):
    metric_type: MetricType
    value: float = Field(..., description="Systolic BP / HR bpm / Glucose mg/dL")
    value_secondary: float | None = Field(None, description="Diastolic BP (omit for HR/glucose)")
    unit: str = Field(..., examples=["mmHg", "bpm", "mg/dL"])
    source: str | None = Field(None, examples=["manual", "apple_watch", "dexcom_g7"])
    notes: str | None = None
    recorded_at: datetime


class ReadingOut(BaseModel):
    id: uuid.UUID
    metric_type: MetricType
    value: float
    value_secondary: float | None
    unit: str
    source: str | None
    notes: str | None
    recorded_at: datetime
    created_at: datetime

    model_config = {"from_attributes": True}


class TimeInRangeResult(BaseModel):
    metric_type: MetricType
    window_days: int
    total_readings: int
    in_range_readings: int
    time_in_range_pct: float = Field(..., description="Percentage 0-100")
    window_start: datetime
    window_end: datetime
