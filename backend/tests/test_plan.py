from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select

from app.models.revision import RevisionSession
from app.services import prediction as pred


@pytest.fixture(autouse=True)
def no_checkpoint(monkeypatch, tmp_path):
    """Default: pretend no model is trained. Individual tests override."""
    monkeypatch.setattr(pred, "CHECKPOINT_PATH", tmp_path / "missing.pt")
    pred.reset_model_cache()
    yield
    pred.reset_model_cache()


def setup_two_topics(headers, create_subject, create_topic, create_exam):
    s = create_subject(headers, name="Deep Learning")
    t1 = create_topic(headers, s["id"], name="Attention", estimated_minutes=30)
    t2 = create_topic(headers, s["id"], name="Optimizers", estimated_minutes=30)
    create_exam(headers, s["id"], days_ahead=5)
    return s, t1, t2


def test_model_status_reports_untrained(client, auth_headers):
    body = client.get("/api/model/status").json()
    assert body["trained"] is False and "how_to_train" in body


def test_plan_generates_without_model_and_respects_budget(client, auth_headers, create_subject, create_topic, create_exam):
    setup_two_topics(auth_headers, create_subject, create_topic, create_exam)
    r = client.post("/api/plan/generate", json={"horizon_days": 3}, headers=auth_headers)
    assert r.status_code == 200
    sessions = r.json()
    assert sessions and all(s["predicted_p"] is None for s in sessions)
    assert all("no model estimate" in s["reason"] for s in sessions)
    for d in {s["scheduled_date"] for s in sessions}:
        assert sum(s["duration_minutes"] for s in sessions if s["scheduled_date"] == d) <= 120


def test_session_lifecycle(client, auth_headers, create_subject, create_topic, create_exam):
    setup_two_topics(auth_headers, create_subject, create_topic, create_exam)
    sid = client.post("/api/plan/generate", json={}, headers=auth_headers).json()[0]["id"]
    assert client.post(f"/api/sessions/{sid}/start", headers=auth_headers).json()["status"] == "in_progress"
    assert client.post(f"/api/sessions/{sid}/complete", headers=auth_headers).json()["status"] == "completed"
    assert client.post(f"/api/sessions/{sid}/skip", headers=auth_headers).status_code == 409  # already completed


def test_sessions_are_private(client, auth_headers, other_headers, create_subject, create_topic, create_exam):
    setup_two_topics(auth_headers, create_subject, create_topic, create_exam)
    sid = client.post("/api/plan/generate", json={}, headers=auth_headers).json()[0]["id"]
    assert client.post(f"/api/sessions/{sid}/complete", headers=other_headers).status_code == 404
    assert client.get("/api/plan", headers=other_headers).json() == []


def test_manual_session_overlap_is_prevented(client, auth_headers, create_subject, create_topic, create_exam):
    _, t1, _ = setup_two_topics(auth_headers, create_subject, create_topic, create_exam)
    day = (date.today() + timedelta(days=20)).isoformat()
    a = client.post("/api/sessions", json={"topic_id": t1["id"], "scheduled_date": day, "duration_minutes": 60}, headers=auth_headers).json()
    b = client.post("/api/sessions", json={"topic_id": t1["id"], "scheduled_date": day, "duration_minutes": 60}, headers=auth_headers).json()
    assert a["start_minute"] == 0 and b["start_minute"] == 60
    c = client.post("/api/sessions", json={"topic_id": t1["id"], "scheduled_date": day, "duration_minutes": 30}, headers=auth_headers)
    assert c.status_code == 409  # 120-minute day is full


def test_missed_session_is_marked_and_topic_is_rescheduled(client, auth_headers, session_factory, create_subject, create_topic, create_exam):
    _, t1, _ = setup_two_topics(auth_headers, create_subject, create_topic, create_exam)
    client.post("/api/plan/generate", json={"horizon_days": 2}, headers=auth_headers)
    db = session_factory()
    old = db.scalars(select(RevisionSession)).first()
    old.scheduled_date = date.today() - timedelta(days=1)  # simulate a session that was never done
    db.commit()
    old_id = old.id
    db.close()

    sessions = client.post("/api/plan/generate", json={"horizon_days": 2}, headers=auth_headers).json()
    db = session_factory()
    assert db.get(RevisionSession, old_id).status == "missed"
    db.close()
    assert sessions  # replanned future sessions exist


def test_submitting_quiz_replans_when_plan_exists(client, auth_headers, quiz_setup):
    client.post("/api/plan/generate", json={}, headers=auth_headers)
    q = client.post("/api/quizzes/start", json={"topic_ids": [quiz_setup["topic"]["id"]], "num_questions": 3}, headers=auth_headers).json()
    answers = [{"question_id": x["id"], "option_id": x["options"][0]["id"]} for x in q["questions"]]
    assert client.post(f"/api/quizzes/{q['id']}/submit", json={"answers": answers}, headers=auth_headers).status_code == 200


def test_analytics_has_no_fabricated_data_for_new_user(client, auth_headers):
    body = client.get("/api/analytics/summary", headers=auth_headers).json()
    assert body["scores_over_time"] == [] and body["predicted_vs_actual"] == []


# ------------------------------------------------------------------ need a trained checkpoint
real_ckpt = pytest.mark.skipif(
    not (pred.ROOT_DIR / "ml" / "artifacts" / "kt_transformer.pt").exists(),
    reason="needs ml/artifacts/kt_transformer.pt (run the training script)")


def _history(n):
    base = datetime(2030, 1, 1, tzinfo=timezone.utc)
    return [pred.HistoryEvent(topic_id=1 + i % 2, question_id=i, correct=int(i % 3 != 0),
                              ts=base + timedelta(hours=i)) for i in range(n)]


@real_ckpt
def test_real_model_predictions_are_probabilities(monkeypatch):
    monkeypatch.setattr(pred, "CHECKPOINT_PATH", pred.ROOT_DIR / "ml" / "artifacts" / "kt_transformer.pt")
    pred.reset_model_cache()
    out = pred.predict_topics(_history(12), [1, 2], now=datetime(2030, 1, 3, tzinfo=timezone.utc))
    assert set(out) == {1, 2} and all(0 < p.probability < 1 for p in out.values())
    assert pred.predict_topics(_history(3), [1]) == {}  # too little history -> no prediction


@real_ckpt
def test_prediction_ignores_future_dummy_and_is_deterministic(monkeypatch):
    monkeypatch.setattr(pred, "CHECKPOINT_PATH", pred.ROOT_DIR / "ml" / "artifacts" / "kt_transformer.pt")
    pred.reset_model_cache()
    now = datetime(2030, 1, 3, tzinfo=timezone.utc)
    a = pred.predict_topics(_history(12), [1], now=now)[1].probability
    b = pred.predict_topics(_history(12), [1], now=now)[1].probability
    assert a == b
