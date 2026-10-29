import pytest
from sqlalchemy import select

from app.models.learning_event import LearningEvent
from app.models.quiz import QuizAttempt


# ------------------------------- helpers ----------------------------------- #
def _correct_id(question):
    return next(o["id"] for o in question["options"] if o["is_correct"])


def _wrong_id(question):
    return next(o["id"] for o in question["options"] if not o["is_correct"])


def _start(client, headers, topic_ids, n=5):
    return client.post(
        "/api/quizzes/start", json={"topic_ids": topic_ids, "num_questions": n}, headers=headers
    )


def _submit(client, headers, attempt_id, answers):
    return client.post(f"/api/quizzes/{attempt_id}/submit", json={"answers": answers}, headers=headers)


def _answers(setup, started, n_correct):
    """Answer the first n_correct questions correctly and the rest wrongly."""
    by_id = {q["id"]: q for q in setup["questions"]}
    out = []
    for i, q in enumerate(started["questions"]):
        full = by_id[q["id"]]
        out.append({
            "question_id": q["id"],
            "option_id": _correct_id(full) if i < n_correct else _wrong_id(full),
        })
    return out


# --------------------------------- start ----------------------------------- #
def test_start_quiz_hides_correct_answers(client, auth_headers, quiz_setup):
    r = _start(client, auth_headers, [quiz_setup["topic"]["id"]])
    assert r.status_code == 201
    assert "is_correct" not in r.text
    assert "explanation" not in r.text
    for q in r.json()["questions"]:
        assert len(q["options"]) == 3
        assert all(set(o) == {"id", "text"} for o in q["options"])


def test_start_quiz_respects_num_questions(client, auth_headers, quiz_setup):
    topic_id = quiz_setup["topic"]["id"]
    assert len(_start(client, auth_headers, [topic_id], n=2).json()["questions"]) == 2
    # only 3 questions exist, so asking for 5 returns 3
    assert len(_start(client, auth_headers, [topic_id], n=5).json()["questions"]) == 3


def test_start_quiz_topic_without_questions(client, auth_headers, create_subject, create_topic):
    t = create_topic(auth_headers, create_subject(auth_headers)["id"])
    assert _start(client, auth_headers, [t["id"]]).status_code == 422


@pytest.mark.parametrize(
    "body",
    [
        {"topic_ids": []},
        {"topic_ids": [1, 1]},
        {"topic_ids": [1], "num_questions": 0},
        {"topic_ids": [1], "num_questions": 21},
    ],
)
def test_start_quiz_validation(client, auth_headers, body):
    assert client.post("/api/quizzes/start", json=body, headers=auth_headers).status_code == 422


# ------------------------------- scoring ----------------------------------- #
@pytest.mark.parametrize("n_correct", [0, 1, 2, 3])
def test_quiz_scoring(client, auth_headers, quiz_setup, n_correct):
    started = _start(client, auth_headers, [quiz_setup["topic"]["id"]]).json()
    r = _submit(client, auth_headers, started["id"], _answers(quiz_setup, started, n_correct))
    assert r.status_code == 200
    result = r.json()
    assert result["score"] == n_correct
    assert result["total"] == 3
    assert result["percent"] == round(n_correct / 3 * 100, 1)
    assert sum(x["is_correct"] for x in result["responses"]) == n_correct

    by_id = {q["id"]: q for q in quiz_setup["questions"]}
    for resp in result["responses"]:
        assert resp["correct_option_id"] == _correct_id(by_id[resp["question_id"]])
        assert resp["explanation"]


# --------------------------- submit validation ----------------------------- #
def test_cannot_submit_twice(client, auth_headers, quiz_setup, session_factory):
    started = _start(client, auth_headers, [quiz_setup["topic"]["id"]]).json()
    answers = _answers(quiz_setup, started, 3)
    assert _submit(client, auth_headers, started["id"], answers).status_code == 200
    assert _submit(client, auth_headers, started["id"], answers).status_code == 409
    with session_factory() as db:
        assert len(db.scalars(select(LearningEvent)).all()) == 3  # no duplicates


def test_must_answer_every_question(client, auth_headers, quiz_setup, session_factory):
    started = _start(client, auth_headers, [quiz_setup["topic"]["id"]]).json()
    partial = _answers(quiz_setup, started, 3)[:2]
    assert _submit(client, auth_headers, started["id"], partial).status_code == 422
    with session_factory() as db:
        assert db.scalars(select(LearningEvent)).all() == []
        assert db.get(QuizAttempt, started["id"]).completed_at is None


def test_duplicate_answers_rejected(client, auth_headers, quiz_setup):
    started = _start(client, auth_headers, [quiz_setup["topic"]["id"]]).json()
    answers = _answers(quiz_setup, started, 3)
    answers.append(answers[0])
    assert _submit(client, auth_headers, started["id"], answers).status_code == 422


def test_option_from_another_question_rejected(client, auth_headers, quiz_setup):
    started = _start(client, auth_headers, [quiz_setup["topic"]["id"]]).json()
    answers = _answers(quiz_setup, started, 3)
    by_id = {q["id"]: q for q in quiz_setup["questions"]}
    other_q = next(q for q in quiz_setup["questions"] if q["id"] != answers[0]["question_id"])
    answers[0]["option_id"] = _correct_id(other_q)
    assert answers[0]["question_id"] in by_id
    assert _submit(client, auth_headers, started["id"], answers).status_code == 422


def test_unknown_option_rejected(client, auth_headers, quiz_setup):
    started = _start(client, auth_headers, [quiz_setup["topic"]["id"]]).json()
    answers = _answers(quiz_setup, started, 3)
    answers[0]["option_id"] = 999999
    assert _submit(client, auth_headers, started["id"], answers).status_code == 422


# ------------------------ learning-event recording ------------------------- #
def test_submit_records_one_learning_event_per_answer(client, auth_headers, quiz_setup, session_factory):
    started = _start(client, auth_headers, [quiz_setup["topic"]["id"]]).json()
    _submit(client, auth_headers, started["id"], _answers(quiz_setup, started, 2))

    with session_factory() as db:
        events = db.scalars(select(LearningEvent).order_by(LearningEvent.id)).all()
    assert len(events) == 3
    assert sum(e.is_correct for e in events) == 2
    for e in events:
        assert e.quiz_attempt_id == started["id"]
        assert e.topic_id == quiz_setup["topic"]["id"]
        assert e.subject_id == quiz_setup["subject"]["id"]
        assert e.event_type == "quiz"
        assert e.attempt_number == 1
        assert e.occurred_at is not None


def test_attempt_number_increments_per_question(
    client, auth_headers, create_subject, create_topic, create_question, session_factory
):
    topic = create_topic(auth_headers, create_subject(auth_headers)["id"])
    question = create_question(auth_headers, topic["id"])
    setup = {"questions": [question]}

    for _ in range(2):
        started = _start(client, auth_headers, [topic["id"]]).json()
        assert _submit(client, auth_headers, started["id"], _answers(setup, started, 1)).status_code == 200

    with session_factory() as db:
        numbers = sorted(e.attempt_number for e in db.scalars(select(LearningEvent)))
    assert numbers == [1, 2]


# -------------------------------- history ---------------------------------- #
def test_history_lists_only_completed_attempts_newest_first(client, auth_headers, quiz_setup):
    topic_id = quiz_setup["topic"]["id"]
    first = _start(client, auth_headers, [topic_id]).json()
    _submit(client, auth_headers, first["id"], _answers(quiz_setup, first, 3))
    second = _start(client, auth_headers, [topic_id]).json()
    _submit(client, auth_headers, second["id"], _answers(quiz_setup, second, 0))
    _start(client, auth_headers, [topic_id])  # started but never submitted

    history = client.get("/api/quizzes", headers=auth_headers).json()
    assert [a["id"] for a in history] == [second["id"], first["id"]]
    assert [a["percent"] for a in history] == [0.0, 100.0]


def test_get_attempt_before_and_after_submit(client, auth_headers, quiz_setup):
    started = _start(client, auth_headers, [quiz_setup["topic"]["id"]]).json()
    assert client.get(f"/api/quizzes/{started['id']}", headers=auth_headers).status_code == 409
    _submit(client, auth_headers, started["id"], _answers(quiz_setup, started, 3))
    r = client.get(f"/api/quizzes/{started['id']}", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()["responses"]) == 3


def test_get_unknown_attempt(client, auth_headers):
    assert client.get("/api/quizzes/999999", headers=auth_headers).status_code == 404
