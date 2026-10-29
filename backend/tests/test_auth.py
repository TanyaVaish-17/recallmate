import pytest


def _register(client, **overrides):
    body = {"email": "new@example.com", "password": "password123", "display_name": "New User"}
    body.update(overrides)
    return client.post("/api/auth/register", json=body)


def test_health(client):
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_register_success_never_returns_password(client):
    r = _register(client)
    assert r.status_code == 201
    data = r.json()
    assert data["email"] == "new@example.com"
    assert data["display_name"] == "New User"
    assert data["daily_study_minutes"] == 120
    assert data["session_minutes"] == 30
    assert "password" not in r.text
    assert "hashed_password" not in r.text


def test_register_normalizes_email_and_name(client):
    r = _register(client, email="  Mixed.Case@Example.COM ", display_name="  Tanya  ")
    assert r.status_code == 201
    assert r.json()["email"] == "mixed.case@example.com"
    assert r.json()["display_name"] == "Tanya"


def test_register_duplicate_email_conflict(client):
    assert _register(client).status_code == 201
    assert _register(client).status_code == 409
    assert _register(client, email="NEW@example.com").status_code == 409


@pytest.mark.parametrize(
    "overrides",
    [
        {"password": "short"},
        {"email": "not-an-email"},
        {"display_name": ""},
        {"display_name": "   "},
    ],
)
def test_register_validation_errors(client, overrides):
    assert _register(client, **overrides).status_code == 422


def test_login_success_and_me(client, register_user):
    headers = register_user("alice@example.com", name="Alice")
    r = client.get("/api/auth/me", headers=headers)
    assert r.status_code == 200
    assert r.json()["email"] == "alice@example.com"


def test_login_wrong_password(client):
    _register(client)
    r = client.post("/api/auth/login", json={"email": "new@example.com", "password": "wrong-password"})
    assert r.status_code == 401


def test_login_unknown_email(client):
    r = client.post("/api/auth/login", json={"email": "ghost@example.com", "password": "password123"})
    assert r.status_code == 401


def test_login_email_is_case_insensitive(client):
    _register(client)
    r = client.post("/api/auth/login", json={"email": "NEW@Example.com", "password": "password123"})
    assert r.status_code == 200
    assert r.json()["token_type"] == "bearer"


def test_me_requires_token(client):
    assert client.get("/api/auth/me").status_code == 401


def test_me_rejects_garbage_token(client):
    r = client.get("/api/auth/me", headers={"Authorization": "Bearer garbage"})
    assert r.status_code == 401


def test_update_profile(client, auth_headers):
    r = client.patch(
        "/api/auth/me",
        json={"display_name": "Alice B", "daily_study_minutes": 180, "session_minutes": 45},
        headers=auth_headers,
    )
    assert r.status_code == 200
    assert r.json()["display_name"] == "Alice B"
    assert r.json()["daily_study_minutes"] == 180
    assert r.json()["session_minutes"] == 45


def test_update_profile_session_cannot_exceed_daily(client, auth_headers):
    r = client.patch(
        "/api/auth/me",
        json={"daily_study_minutes": 60, "session_minutes": 90},
        headers=auth_headers,
    )
    assert r.status_code == 422


@pytest.mark.parametrize(
    "body",
    [{"daily_study_minutes": 5}, {"session_minutes": 500}, {"display_name": " "}],
)
def test_update_profile_validation(client, auth_headers, body):
    assert client.patch("/api/auth/me", json=body, headers=auth_headers).status_code == 422
