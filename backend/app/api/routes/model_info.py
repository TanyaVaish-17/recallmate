"""Endpoints the React frontend calls that did not exist in the backend yet.

Frontend call                         ->  handled here
GET    /api/plan/today                    today's + overdue sessions (Dashboard)
GET    /api/predictions/topics            per-topic model estimates (Dashboard, Analytics)
GET    /api/model/results                 status + explainer + results.json (Model page)
POST   /api/plan/sessions                 add a session manually
POST   /api/plan/sessions/{id}/complete   mark done
POST   /api/plan/sessions/{id}/skip       skip
POST   /api/plan/sessions/{id}/reschedule move to another day
DELETE /api/plan/sessions/{id}            delete a session

Session actions reuse the existing logic in routes/plan.py, so behaviour is identical
to /api/sessions/... (which keeps working for the tests).
"""
import json

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.api.deps import get_current_user
from app.api.routes import plan as plan_routes
from app.db.session import get_db
from app.models.revision import RevisionSession
from app.models.subject import Subject
from app.models.user import User
from app.schemas.revision import SessionCreate, SessionRead, SessionReschedule
from app.services import planner, prediction as pred

router = APIRouter(tags=["frontend"])


# --------------------------------------------------------------------------- dashboard
@router.get("/plan/today")
def plan_today(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    today = planner._today()
    rows = list(db.scalars(
        select(RevisionSession).where(
            RevisionSession.user_id == user.id,
            RevisionSession.scheduled_date <= today,
            RevisionSession.status.in_(("planned", "in_progress", "completed", "skipped")),
        ).order_by(RevisionSession.scheduled_date, RevisionSession.start_minute)))
    sessions = plan_routes._read(db, rows)
    open_states = ("planned", "in_progress")
    return {
        "overdue": [s for s in sessions if s.scheduled_date < today and s.status in open_states],
        "today": [s for s in sessions if s.scheduled_date == today],
    }


@router.get("/predictions/topics")
def predictions_topics(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    states, info = planner.gather_topic_states(db, user, planner._today())
    colors = {s.id: s.color for s in db.scalars(select(Subject).where(Subject.user_id == user.id))}
    return {
        "model": info,
        "topics": [
            {
                "topic_id": s.topic_id,
                "topic_name": s.name,
                "subject_name": s.subject_name,
                "subject_color": colors.get(s.subject_id, "#6366f1"),
                "probability": s.predicted_p,
                "model_version": s.model_version,
                "n_events": s.n_events,
                "recent_accuracy": s.recent_accuracy,
            }
            for s in states
        ],
    }


# --------------------------------------------------------------------------- model page
EXPLAINER = {
    "why_transformer": (
        "Knowledge tracing predicts whether a student will answer the next question correctly "
        "from their whole answer history. Self-attention lets the model weigh any earlier answer "
        "directly, so it can pick up spacing and repetition effects without a hand-written "
        "forgetting curve."
    ),
    "architecture": (
        "A compact causal Transformer encoder (pre-LayerNorm). Each step sums question, topic and "
        "previous-answer embeddings, a linear projection of five numeric features, and a positional "
        "embedding. Two encoder blocks with causal multi-head self-attention follow, then a small "
        "head outputs P(correct) through a sigmoid."
    ),
    "input_features": [
        "Question id and topic id (hidden as UNK for RecallMate's own question bank)",
        "Whether the previous answer was right, wrong, or none yet",
        "log(1 + hours since the previous answer on any topic)",
        "log(1 + hours since the previous answer on the same topic)",
        "log(1 + prior attempts at this exact question) and at this topic",
        "Whether a revision session on the topic was completed since the last answer",
    ],
    "target_construction": (
        "At every step the target is whether that answer was correct, and the input at that step "
        "never includes that answer. Attention is causal, so a step can only see earlier steps. "
        "Students are split between train, validation and test, and normalisation is fitted on the "
        "training split only."
    ),
    "limitations": [
        "The output is an estimate of answering correctly, not a direct measure of memory.",
        "Results shown come from the dataset named on this page; synthetic data is only a development check.",
        "A student needs a minimum number of recorded answers before the model produces estimates.",
        "RecallMate's questions are not in the training vocabulary, so ids are hidden and the model "
        "relies on answer history, timing and revision flags.",
    ],
}


@router.get("/model/results")
def model_results():
    results = None
    if pred.RESULTS_PATH.exists():
        results = json.loads(pred.RESULTS_PATH.read_text())
    return {"status": pred.model_status(), "explainer": EXPLAINER, "results": results}


# --------------------------------------------------------------------------- session actions
@router.post("/plan/sessions", response_model=SessionRead, status_code=status.HTTP_201_CREATED)
def add_session(payload: SessionCreate, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return plan_routes.create_session(payload, db, user)


@router.post("/plan/sessions/{session_id}/complete", response_model=SessionRead)
def complete(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return plan_routes.complete_session(session_id, db, user)


@router.post("/plan/sessions/{session_id}/skip", response_model=SessionRead)
def skip(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return plan_routes.skip_session(session_id, db, user)


@router.post("/plan/sessions/{session_id}/reschedule", response_model=SessionRead)
def reschedule(session_id: int, payload: SessionReschedule, db: Session = Depends(get_db),
               user: User = Depends(get_current_user)):
    return plan_routes.reschedule(session_id, payload, db, user)


@router.delete("/plan/sessions/{session_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_session(session_id: int, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    s = plan_routes._owned_session(db, session_id, user)
    db.delete(s)
    db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)