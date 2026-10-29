from fastapi import HTTPException, status
from sqlalchemy import select
from app.models.exam import Exam
from app.models.subject import Subject
from app.models.topic import Topic
from app.models.user import User
from sqlalchemy.orm import Session, selectinload
from app.models.question import Question
from app.models.quiz import QuizAttempt, QuizResponse


def get_owned_subject(db: Session, subject_id: int, user: User) -> Subject:
    subject = db.scalar(
        select(Subject).where(Subject.id == subject_id, Subject.user_id == user.id)
    )
    if subject is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Subject not found")
    return subject


def get_owned_topic(db: Session, topic_id: int, user: User) -> Topic:
    topic = db.scalar(
        select(Topic)
        .join(Subject, Topic.subject_id == Subject.id)
        .where(Topic.id == topic_id, Subject.user_id == user.id)
    )
    if topic is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Topic not found")
    return topic


def get_owned_exam(db: Session, exam_id: int, user: User) -> Exam:
    exam = db.scalar(select(Exam).where(Exam.id == exam_id, Exam.user_id == user.id))
    if exam is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Exam not found")
    return exam

def get_owned_question(db: Session, question_id: int, user: User) -> Question:
    question = db.scalar(
        select(Question)
        .options(selectinload(Question.options))
        .join(Topic, Question.topic_id == Topic.id)
        .join(Subject, Topic.subject_id == Subject.id)
        .where(Question.id == question_id, Subject.user_id == user.id)
    )
    if question is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Question not found")
    return question

def get_owned_attempt(db: Session, attempt_id: int, user: User) -> QuizAttempt:
    attempt = db.scalar(
        select(QuizAttempt)
        .options(
            selectinload(QuizAttempt.responses)
            .selectinload(QuizResponse.question)
            .selectinload(Question.options)
        )
        .where(QuizAttempt.id == attempt_id, QuizAttempt.user_id == user.id)
    )
    if attempt is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Quiz not found")
    return attempt