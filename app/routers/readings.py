import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.reading import HealthReading, MetricType
from app.repositories.reading_repo import ReadingRepository
from app.schemas.reading import ReadingCreate, ReadingOut, TimeInRangeResult
from app.services.analytics import AnalyticsService

router = APIRouter(prefix="/users/{user_id}/readings", tags=["readings"])


@router.post("/", response_model=ReadingOut, status_code=201)
async def create_reading(
    user_id: uuid.UUID,
    body: ReadingCreate,
    db: AsyncSession = Depends(get_db),
):
    repo = ReadingRepository(db)
    reading = HealthReading(
        user_id=user_id,
        metric_type=body.metric_type,
        value=body.value,
        value_secondary=body.value_secondary,
        unit=body.unit,
        source=body.source,
        notes=body.notes,
        recorded_at=body.recorded_at,
    )
    created = await repo.create(reading)
    return created


@router.get("/", response_model=list[ReadingOut])
async def list_readings(
    user_id: uuid.UUID,
    metric_type: MetricType = Query(...),
    start: datetime | None = Query(None),
    end: datetime | None = Query(None),
    limit: int = Query(100, le=1000),
    db: AsyncSession = Depends(get_db),
):
    repo = ReadingRepository(db)
    if start and end:
        return await repo.get_range(user_id, metric_type, start, end)
    return await repo.get_latest(user_id, metric_type, limit=limit)


@router.get("/time-in-range", response_model=TimeInRangeResult)
async def get_time_in_range(
    user_id: uuid.UUID,
    metric_type: MetricType = Query(...),
    window_days: int = Query(30, ge=1, le=365),
    db: AsyncSession = Depends(get_db),
):
    svc = AnalyticsService(db)
    try:
        return await svc.time_in_range(user_id, metric_type, window_days)
    except ValueError as exc:
        raise HTTPException(status_code=404, detail=str(exc))
