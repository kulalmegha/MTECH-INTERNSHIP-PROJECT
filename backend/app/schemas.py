"""
Pydantic v2 schemas for request / response validation.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, field_validator

from app.models import AlertStatus, CaseStatus, UserRole


# ── Shared ────────────────────────────────────────────────────────────────────

class OrmModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)


# ── Auth / Token ─────────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"


class LoginRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=80)
    password: str = Field(..., min_length=6)


# ── User ─────────────────────────────────────────────────────────────────────

class UserRead(OrmModel):
    id: int
    username: str
    role: UserRole
    case_id: Optional[int]
    created_at: datetime


# ── Case ─────────────────────────────────────────────────────────────────────

class CaseCreate(BaseModel):
    """
    Body sent by a counsellor to register a new case.
    consent_given MUST be True; the API refuses the request otherwise.
    """
    case_code: str = Field(
        ...,
        min_length=2,
        max_length=20,
        pattern=r"^[A-Za-z0-9_-]+$",
        examples=["V001"],
    )
    consent_given: bool
    follow_up_interval_days: int = Field(7, ge=1, le=365)
    initial_victim_password: Optional[str] = None

    @field_validator("consent_given")
    @classmethod
    def consent_must_be_true(cls, v: bool) -> bool:
        if not v:
            raise ValueError(
                "consent_given must be true — a case cannot be created without consent."
            )
        return v


class CaseRead(OrmModel):
    id: int
    case_code: str
    consent_given: bool
    consent_timestamp: Optional[datetime]
    assigned_counsellor_id: Optional[int]
    follow_up_interval_days: int
    next_follow_up_due: Optional[datetime]
    status: CaseStatus
    created_at: datetime


class CaseCreatedResponse(BaseModel):
    """
    Returned once on case creation. The one-time password is NOT stored
    anywhere after this response — the victim must save it.
    """
    case: CaseRead
    victim_username: str
    one_time_password: str   # shown once; victim should change it


# ── Check-in ─────────────────────────────────────────────────────────────────

class CheckinCreate(BaseModel):
    stress_level: int = Field(..., ge=1, le=10)
    feels_safe: bool
    faces_threat: bool
    sleep_difficulty: bool
    wants_counselling: bool
    free_text: Optional[str] = Field(None, max_length=2000)
    created_at: Optional[datetime] = None


class SupportTagRead(OrmModel):
    id: int
    checkin_id: int
    category: str
    suggested_by_system: bool
    approved_by: Optional[int]
    status_label: str = "pending professional review"


class CheckinRead(OrmModel):
    id: int
    case_id: int
    created_at: datetime
    stress_level: int
    feels_safe: bool
    faces_threat: bool
    sleep_difficulty: bool
    wants_counselling: bool
    free_text: Optional[str]
    sentiment_label: Optional[str]
    sentiment_score: Optional[float]
    emotion_label: Optional[str]
    emotion_score: Optional[float]
    distress_score: Optional[float]
    distress_band: Optional[str]
    score_breakdown: Optional[dict]
    alerts: list[AlertRead] = []
    support_tags: list[SupportTagRead] = []


class CheckinCreatedResponse(BaseModel):
    checkin: CheckinRead
    alerts: list[AlertRead]
    support_suggestions: list[SupportTagRead]


# ── Alert ─────────────────────────────────────────────────────────────────────

class AlertRead(OrmModel):
    id: int
    case_id: int
    checkin_id: Optional[int]
    alert_type: str
    reason: str
    status: AlertStatus
    created_at: datetime
    reviewed_by: Optional[int]
    reviewed_at: Optional[datetime]


class AlertWithCaseRead(AlertRead):
    case_code: str
    priority: int = 1


# ── Action ───────────────────────────────────────────────────────────────────

class ActionCreate(BaseModel):
    action_taken: str = Field(..., min_length=3)
    contact_channel: Optional[str] = None
    outcome: Optional[str] = None
    resolve_alert: bool = True


class ActionRead(OrmModel):
    id: int
    alert_id: int
    case_id: int
    counsellor_id: int
    action_taken: str
    contact_channel: Optional[str]
    outcome: Optional[str]
    created_at: datetime


# ── Trend & Dashboard ────────────────────────────────────────────────────────

class TrendPoint(BaseModel):
    date: datetime
    distress_score: Optional[float]
    stress_level: int
    emotion_label: Optional[str]
    has_alert: bool
    alert_types: list[str]


class DashboardSummary(BaseModel):
    total_cases: int
    open_alerts: int
    pending_followups: int
    high_band_cases: int


class CaseSummaryItem(OrmModel):
    id: int
    case_code: str
    status: CaseStatus
    follow_up_interval_days: int
    next_follow_up_due: Optional[datetime]
    created_at: datetime
    latest_distress_band: Optional[str] = None
    latest_distress_score: Optional[float] = None
    open_alerts_count: int = 0
