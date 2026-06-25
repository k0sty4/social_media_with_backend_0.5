"""Security-focused API tests (the "bonus" hardening):
CSRF origin check, HTML sanitisation end-to-end, session expiry, and that
uploaded-file serving can't be tricked into path traversal.
"""

from datetime import datetime, timedelta

from models import db, Session
from app import _hash_token, FRONTEND_ORIGIN
from tests.conftest import _make_client, TEST_PASSWORD


# --- CSRF: the Origin header must match -------------------------------------

def test_mutation_with_wrong_origin_is_blocked(app, user):
    """A mutating request from a foreign Origin is rejected with 403."""
    c = app.test_client()
    # login is CSRF-exempt, so it works without a trusted Origin.
    c.post("/api/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    # A guarded mutation from evil.com must be refused.
    resp = c.post(
        "/api/posts",
        data={"title": "x", "body": "<p>x</p>"},
        content_type="multipart/form-data",
        headers={"Origin": "http://evil.com"},
    )
    assert resp.status_code == 403


def test_mutation_with_correct_origin_passes(auth_client):
    """Sanity check: the same mutation from the trusted Origin succeeds."""
    resp = auth_client.post(
        "/api/posts",
        data={"title": "ok", "body": "<p>ok</p>"},
        content_type="multipart/form-data",
        headers={"Origin": FRONTEND_ORIGIN},
    )
    assert resp.status_code == 201


# --- Sanitisation end-to-end -----------------------------------------------

def test_script_is_stripped_before_storage(auth_client, app):
    """An injected <script> never reaches the database."""
    auth_client.post("/api/posts", data={
        "title": "XSS attempt",
        "body": "<p>safe</p><script>steal()</script>",
    }, content_type="multipart/form-data")
    from models import Post
    stored = db.session.scalar(db.select(Post))
    assert "<script" not in stored.body


# --- Session expiry --------------------------------------------------------

def test_expired_session_is_rejected(app, user):
    """A cookie pointing at an expired session is treated as logged out."""
    raw_token = "expired-token-value"
    db.session.add(Session(
        token=_hash_token(raw_token),
        user_id=user.id,
        expires_at=datetime.utcnow() - timedelta(days=1),  # already expired
    ))
    db.session.commit()

    c = _make_client(app)
    c.set_cookie("session_id", raw_token, domain="localhost")
    # A protected action should fail as if no one is logged in.
    resp = c.patch(f"/api/user/{user.id}", json={"name": "x"})
    assert resp.status_code == 401


# --- Upload serving: no path traversal -------------------------------------

def test_upload_unknown_file_404(client):
    assert client.get("/api/uploads/does-not-exist.png").status_code == 404


def test_upload_path_traversal_blocked(client):
    """A crafted filename can't escape the uploads directory to read app.py."""
    resp = client.get("/api/uploads/..%2f..%2fapp.py")
    assert resp.status_code in (403, 404)
    # Whatever happens, the Python source must NOT be served.
    assert b"Flask" not in resp.data
