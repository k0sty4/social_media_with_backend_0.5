"""API tests for authentication (requirement a): register, login, logout,
change-password. Each test drives a real HTTP endpoint against a fresh DB.
"""

from models import db, User, Session
from app import _hash_token
from tests.conftest import TEST_PASSWORD


# --- Registration ----------------------------------------------------------

def test_register_success(client):
    """A valid signup creates the user, returns 201, and sets a session cookie."""
    resp = client.post("/api/auth/register", json={
        "name": "Carol", "email": "carol@example.com", "password": "password123",
    })
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["name"] == "Carol"
    assert data["email"] == "carol@example.com"
    assert "password" not in data and "password_hash" not in data
    # A session cookie must have been issued.
    assert "session_id" in resp.headers.get("Set-Cookie", "")


def test_register_password_is_hashed_in_db(client, app):
    """The stored password must be a hash, never the plaintext."""
    client.post("/api/auth/register", json={
        "name": "Dan", "email": "dan@example.com", "password": "password123",
    })
    u = db.session.scalar(db.select(User).where(User.email == "dan@example.com"))
    assert u.password_hash is not None
    assert u.password_hash != "password123"
    assert u.check_password("password123")


def test_register_missing_fields(client):
    resp = client.post("/api/auth/register", json={"email": "x@x.com"})
    assert resp.status_code == 400


def test_register_short_password(client):
    resp = client.post("/api/auth/register", json={
        "name": "Eve", "email": "eve@example.com", "password": "short",
    })
    assert resp.status_code == 400


def test_register_duplicate_email(client, user):
    """Registering with an email that already exists returns 409 Conflict."""
    resp = client.post("/api/auth/register", json={
        "name": "Imposter", "email": user.email, "password": "password123",
    })
    assert resp.status_code == 409


def test_register_email_is_case_insensitive(client, user):
    """Email is normalised to lowercase, so a different case still collides."""
    resp = client.post("/api/auth/register", json={
        "name": "Imposter", "email": user.email.upper(), "password": "password123",
    })
    assert resp.status_code == 409


# --- Login -----------------------------------------------------------------

def test_login_success(client, user):
    resp = client.post("/api/auth/login", json={
        "email": user.email, "password": TEST_PASSWORD,
    })
    assert resp.status_code == 200
    assert "session_id" in resp.headers.get("Set-Cookie", "")


def test_login_wrong_password(client, user):
    resp = client.post("/api/auth/login", json={
        "email": user.email, "password": "wrongpassword",
    })
    assert resp.status_code == 401


def test_login_unknown_email_same_error(client):
    """An unknown email returns 401 with the SAME message as a wrong password,
    so we never leak whether an account exists."""
    resp = client.post("/api/auth/login", json={
        "email": "nobody@example.com", "password": "whatever123",
    })
    assert resp.status_code == 401


def test_login_missing_fields(client):
    resp = client.post("/api/auth/login", json={"email": "x@x.com"})
    assert resp.status_code == 400


def test_login_seed_user_cannot_login(client, app):
    """A user with no password_hash (imported seed user) can't log in."""
    db.session.add(User(name="Seed", email="seed@example.com"))
    db.session.commit()
    resp = client.post("/api/auth/login", json={
        "email": "seed@example.com", "password": "anything",
    })
    assert resp.status_code == 401


def test_login_rate_limited_after_repeated_failures(client, user):
    """After enough wrong attempts for one email, further tries get 429."""
    for _ in range(5):
        r = client.post("/api/auth/login", json={
            "email": user.email, "password": "wrongpassword",
        })
        assert r.status_code == 401
    # The 6th attempt is blocked by the per-email limiter.
    blocked = client.post("/api/auth/login", json={
        "email": user.email, "password": "wrongpassword",
    })
    assert blocked.status_code == 429


# --- Logout ----------------------------------------------------------------

def test_logout_clears_session(auth_client, app):
    """Logout deletes the session row and returns 200."""
    assert db.session.scalar(db.select(db.func.count()).select_from(Session)) == 1
    resp = auth_client.post("/api/auth/logout")
    assert resp.status_code == 200
    assert db.session.scalar(db.select(db.func.count()).select_from(Session)) == 0


def test_logout_without_session_is_ok(client):
    """Logging out when not logged in is a harmless no-op (idempotent)."""
    resp = client.post("/api/auth/logout")
    assert resp.status_code == 200


# --- Change password -------------------------------------------------------

def test_change_password_success(auth_client, user):
    resp = auth_client.post("/api/auth/change-password", json={
        "current_password": TEST_PASSWORD, "new_password": "newpassword123",
    })
    assert resp.status_code == 200
    assert user.check_password("newpassword123")


def test_change_password_wrong_current(auth_client):
    resp = auth_client.post("/api/auth/change-password", json={
        "current_password": "wrongcurrent", "new_password": "newpassword123",
    })
    assert resp.status_code == 401


def test_change_password_too_short(auth_client):
    resp = auth_client.post("/api/auth/change-password", json={
        "current_password": TEST_PASSWORD, "new_password": "short",
    })
    assert resp.status_code == 400


def test_change_password_same_as_current(auth_client):
    resp = auth_client.post("/api/auth/change-password", json={
        "current_password": TEST_PASSWORD, "new_password": TEST_PASSWORD,
    })
    assert resp.status_code == 400


def test_change_password_requires_auth(client):
    resp = client.post("/api/auth/change-password", json={
        "current_password": TEST_PASSWORD, "new_password": "newpassword123",
    })
    assert resp.status_code == 401


def test_change_password_kills_other_sessions(app, user):
    """Changing the password signs out every OTHER session but keeps the one
    that made the change."""
    from tests.conftest import _make_client
    # Two separate logins for the same user = two sessions.
    c1 = _make_client(app)
    c1.post("/api/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    c2 = _make_client(app)
    c2.post("/api/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    assert db.session.scalar(db.select(db.func.count()).select_from(Session)) == 2

    # c1 changes the password.
    c1.post("/api/auth/change-password", json={
        "current_password": TEST_PASSWORD, "new_password": "newpassword123",
    })
    # Only c1's session survives.
    assert db.session.scalar(db.select(db.func.count()).select_from(Session)) == 1
