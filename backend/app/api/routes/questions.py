from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.api.ownership import get_owned_question, get_owned_topic
from app.db.session import get_db
from app.models.question import Question, QuestionOption
from app.models.user import User
from app.schemas.question import OptionCreate, QuestionCreate, QuestionRead, QuestionUpdate

router = APIRouter(tags=["questions"])


def _build_options(options: list[OptionCreate]) -> list[QuestionOption]:
    return [
        QuestionOption(text=o.text, is_correct=o.is_correct, position=i)
        for i, o in enumerate(options)
    ]


# Questions under a topic
@router.get("/topics/{topic_id}/questions", response_model=list[QuestionRead])
def list_questions(
    topic_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_topic(db, topic_id, current_user)
    stmt = (
        select(Question)
        .options(selectinload(Question.options))
        .where(Question.topic_id == topic_id)
        .order_by(Question.id)
        .offset(skip)
        .limit(limit)
    )
    return list(db.scalars(stmt))


@router.post(
    "/topics/{topic_id}/questions",
    response_model=QuestionRead,
    status_code=status.HTTP_201_CREATED,
)
def create_question(
    topic_id: int,
    payload: QuestionCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    get_owned_topic(db, topic_id, current_user)

    duplicate = db.scalar(
        select(Question).where(Question.topic_id == topic_id, Question.text == payload.text)
    )
    if duplicate:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Question already exists")

    question = Question(
        topic_id=topic_id,
        text=payload.text,
        explanation=payload.explanation,
        options=_build_options(payload.options),
    )
    db.add(question)
    db.commit()
    db.refresh(question)
    return question


# Single question
@router.get("/questions/{question_id}", response_model=QuestionRead)
def get_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    return get_owned_question(db, question_id, current_user)


@router.patch("/questions/{question_id}", response_model=QuestionRead)
def update_question(
    question_id: int,
    payload: QuestionUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    question = get_owned_question(db, question_id, current_user)

    if payload.text is not None and payload.text != question.text:
        duplicate = db.scalar(
            select(Question).where(
                Question.topic_id == question.topic_id, Question.text == payload.text
            )
        )
        if duplicate:
            raise HTTPException(
                status_code=status.HTTP_409_CONFLICT, detail="Question already exists"
            )
        question.text = payload.text
    if "explanation" in payload.model_fields_set:
        question.explanation = payload.explanation
    if payload.options is not None:
        question.options = _build_options(payload.options)

    db.commit()
    db.refresh(question)
    return question


@router.delete("/questions/{question_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_question(
    question_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    question = get_owned_question(db, question_id, current_user)
    db.delete(question)
    db.commit()