"""
pytest test suite for the MHM backend.

Covered scenarios
-----------------
1. Login success — counsellor gets a valid JWT.
2. Login failure — wrong password returns 401.
3. Consent enforcement — POST /cases with consent_given=false returns 422.
4. Victim isolation — a victim cannot read another victim's case (403).
5. Counsellor isolation — a counsellor cannot read a case assigned to another
   counsellor (403).

Design decisions
----------------
- Uses an in-memory SQLite database via a DATABASE_URL override so tests never
  touch the production file.
- Overrides the `get_db` dependency in the FastAPI app for the test client.
- Uses the synchronous httpx.AsyncClient with anyio so tests remain fast.
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sqlalchemy.pool import StaticPool

from app.database import Base
from app.deps import get_db
from app.main import app
from app.models import User, UserRole
from app.security import hash_password

# ── Test database setup ───────────────────────────────────────────────────────

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"

test_engine = create_async_engine(
    TEST_DATABASE_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
)

TestSessionLocal = async_sessionmaker(
    bind=test_engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


async def override_get_db():  # type: ignore[override]
    async with TestSessionLocal() as session:
        yield session


# ── Fixtures ──────────────────────────────────────────────────────────────────


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_db():
    """Recreate all tables before each test for isolation."""
    app.dependency_overrides[get_db] = override_get_db
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # Seed two counsellors and one case with one victim so tests can use them.
    async with TestSessionLocal() as db:
        counsellor_a = User(
            username="counsellor_a",
            password_hash=hash_password("password_a"),
            role=UserRole.counsellor,
        )
        counsellor_b = User(
            username="counsellor_b",
            password_hash=hash_password("password_b"),
            role=UserRole.counsellor,
        )
        db.add_all([counsellor_a, counsellor_b])
        await db.flush()

        # Seed counsellor_a's case + victim
        from app.models import Case, CaseStatus
        from datetime import datetime, timedelta, timezone

        now = datetime.now(tz=timezone.utc)
        case_a = Case(
            case_code="V001",
            consent_given=True,
            consent_timestamp=now,
            assigned_counsellor_id=counsellor_a.id,
            follow_up_interval_days=7,
            next_follow_up_due=now + timedelta(days=7),
            status=CaseStatus.active,
        )
        db.add(case_a)
        await db.flush()

        victim_a = User(
            username="v_v001",
            password_hash=hash_password("victim_pass_a"),
            role=UserRole.victim,
            case_id=case_a.id,
        )
        db.add(victim_a)

        # Seed counsellor_b's case + victim (different case)
        case_b = Case(
            case_code="V002",
            consent_given=True,
            consent_timestamp=now,
            assigned_counsellor_id=counsellor_b.id,
            follow_up_interval_days=7,
            next_follow_up_due=now + timedelta(days=7),
            status=CaseStatus.active,
        )
        db.add(case_b)
        await db.flush()

        victim_b = User(
            username="v_v002",
            password_hash=hash_password("victim_pass_b"),
            role=UserRole.victim,
            case_id=case_b.id,
        )
        db.add(victim_b)

        await db.commit()

    yield  # run the test


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


# ── Helper ────────────────────────────────────────────────────────────────────

async def _login(client: AsyncClient, username: str, password: str) -> str:
    """Login and return the access token."""
    resp = await client.post(
        "/auth/login", json={"username": username, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


# ── Tests ─────────────────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_login_success(client: AsyncClient):
    """A counsellor with correct credentials receives a JWT."""
    resp = await client.post(
        "/auth/login",
        json={"username": "counsellor_a", "password": "password_a"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_login_failure_wrong_password(client: AsyncClient):
    """Wrong password must return 401."""
    resp = await client.post(
        "/auth/login",
        json={"username": "counsellor_a", "password": "WRONG_PASSWORD"},
    )
    assert resp.status_code == 401
    assert "Incorrect" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_login_failure_unknown_user(client: AsyncClient):
    """Non-existent user must return 401."""
    resp = await client.post(
        "/auth/login",
        json={"username": "ghost_user", "password": "anything"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_consent_enforcement_schema(client: AsyncClient):
    """
    POST /cases with consent_given=false must be rejected at the schema level
    (422 Unprocessable Entity) before hitting the database.
    """
    token = await _login(client, "counsellor_a", "password_a")
    resp = await client.post(
        "/cases",
        json={
            "case_code": "V_NO_CONSENT",
            "consent_given": False,
            "follow_up_interval_days": 7,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 422
    # Confirm the reason is the consent validator
    errors = resp.json()["detail"]
    assert any("consent" in str(e).lower() for e in errors)


@pytest.mark.asyncio
async def test_victim_cannot_access_another_victims_case(client: AsyncClient):
    """
    victim_a (linked to V001) must receive 403 when requesting V002.
    """
    token = await _login(client, "v_v001", "victim_pass_a")
    resp = await client.get(
        "/cases/V002",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert "access" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_victim_can_access_own_case(client: AsyncClient):
    """victim_a can read their own case V001 — positive RBAC check."""
    token = await _login(client, "v_v001", "victim_pass_a")
    resp = await client.get(
        "/cases/V001",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["case_code"] == "V001"


@pytest.mark.asyncio
async def test_counsellor_denied_unassigned_case(client: AsyncClient):
    """
    counsellor_a is assigned to V001, not V002.
    Requesting V002 must return 403.
    """
    token = await _login(client, "counsellor_a", "password_a")
    resp = await client.get(
        "/cases/V002",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403
    assert "not assigned" in resp.json()["detail"].lower()


@pytest.mark.asyncio
async def test_counsellor_can_access_assigned_case(client: AsyncClient):
    """counsellor_a can read their assigned case V001."""
    token = await _login(client, "counsellor_a", "password_a")
    resp = await client.get(
        "/cases/V001",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 200
    assert resp.json()["case_code"] == "V001"


@pytest.mark.asyncio
async def test_create_case_success(client: AsyncClient):
    """counsellor_a can create a new case and receives a one-time password."""
    token = await _login(client, "counsellor_a", "password_a")
    resp = await client.post(
        "/cases",
        json={
            "case_code": "V099",
            "consent_given": True,
            "follow_up_interval_days": 14,
        },
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["case"]["case_code"] == "V099"
    assert data["victim_username"] == "v_v099"
    assert len(data["one_time_password"]) == 16


@pytest.mark.asyncio
async def test_create_case_duplicate_code(client: AsyncClient):
    """Re-using an existing case_code returns 409 Conflict."""
    token = await _login(client, "counsellor_a", "password_a")
    resp = await client.post(
        "/cases",
        json={"case_code": "V001", "consent_given": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 409


@pytest.mark.asyncio
async def test_victim_cannot_create_case(client: AsyncClient):
    """A victim attempting POST /cases must get 403."""
    token = await _login(client, "v_v001", "victim_pass_a")
    resp = await client.post(
        "/cases",
        json={"case_code": "V_ILLEGAL", "consent_given": True},
        headers={"Authorization": f"Bearer {token}"},
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_counsellor_list_only_own_cases(client: AsyncClient):
    """GET /cases returns only cases assigned to the requesting counsellor."""
    token_a = await _login(client, "counsellor_a", "password_a")
    resp = await client.get("/cases", headers={"Authorization": f"Bearer {token_a}"})
    assert resp.status_code == 200
    codes = [c["case_code"] for c in resp.json()]
    assert "V001" in codes
    assert "V002" not in codes


@pytest.mark.asyncio
async def test_unauthenticated_request_denied(client: AsyncClient):
    """No token → 403 (HTTPBearer auto_error=True returns 403)."""
    resp = await client.get("/cases")
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_me_endpoint(client: AsyncClient):
    """GET /auth/me returns the authenticated user's profile."""
    token = await _login(client, "counsellor_a", "password_a")
    resp = await client.get("/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert resp.status_code == 200
    data = resp.json()
    assert data["username"] == "counsellor_a"
    assert data["role"] == "counsellor"
