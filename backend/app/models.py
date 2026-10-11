"""
SQLAlchemy ORM models.

Privacy requirements implemented here:
  - No PII fields (no name / address / phone).
  - Consent enforced at the DB level: cases.consent_given NOT NULL with a
    check constraint; application layer refuses creation without it.
  - Cascade delete: removing a Case removes its checkins, alerts, actions.
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import List, Optional

from sqlalchemy import (
    JSON,
    Boolean,
    CheckConstraint,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.database import Base


# ── Enums ────────────────────────────────────────────────────────────────────

class UserRole(str, enum.Enum):
    counsellor = "counsellor"
    victim = "victim"


class AlertStatus(str, enum.Enum):
    open = "open"
    reviewed = "reviewed"
    resolved = "resolved"


class CaseStatus(str, enum.Enum):
    active = "active"
    closed = "closed"
    suspended = "suspended"


# ── Users ────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    username: Mapped[str] = mapped_column(String(80), unique=True, nullable=False, index=True)
    password_hash: Mapped[str] = mapped_column(String(128), nullable=False)
    role: Mapped[UserRole] = mapped_column(
        Enum(UserRole, name="userrole"), nullable=False
    )
    # For victims: references the case they belong to.
    # use_alter=True breaks the circular FK cycle with cases.assigned_counsellor_id
    # so SQLAlchemy can generate DROP TABLE statements in the correct order.
    case_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("cases.id", ondelete="SET NULL", use_alter=True, name="fk_users_case_id"),
        nullable=True,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    case: Mapped[Optional["Case"]] = relationship(
        "Case", foreign_keys=[case_id], back_populates="victim_user"
    )
    assigned_cases: Mapped[List["Case"]] = relationship(
        "Case",
        foreign_keys="Case.assigned_counsellor_id",
        back_populates="counsellor",
    )
    actions_taken: Mapped[List["Action"]] = relationship(
        "Action", back_populates="counsellor_user"
    )


# ── Cases ────────────────────────────────────────────────────────────────────

class Case(Base):
    __tablename__ = "cases"
    __table_args__ = (
        UniqueConstraint("case_code", name="uq_cases_case_code"),
        # Enforce consent at DB level
        CheckConstraint("consent_given = 1 OR consent_given = true", name="ck_cases_consent"),
    )

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    case_code: Mapped[str] = mapped_column(String(20), nullable=False, index=True)
    consent_given: Mapped[bool] = mapped_column(Boolean, nullable=False)
    consent_timestamp: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    assigned_counsellor_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    follow_up_interval_days: Mapped[int] = mapped_column(Integer, default=7, nullable=False)
    next_follow_up_due: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[CaseStatus] = mapped_column(
        Enum(CaseStatus, name="casestatus"), default=CaseStatus.active, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    counsellor: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys=[assigned_counsellor_id], back_populates="assigned_cases"
    )
    victim_user: Mapped[Optional["User"]] = relationship(
        "User", foreign_keys="User.case_id", back_populates="case"
    )
    checkins: Mapped[List["Checkin"]] = relationship(
        "Checkin", back_populates="case", cascade="all, delete-orphan"
    )
    alerts: Mapped[List["Alert"]] = relationship(
        "Alert", back_populates="case", cascade="all, delete-orphan"
    )
    actions: Mapped[List["Action"]] = relationship(
        "Action", back_populates="case", cascade="all, delete-orphan"
    )


# ── Check-ins ────────────────────────────────────────────────────────────────

class Checkin(Base):
    __tablename__ = "checkins"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── Raw symptom data ─────────────────────────────────────────────────────
    stress_level: Mapped[int] = mapped_column(Integer, nullable=False)          # 1-10
    feels_safe: Mapped[bool] = mapped_column(Boolean, nullable=False)
    faces_threat: Mapped[bool] = mapped_column(Boolean, nullable=False)
    sleep_difficulty: Mapped[bool] = mapped_column(Boolean, nullable=False)
    wants_counselling: Mapped[bool] = mapped_column(Boolean, nullable=False)
    free_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── NLP / AI outputs ─────────────────────────────────────────────────────
    sentiment_label: Mapped[Optional[str]] = mapped_column(String(20), nullable=True)
    sentiment_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    emotion_label: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    emotion_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)

    # ── Distress scoring ─────────────────────────────────────────────────────
    distress_score: Mapped[Optional[float]] = mapped_column(Float, nullable=True)   # 0-100
    distress_band: Mapped[Optional[str]] = mapped_column(String(20), nullable=True) # low/medium/high/critical
    score_breakdown: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="checkins")
    alerts: Mapped[List["Alert"]] = relationship("Alert", back_populates="checkin")
    support_tags: Mapped[List["SupportTag"]] = relationship(
        "SupportTag", back_populates="checkin", cascade="all, delete-orphan"
    )


# ── Alerts ───────────────────────────────────────────────────────────────────

class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False, index=True
    )
    checkin_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("checkins.id", ondelete="SET NULL"), nullable=True
    )
    alert_type: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[AlertStatus] = mapped_column(
        Enum(AlertStatus, name="alertstatus"),
        default=AlertStatus.open,
        nullable=False,
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    reviewed_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    reviewed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    # Relationships
    case: Mapped["Case"] = relationship("Case", back_populates="alerts")
    checkin: Mapped[Optional["Checkin"]] = relationship("Checkin", back_populates="alerts")
    actions: Mapped[List["Action"]] = relationship("Action", back_populates="alert")


# ── Actions ──────────────────────────────────────────────────────────────────

class Action(Base):
    __tablename__ = "actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    alert_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("alerts.id", ondelete="CASCADE"), nullable=False
    )
    case_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("cases.id", ondelete="CASCADE"), nullable=False
    )
    counsellor_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    action_taken: Mapped[str] = mapped_column(Text, nullable=False)
    contact_channel: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    outcome: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # Relationships
    alert: Mapped["Alert"] = relationship("Alert", back_populates="actions")
    case: Mapped["Case"] = relationship("Case", back_populates="actions")
    counsellor_user: Mapped["User"] = relationship("User", back_populates="actions_taken")


# ── Support Tags (optional, scaffolded) ──────────────────────────────────────

class SupportTag(Base):
    __tablename__ = "support_tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    checkin_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("checkins.id", ondelete="CASCADE"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    suggested_by_system: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    approved_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    # Relationships
    checkin: Mapped["Checkin"] = relationship("Checkin", back_populates="support_tags")
