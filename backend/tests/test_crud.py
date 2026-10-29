from datetime import date, timedelta

import pytest


# ------------------------------- Subjects ---------------------------------- #
def test_create_subject_defaults(create_subject, auth_headers):
    subject = create_subject(auth_headers, name="  Operating Systems  ")
    assert subject["name"] == "Operating Systems"
    assert subject["color"] == "#F5C518"


def test_duplicate_subject_conflict_but_other_user_can_reuse_name(
    client, auth_headers, other_headers, create_subject
):
    create_subject(auth_headers, name="DBMS")
    r = client.post("/api/subjects", json={"name": "DBMS"}, headers=auth_headers)
    assert r.status_code == 409
    assert client.post("/api/subjects", json={"name": "DBMS"}, headers=other_headers).status_code == 201


@pytest.mark.parametrize("color", ["red", "#12345", "#GGGGGG", "123456"])
def test_subject_invalid_color(client, auth_headers, color):
    r = client.post("/api/subjects", json={"name": "X", "color": color}, headers=auth_headers)
    assert r.status_code == 422


def test_subject_pagination(client, auth_headers, create_subject):
    for name in ["A", "B", "C"]:
        create_subject(auth_headers, name=name)
    assert len(client.get("/api/subjects", headers=auth_headers).json()) == 3
    assert len(client.get("/api/subjects?limit=2", headers=auth_headers).json()) == 2
    assert len(client.get("/api/subjects?skip=2", headers=auth_headers).json()) == 1
    assert client.get("/api/subjects?limit=0", headers=auth_headers).status_code == 422


def test_update_subject(client, auth_headers, create_subject):
    s = create_subject(auth_headers, name="DL")
    other = create_subject(auth_headers, name="OS")
    r = client.patch(f"/api/subjects/{s['id']}", json={"name": "Deep Learning", "color": "#00FF00"}, headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["name"] == "Deep Learning"
    assert r.json()["color"] == "#00FF00"
    r = client.patch(f"/api/subjects/{s['id']}", json={"name": other["name"]}, headers=auth_headers)
    assert r.status_code == 409


def test_delete_subject_cascades_to_topics(client, auth_headers, create_subject, create_topic):
    s = create_subject(auth_headers)
    t = create_topic(auth_headers, s["id"])
    assert client.delete(f"/api/subjects/{s['id']}", headers=auth_headers).status_code == 204
    assert client.get(f"/api/subjects/{s['id']}", headers=auth_headers).status_code == 404
    assert client.get(f"/api/topics/{t['id']}", headers=auth_headers).status_code == 404


def test_subject_detail_includes_topics(client, auth_headers, create_subject, create_topic):
    s = create_subject(auth_headers)
    create_topic(auth_headers, s["id"], name="CNNs")
    create_topic(auth_headers, s["id"], name="RNNs")
    r = client.get(f"/api/subjects/{s['id']}", headers=auth_headers)
    assert [t["name"] for t in r.json()["topics"]] == ["CNNs", "RNNs"]


# -------------------------------- Topics ----------------------------------- #
def test_topic_defaults(create_subject, create_topic, auth_headers):
    t = create_topic(auth_headers, create_subject(auth_headers)["id"])
    assert t["difficulty"] == 3
    assert t["estimated_minutes"] == 30


def test_duplicate_topic_conflict(client, auth_headers, create_subject, create_topic):
    s = create_subject(auth_headers)
    create_topic(auth_headers, s["id"], name="GANs")
    r = client.post(f"/api/subjects/{s['id']}/topics", json={"name": "GANs"}, headers=auth_headers)
    assert r.status_code == 409


@pytest.mark.parametrize(
    "body",
    [{"difficulty": 0}, {"difficulty": 6}, {"estimated_minutes": 4}, {"estimated_minutes": 241}, {"name": " "}],
)
def test_topic_validation(client, auth_headers, create_subject, body):
    s = create_subject(auth_headers)
    payload = {"name": "T", **body}
    assert client.post(f"/api/subjects/{s['id']}/topics", json=payload, headers=auth_headers).status_code == 422


def test_update_and_delete_topic(client, auth_headers, create_subject, create_topic):
    s = create_subject(auth_headers)
    t = create_topic(auth_headers, s["id"])
    r = client.patch(f"/api/topics/{t['id']}", json={"difficulty": 5, "estimated_minutes": 60}, headers=auth_headers)
    assert r.status_code == 200
    assert (r.json()["difficulty"], r.json()["estimated_minutes"]) == (5, 60)
    assert client.delete(f"/api/topics/{t['id']}", headers=auth_headers).status_code == 204
    assert client.get(f"/api/topics/{t['id']}", headers=auth_headers).status_code == 404


# --------------------------------- Exams ----------------------------------- #
def test_create_exam_reports_days_remaining(create_exam, create_subject, auth_headers):
    exam = create_exam(auth_headers, create_subject(auth_headers)["id"], days_ahead=10)
    assert exam["days_remaining"] == 10


def test_exam_in_the_past_is_rejected(client, auth_headers, create_subject):
    s = create_subject(auth_headers)
    r = client.post(
        "/api/exams",
        json={"subject_id": s["id"], "exam_date": (date.today() - timedelta(days=1)).isoformat()},
        headers=auth_headers,
    )
    assert r.status_code == 422


def test_exam_list_filter_update_delete(client, auth_headers, create_subject, create_exam):
    s1 = create_subject(auth_headers, name="DL")
    s2 = create_subject(auth_headers, name="OS")
    e1 = create_exam(auth_headers, s1["id"], days_ahead=5)
    create_exam(auth_headers, s2["id"], days_ahead=3)

    all_exams = client.get("/api/exams", headers=auth_headers).json()
    assert [e["days_remaining"] for e in all_exams] == [3, 5]  # sorted by date
    only_dl = client.get(f"/api/exams?subject_id={s1['id']}", headers=auth_headers).json()
    assert [e["id"] for e in only_dl] == [e1["id"]]

    new_date = (date.today() + timedelta(days=20)).isoformat()
    r = client.patch(f"/api/exams/{e1['id']}", json={"exam_date": new_date}, headers=auth_headers)
    assert r.status_code == 200 and r.json()["days_remaining"] == 20
    past = (date.today() - timedelta(days=2)).isoformat()
    assert client.patch(f"/api/exams/{e1['id']}", json={"exam_date": past}, headers=auth_headers).status_code == 422

    assert client.delete(f"/api/exams/{e1['id']}", headers=auth_headers).status_code == 204
    assert len(client.get("/api/exams", headers=auth_headers).json()) == 1


# ------------------------------- Questions --------------------------------- #
def test_create_question_orders_options(create_question, create_topic, create_subject, auth_headers):
    t = create_topic(auth_headers, create_subject(auth_headers)["id"])
    q = create_question(auth_headers, t["id"])
    assert [o["position"] for o in q["options"]] == [0, 1, 2]
    assert sum(o["is_correct"] for o in q["options"]) == 1
    assert q["explanation"]


@pytest.mark.parametrize(
    "options",
    [
        [{"text": "a", "is_correct": False}, {"text": "b", "is_correct": False}],   # none correct
        [{"text": "a", "is_correct": True}, {"text": "b", "is_correct": True}],     # two correct
        [{"text": "a", "is_correct": True}],                                         # only one option
        [{"text": "a", "is_correct": True}, {"text": "A", "is_correct": False}],     # duplicate (case-insens.)
    ],
)
def test_question_option_validation(client, auth_headers, create_subject, create_topic, options):
    t = create_topic(auth_headers, create_subject(auth_headers)["id"])
    r = client.post(f"/api/topics/{t['id']}/questions", json={"text": "Q?", "options": options}, headers=auth_headers)
    assert r.status_code == 422


def test_duplicate_question_conflict(client, auth_headers, create_subject, create_topic, create_question):
    t = create_topic(auth_headers, create_subject(auth_headers)["id"])
    q = create_question(auth_headers, t["id"])
    r = client.post(
        f"/api/topics/{t['id']}/questions",
        json={"text": q["text"], "options": [{"text": "x", "is_correct": True}, {"text": "y", "is_correct": False}]},
        headers=auth_headers,
    )
    assert r.status_code == 409


def test_update_question_replaces_options_and_clears_explanation(
    client, auth_headers, create_subject, create_topic, create_question
):
    t = create_topic(auth_headers, create_subject(auth_headers)["id"])
    q = create_question(auth_headers, t["id"])
    new_options = [{"text": "Yes", "is_correct": False}, {"text": "No", "is_correct": True}]
    r = client.patch(
        f"/api/questions/{q['id']}",
        json={"options": new_options, "explanation": None},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert [o["text"] for o in r.json()["options"]] == ["Yes", "No"]
    assert r.json()["explanation"] is None


def test_list_and_delete_question(client, auth_headers, create_subject, create_topic, create_question):
    t = create_topic(auth_headers, create_subject(auth_headers)["id"])
    q = create_question(auth_headers, t["id"])
    assert len(client.get(f"/api/topics/{t['id']}/questions", headers=auth_headers).json()) == 1
    assert client.delete(f"/api/questions/{q['id']}", headers=auth_headers).status_code == 204
    assert client.get(f"/api/questions/{q['id']}", headers=auth_headers).status_code == 404
