from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, field_validator


class OptionCreate(BaseModel):
    text: str = Field(min_length=1, max_length=500)
    is_correct: bool = False

    @field_validator("text")
    @classmethod
    def strip_text(cls, value: str) -> str:
        value = value.strip()
        if not value:
            raise ValueError("Option text cannot be empty")
        return value


def _validate_options(options: list[OptionCreate] | None) -> list[OptionCreate] | None:
    if options is None:
        return options
    if sum(1 for o in options if o.is_correct) != 1:
        raise ValueError("Exactly one option must be marked correct")
    texts = [o.text.lower() for o in options]
    if len(set(texts)) != len(texts):
        raise ValueError("Options must be unique")
    return options


def _clean_text(value: str | None) -> str | None:
    if value is None:
        return value
    value = value.strip()
    if not value:
        raise ValueError("Text cannot be empty")
    return value


class QuestionCreate(BaseModel):
    text: str = Field(min_length=1, max_length=1000)
    explanation: str | None = Field(default=None, max_length=2000)
    options: list[OptionCreate] = Field(min_length=2, max_length=6)

    _text = field_validator("text")(_clean_text)
    _options = field_validator("options")(_validate_options)


class QuestionUpdate(BaseModel):
    text: str | None = Field(default=None, min_length=1, max_length=1000)
    explanation: str | None = Field(default=None, max_length=2000)
    options: list[OptionCreate] | None = Field(default=None, min_length=2, max_length=6)

    _text = field_validator("text")(_clean_text)
    _options = field_validator("options")(_validate_options)


class OptionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    text: str
    is_correct: bool
    position: int


class QuestionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    topic_id: int
    text: str
    explanation: str | None
    options: list[OptionRead]
    created_at: datetime