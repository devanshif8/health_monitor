"""Time-series table holding every vitals reading.

One table for all metric types, discriminated by `metric_type` - simpler to
query than a table per metric, and it maps cleanly onto a TimescaleDB
hypertable later if we need it. `value` is the primary number (HR, glucose,
systolic) and `value_secondary` carries diastolic for blood pressure, NULL
otherwise. `recorded_at` is when the reading was taken; `created_at` is when we
stored it.
"""

import enum
import uuid
from datetime import datetime, timezone

from sqlalchemy import (
    DateTime,
    Float,
    ForeignKey,
    Index,
    String,
    Text,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


class MetricType(str, enum.Enum):
    BLOOD_PRESSURE = "blood_pressure"
    HEART_RATE = "heart_rate"
    GLUCOSE = "glucose"


class HealthReading(Base):
    __tablename__ = "health_readings"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    metric_type: Mapped[MetricType] = mapped_column(String(20))

    # Primary value: systolic BP (mmHg), heart rate (bpm), or glucose (mg/dL)
    value: Mapped[float] = mapped_column(Float)
    # Secondary value: diastolic BP, NULL for heart_rate / glucose
    value_secondary: Mapped[float | None] = mapped_column(Float, nullable=True)

    unit: Mapped[str] = mapped_column(String(20))
    source: Mapped[str | None] = mapped_column(String(60), nullable=True)
    notes: Mapped[str | None] = mapped_column(Text, nullable=True)

    recorded_at: Mapped[datetime] = mapped_column(DateTime(timezone=True))
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship(back_populates="readings")

    __table_args__ = (
        # the workhorse index: last-N readings of a metric for a user
        Index("ix_readings_user_metric_time", "user_id", "metric_type", "recorded_at"),
        Index("ix_readings_recorded_at", "recorded_at"),
    )


from app.models.user import User  # noqa: E402, F811
