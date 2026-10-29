from datetime import date, datetime
from typing import Optional

from sqlalchemy import (
    Boolean, CheckConstraint, Date, DateTime, Float, ForeignKey,
    Index, Integer, String, Text, func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base

SESSION_STATUSES = ("planned", "in_progress", "completed", "skipped", "missed")


class RevisionSession(Base):
    __tablename__ = "revision_sessions"
    __table_args__ = (
        Index("ix_revision_user_date", "user_id", "scheduled_date"),
        CheckConstraint(
            "status IN ('planned','in_progress','completed','skipped','missed')",
            name="ck_revision_status",
        ),
        CheckConstraint("duration_minutes > 0", name="ck_revision_duration"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    subject_id: Mapped[int] = mapped_column(ForeignKey("subjects.id", ondelete="CASCADE"), index=True)
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"), index=True)

    scheduled_date: Mapped[date] = mapped_column(Date)
    # Minutes after the start of the study day; used for ordering and overlap checks.
    start_minute: Mapped[int] = mapped_column(Integer, default=0, server_default="0")
    duration_minutes: Mapped[int] = mapped_column(Integer)

    status: Mapped[str] = mapped_column(String(20), default="planned", server_default="planned")
    priority_score: Mapped[float] = mapped_column(Float, default=0.0, server_default="0")
    reason: Mapped[str] = mapped_column(Text, default="", server_default="")
    predicted_p: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    model_version: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    is_manual: Mapped[bool] = mapped_column(Boolean, default=False, server_default="false")

    started_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    completed_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), onupdate=func.now()
    )


class ModelPrediction(Base):
    """One estimate of P(correct) for a topic, kept so predicted vs actual can be charted."""

    __tablename__ = "model_predictions"
    __table_args__ = (Index("ix_prediction_user_topic", "user_id", "topic_id", "created_at"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(ForeignKey("users.id", ondelete="CASCADE"))
    topic_id: Mapped[int] = mapped_column(ForeignKey("topics.id", ondelete="CASCADE"))
    predicted_p: Mapped[float] = mapped_column(Float)
    model_version: Mapped[str] = mapped_column(String(100))
    n_events_used: Mapped[int] = mapped_column(Integer)
    # Filled in later, when the next quiz on this topic is submitted.
    actual_rate: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())