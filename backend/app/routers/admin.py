"""
/admin router and follow-up background tasks.

Endpoints
---------
POST /admin/run-followup-check  triggers routine scan for overdue follow-ups
                                and generates low-priority process reminders.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List

from fastapi import APIRouter
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.alerts import (
    ALERT_MISSED_FOLLOWUP,
    evaluate_missed_followup,
    get_open_alert_types_for_case,
)
from app.deps import CounsellorOnly, DBSession
from app.models import Alert, AlertStatus, Case, CaseStatus

router = APIRouter(prefix="/admin", tags=["admin"])


async def run_missed_followup_scan(db: AsyncSession, now: datetime | None = None) -> List[Alert]:
    """
    Scans all active cases where next_follow_up_due has passed.
    Generates 'missed_followup' alerts without duplicate creation.
    Can be run as a startup task or background worker.
    """
    current_time = now or datetime.now(timezone.utc)

    stmt = (
        select(Case)
        .where(
            Case.status == CaseStatus.active,
            Case.next_follow_up_due.is_not(None),
            Case.next_follow_up_due <= current_time,
        )
    )
    result = await db.execute(stmt)
    overdue_cases = result.scalars().all()

    created: List[Alert] = []
    for c in overdue_cases:
        open_types = await get_open_alert_types_for_case(db, c.id)
        candidate = evaluate_missed_followup(
            next_follow_up_due=c.next_follow_up_due,
            now=current_time,
            existing_open_types=open_types,
        )
        if candidate:
            alert = Alert(
                case_id=c.id,
                checkin_id=None,
                alert_type=candidate.alert_type,
                reason=candidate.reason,
                status=AlertStatus.open,
                created_at=current_time,
            )
            db.add(alert)
            created.append(alert)

    if created:
        await db.commit()

    return created


@router.post(
    "/run-followup-check",
    summary="Execute scheduled scan for overdue follow-up check-ins",
)
async def trigger_followup_check(
    counsellor: CounsellorOnly,
    db: DBSession,
) -> dict:
    """
    Triggers an on-demand follow-up audit. Generates low-priority
    alerts for cases that have lapsed their routine follow-up schedule.
    """
    alerts = await run_missed_followup_scan(db)
    return {
        "status": "success",
        "scanned_at": datetime.now(timezone.utc).isoformat(),
        "alerts_generated": len(alerts),
        "detail": f"Follow-up check completed. {len(alerts)} missed follow-up alert(s) generated.",
    }
