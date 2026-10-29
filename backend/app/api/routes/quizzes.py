import random
import logging
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.api.deps import get_current_user
from app.api.ownership import get_owned_attempt
from app.db.session import get_db
from app.models.learning_event import LearningEvent
from app.models.question import Question
from app.models.quiz import QuizAttempt, QuizResponse
from app.models.subject import Subject
from app.models.topic import Topic
from app.models.user import User
from app.schemas.quiz import (
    QuizOptionPublic,
    QuizQuestionPublic,
    QuizResult,
    QuizStart,
    QuizStarted,
    QuizSubmit,
    QuizSummary,
    ResponseResult,
)

from app.services.planner import on_quiz_submitted

router = APIRouter(prefix="/quizzes", tags=["quizzes"])


# Helpers
def _public_question(question: Question) -> QuizQuestionPublic:
    options = list(question.options)
    random.shuffle(options)
    return QuizQuestionPublic(
        id=question.id,
        topic_id=question.topic_id,
        text=question.text,
        options=[QuizOptionPublic(id=o.id, text=o.text) for o in options],
    )


def _build_result(attempt: QuizAttempt) -> QuizResult:
    responses = []
    for response in attempt.responses:
        question = response.question
        correct = next(o for o in question.options if o.is_correct)
        responses.append(
            ResponseResult(
                question_id=question.id,
                topic_id=question.topic_id,
                text=question.text,
                selected_option_id=response.selected_option_id,
                correct_option_id=correct.id,
                is_correct=bool(response.is_correct),
                explanation=question.explanation,
            )
        )
    return QuizResult(
        id=attempt.id,
        started_at=attempt.started_at,
        completed_at=attempt.completed_at,
        score=attempt.score,
        total=attempt.total,
        responses=responses,
    )


# Start
@router.post("/start", response_model=QuizStarted, status_code=status.HTTP_201_CREATED)
def start_quiz(
    payload: QuizStart,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    owned_ids = set(
        db.scalars(
            select(Topic.id)
            .join(Subject, Topic.subject_id == Subject.id)
            .where(Topic.id.in_(payload.topic_ids), Subject.user_id == current_user.id)
        )
    )
    if owned_ids != set(payload.topic_ids):
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")

    questions = list(
        db.scalars(
            select(Question)
            .options(selectinload(Question.options))
            .where(Question.topic_id.in_(payload.topic_ids))
            .order_by(func.random())
            .limit(payload.num_questions)
        )
    )
    if not questions:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="The selected topics have no questions yet",
        )

    attempt = QuizAttempt(
        user_id=current_user.id,
        total=len(questions),
        responses=[QuizResponse(question_id=q.id) for q in questions],
    )
    db.add(attempt)
    db.commit()
    db.refresh(attempt)

    return QuizStarted(
        id=attempt.id,
        started_at=attempt.started_at,
        questions=[_public_question(q) for q in questions],
    )


# Submit
@router.post("/{attempt_id}/submit", response_model=QuizResult)
def submit_quiz(
    attempt_id: int,
    payload: QuizSubmit,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    attempt = get_owned_attempt(db, attempt_id, current_user)
    if attempt.completed_at is not None:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Quiz already submitted")

    answers = {a.question_id: a.option_id for a in payload.answers}
    if len(answers) != len(payload.answers):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Duplicate answers for the same question",
        )
    if set(answers) != {r.question_id for r in attempt.responses}:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="Answer every question in the quiz exactly once",
        )

    graded = []
    for response in attempt.responses:
        option = next(
            (o for o in response.question.options if o.id == answers[response.question_id]),
            None,
        )
        if option is None:
            raise HTTPException(
                status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
                detail="Selected option does not belong to the question",
            )
        graded.append((response, option))

    question_ids = [r.question_id for r in attempt.responses]
    prior_counts = dict(
        db.execute(
            select(LearningEvent.question_id, func.count())
            .where(
                LearningEvent.user_id == current_user.id,
                LearningEvent.event_type == "quiz",
                LearningEvent.question_id.in_(question_ids),
            )
            .group_by(LearningEvent.question_id)
        ).all()
    )
    subject_by_topic = dict(
        db.execute(
            select(Topic.id, Topic.subject_id).where(
                Topic.id.in_({r.question.topic_id for r in attempt.responses})
            )
        ).all()
    )

    now = datetime.now(timezone.utc)
    score = 0
    for response, option in graded:
        response.selected_option_id = option.id
        response.is_correct = option.is_correct
        score += int(option.is_correct)
        db.add(
            LearningEvent(
                user_id=current_user.id,
                subject_id=subject_by_topic[response.question.topic_id],
                topic_id=response.question.topic_id,
                question_id=response.question_id,
                quiz_attempt_id=attempt.id,
                event_type="quiz",
                is_correct=option.is_correct,
                attempt_number=prior_counts.get(response.question_id, 0) + 1,
                occurred_at=now,
            )
        )

    attempt.score = score
    attempt.completed_at = now
    db.commit()
    result = _build_result(attempt)  # build the response BEFORE the hook can touch the session
    try:  # never let prediction/scheduling problems break quiz submission
        on_quiz_submitted(db, current_user, attempt)
    except Exception:
        logging.getLogger("recallmate").exception("Post-quiz prediction/plan update failed")
        db.rollback()
    return result


# History
@router.get("", response_model=list[QuizSummary])
def list_attempts(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    stmt = (
        select(QuizAttempt)
        .where(QuizAttempt.user_id == current_user.id, QuizAttempt.completed_at.is_not(None))
        .order_by(QuizAttempt.completed_at.desc())
        .offset(skip)
        .limit(limit)
    )
    return list(db.scalars(stmt))


@router.get("/{attempt_id}", response_model=QuizResult)
def get_attempt(
    attempt_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    attempt = get_owned_attempt(db, attempt_id, current_user)
    if attempt.completed_at is None:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT, detail="Quiz has not been submitted yet"
        )
    return _build_result(attempt)