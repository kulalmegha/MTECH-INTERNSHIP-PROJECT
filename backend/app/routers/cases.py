"""
/cases router.

Endpoints
---------
POST   /cases           counsellor-only; creates case + linked victim account
GET    /cases           counsellor: only their assigned cases
GET    /cases/{code}    counsellor: only if assigned; victim: only their own case
"""
from __future__ import annotations

import secrets
import string
from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.deps import CounsellorOnly, CurrentUser, DBSession
from app.models import Case, CaseStatus, User, UserRole
from app.schemas import CaseCreate, CaseCreatedResponse, CaseRead, CaseSummaryItem, CheckinRead, TrendPoint
from app.security import hash_password

router = APIRouter(prefix="/cases", tags=["cases"])

# ── Helpers ───────────────────────────────────────────────────────────────────

_OTP_ALPHABET = string.ascii_letters + string.digits


def _generate_otp(length: int = 16) -> str:
    """Cryptographically secure random password."""
    return "".join(secrets.choice(_OTP_ALPHABET) for _ in range(length))


def _victim_username(case_code: str) -> str:
    """Deterministic username for the victim account: v_<case_code>."""
    return f"v_{case_code.lower()}"


# ── Routes ────────────────────────────────────────────────────────────────────

@router.post(
    "",
    response_model=CaseCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Register a new case (counsellor only)",
)
async def create_case(
    body: CaseCreate,
    counsellor: CounsellorOnly,
    db: DBSession,
) -> CaseCreatedResponse:
    """
    Creates a Case record and a linked victim User account.

    - ``consent_given`` must be ``true`` (enforced by schema validator).
    - Returns a one-time password the counsellor must securely hand to the
      victim.  The plaintext is NEVER stored.
    - The victim's username is deterministically ``v_<case_code_lower>``.

    Raises 409 if ``case_code`` is already in use.
    """
    # Duplicate check
    existing = await db.execute(
        select(Case).where(Case.case_code == body.case_code)
    )
    if existing.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Case code '{body.case_code}' is already registered.",
        )

    now = datetime.now(tz=timezone.utc)
    next_follow_up = now + timedelta(days=body.follow_up_interval_days)

    # Create the case
    case = Case(
        case_code=body.case_code,
        consent_given=True,
        consent_timestamp=now,
        assigned_counsellor_id=counsellor.id,
        follow_up_interval_days=body.follow_up_interval_days,
        next_follow_up_due=next_follow_up,
        status=CaseStatus.active,
    )
    db.add(case)
    await db.flush()  # populate case.id before creating the victim user

    # Create the victim account
    otp = body.initial_victim_password if body.initial_victim_password else _generate_otp()
    victim_username = _victim_username(body.case_code)

    # Check if victim username already taken (defensive)
    existing_user = await db.execute(
        select(User).where(User.username == victim_username)
    )
    if existing_user.scalar_one_or_none() is not None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Victim account '{victim_username}' already exists.",
        )

    victim = User(
        username=victim_username,
        password_hash=hash_password(otp),
        role=UserRole.victim,
        case_id=case.id,
    )
    db.add(victim)
    await db.commit()
    await db.refresh(case)

    return CaseCreatedResponse(
        case=CaseRead.model_validate(case),
        victim_username=victim_username,
        one_time_password=otp,
    )


@router.get(
    "",
    response_model=List[CaseSummaryItem],
    summary="List cases assigned to the current counsellor with latest band and alert counts",
)
async def list_cases(
    counsellor: CounsellorOnly,
    db: DBSession,
) -> List[CaseSummaryItem]:
    """
    Returns cases where ``assigned_counsellor_id`` matches the
    authenticated counsellor, annotated with latest distress band and open alert count.
    """
    from app.models import Alert, AlertStatus, Checkin

    result = await db.execute(
        select(Case).where(Case.assigned_counsellor_id == counsellor.id)
    )
    cases = result.scalars().all()

    summary_items: List[CaseSummaryItem] = []
    for c in cases:
        # Latest check-in
        stmt_latest = (
            select(Checkin)
            .where(Checkin.case_id == c.id)
            .order_by(Checkin.created_at.desc())
            .limit(1)
        )
        latest_chk = (await db.execute(stmt_latest)).scalar_one_or_none()

        # Open alerts count
        stmt_open = select(Alert).where(
            Alert.case_id == c.id,
            Alert.status == AlertStatus.open,
        )
        open_count = len((await db.execute(stmt_open)).scalars().all())

        summary_items.append(
            CaseSummaryItem(
                id=c.id,
                case_code=c.case_code,
                status=c.status,
                follow_up_interval_days=c.follow_up_interval_days,
                next_follow_up_due=c.next_follow_up_due,
                created_at=c.created_at,
                latest_distress_band=latest_chk.distress_band if latest_chk else None,
                latest_distress_score=latest_chk.distress_score if latest_chk else None,
                open_alerts_count=open_count,
            )
        )
    return summary_items


@router.get(
    "/{case_code}",
    response_model=CaseRead,
    summary="Get a single case by its code",
)
async def get_case(
    case_code: str,
    current_user: CurrentUser,
    db: DBSession,
) -> CaseRead:
    """
    Access rules:
    - **Counsellor**: may access only cases assigned to them.
    - **Victim**: may access only the case linked to their own account.
    """
    case = await _get_authorized_case(case_code, current_user, db)
    return CaseRead.model_validate(case)


@router.get(
    "/{case_code}/checkins",
    response_model=List[CheckinRead],
    summary="Get check-in history for a case",
)
async def get_case_checkins(
    case_code: str,
    current_user: CurrentUser,
    db: DBSession,
) -> List[CheckinRead]:
    """
    Returns all check-ins for the specified case, ordered chronologically by time.
    Includes score breakdowns, alerts, and suggested support categories.
    """
    from sqlalchemy.orm import selectinload
    from app.models import Checkin

    case = await _get_authorized_case(case_code, current_user, db)

    stmt = (
        select(Checkin)
        .options(selectinload(Checkin.alerts), selectinload(Checkin.support_tags))
        .where(Checkin.case_id == case.id)
        .order_by(Checkin.created_at.asc())
    )
    result = await db.execute(stmt)
    checkins = result.scalars().all()
    return [CheckinRead.model_validate(c) for c in checkins]


@router.get(
    "/{case_code}/trend",
    response_model=List[TrendPoint],
    summary="Get longitudinal trend data points for chart rendering",
)
async def get_case_trend(
    case_code: str,
    current_user: CurrentUser,
    db: DBSession,
) -> List[TrendPoint]:
    """
    Returns time series trend points: date, distress_score, stress_level, emotion_label,
    and alert flags suitable for Chart.js visualization.
    """
    from sqlalchemy.orm import selectinload
    from app.models import Checkin

    case = await _get_authorized_case(case_code, current_user, db)

    stmt = (
        select(Checkin)
        .options(selectinload(Checkin.alerts))
        .where(Checkin.case_id == case.id)
        .order_by(Checkin.created_at.asc())
    )
    result = await db.execute(stmt)
    checkins = result.scalars().all()

    points: List[TrendPoint] = []
    for c in checkins:
        alert_types = [a.alert_type for a in c.alerts]
        points.append(
            TrendPoint(
                date=c.created_at,
                distress_score=c.distress_score,
                stress_level=c.stress_level,
                emotion_label=c.emotion_label,
                has_alert=len(alert_types) > 0,
                alert_types=alert_types,
            )
        )
    return points


async def _get_authorized_case(case_code: str, current_user: User, db: AsyncSession) -> Case:
    """Helper to verify access rights to a case."""
    result = await db.execute(select(Case).where(Case.case_code == case_code))
    case: Case | None = result.scalar_one_or_none()

    if case is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Case '{case_code}' not found.",
        )

    if current_user.role == UserRole.counsellor:
        if case.assigned_counsellor_id != current_user.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You are not assigned to this case.",
            )
    elif current_user.role == UserRole.victim:
        if current_user.case_id != case.id:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have access to this case.",
            )
    else:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Unknown role.",
        )

    return case
