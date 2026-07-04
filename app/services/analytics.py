"""
Time-in-Healthy-Range analytics.

The calculation is reading-count-based:
    TIR% = (readings inside healthy bounds / total readings) * 100

For blood pressure, BOTH systolic AND diastolic must be in range
for the reading to count as "in range".
"""

import uuid
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.healthy_range import HealthyRange
from app.models.reading import HealthReading, MetricType
from app.repositories.reading_repo import ReadingRepository
from app.schemas.reading import TimeInRangeResult


class AnalyticsService:
    def __init__(self, db: AsyncSession):
        self._db = db
        self._repo = ReadingRepository(db)

    async def time_in_range(
        self,
        user_id: uuid.UUID,
        metric_type: MetricType,
        window_days: int = 30,
    ) -> TimeInRangeResult:
        now = datetime.now(timezone.utc)
        window_start = now - timedelta(days=window_days)

        # Fetch healthy range thresholds for this user + metric
        stmt = select(HealthyRange).where(
            HealthyRange.user_id == user_id,
            HealthyRange.metric_type == metric_type,
        )
        result = await self._db.execute(stmt)
        healthy_range = result.scalar_one_or_none()
        if healthy_range is None:
            raise ValueError(f"No healthy range configured for metric {metric_type.value}")

        readings = await self._repo.get_range(user_id, metric_type, window_start, now)
        total = len(readings)

        in_range = 0
        for r in readings:
            primary_ok = healthy_range.min_value <= r.value <= healthy_range.max_value

            if metric_type == MetricType.BLOOD_PRESSURE:
                secondary_ok = (
                    healthy_range.min_value_secondary is not None
                    and healthy_range.max_value_secondary is not None
                    and r.value_secondary is not None
                    and healthy_range.min_value_secondary <= r.value_secondary <= healthy_range.max_value_secondary
                )
                in_range += int(primary_ok and secondary_ok)
            else:
                in_range += int(primary_ok)

        pct = (in_range / total * 100) if total > 0 else 0.0

        return TimeInRangeResult(
            metric_type=metric_type,
            window_days=window_days,
            total_readings=total,
            in_range_readings=in_range,
            time_in_range_pct=round(pct, 2),
            window_start=window_start,
            window_end=now,
        )
