"""Shared test fixtures.

Uses an isolated in-memory SQLite database (StaticPool keeps a single
connection alive so the schema persists across sessions) and overrides the
app's `get_db` dependency. The ASGI transport does NOT run the app lifespan,
so the production 1,000-patient manifest seeding is skipped — tests start
from an empty, deterministic database.
"""

import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.pool import StaticPool

# Importing app.main registers every model on Base.metadata.
from app.database import Base, get_db
from app.main import app


@pytest_asyncio.fixture
async def db_engine():
    engine = create_async_engine(
        "sqlite+aiosqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest_asyncio.fixture
async def session_factory(db_engine):
    return async_sessionmaker(db_engine, expire_on_commit=False)


@pytest_asyncio.fixture
async def client(session_factory):
    async def _override_get_db():
        async with session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_db] = _override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac
    app.dependency_overrides.clear()


@pytest_asyncio.fixture
async def auth_headers(client):
    """Register a doctor and return Authorization headers with a valid JWT."""
    resp = await client.post(
        "/auth/register",
        json={
            "email": "doc@example.com",
            "full_name": "Dr. Test",
            "password": "supersecret",
        },
    )
    assert resp.status_code == 201, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}
