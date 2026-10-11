"""
/alerts router.

Endpoints
---------
GET    /alerts              counsellor: their cases only; filters by status, sorted by priority then date
PATCH  /alerts/{id}/review  counsellor: marks alert as reviewed with timestamp & user id
POST   /alerts/{id}/actions records action_taken, channel, outcome; resolves alert if requested
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import List, Optional

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.alerts import ALERT_PRIORITIES
from app.deps import CounsellorOnly, DBSession
from app.models import Action, Alert, AlertStatus, Case
from app.schemas import ActionCreate, ActionRead, AlertRead, AlertWithCaseRead

router = APIRouter(prefix="/alerts", tags=["alerts"])


@router.get(
    "",
    response_model=List[AlertWithCaseRead],
    summary="List alerts for cases assigned to current counsellor",
)
async def list_alerts(
    counsellor: CounsellorOnly,
    db: DBSession,
    status_filter: Optional[AlertStatus] = Query(None, alias="status"),
) -> List[AlertWithCaseRead]:
    """
    Returns alerts belonging strictly to the counsellor's assigned cases.
    Sorted by priority (1=Safety Concern, 2=Counselling, 3=Distress Increase, 4=Missed Follow-up)
    then created_at descending.
    """
    # Join with Case to ensure assignment and extract case_code
    stmt = (
        select(Alert, Case.case_code)
        .join(Case, Alert.case_id == Case.id)
        .where(Case.assigned_counsellor_id == counsellor.id)
    )
    if status_filter:
        stmt = stmt.where(Alert.status == status_filter)

    result = await db.execute(stmt)
    rows = result.all()

    alert_items: List[AlertWithCaseRead] = []
    for alert, case_code in rows:
        priority = ALERT_PRIORITIES.get(alert.alert_type, 5)
        alert_items.append(
            AlertWithCaseRead(
                id=alert.id,
                case_id=alert.case_id,
                checkin_id=alert.checkin_id,
                alert_type=alert.alert_type,
                reason=alert.reason,
                status=alert.status,
                created_at=alert.created_at,
                reviewed_by=alert.reviewed_by,
                reviewed_at=alert.reviewed_at,
                case_code=case_code,
                priority=priority,
            )
        )

    # Sort by priority ascending, then created_at descending
    alert_items.sort(key=lambda a: (a.priority, -a.created_at.timestamp()))
    return alert_items


@router.patch(
    "/{alert_id}/review",
    response_model=AlertRead,
    summary="Mark an alert as reviewed by the counsellor",
)
async def review_alert(
    alert_id: int,
    counsellor: CounsellorOnly,
    db: DBSession,
) -> AlertRead:
    """
    Sets alert status to 'reviewed' and attaches current counsellor ID and timestamp.
    """
    alert = await _get_authorized_alert(alert_id, counsellor.id, db)

    now = datetime.now(timezone.utc)
    alert.status = AlertStatus.reviewed
    alert.reviewed_by = counsellor.id
    alert.reviewed_at = now

    await db.commit()
    await db.refresh(alert)
    return AlertRead.model_validate(alert)


@router.post(
    "/{alert_id}/actions",
    response_model=ActionRead,
    status_code=status.HTTP_201_CREATED,
    summary="Record clinical follow-up action for an alert and optionally resolve it",
)
async def record_action(
    alert_id: int,
    body: ActionCreate,
    counsellor: CounsellorOnly,
    db: DBSession,
) -> ActionRead:
    """
    Records counsellor outreach / intervention details.
    If body.resolve_alert is true (default), transitions the alert status to 'resolved'.
    """
    alert = await _get_authorized_alert(alert_id, counsellor.id, db)

    now = datetime.now(timezone.utc)
    action = Action(
        alert_id=alert.id,
        case_id=alert.case_id,
        counsellor_id=counsellor.id,
        action_taken=body.action_taken,
        contact_channel=body.contact_channel,
        outcome=body.outcome,
        created_at=now,
    )
    db.add(action)

    if body.resolve_alert:
        alert.status = AlertStatus.resolved
        if alert.reviewed_by is None:
            alert.reviewed_by = counsellor.id
            alert.reviewed_at = now

    await db.commit()
    await db.refresh(action)
    return ActionRead.model_validate(action)


async def _get_authorized_alert(alert_id: int, counsellor_id: int, db: DBSession) -> Alert:
    """Helper to verify alert exists and belongs to counsellor's assigned case."""
    stmt = (
        select(Alert)
        .join(Case, Alert.case_id == Case.id)
        .where(Alert.id == alert_id, Case.assigned_counsellor_id == counsellor_id)
    )
    res = await db.execute(stmt)
    alert = res.scalar_one_or_none()
    if not alert:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Alert {alert_id} not found or not assigned to you.",
        )
    return alert
