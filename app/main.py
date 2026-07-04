import os
import uuid
from contextlib import asynccontextmanager

import pandas as pd
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from sqlalchemy import delete, func, select

from app.config import get_settings
from app.database import async_session_factory, engine, Base
from app.models import doctor as _doctor  # noqa: F401  ensures Doctor table is registered
from app.models.healthy_range import DEFAULT_HEALTHY_RANGES, HealthyRange
from app.models.user import User
from app.routers import auth, dashboard, patients, readings, users

MANIFEST_FILE = os.path.join(
    os.path.dirname(__file__), "..", "data", "patients_manifest.csv"
)


async def _seed_patients_from_manifest_if_empty() -> None:
    """Load patients_manifest.csv into the User table on first run.

    Re-seeds if the User table has fewer rows than the manifest (e.g. an
    old single-patient seed left behind). Doctor accounts are untouched.
    """
    if not os.path.exists(MANIFEST_FILE):
        return

    df = pd.read_csv(MANIFEST_FILE)
    expected = len(df)

    async with async_session_factory() as session:
        existing = await session.execute(select(func.count(User.id)))
        existing_count = existing.scalar() or 0
        if existing_count >= expected:
            return

        # stale state: wipe patients (cascades to readings + healthy_ranges) and reload
        if existing_count > 0:
            await session.execute(delete(HealthyRange))
            await session.execute(delete(User))

        for _, row in df.iterrows():
            user = User(
                id=uuid.UUID(row["id"]),
                email=row["email"],
                full_name=row["full_name"],
            )
            session.add(user)
            await session.flush()
            for metric_type, bounds in DEFAULT_HEALTHY_RANGES.items():
                session.add(HealthyRange(user_id=user.id, metric_type=metric_type, **bounds))
        await session.commit()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create tables on startup (use Alembic migrations in production)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    await _seed_patients_from_manifest_if_empty()
    yield
    await engine.dispose()


settings = get_settings()

app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173", "http://[::1]:5173"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router)
app.include_router(users.router)
app.include_router(patients.router)
app.include_router(readings.router)
app.include_router(dashboard.router)


@app.get("/health")
async def health_check():
    return {"status": "ok"}
