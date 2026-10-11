"""
/dashboard router.

Endpoints
---------
GET /dashboard/summary   counsellor-only; counts total cases, open alerts,
                         pending follow-ups, and high-band cases.
"""
from __future__ import annotations

from datetime import datetime, timezone

from fastapi import APIRouter
from sqlalchemy import func, select

from app.deps import CounsellorOnly, DBSession
from app.models import Alert, AlertStatus, Case, CaseStatus, Checkin
from app.schemas import DashboardSummary
from app.scoring import BAND_HIGHER

router = APIRouter(prefix="/dashboard", tags=["dashboard"])


@router.get(
    "/summary",
    response_model=DashboardSummary,
    summary="Get caseload metrics and triage summary for counsellor",
)
async def get_dashboard_summary(
    counsellor: CounsellorOnly,
    db: DBSession,
) -> DashboardSummary:
    """
    Returns caseload metrics for the authenticated counsellor:
    - total_cases: Total assigned cases
    - open_alerts: Active unreviewed/unresolved alerts
    - pending_followups: Cases where next_follow_up_due has arrived or passed
    - high_band_cases: Cases where the most recent check-in is in the 'higher' distress band
    """
    now = datetime.now(timezone.utc)

    # 1. Total cases
    stmt_cases = select(Case).where(Case.assigned_counsellor_id == counsellor.id)
    cases = (await db.execute(stmt_cases)).scalars().all()
    total_cases = len(cases)
    case_ids = [c.id for c in cases]

    if not case_ids:
        return DashboardSummary(
            total_cases=0,
            open_alerts=0,
            pending_followups=0,
            high_band_cases=0,
        )

    # 2. Open alerts
    stmt_alerts = select(func.count(Alert.id)).where(
        Alert.case_id.in_(case_ids),
        Alert.status == AlertStatus.open,
    )
    open_alerts = (await db.execute(stmt_alerts)).scalar() or 0

    # 3. Pending follow-ups
    def _is_overdue(dt: datetime | None) -> bool:
        if dt is None:
            return False
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt <= now

    pending_followups = sum(
        1 for c in cases
        if c.status == CaseStatus.active and _is_overdue(c.next_follow_up_due)
    )

    # 4. High band cases (latest check-in in 'higher' band)
    high_band_count = 0
    for cid in case_ids:
        stmt_latest = (
            select(Checkin.distress_band)
            .where(Checkin.case_id == cid)
            .order_by(Checkin.created_at.desc())
            .limit(1)
        )
        band = (await db.execute(stmt_latest)).scalar_one_or_none()
        if band == BAND_HIGHER:
            high_band_count += 1

    return DashboardSummary(
        total_cases=total_cases,
        open_alerts=open_alerts,
        pending_followups=pending_followups,
        high_band_cases=high_band_count,
    )
