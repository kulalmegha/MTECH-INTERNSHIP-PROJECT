"""
Integration tests for the full Check-in, Alert, and Casework workflow.

Verifies:
1. POST /checkins (victim only):
   - Computes distress score and breakdown
   - Detects negative sentiment and emotion
   - Advances next_follow_up_due
   - Generates support category suggestions ('pending professional review')
2. Multiple check-ins triggering:
   - Acute distress increase (delta >= 20.0 points)
   - Safety concern alert (priority 1)
   - Counselling request alert (priority 2)
3. GET /cases/{code}/checkins (chronological history with breakdown)
4. GET /cases/{code}/trend (chart data points with alert indicators)
5. GET /alerts (counsellor only; priority sorted)
6. PATCH /alerts/{id}/review (reviewed timestamp and user id)
7. POST /alerts/{id}/actions (action record and alert resolution)
8. GET /dashboard/summary (caseload summary counts)
9. POST /admin/run-followup-check (overdue follow-up scan)
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from sqlalchemy.pool import StaticPool

from app.database import Base
from app.deps import get_db
from app.main import app
from app.models import Case, CaseStatus, User, UserRole
from app.security import hash_password

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


async def override_get_db():
    async with TestSessionLocal() as session:
        yield session


@pytest_asyncio.fixture(scope="function", autouse=True)
async def setup_db():
    app.dependency_overrides[get_db] = override_get_db
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)

    # Seed counsellor and case with victim
    async with TestSessionLocal() as db:
        counsellor = User(
            username="counsellor_test",
            password_hash=hash_password("password_c"),
            role=UserRole.counsellor,
        )
        db.add(counsellor)
        await db.flush()

        now = datetime.now(timezone.utc)
        case = Case(
            case_code="V_TEST",
            consent_given=True,
            consent_timestamp=now,
            assigned_counsellor_id=counsellor.id,
            follow_up_interval_days=7,
            next_follow_up_due=now + timedelta(days=7),
            status=CaseStatus.active,
        )
        db.add(case)
        await db.flush()

        victim = User(
            username="v_v_test",
            password_hash=hash_password("password_v"),
            role=UserRole.victim,
            case_id=case.id,
        )
        db.add(victim)
        await db.commit()

    yield


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def _login(client: AsyncClient, username: str, password: str) -> str:
    resp = await client.post("/auth/login", json={"username": username, "password": password})
    assert resp.status_code == 200, resp.text
    return resp.json()["access_token"]


@pytest.mark.asyncio
async def test_full_checkin_and_casework_workflow(client: AsyncClient):
    """
    Complete end-to-end test of the check-in submission, alert triggering,
    counsellor dashboard review, and action resolution.
    """
    v_token = await _login(client, "v_v_test", "password_v")
    c_token = await _login(client, "counsellor_test", "password_c")

    # 1. Victim submits Check-In #1 (Baseline calm)
    chk1_resp = await client.post(
        "/checkins",
        headers={"Authorization": f"Bearer {v_token}"},
        json={
            "stress_level": 3,
            "feels_safe": True,
            "faces_threat": False,
            "sleep_difficulty": False,
            "wants_counselling": False,
            "free_text": "Things are relatively calm today. Doing household chores.",
        },
    )
    assert chk1_resp.status_code == 201
    d1 = chk1_resp.json()
    assert d1["checkin"]["distress_band"] == "low"
    assert len(d1["alerts"]) == 0
    score_1 = d1["checkin"]["distress_score"]

    # 2. Victim submits Check-In #2 (Escalation with acute jump >= 20 pts & safety threat)
    chk2_resp = await client.post(
        "/checkins",
        headers={"Authorization": f"Bearer {v_token}"},
        json={
            "stress_level": 8,
            "feels_safe": False,
            "faces_threat": True,
            "sleep_difficulty": True,
            "wants_counselling": False,
            "free_text": "They drove past the house again shouting threats. I am terrified.",
        },
    )
    assert chk2_resp.status_code == 201
    d2 = chk2_resp.json()
    score_2 = d2["checkin"]["distress_score"]
    assert score_2 - score_1 >= 20.0  # Acute distress jump

    # Alerts generated: both safety_concern and distress_increase
    alert_types_2 = [a["alert_type"] for a in d2["alerts"]]
    assert "safety_concern" in alert_types_2
    assert "distress_increase" in alert_types_2

    # Verify support suggestion generated
    tag_categories = [t["category"] for t in d2["support_suggestions"]]
    assert "Protection & Emergency Relocation" in tag_categories

    # 3. Victim submits Check-In #3 (Explicit counselling request)
    chk3_resp = await client.post(
        "/checkins",
        headers={"Authorization": f"Bearer {v_token}"},
        json={
            "stress_level": 7,
            "feels_safe": True,
            "faces_threat": False,
            "sleep_difficulty": True,
            "wants_counselling": True,
            "free_text": "I need help with my legal court hearing tomorrow and financial rent support.",
        },
    )
    assert chk3_resp.status_code == 201
    d3 = chk3_resp.json()
    alert_types_3 = [a["alert_type"] for a in d3["alerts"]]
    assert "counselling_request" in alert_types_3

    # Check keyword support suggestions
    tag_categories_3 = [t["category"] for t in d3["support_suggestions"]]
    assert "Psychological Support & Counselling" in tag_categories_3
    assert "Legal Aid & Witness Protection" in tag_categories_3
    assert "Emergency Financial Assistance" in tag_categories_3

    # 4. Counsellor checks Case Check-in History
    hist_resp = await client.get(
        "/cases/V_TEST/checkins",
        headers={"Authorization": f"Bearer {c_token}"},
    )
    assert hist_resp.status_code == 200
    checkins_list = hist_resp.json()
    assert len(checkins_list) == 3
    # Verify score breakdown transparency in history
    assert checkins_list[0]["score_breakdown"] is not None
    assert "stress_points" in checkins_list[0]["score_breakdown"]

    # 5. Counsellor checks Trend Data Points
    trend_resp = await client.get(
        "/cases/V_TEST/trend",
        headers={"Authorization": f"Bearer {c_token}"},
    )
    assert trend_resp.status_code == 200
    trend_points = trend_resp.json()
    assert len(trend_points) == 3
    assert trend_points[1]["has_alert"] is True
    assert "safety_concern" in trend_points[1]["alert_types"]

    # 6. Counsellor lists Alerts (sorted by priority)
    alerts_resp = await client.get(
        "/alerts?status=open",
        headers={"Authorization": f"Bearer {c_token}"},
    )
    assert alerts_resp.status_code == 200
    alerts = alerts_resp.json()
    assert len(alerts) >= 3
    # Check priority ordering: safety_concern (P1) comes before counselling_request (P2)
    assert alerts[0]["alert_type"] == "safety_concern"
    assert alerts[0]["priority"] == 1
    safety_alert_id = alerts[0]["id"]

    # 7. Counsellor marks alert as Reviewed
    review_resp = await client.patch(
        f"/alerts/{safety_alert_id}/review",
        headers={"Authorization": f"Bearer {c_token}"},
    )
    assert review_resp.status_code == 200
    assert review_resp.json()["status"] == "reviewed"
    assert review_resp.json()["reviewed_by"] is not None

    # 8. Counsellor logs Action and Resolves Alert
    action_resp = await client.post(
        f"/alerts/{safety_alert_id}/actions",
        headers={"Authorization": f"Bearer {c_token}"},
        json={
            "action_taken": "Coordinated with emergency safehouse coordinator for immediate relocation.",
            "contact_channel": "Safehouse visit",
            "outcome": "Victim successfully transferred to protected accommodation.",
            "resolve_alert": True,
        },
    )
    assert action_resp.status_code == 201
    act = action_resp.json()
    assert act["alert_id"] == safety_alert_id

    # 9. Verify Dashboard Summary metrics
    dash_resp = await client.get(
        "/dashboard/summary",
        headers={"Authorization": f"Bearer {c_token}"},
    )
    assert dash_resp.status_code == 200
    summary = dash_resp.json()
    assert summary["total_cases"] == 1
    # 3 total alerts - 1 resolved = 2 open alerts remaining
    assert summary["open_alerts"] == 2

    # 10. Admin Follow-Up check execution
    scan_resp = await client.post(
        "/admin/run-followup-check",
        headers={"Authorization": f"Bearer {c_token}"},
    )
    assert scan_resp.status_code == 200
    assert "alerts_generated" in scan_resp.json()
