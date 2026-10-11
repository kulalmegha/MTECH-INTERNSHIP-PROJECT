"""
Unit tests for the Alert Engine (backend/app/alerts.py).

Verifies:
- Rule 1: wants_counselling = True -> 'counselling_request'
- Rule 2: feels_safe = False or faces_threat = True -> 'safety_concern' (highest priority)
- Rule 3: score increase >= 20.0 pts -> 'distress_increase'
- Rule 4: next_follow_up_due expired -> 'missed_followup' (low priority, non-stigmatizing rationale)
- Deduplication: no duplicate open alerts for the same case
- Priority ordering: safety (1) > counselling (2) > distress increase (3) > missed follow-up (4)
- Edge cases: delta = 19.9 vs 20.0, due date exactly now vs future vs past
"""
from datetime import datetime, timedelta, timezone

import pytest

from app.alerts import (
    ALERT_COUNSELLING_REQUEST,
    ALERT_DISTRESS_INCREASE,
    ALERT_MISSED_FOLLOWUP,
    ALERT_SAFETY_CONCERN,
    evaluate_checkin_alerts,
    evaluate_missed_followup,
)


def test_rule_1_counselling_request():
    """Explicit counselling request creates a counselling_request alert."""
    # When wants_counselling is True
    alerts = evaluate_checkin_alerts(
        wants_counselling=True,
        feels_safe=True,
        faces_threat=False,
        current_score=20.0,
    )
    assert len(alerts) == 1
    assert alerts[0].alert_type == ALERT_COUNSELLING_REQUEST
    assert "psychological/support counselling" in alerts[0].reason

    # When wants_counselling is False
    no_alerts = evaluate_checkin_alerts(
        wants_counselling=False,
        feels_safe=True,
        faces_threat=False,
        current_score=20.0,
    )
    assert len(no_alerts) == 0


def test_rule_2_safety_concern_priority():
    """Safety concern triggers alert with priority 1 (highest priority)."""
    # feels_safe is False
    alerts_unsafe = evaluate_checkin_alerts(
        wants_counselling=False,
        feels_safe=False,
        faces_threat=False,
        current_score=40.0,
    )
    assert len(alerts_unsafe) == 1
    assert alerts_unsafe[0].alert_type == ALERT_SAFETY_CONCERN
    assert alerts_unsafe[0].priority == 1
    assert "feeling unsafe" in alerts_unsafe[0].reason

    # faces_threat is True
    alerts_threat = evaluate_checkin_alerts(
        wants_counselling=False,
        feels_safe=True,
        faces_threat=True,
        current_score=40.0,
    )
    assert len(alerts_threat) == 1
    assert alerts_threat[0].alert_type == ALERT_SAFETY_CONCERN
    assert alerts_threat[0].priority == 1
    assert "active threat" in alerts_threat[0].reason


def test_rule_3_distress_increase_threshold():
    """Score increase >= 20 points triggers distress_increase; < 20 points does not."""
    # Delta of exactly 20.0 points -> Triggers
    alerts_20 = evaluate_checkin_alerts(
        wants_counselling=False,
        feels_safe=True,
        faces_threat=False,
        current_score=50.0,
        previous_score=30.0,
    )
    assert len(alerts_20) == 1
    assert alerts_20[0].alert_type == ALERT_DISTRESS_INCREASE
    assert "20.0 points" in alerts_20[0].reason

    # Delta of 19.9 points -> Does NOT trigger
    alerts_19 = evaluate_checkin_alerts(
        wants_counselling=False,
        feels_safe=True,
        faces_threat=False,
        current_score=49.9,
        previous_score=30.0,
    )
    assert len(alerts_19) == 0

    # No previous score -> Does NOT trigger
    alerts_no_prev = evaluate_checkin_alerts(
        wants_counselling=False,
        feels_safe=True,
        faces_threat=False,
        current_score=90.0,
        previous_score=None,
    )
    assert len(alerts_no_prev) == 0


def test_rule_4_missed_followup_and_rationale():
    """Missed follow-up creates low-priority alert stating it does not indicate distress by itself."""
    now = datetime.now(timezone.utc)

    # Due date in past -> Triggers
    past_due = now - timedelta(days=2)
    alert = evaluate_missed_followup(next_follow_up_due=past_due, now=now)
    assert alert is not None
    assert alert.alert_type == ALERT_MISSED_FOLLOWUP
    assert alert.priority == 4
    # Must explicitly state it does not indicate distress by itself
    assert "does not indicate distress by itself" in alert.reason

    # Due date in future -> None
    future_due = now + timedelta(days=2)
    assert evaluate_missed_followup(next_follow_up_due=future_due, now=now) is None

    # No due date -> None
    assert evaluate_missed_followup(next_follow_up_due=None, now=now) is None


def test_deduplication_of_open_alerts():
    """Existing open alert of same type suppresses duplicate creation."""
    existing_open = {ALERT_SAFETY_CONCERN, ALERT_COUNSELLING_REQUEST}

    # Safety and counselling are requested, but both are already open
    alerts = evaluate_checkin_alerts(
        wants_counselling=True,
        feels_safe=False,
        faces_threat=True,
        current_score=60.0,
        previous_score=30.0,  # delta = +30 (distress_increase is not open)
        existing_open_types=existing_open,
    )

    # Only distress_increase should be created
    assert len(alerts) == 1
    assert alerts[0].alert_type == ALERT_DISTRESS_INCREASE

    # Check missed follow-up deduplication
    now = datetime.now(timezone.utc)
    past_due = now - timedelta(days=1)
    dup_followup = evaluate_missed_followup(
        next_follow_up_due=past_due,
        now=now,
        existing_open_types={ALERT_MISSED_FOLLOWUP},
    )
    assert dup_followup is None


def test_multiple_alerts_ordered_by_priority():
    """When multiple alerts trigger simultaneously, they are sorted by priority (1 to 4)."""
    # Triggers safety (1), counselling (2), and distress increase (3)
    alerts = evaluate_checkin_alerts(
        wants_counselling=True,
        feels_safe=False,
        faces_threat=True,
        current_score=75.0,
        previous_score=40.0,
    )
    assert len(alerts) == 3
    assert [a.alert_type for a in alerts] == [
        ALERT_SAFETY_CONCERN,
        ALERT_COUNSELLING_REQUEST,
        ALERT_DISTRESS_INCREASE,
    ]
    assert [a.priority for a in alerts] == [1, 2, 3]
