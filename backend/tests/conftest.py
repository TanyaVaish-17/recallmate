"""Shared pytest fixtures.

Tests run against an in-memory SQLite database, never your real Postgres.
DATABASE_URL / JWT_SECRET are overridden BEFORE the app is imported, and real
environment variables take priority over the .env file in pydantic-settings.
"""
import os

os.environ["DATABASE_URL"] = "sqlite://"
os.environ["JWT_SECRET"] = "test-secret-not-for-production-0123456789abcdef"
os.environ["JWT_ALGORITHM"] = "HS256"
os.environ["ACCESS_TOKEN_EXPIRE_MINUTES"] = "60"

from datetime import date, timedelta  # noqa: E402

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import create_engine, event  # noqa: E402
from sqlalchemy.orm import sessionmaker  # noqa: E402
from sqlalchemy.pool import StaticPool  # noqa: E402

from app import models  # noqa: E402,F401  (registers all tables on Base.metadata)
from app.db.base import Base  # noqa: E402
from app.db.session import get_db  # noqa: E402
from app.main import app as fastapi_app  # noqa: E402


# --------------------------------------------------------------------------- #
# Database + client
# --------------------------------------------------------------------------- #
@pytest.fixture()
def engine():
    eng = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )

    @event.listens_for(eng, "connect")
    def _enable_foreign_keys(dbapi_conn, _record):
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    Base.metadata.create_all(eng)
    yield eng
    Base.metadata.drop_all(eng)
    eng.dispose()


@pytest.fixture()
def session_factory(engine):
    return sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)


@pytest.fixture()
def client(session_factory):
    def override_get_db():
        db = session_factory()
        try:
            yield db
        finally:
            db.close()

    fastapi_app.dependency_overrides[get_db] = override_get_db
    with TestClient(fastapi_app) as c:
        yield c
    fastapi_app.dependency_overrides.clear()


# --------------------------------------------------------------------------- #
# Users
# --------------------------------------------------------------------------- #
@pytest.fixture()
def register_user(client):
    def _register(email="student@example.com", password="password123", name="Student"):
        r = client.post(
            "/api/auth/register",
            json={"email": email, "password": password, "display_name": name},
        )
        assert r.status_code == 201, r.text
        r = client.post("/api/auth/login", json={"email": email, "password": password})
        assert r.status_code == 200, r.text
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    return _register


@pytest.fixture()
def auth_headers(register_user):
    return register_user("alice@example.com", name="Alice")


@pytest.fixture()
def other_headers(register_user):
    return register_user("bob@example.com", name="Bob")


# --------------------------------------------------------------------------- #
# Object factories (each returns the JSON of the created object)
# --------------------------------------------------------------------------- #
@pytest.fixture()
def create_subject(client):
    def _create(headers, name="Deep Learning", **extra):
        r = client.post("/api/subjects", json={"name": name, **extra}, headers=headers)
        assert r.status_code == 201, r.text
        return r.json()

    return _create


@pytest.fixture()
def create_topic(client):
    def _create(headers, subject_id, name="Transformers", **extra):
        r = client.post(
            f"/api/subjects/{subject_id}/topics",
            json={"name": name, **extra},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        return r.json()

    return _create


@pytest.fixture()
def create_question(client):
    def _create(headers, topic_id, text="What does self-attention compute?", options=None,
                explanation="Because attention weights are a softmax over similarities."):
        options = options or [
            {"text": "Weighted sum of values", "is_correct": True},
            {"text": "A convolution", "is_correct": False},
            {"text": "A pooling step", "is_correct": False},
        ]
        r = client.post(
            f"/api/topics/{topic_id}/questions",
            json={"text": text, "options": options, "explanation": explanation},
            headers=headers,
        )
        assert r.status_code == 201, r.text
        return r.json()

    return _create


@pytest.fixture()
def create_exam(client):
    def _create(headers, subject_id, days_ahead=10, title="Midterm"):
        r = client.post(
            "/api/exams",
            json={
                "subject_id": subject_id,
                "title": title,
                "exam_date": (date.today() + timedelta(days=days_ahead)).isoformat(),
            },
            headers=headers,
        )
        assert r.status_code == 201, r.text
        return r.json()

    return _create


@pytest.fixture()
def quiz_setup(auth_headers, create_subject, create_topic, create_question):
    """Alice has 1 subject, 1 topic and 3 questions (first option is correct)."""
    subject = create_subject(auth_headers)
    topic = create_topic(auth_headers, subject["id"])
    questions = [
        create_question(auth_headers, topic["id"], text=f"Question number {i}?")
        for i in range(3)
    ]
    return {"subject": subject, "topic": topic, "questions": questions}
