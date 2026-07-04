import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_db
from app.models.healthy_range import DEFAULT_HEALTHY_RANGES, HealthyRange
from app.models.reading import MetricType
from app.models.user import User
from app.schemas.user import UserCreate, UserOut

router = APIRouter(prefix="/users", tags=["users"])


@router.post("/", response_model=UserOut, status_code=201)
async def create_user(
    body: UserCreate,
    db: AsyncSession = Depends(get_db),
):
    user = User(email=body.email, full_name=body.full_name)
    db.add(user)
    await db.flush()

    # Seed default healthy ranges for all metric types
    for metric_type, bounds in DEFAULT_HEALTHY_RANGES.items():
        db.add(HealthyRange(user_id=user.id, metric_type=metric_type, **bounds))
    await db.flush()

    return user


@router.get("/{user_id}", response_model=UserOut)
async def get_user(
    user_id: uuid.UUID,
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(User).where(User.id == user_id))
    user = result.scalar_one_or_none()
    if user is None:
        raise HTTPException(status_code=404, detail="User not found")
    return user
