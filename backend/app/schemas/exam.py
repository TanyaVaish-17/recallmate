from datetime import date, datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


def _check_future(value: date | None) -> date | None:
    if value is not None and value < date.today():
        raise ValueError("Exam date cannot be in the past")
    return value


def _clean_title(value: str | None) -> str | None:
    if value is None:
        return value
    value = value.strip()
    if not value:
        raise ValueError("Title cannot be empty")
    return value


class ExamCreate(BaseModel):
    subject_id: int
    title: str = Field(default="Exam", min_length=1, max_length=100)
    exam_date: date

    _title = field_validator("title")(_clean_title)
    _date = field_validator("exam_date")(_check_future)


class ExamUpdate(BaseModel):
    title: str | None = Field(default=None, min_length=1, max_length=100)
    exam_date: date | None = None

    _title = field_validator("title")(_clean_title)
    _date = field_validator("exam_date")(_check_future)


class ExamRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject_id: int
    title: str
    exam_date: date
    created_at: datetime

    @computed_field
    @property
    def days_remaining(self) -> int:
        return (self.exam_date - date.today()).days