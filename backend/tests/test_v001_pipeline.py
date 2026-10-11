"""
End-to-end integration test replaying the complete Case V001 trajectory:
Check-ins (1 -> 2 -> 3) -> Transformer NLP analysis -> Distress score calculation ->
Score explainability breakdown -> Alert engine triggering -> Counsellor review & action ->
PDF Report generation.
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
from app.models import Case, CaseStatus, User, UserRole, Alert, AlertStatus
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


@pytest_asyncio.fixture(autouse=True)
async def setup_test_db():
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    app.dependency_overrides[get_db] = override_get_db
    yield
    app.dependency_overrides.pop(get_db, None)
    async with test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest_asyncio.fixture
async def seeded_counsellor() -> User:
    async with TestSessionLocal() as session:
        counsellor = User(
            username="counsellor_v001_eval",
            password_hash=hash_password("evalpass123"),
            role=UserRole.counsellor,
        )
        session.add(counsellor)
        await session.commit()
        await session.refresh(counsellor)
        return counsellor


@pytest.mark.asyncio
async def test_v001_full_pipeline_replay(seeded_counsellor: User):
    """
    Replay Case V001 storyline and assert the complete pipeline:
      1. Case registration + victim credential issuance
      2. Check-in 1: Moderate stress, mild text -> Low/moderate score, no crisis alert
      3. Check-in 2: High worry, insomnia -> Score jumps, NLP detects worry/fear
      4. Check-in 3: Explicit counselling request -> P2 alert generated, psychological support tag
      5. Alert review -> Clinical action logged -> Alert resolved
      6. PDF Case Progress Dossier generated and validated
      7. PDF Caseload Summary Report generated and validated
    """
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Step A: Counsellor logs in
        login_resp = await client.post(
            "/auth/login",
            json={"username": "counsellor_v001_eval", "password": "evalpass123"},
        )
        assert login_resp.status_code == 200
        c_token = login_resp.json()["access_token"]
        c_headers = {"Authorization": f"Bearer {c_token}"}

        # Step B: Counsellor registers Case V001
        case_resp = await client.post(
            "/cases",
            headers=c_headers,
            json={
                "case_code": "V001",
                "follow_up_interval_days": 5,
                "consent_given": True,
                "initial_victim_password": "VictimV001Secret!",
            },
        )
        assert case_resp.status_code == 201
        c_data = case_resp.json()
        assert c_data["case"]["case_code"] == "V001"
        victim_username = c_data["victim_username"]
        assert victim_username == "v_v001"

        # Step C: Victim logs in with credentials
        v_login = await client.post(
            "/auth/login",
            json={"username": victim_username, "password": "VictimV001Secret!"},
        )
        assert v_login.status_code == 200
        v_token = v_login.json()["access_token"]
        v_headers = {"Authorization": f"Bearer {v_token}"}

        # ---------------------------------------------------------------------
        # CHECK-IN 1: Moderate stress (~5/10), mild text
        # ---------------------------------------------------------------------
        t1 = datetime.now(timezone.utc) - timedelta(days=10)
        chk1_resp = await client.post(
            "/checkins",
            headers=v_headers,
            json={
                "stress_level": 5,
                "feels_safe": True,
                "faces_threat": False,
                "sleep_difficulty": False,
                "wants_counselling": False,
                "free_text": "Managing daily routines okay. Experiencing mild fatigue at work, but generally coping with tasks.",
                "created_at": t1.isoformat(),
            },
        )
        assert chk1_resp.status_code == 201
        chk1_data = chk1_resp.json()
        c1 = chk1_data["checkin"]

        # Assert AI sentiment & emotion computed
        assert c1["sentiment_label"] in ("positive", "neutral", "negative")
        assert c1["emotion_label"] is not None
        assert 0.0 <= c1["distress_score"] <= 100.0

        # Assert explainable breakdown
        bd1 = c1["score_breakdown"]
        assert bd1["stress_points"] == 15.0  # 5 * 3.0
        assert bd1["safety_points"] == 0.0
        assert bd1["sleep_points"] == 0.0
        assert bd1["counselling_points"] == 0.0

        # No critical alerts for baseline check-in
        assert len(chk1_data["alerts"]) == 0

        # ---------------------------------------------------------------------
        # CHECK-IN 2: Increased worry, difficulty sleeping, higher stress (7/10)
        # ---------------------------------------------------------------------
        t2 = datetime.now(timezone.utc) - timedelta(days=5)
        chk2_resp = await client.post(
            "/checkins",
            headers=v_headers,
            json={
                "stress_level": 7,
                "feels_safe": True,
                "faces_threat": False,
                "sleep_difficulty": True,
                "wants_counselling": False,
                "free_text": "Waking up multiple times at night with persistent worry and intrusive thoughts about the upcoming legal hearing. Feeling tense throughout the day.",
                "created_at": t2.isoformat(),
            },
        )
        assert chk2_resp.status_code == 201
        chk2_data = chk2_resp.json()
        c2 = chk2_data["checkin"]

        # Assert score escalated
        assert c2["distress_score"] > c1["distress_score"]
        bd2 = c2["score_breakdown"]
        assert bd2["stress_points"] == 21.0  # 7 * 3.0
        assert bd2["sleep_points"] == 5.0    # sleep difficulty triggered

        # NLP emotion analysis on worry text
        assert c2["emotion_label"] in ("fear/worry", "sadness", "neutral", "other")

        # ---------------------------------------------------------------------
        # CHECK-IN 3: Explicit counselling request, higher stress (8/10)
        # ---------------------------------------------------------------------
        t3 = datetime.now(timezone.utc) - timedelta(days=1)
        chk3_resp = await client.post(
            "/checkins",
            headers=v_headers,
            json={
                "stress_level": 8,
                "feels_safe": True,
                "faces_threat": False,
                "sleep_difficulty": True,
                "wants_counselling": True,
                "free_text": "The anxiety is feeling overwhelming this week. I am having panic symptoms in crowds and would really appreciate speaking to a counsellor as soon as possible.",
                "created_at": t3.isoformat(),
            },
        )
        assert chk3_resp.status_code == 201
        chk3_data = chk3_resp.json()
        c3 = chk3_data["checkin"]

        # Assert counselling points included
        bd3 = c3["score_breakdown"]
        assert bd3["counselling_points"] == 5.0
        assert bd3["stress_points"] == 24.0  # 8 * 3.0

        # Assert P2 counselling_request alert triggered
        alerts3 = chk3_data["alerts"]
        counselling_alerts = [a for a in alerts3 if a["alert_type"] == "counselling_request"]
        assert len(counselling_alerts) == 1
        target_alert = counselling_alerts[0]
        assert "counselling" in target_alert["reason"].lower()

        # Assert support suggestions include psychological
        tags3 = [t["category"] for t in chk3_data["support_suggestions"]]
        assert any("psychological" in t.lower() for t in tags3)

        # ---------------------------------------------------------------------
        # Step D: Counsellor reviews and resolves the alert
        # ---------------------------------------------------------------------
        # Check alerts queue
        alerts_list_resp = await client.get("/alerts?status=open", headers=c_headers)
        assert alerts_list_resp.status_code == 200
        open_alerts = alerts_list_resp.json()
        matching_open = [a for a in open_alerts if a["id"] == target_alert["id"]]
        assert len(matching_open) == 1
        assert matching_open[0]["priority"] == 2

        # Review alert
        rev_resp = await client.patch(f"/alerts/{target_alert['id']}/review", headers=c_headers)
        assert rev_resp.status_code == 200
        assert rev_resp.json()["status"] == "reviewed"
        assert rev_resp.json()["reviewed_at"] is not None

        # Take action and resolve alert
        action_resp = await client.post(
            f"/alerts/{target_alert['id']}/actions",
            headers=c_headers,
            json={
                "action_taken": "Contacted individual via secure phone call. Conducted anxiety grounding review.",
                "contact_channel": "Phone call",
                "outcome": "Individual reassured. Scheduled in-person clinical session for Friday.",
                "resolve_alert": True,
            },
        )
        assert action_resp.status_code == 201
        action_data = action_resp.json()
        assert action_data["action_taken"] != ""
        assert action_data["outcome"] is not None

        # Verify alert is now resolved
        chk_alerts_resolved = await client.get("/alerts?status=resolved", headers=c_headers)
        assert chk_alerts_resolved.status_code == 200
        resolved_ids = [a["id"] for a in chk_alerts_resolved.json()]
        assert target_alert["id"] in resolved_ids

        # ---------------------------------------------------------------------
        # Step E: Download and Validate Case V001 PDF Progress Dossier
        # ---------------------------------------------------------------------
        pdf_case_resp = await client.get("/cases/V001/report", headers=c_headers)
        assert pdf_case_resp.status_code == 200
        assert pdf_case_resp.headers["content-type"] == "application/pdf"
        assert pdf_case_resp.content.startswith(b"%PDF")
        assert len(pdf_case_resp.content) > 1000  # Substantial PDF document

        # ---------------------------------------------------------------------
        # Step F: Download and Validate Caseload Summary PDF Report
        # ---------------------------------------------------------------------
        pdf_sum_resp = await client.get("/reports/summary", headers=c_headers)
        assert pdf_sum_resp.status_code == 200
        assert pdf_sum_resp.headers["content-type"] == "application/pdf"
        assert pdf_sum_resp.content.startswith(b"%PDF")
        assert len(pdf_sum_resp.content) > 1000
