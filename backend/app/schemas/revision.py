from datetime import date, datetime

from pydantic import BaseModel, Field


class SessionRead(BaseModel):
    id: int
    topic_id: int
    topic_name: str
    subject_id: int
    subject_name: str
    subject_color: str
    scheduled_date: date
    start_minute: int
    duration_minutes: int
    status: str
    priority_score: float
    reason: str
    predicted_p: float | None
    model_version: str | None
    is_manual: bool
    started_at: datetime | None
    completed_at: datetime | None


class PlanGenerate(BaseModel):
    horizon_days: int = Field(default=7, ge=1, le=14)


class SessionCreate(BaseModel):
    topic_id: int
    scheduled_date: date
    duration_minutes: int = Field(default=30, ge=5, le=240)


class SessionReschedule(BaseModel):
    scheduled_date: date | None = None
    duration_minutes: int | None = Field(default=None, ge=5, le=240)
