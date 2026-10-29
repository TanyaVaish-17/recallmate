from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class TopicCreate(BaseModel):
    name: str = Field(min_length=1, max_length=150)
    difficulty: int = Field(default=3, ge=1, le=5)
    estimated_minutes: int = Field(default=30, ge=5, le=240)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be empty")
        return value


class TopicUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=150)
    difficulty: int | None = Field(default=None, ge=1, le=5)
    estimated_minutes: int | None = Field(default=None, ge=5, le=240)

    @field_validator("name")
    @classmethod
    def strip_name(cls, value: str | None) -> str | None:
        if value is None:
            return value
        value = value.strip()
        if not value:
            raise ValueError("Name cannot be empty")
        return value


class TopicRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    subject_id: int
    name: str
    difficulty: int
    estimated_minutes: int
    created_at: datetime