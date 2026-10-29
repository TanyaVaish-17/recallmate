from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, computed_field, field_validator


class QuizStart(BaseModel):
    topic_ids: list[int] = Field(min_length=1, max_length=10)
    num_questions: int = Field(default=5, ge=1, le=20)

    @field_validator("topic_ids")
    @classmethod
    def unique_topics(cls, value: list[int]) -> list[int]:
        if len(set(value)) != len(value):
            raise ValueError("Topic ids must be unique")
        return value


class QuizOptionPublic(BaseModel):
    id: int
    text: str


class QuizQuestionPublic(BaseModel):
    id: int
    topic_id: int
    text: str
    options: list[QuizOptionPublic]


class QuizStarted(BaseModel):
    id: int
    started_at: datetime
    questions: list[QuizQuestionPublic]


class AnswerIn(BaseModel):
    question_id: int
    option_id: int


class QuizSubmit(BaseModel):
    answers: list[AnswerIn] = Field(min_length=1, max_length=20)


class ResponseResult(BaseModel):
    question_id: int
    topic_id: int
    text: str
    selected_option_id: int | None
    correct_option_id: int
    is_correct: bool
    explanation: str | None


class QuizSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    started_at: datetime
    completed_at: datetime
    score: int
    total: int

    @computed_field
    @property
    def percent(self) -> float:
        return round(self.score / self.total * 100, 1) if self.total else 0.0


class QuizResult(QuizSummary):
    responses: list[ResponseResult]