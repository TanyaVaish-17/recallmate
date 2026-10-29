"""Student data isolation: user B must never see or change user A's data."""
import pytest


@pytest.fixture()
def world(auth_headers, create_subject, create_topic, create_question, create_exam):
    subject = create_subject(auth_headers)
    topic = create_topic(auth_headers, subject["id"])
    question = create_question(auth_headers, topic["id"])
    exam = create_exam(auth_headers, subject["id"])
    return {"subject": subject, "topic": topic, "question": question, "exam": exam}


def test_other_user_cannot_read_update_or_delete_subject(client, other_headers, world):
    sid = world["subject"]["id"]
    assert client.get(f"/api/subjects/{sid}", headers=other_headers).status_code == 404
    assert client.patch(f"/api/subjects/{sid}", json={"name": "Hacked"}, headers=other_headers).status_code == 404
    assert client.delete(f"/api/subjects/{sid}", headers=other_headers).status_code == 404
    assert client.get(f"/api/subjects/{sid}/topics", headers=other_headers).status_code == 404


def test_other_user_cannot_create_topic_in_foreign_subject(client, other_headers, world):
    r = client.post(f"/api/subjects/{world['subject']['id']}/topics", json={"name": "Sneaky"}, headers=other_headers)
    assert r.status_code == 404


def test_other_user_cannot_touch_topic(client, other_headers, world):
    tid = world["topic"]["id"]
    assert client.get(f"/api/topics/{tid}", headers=other_headers).status_code == 404
    assert client.patch(f"/api/topics/{tid}", json={"difficulty": 1}, headers=other_headers).status_code == 404
    assert client.delete(f"/api/topics/{tid}", headers=other_headers).status_code == 404


def test_other_user_cannot_touch_questions(client, other_headers, world):
    tid, qid = world["topic"]["id"], world["question"]["id"]
    body = {"text": "Injected?", "options": [{"text": "a", "is_correct": True}, {"text": "b", "is_correct": False}]}
    assert client.get(f"/api/topics/{tid}/questions", headers=other_headers).status_code == 404
    assert client.post(f"/api/topics/{tid}/questions", json=body, headers=other_headers).status_code == 404
    assert client.get(f"/api/questions/{qid}", headers=other_headers).status_code == 404
    assert client.patch(f"/api/questions/{qid}", json={"text": "Changed"}, headers=other_headers).status_code == 404
    assert client.delete(f"/api/questions/{qid}", headers=other_headers).status_code == 404


def test_other_user_cannot_touch_exams(client, other_headers, world):
    eid = world["exam"]["id"]
    assert client.patch(f"/api/exams/{eid}", json={"title": "Hacked"}, headers=other_headers).status_code == 404
    assert client.delete(f"/api/exams/{eid}", headers=other_headers).status_code == 404
    r = client.post(
        "/api/exams",
        json={"subject_id": world["subject"]["id"], "exam_date": world["exam"]["exam_date"]},
        headers=other_headers,
    )
    assert r.status_code == 404


def test_other_user_lists_are_empty(client, other_headers, world):
    assert client.get("/api/subjects", headers=other_headers).json() == []
    assert client.get("/api/exams", headers=other_headers).json() == []
    assert client.get("/api/quizzes", headers=other_headers).json() == []


def test_other_user_cannot_use_quizzes_of_foreign_data(client, auth_headers, other_headers, world):
    # start a quiz on someone else's topic
    r = client.post("/api/quizzes/start", json={"topic_ids": [world["topic"]["id"]]}, headers=other_headers)
    assert r.status_code == 404

    # Alice starts a quiz; Bob cannot read or submit it
    started = client.post("/api/quizzes/start", json={"topic_ids": [world["topic"]["id"]]}, headers=auth_headers).json()
    aid = started["id"]
    q = started["questions"][0]
    answer = {"answers": [{"question_id": q["id"], "option_id": q["options"][0]["id"]}]}
    assert client.get(f"/api/quizzes/{aid}", headers=other_headers).status_code == 404
    assert client.post(f"/api/quizzes/{aid}/submit", json=answer, headers=other_headers).status_code == 404


def test_owner_data_is_untouched_after_failed_attacks(client, auth_headers, other_headers, world):
    sid = world["subject"]["id"]
    client.patch(f"/api/subjects/{sid}", json={"name": "Hacked"}, headers=other_headers)
    client.delete(f"/api/subjects/{sid}", headers=other_headers)
    r = client.get(f"/api/subjects/{sid}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["name"] == world["subject"]["name"]


PROTECTED = [
    ("GET", "/api/auth/me"),
    ("PATCH", "/api/auth/me"),
    ("GET", "/api/subjects"),
    ("POST", "/api/subjects"),
    ("GET", "/api/subjects/1"),
    ("GET", "/api/topics/1"),
    ("GET", "/api/topics/1/questions"),
    ("GET", "/api/questions/1"),
    ("GET", "/api/exams"),
    ("POST", "/api/exams"),
    ("POST", "/api/quizzes/start"),
    ("GET", "/api/quizzes"),
    ("GET", "/api/quizzes/1"),
    ("POST", "/api/quizzes/1/submit"),
]


@pytest.mark.parametrize("method,path", PROTECTED)
def test_endpoints_require_authentication(client, method, path):
    r = client.request(method, path, json={} if method in {"POST", "PATCH"} else None)
    assert r.status_code == 401
