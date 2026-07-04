"""
Per-user healthy range thresholds.

Defaults are seeded on user creation but can be overridden
(e.g., a diabetic patient may have a wider glucose target).
"""

import uuid
from datetime import datetime, timezone

from sqlalchemy import DateTime, Float, ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base
from app.models.reading import MetricType


class HealthyRange(Base):
    __tablename__ = "healthy_ranges"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    user_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))

    metric_type: Mapped[MetricType] = mapped_column(String(20))

    # Inclusive bounds for the primary value
    min_value: Mapped[float] = mapped_column(Float)
    max_value: Mapped[float] = mapped_column(Float)
    # Inclusive bounds for secondary value (diastolic BP). NULL for non-BP.
    min_value_secondary: Mapped[float | None] = mapped_column(Float, nullable=True)
    max_value_secondary: Mapped[float | None] = mapped_column(Float, nullable=True)

    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc)
    )

    user: Mapped["User"] = relationship(back_populates="healthy_ranges")

    __table_args__ = (
        UniqueConstraint("user_id", "metric_type", name="uq_user_metric_range"),
    )


# Clinical defaults used when seeding a new user
DEFAULT_HEALTHY_RANGES: dict[MetricType, dict] = {
    MetricType.BLOOD_PRESSURE: {
        "min_value": 90, "max_value": 120,
        "min_value_secondary": 60, "max_value_secondary": 80,
    },
    MetricType.HEART_RATE: {
        "min_value": 60, "max_value": 100,
    },
    MetricType.GLUCOSE: {
        "min_value": 70, "max_value": 140,
    },
}


from app.models.user import User  # noqa: E402, F811
