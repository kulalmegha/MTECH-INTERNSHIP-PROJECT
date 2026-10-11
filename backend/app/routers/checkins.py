"""
/checkins router.

Endpoints
---------
POST /checkins   victim-only; validates answers + text, runs NLP, computes score,
                 generates support category suggestions, runs alert engine,
                 updates next_follow_up_due, and returns saved checkin + alerts.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import List

from fastapi import APIRouter, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.ai.nlp_service import get_nlp_service
from app.ai.support_suggestions import suggest_support_categories
from app.alerts import trigger_alerts_for_checkin
from app.deps import CurrentUser, DBSession, VictimOnly
from app.models import Case, Checkin, SupportTag, UserRole
from app.schemas import AlertRead, CheckinCreate, CheckinCreatedResponse, CheckinRead, SupportTagRead
from app.scoring import calculate_distress_score

router = APIRouter(prefix="/checkins", tags=["checkins"])


@router.post(
    "",
    response_model=CheckinCreatedResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Submit a self-care check-in (victim only)",
)
async def submit_checkin(
    body: CheckinCreate,
    victim: VictimOnly,
    db: DBSession,
) -> CheckinCreatedResponse:
    """
    Submits a routine check-in for the authenticated victim:
    1. Validates structured inputs and free-text narrative.
    2. Runs NLP inference (sentiment & emotion) via cached pipeline / fallback.
    3. Retrieves previous check-in for this case to evaluate escalation delta.
    4. Computes transparent distress score (0-100), band, and factor breakdown.
    5. Saves check-in and generates non-binding support category suggestions.
    6. Triggers alert engine (deduplicating open alerts).
    7. Advances case.next_follow_up_due by case.follow_up_interval_days.
    """
    if victim.case_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Victim account is not linked to any active case.",
        )

    # 1. Fetch case
    stmt_case = select(Case).where(Case.id == victim.case_id)
    case_res = await db.execute(stmt_case)
    case = case_res.scalar_one_or_none()
    if not case:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Linked case record not found.",
        )

    # 2. Run NLP inference
    nlp_service = get_nlp_service()
    nlp_res = nlp_service.analyze_text(body.free_text)
    sentiment_label = nlp_res["sentiment_label"]
    sentiment_score = nlp_res["sentiment_score"]
    emotion_label = nlp_res["emotion_label"]
    emotion_score = nlp_res["emotion_score"]

    # 3. Retrieve previous check-in for baseline delta
    stmt_prev = (
        select(Checkin)
        .where(Checkin.case_id == case.id)
        .order_by(Checkin.created_at.desc())
        .limit(1)
    )
    prev_res = await db.execute(stmt_prev)
    prev_checkin = prev_res.scalar_one_or_none()
    previous_score = prev_checkin.distress_score if prev_checkin else None

    # 4. Compute Distress Score
    final_score, distress_band, breakdown = calculate_distress_score(
        stress_level=body.stress_level,
        feels_safe=body.feels_safe,
        faces_threat=body.faces_threat,
        sleep_difficulty=body.sleep_difficulty,
        wants_counselling=body.wants_counselling,
        sentiment_label=sentiment_label,
        sentiment_score=sentiment_score,
        emotion_label=emotion_label,
        emotion_score=emotion_score,
        previous_distress_score=previous_score,
    )

    # 5. Persist Checkin
    now = body.created_at if body.created_at is not None else datetime.now(timezone.utc)
    checkin = Checkin(
        case_id=case.id,
        created_at=now,
        stress_level=body.stress_level,
        feels_safe=body.feels_safe,
        faces_threat=body.faces_threat,
        sleep_difficulty=body.sleep_difficulty,
        wants_counselling=body.wants_counselling,
        free_text=body.free_text,
        sentiment_label=sentiment_label,
        sentiment_score=sentiment_score,
        emotion_label=emotion_label,
        emotion_score=emotion_score,
        distress_score=final_score,
        distress_band=distress_band,
        score_breakdown=breakdown,
    )
    db.add(checkin)
    await db.flush()

    # 6. Generate support category suggestions
    suggested_cats = suggest_support_categories(
        feels_safe=body.feels_safe,
        faces_threat=body.faces_threat,
        wants_counselling=body.wants_counselling,
        sleep_difficulty=body.sleep_difficulty,
        free_text=body.free_text,
    )
    created_tags: List[SupportTag] = []
    for cat in suggested_cats:
        tag = SupportTag(
            checkin_id=checkin.id,
            category=cat,
            suggested_by_system=True,
            approved_by=None,
        )
        db.add(tag)
        created_tags.append(tag)

    # 7. Evaluate and create alerts
    created_alerts = await trigger_alerts_for_checkin(
        db=db,
        case_id=case.id,
        checkin=checkin,
        previous_score=previous_score,
    )

    # 8. Update case next_follow_up_due
    case.next_follow_up_due = now + timedelta(days=case.follow_up_interval_days)

    await db.commit()

    # Reload relationships for response serialization
    stmt_reload = (
        select(Checkin)
        .options(selectinload(Checkin.alerts), selectinload(Checkin.support_tags))
        .where(Checkin.id == checkin.id)
    )
    reloaded = (await db.execute(stmt_reload)).scalar_one()

    return CheckinCreatedResponse(
        checkin=CheckinRead.model_validate(reloaded),
        alerts=[AlertRead.model_validate(a) for a in created_alerts],
        support_suggestions=[SupportTagRead.model_validate(t) for t in created_tags],
    )
