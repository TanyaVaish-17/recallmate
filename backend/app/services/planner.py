"""Database glue: gathers a student's state, calls the model + scheduler, saves the plan."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete, func, select, update
from sqlalchemy.orm import Session

from app.models.exam import Exam
from app.models.learning_event import LearningEvent
from app.models.quiz import QuizAttempt
from app.models.revision import ModelPrediction, RevisionSession
from app.models.subject import Subject
from app.models.topic import Topic
from app.models.user import User
from app.services import prediction as pred
from app.services.scheduler import Booked, TopicState, build_plan

ACTIVE_BOOKED = ("planned", "in_progress", "completed")


def _today() -> date:
    return date.today()


def gather_topic_states(
    db: Session, user: User, today: date, store_predictions: bool = False
) -> tuple[list[TopicState], dict]:
    now = datetime.now(timezone.utc)
    rows = db.execute(
        select(Topic, Subject).join(Subject, Topic.subject_id == Subject.id)
        .where(Subject.user_id == user.id).order_by(Topic.id)
    ).all()
    if not rows:
        return [], pred.model_status()

    events = list(db.scalars(
        select(LearningEvent).where(LearningEvent.user_id == user.id)
        .order_by(LearningEvent.occurred_at, LearningEvent.id)
    ))
    history = [pred.HistoryEvent(e.topic_id, e.question_id or 0, int(e.is_correct), e.occurred_at) for e in events]

    completions: dict[int, list[datetime]] = {}
    missed: dict[int, int] = {}
    for s in db.scalars(select(RevisionSession).where(RevisionSession.user_id == user.id)):
        if s.status == "completed" and s.completed_at:
            completions.setdefault(s.topic_id, []).append(s.completed_at)
        elif s.status == "missed" and s.scheduled_date >= today - timedelta(days=14):
            missed[s.topic_id] = missed.get(s.topic_id, 0) + 1

    exams: dict[int, date] = {}
    for e in db.scalars(select(Exam).where(Exam.user_id == user.id, Exam.exam_date > today).order_by(Exam.exam_date)):
        exams.setdefault(e.subject_id, e.exam_date)

    topic_ids = [t.id for t, _ in rows]
    info = pred.model_status()
    predictions: dict[int, pred.Prediction] = {}
    try:
        predictions = pred.predict_topics(history, topic_ids, completions, now)
    except pred.ModelUnavailable:
        pass

    by_topic: dict[int, list[bool]] = {}
    for e in events:
        by_topic.setdefault(e.topic_id, []).append(bool(e.is_correct))

    states = []
    for topic, subject in rows:
        recent = by_topic.get(topic.id, [])[-5:]
        comps = completions.get(topic.id)
        p = predictions.get(topic.id)
        states.append(TopicState(
            topic_id=topic.id, subject_id=subject.id, name=topic.name, subject_name=subject.name,
            difficulty=topic.difficulty, estimated_minutes=topic.estimated_minutes,
            predicted_p=p.probability if p else None, model_version=p.model_version if p else None,
            recent_accuracy=(sum(recent) / len(recent)) if recent else None,
            recent_wrong=sum(1 for r in recent if not r),
            n_events=len(by_topic.get(topic.id, [])),
            days_since_revision=(today - max(pred.aware(c) for c in comps).date()).days if comps else None,
            missed_count=missed.get(topic.id, 0), exam_date=exams.get(subject.id),
        ))
        if store_predictions and p:
            db.add(ModelPrediction(user_id=user.id, topic_id=topic.id, predicted_p=p.probability,
                                   model_version=p.model_version, n_events_used=p.n_events))
    return states, info


def generate_plan(db: Session, user: User, horizon_days: int = 7, today: date | None = None) -> list[RevisionSession]:
    today = today or _today()
    # 1) Planned sessions whose day has passed were never done -> missed (feeds the scheduler).
    db.execute(update(RevisionSession).where(
        RevisionSession.user_id == user.id, RevisionSession.status == "planned",
        RevisionSession.scheduled_date < today).values(status="missed"))
    # 2) Drop future auto-generated sessions; they are recomputed. Manual / started / done stay.
    db.execute(delete(RevisionSession).where(
        RevisionSession.user_id == user.id, RevisionSession.status == "planned",
        RevisionSession.is_manual.is_(False), RevisionSession.scheduled_date >= today))
    db.flush()

    end = today + timedelta(days=horizon_days)
    booked = [
        Booked(s.scheduled_date, s.start_minute, s.duration_minutes)
        for s in db.scalars(select(RevisionSession).where(
            RevisionSession.user_id == user.id, RevisionSession.status.in_(ACTIVE_BOOKED),
            RevisionSession.scheduled_date >= today, RevisionSession.scheduled_date < end))
    ]
    states, _ = gather_topic_states(db, user, today, store_predictions=True)
    planned = build_plan(states, booked, today, horizon_days, user.daily_study_minutes, user.session_minutes)
    created = [RevisionSession(
        user_id=user.id, subject_id=p.subject_id, topic_id=p.topic_id, scheduled_date=p.scheduled_date,
        start_minute=p.start_minute, duration_minutes=p.duration_minutes, status="planned",
        priority_score=p.priority_score, reason=p.reason, predicted_p=p.predicted_p,
        model_version=p.model_version) for p in planned]
    db.add_all(created)
    db.commit()
    return created


def on_quiz_submitted(db: Session, user: User, attempt: QuizAttempt) -> None:
    """After a quiz: record actual accuracy against the latest prediction, then replan."""
    per_topic: dict[int, list[bool]] = {}
    for r in attempt.responses:
        per_topic.setdefault(r.question.topic_id, []).append(bool(r.is_correct))
    for topic_id, results in per_topic.items():
        latest = db.scalar(
            select(ModelPrediction).where(
                ModelPrediction.user_id == user.id, ModelPrediction.topic_id == topic_id,
                ModelPrediction.actual_rate.is_(None), ModelPrediction.created_at < attempt.started_at)
            .order_by(ModelPrediction.created_at.desc()).limit(1))
        if latest:
            latest.actual_rate = sum(results) / len(results)
    db.commit()
    if db.scalar(select(func.count()).select_from(RevisionSession).where(RevisionSession.user_id == user.id)):
        generate_plan(db, user)
