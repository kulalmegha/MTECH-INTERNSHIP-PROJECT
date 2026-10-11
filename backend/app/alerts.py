"""
Alert Generation Engine for Victim Distress and Safety Monitoring.

Rules implemented:
1. wants_counselling = True -> alert 'counselling_request'
2. feels_safe = False or faces_threat = True -> alert 'safety_concern' (highest priority)
3. score increased by >= 20 points vs previous check-in -> alert 'distress_increase'
4. next_follow_up_due has passed with no check-in -> alert 'missed_followup'
   (Explicitly notes that missed check-in does not indicate distress by itself, lower priority)

Enforces:
- No duplicate open alerts of the same type for the same case.
"""
from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import List, Optional, Sequence, Set

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models import Alert, AlertStatus, Case, Checkin


# ── Alert Type Constants ──────────────────────────────────────────────────────

ALERT_SAFETY_CONCERN = "safety_concern"
ALERT_COUNSELLING_REQUEST = "counselling_request"
ALERT_DISTRESS_INCREASE = "distress_increase"
ALERT_MISSED_FOLLOWUP = "missed_followup"

# Priority ranking (1 is highest priority)
ALERT_PRIORITIES = {
    ALERT_SAFETY_CONCERN: 1,       # Highest priority
    ALERT_COUNSELLING_REQUEST: 2,  # Urgent direct request
    ALERT_DISTRESS_INCREASE: 3,    # Clinical score spike
    ALERT_MISSED_FOLLOWUP: 4,      # Low priority process reminder
}


@dataclass(frozen=True)
class AlertCandidate:
    """In-memory representation of an alert before persistence."""
    alert_type: str
    reason: str
    priority: int


def evaluate_checkin_alerts(
    wants_counselling: bool,
    feels_safe: bool,
    faces_threat: bool,
    current_score: float,
    previous_score: Optional[float] = None,
    existing_open_types: Optional[Set[str]] = None,
) -> List[AlertCandidate]:
    """
    Pure evaluation of alert conditions triggered by an incoming check-in.

    Filters out alert types that already have an open alert on the case.
    """
    open_types = existing_open_types or set()
    candidates: List[AlertCandidate] = []

    # Rule 2: Safety Concern (Priority 1 - Highest)
    if (not feels_safe or faces_threat) and ALERT_SAFETY_CONCERN not in open_types:
        reasons = []
        if not feels_safe:
            reasons.append("individual reported feeling unsafe")
        if faces_threat:
            reasons.append("individual reported facing active threat/intimidation")
        details = " and ".join(reasons)
        candidates.append(
            AlertCandidate(
                alert_type=ALERT_SAFETY_CONCERN,
                reason=f"Immediate safety concern flagged: {details}.",
                priority=ALERT_PRIORITIES[ALERT_SAFETY_CONCERN],
            )
        )

    # Rule 1: Counselling Request (Priority 2)
    if wants_counselling and ALERT_COUNSELLING_REQUEST not in open_types:
        candidates.append(
            AlertCandidate(
                alert_type=ALERT_COUNSELLING_REQUEST,
                reason="Individual explicitly requested psychological/support counselling.",
                priority=ALERT_PRIORITIES[ALERT_COUNSELLING_REQUEST],
            )
        )

    # Rule 3: Distress Increase (Priority 3)
    if previous_score is not None and ALERT_DISTRESS_INCREASE not in open_types:
        delta = current_score - previous_score
        if delta >= 20.0:
            candidates.append(
                AlertCandidate(
                    alert_type=ALERT_DISTRESS_INCREASE,
                    reason=(
                        f"Acute distress increase detected: distress score jumped by "
                        f"{delta:+.1f} points (from {previous_score:.1f} to {current_score:.1f})."
                    ),
                    priority=ALERT_PRIORITIES[ALERT_DISTRESS_INCREASE],
                )
            )

    # Sort by priority (1 is highest)
    candidates.sort(key=lambda c: c.priority)
    return candidates


def evaluate_missed_followup(
    next_follow_up_due: Optional[datetime],
    now: Optional[datetime] = None,
    existing_open_types: Optional[Set[str]] = None,
) -> Optional[AlertCandidate]:
    """
    Pure evaluation of overdue follow-up.

    Rule 4: next_follow_up_due has passed with no check-in.
    Low priority; explicitly states missed check-in does not indicate distress by itself.
    """
    if next_follow_up_due is None:
        return None

    open_types = existing_open_types or set()
    if ALERT_MISSED_FOLLOWUP in open_types:
        return None

    current_time = now or datetime.now(timezone.utc)
    if next_follow_up_due.tzinfo is None:
        next_follow_up_due = next_follow_up_due.replace(tzinfo=timezone.utc)
    if current_time.tzinfo is None:
        current_time = current_time.replace(tzinfo=timezone.utc)

    if current_time > next_follow_up_due:
        return AlertCandidate(
            alert_type=ALERT_MISSED_FOLLOWUP,
            reason=(
                "Scheduled follow-up interval has elapsed without a check-in. "
                "Note: A missed check-in does not indicate distress by itself; "
                "this is a routine low-priority continuity reminder for the counsellor."
            ),
            priority=ALERT_PRIORITIES[ALERT_MISSED_FOLLOWUP],
        )

    return None


async def get_open_alert_types_for_case(db: AsyncSession, case_id: int) -> Set[str]:
    """Fetch set of active open alert types for a given case to prevent duplicates."""
    stmt = select(Alert.alert_type).where(
        Alert.case_id == case_id,
        Alert.status == AlertStatus.open,
    )
    result = await db.execute(stmt)
    return set(result.scalars().all())


async def trigger_alerts_for_checkin(
    db: AsyncSession,
    case_id: int,
    checkin: Checkin,
    previous_score: Optional[float] = None,
) -> List[Alert]:
    """
    Evaluates check-in conditions against database state, creates alerts,
    and commits them to the database. Avoids duplicate open alerts.
    """
    open_types = await get_open_alert_types_for_case(db, case_id)
    candidates = evaluate_checkin_alerts(
        wants_counselling=checkin.wants_counselling,
        feels_safe=checkin.feels_safe,
        faces_threat=checkin.faces_threat,
        current_score=checkin.distress_score if checkin.distress_score is not None else 0.0,
        previous_score=previous_score,
        existing_open_types=open_types,
    )

    created_alerts: List[Alert] = []
    for cand in candidates:
        alert = Alert(
            case_id=case_id,
            checkin_id=checkin.id,
            alert_type=cand.alert_type,
            reason=cand.reason,
            status=AlertStatus.open,
        )
        db.add(alert)
        created_alerts.append(alert)

    if created_alerts:
        await db.flush()

    return created_alerts
