import uuid
from datetime import datetime

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.reading import HealthReading, MetricType


class ReadingRepository:
    def __init__(self, db: AsyncSession):
        self._db = db

    async def create(self, reading: HealthReading) -> HealthReading:
        self._db.add(reading)
        await self._db.flush()
        return reading

    async def get_range(
        self,
        user_id: uuid.UUID,
        metric_type: MetricType,
        start: datetime,
        end: datetime,
    ) -> list[HealthReading]:
        stmt = (
            select(HealthReading)
            .where(
                HealthReading.user_id == user_id,
                HealthReading.metric_type == metric_type,
                HealthReading.recorded_at >= start,
                HealthReading.recorded_at <= end,
            )
            .order_by(HealthReading.recorded_at.desc())
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def get_latest(
        self,
        user_id: uuid.UUID,
        metric_type: MetricType,
        limit: int = 1,
    ) -> list[HealthReading]:
        stmt = (
            select(HealthReading)
            .where(
                HealthReading.user_id == user_id,
                HealthReading.metric_type == metric_type,
            )
            .order_by(HealthReading.recorded_at.desc())
            .limit(limit)
        )
        result = await self._db.execute(stmt)
        return list(result.scalars().all())

    async def count_in_window(
        self,
        user_id: uuid.UUID,
        metric_type: MetricType,
        start: datetime,
        end: datetime,
    ) -> int:
        stmt = (
            select(func.count())
            .select_from(HealthReading)
            .where(
                HealthReading.user_id == user_id,
                HealthReading.metric_type == metric_type,
                HealthReading.recorded_at >= start,
                HealthReading.recorded_at <= end,
            )
        )
        result = await self._db.execute(stmt)
        return result.scalar_one()
