import json
from datetime import date, datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy import Integer, cast, func, select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.ownership import get_owned_topic
from app.db.session import get_db
from app.models.exam import Exam
from app.models.learning_event import LearningEvent
from app.models.quiz import QuizAttempt
from app.models.revision import ModelPrediction, RevisionSession
from app.models.subject import Subject
from app.models.topic import Topic
from app.models.user import User
from app.schemas.revision import PlanGenerate, SessionCreate, SessionRead, SessionReschedule
from app.services import planner, prediction as pred
from app.services.scheduler import first_free

router = APIRouter(tags=["plan"])


# --------------------------------------------------------------------------- helpers
def _read(db: Session, sessions: list[RevisionSession]) -> list[SessionRead]:
    if not sessions:
        return []
    topics = {t.id: t for t in db.scalars(select(Topic).where(Topic.id.in_({s.topic_id for s in sessions})))}
    subjects = {s.id: s for s in db.scalars(select(Subject).where(Subject.id.in_({s.subject_id for s in sessions})))}
    return [
        SessionRead(
            id=s.id, topic_id=s.topic_id, topic_name=topics[s.topic_id].name, subject_id=s.subject_id,
            subject_name=subjects[s.subject_id].name, subject_color=subjects[s.subject_id].color,
            scheduled_date=s.scheduled_date, start_minute=s.start_minute, duration_minutes=s.duration_minutes,
            status=s.status, priority_score=s.priority_score, reason=s.reason, predicted_p=s.predicted_p,
            model_version=s.model_version, is_manual=s.is_manual, started_at=s.started_at, completed_at=s.completed_at,
        ) for s in sessions
    ]


def _owned_session(db: Session, session_id: int, user: User) -> RevisionSession:
    s = db.scalar(select(RevisionSession).where(RevisionSession.id == session_id, RevisionSession.user_id == user.id))
    if s is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Session not found")
    return s


def _place(db: Session, user: User, day: date, duration: int, exclude_id: int | None = None) -> int:
    others = db.scalars(select(RevisionSession).where(
        RevisionSession.user_id == user.id, RevisionSession.scheduled_date == day,
        RevisionSession.status.in_(planner.ACTIVE_BOOKED)))
    intervals = [(o.start_minute, o.start_minute + o.duration_minutes) for o in others if o.id != exclude_id]
    start = first_free(intervals, duration, user.daily_study_minutes)
    if start is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Not enough free study time on that day")
    return start


# --------------------------------------------------------------------------- model
@router.get("/model/status")
def model_status():
    return pred.model_status()


@router.get("/model/metrics")
def model_metrics():
    """Measured experiment results written by `python -m ml.training.train` (never fabricated)."""
    if not pred.RESULTS_PATH.exists():
        raise HTTPException(status.HTTP_404_NOT_FOUND, "No experiment results found. Train the model first.")
    return json.loads(pred.RESULTS_PATH.read_text())


@router.get("/predictions")
def topic_predictions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    states, info = planner.gather_topic_states(db, user, planner._today())
    return {
        "model": info,
        "topics": [
            {"topic_id": s.topic_id, "topic": s.name, "subject": s.subject_name,
             "predicted_p": s.predicted_p, "model_version": s.model_version, "n_events": s.n_events,
             "recent_accuracy": s.recent_accuracy}
            for s in states
        ],
    }


# --------------------------------------------------------------------------- plan
@router.post("/plan/generate", response_model=list[SessionRead])
def generate(payload: PlanGenerate = PlanGenerate(), db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return _read(db, planner.generate_plan(db, user, payload.horizon_days))


@router.get("/plan", response_model=list[SessionRead])
def get_plan(
    start: date | None = None, end: date | None = None, limit: int = Query(200, ge=1, le=500),
    db: Session = Depends(get_db), user: User = Depends(get_current_user),
):
    start = start or planner._today()
    end = end or start + timedelta(days=6)
    rows = db.scalars(
        select(RevisionSession).where(
            RevisionSession.user_id == user.id, RevisionSession.scheduled_date >= start,
            RevisionSession.scheduled_date <= end)
        .order_by(RevisionSession.scheduled_date, RevisionSession.start_minute).limit(limit))
    return _read(db, list(rows))


@router.post("/sessions", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
def create_session(payload: SessionCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    topic = get_owned_topic(db, payload.topic_id, user)
    if payload.scheduled_date < planner._today():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Cannot schedule in the past")
    start = _place(db, user, payload.scheduled_date, payload.duration_minutes)
    s = RevisionSession(
        user_id=user.id, subject_id=topic.subject_id, topic_id=topic.id, scheduled_date=payload.scheduled_date,
        start_minute=start, duration_minutes=payload.duration_minutes, is_manual=True,
        reason="Added manually by you.")
    db.add(s)
    db.commit()
    return _read(db, [s])[0]


@router.patch("/sessions/{session_id}", response_model=SessionRead)
def reschedule(session_id: int, payload: SessionReschedule, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = _owned_session(db, session_id, user)
    if s.status not in ("planned", "missed"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"A {s.status} session cannot be rescheduled")
    day = payload.scheduled_date or s.scheduled_date
    duration = payload.duration_minutes or s.duration_minutes
    if day < planner._today():
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY, "Cannot schedule in the past")
    s.start_minute = _place(db, user, day, duration, exclude_id=s.id)
    s.scheduled_date, s.duration_minutes = day, duration
    s.status, s.is_manual = "planned", True
    s.reason = (s.reason + " | Rescheduled by you.") if "Rescheduled" not in s.reason else s.reason
    db.commit()
    return _read(db, [s])[0]


@router.post("/sessions/{session_id}/start", response_model=SessionRead)
def start_session(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = _owned_session(db, session_id, user)
    if s.status != "planned":
        raise HTTPException(status.HTTP_409_CONFLICT, f"A {s.status} session cannot be started")
    s.status, s.started_at = "in_progress", datetime.now(timezone.utc)
    db.commit()
    return _read(db, [s])[0]


@router.post("/sessions/{session_id}/complete", response_model=SessionRead)
def complete_session(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = _owned_session(db, session_id, user)
    if s.status not in ("planned", "in_progress"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"A {s.status} session cannot be completed")
    s.status, s.completed_at = "completed", datetime.now(timezone.utc)
    db.commit()
    planner.generate_plan(db, user)  # completing revision changes "days since revision"
    db.refresh(s)
    return _read(db, [s])[0]


@router.post("/sessions/{session_id}/skip", response_model=SessionRead)
def skip_session(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = _owned_session(db, session_id, user)
    if s.status not in ("planned", "in_progress"):
        raise HTTPException(status.HTTP_409_CONFLICT, f"A {s.status} session cannot be skipped")
    s.status = "skipped"
    db.commit()
    planner.generate_plan(db, user)
    db.refresh(s)
    return _read(db, [s])[0]


# --------------------------------------------------------------------------- analytics
@router.get("/analytics/summary")
def analytics(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    today = planner._today()

    attempts = db.scalars(
        select(QuizAttempt).where(QuizAttempt.user_id == user.id, QuizAttempt.completed_at.is_not(None))
        .order_by(QuizAttempt.completed_at).limit(200))
    scores_over_time = [
        {"attempt_id": a.id, "date": a.completed_at.isoformat(), "score": a.score, "total": a.total,
         "percent": round(100 * a.score / a.total, 1) if a.total else 0}
        for a in attempts
    ]

    subj_rows = db.execute(
        select(Subject.id, Subject.name, Subject.color, func.count(LearningEvent.id),
               func.sum(cast(LearningEvent.is_correct, Integer)))
        .join(LearningEvent, LearningEvent.subject_id == Subject.id, isouter=True)
        .where(Subject.user_id == user.id).group_by(Subject.id)).all()
    subject_performance = [
        {"subject_id": i, "subject": n, "color": c, "answers": int(cnt or 0),
         "accuracy": round(int(ok or 0) / cnt, 3) if cnt else None}
        for i, n, c, cnt, ok in subj_rows
    ]

    topic_rows = db.execute(
        select(Topic.id, Topic.name, Subject.name, func.count(LearningEvent.id),
               func.sum(cast(LearningEvent.is_correct, Integer)))
        .join(Subject, Topic.subject_id == Subject.id)
        .join(LearningEvent, LearningEvent.topic_id == Topic.id)
        .where(Subject.user_id == user.id).group_by(Topic.id, Subject.name)).all()
    needs_practice = sorted(
        [{"topic_id": i, "topic": t, "subject": s, "answers": int(cnt), "accuracy": round(int(ok or 0) / cnt, 3)}
         for i, t, s, cnt, ok in topic_rows if cnt >= 3 and (int(ok or 0) / cnt) < 0.7],
        key=lambda r: r["accuracy"])[:8]

    week_start = today - timedelta(days=6)
    sess = list(db.scalars(select(RevisionSession).where(
        RevisionSession.user_id == user.id, RevisionSession.scheduled_date >= week_start,
        RevisionSession.scheduled_date <= today)))
    revision_completion = [
        {"date": (week_start + timedelta(days=i)).isoformat(),
         "planned": sum(1 for s in sess if s.scheduled_date == week_start + timedelta(days=i)),
         "completed": sum(1 for s in sess if s.scheduled_date == week_start + timedelta(days=i) and s.status == "completed")}
        for i in range(7)
    ]

    pairs = db.scalars(select(ModelPrediction).where(
        ModelPrediction.user_id == user.id, ModelPrediction.actual_rate.is_not(None))
        .order_by(ModelPrediction.created_at.desc()).limit(100))
    predicted_vs_actual = [{"topic_id": p.topic_id, "predicted": round(p.predicted_p, 3),
                            "actual": round(p.actual_rate, 3), "model_version": p.model_version} for p in pairs]

    exams = db.execute(
        select(Exam, Subject.name, Subject.color).join(Subject, Exam.subject_id == Subject.id)
        .where(Exam.user_id == user.id, Exam.exam_date >= today).order_by(Exam.exam_date).limit(10)).all()
    upcoming_exams = [{"id": e.id, "title": e.title, "subject": n, "color": c,
                       "exam_date": e.exam_date.isoformat(), "days_left": (e.exam_date - today).days}
                      for e, n, c in exams]

    counts = dict(db.execute(select(RevisionSession.status, func.count()).where(
        RevisionSession.user_id == user.id).group_by(RevisionSession.status)).all())
    return {
        "scores_over_time": scores_over_time,
        "subject_performance": subject_performance,
        "needs_practice": needs_practice,
        "revision_completion": revision_completion,
        "predicted_vs_actual": predicted_vs_actual,
        "upcoming_exams": upcoming_exams,
        "session_counts": counts,
        "model": pred.model_status(),
    }

