"""Auth flow: registration, login, JWT-protected routes."""


async def test_health_check(client):
    resp = await client.get("/health")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_register_returns_token_and_doctor(client):
    resp = await client.post(
        "/auth/register",
        json={"email": "a@example.com", "full_name": "Dr. A", "password": "hunter2pw"},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["access_token"]
    assert body["token_type"] == "bearer"
    assert body["doctor"]["email"] == "a@example.com"
    # Password must never be echoed back.
    assert "password" not in body["doctor"]
    assert "hashed_password" not in body["doctor"]


async def test_register_duplicate_email_rejected(client):
    payload = {"email": "dup@example.com", "full_name": "Dr. Dup", "password": "hunter2pw"}
    first = await client.post("/auth/register", json=payload)
    assert first.status_code == 201
    second = await client.post("/auth/register", json=payload)
    assert second.status_code == 400


async def test_register_short_password_is_422(client):
    resp = await client.post(
        "/auth/register",
        json={"email": "x@example.com", "full_name": "Dr. X", "password": "short"},
    )
    assert resp.status_code == 422  # Pydantic min_length=6


async def test_login_success(client):
    await client.post(
        "/auth/register",
        json={"email": "log@example.com", "full_name": "Dr. Log", "password": "hunter2pw"},
    )
    resp = await client.post(
        "/auth/login", json={"email": "log@example.com", "password": "hunter2pw"}
    )
    assert resp.status_code == 200
    assert resp.json()["access_token"]


async def test_login_wrong_password_is_401(client):
    await client.post(
        "/auth/register",
        json={"email": "wp@example.com", "full_name": "Dr. WP", "password": "hunter2pw"},
    )
    resp = await client.post(
        "/auth/login", json={"email": "wp@example.com", "password": "WRONGpass"}
    )
    assert resp.status_code == 401


async def test_login_unknown_email_is_401(client):
    resp = await client.post(
        "/auth/login", json={"email": "nobody@example.com", "password": "whatever1"}
    )
    assert resp.status_code == 401


async def test_me_requires_token(client):
    resp = await client.get("/auth/me")
    assert resp.status_code == 401


async def test_me_with_valid_token(client, auth_headers):
    resp = await client.get("/auth/me", headers=auth_headers)
    assert resp.status_code == 200
    assert resp.json()["email"] == "doc@example.com"


async def test_me_with_garbage_token_is_401(client):
    resp = await client.get("/auth/me", headers={"Authorization": "Bearer not.a.jwt"})
    assert resp.status_code == 401
