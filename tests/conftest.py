"""Shared pytest fixtures for the whole test suite.

A "fixture" is a reusable piece of setup that tests can ask for by naming it as
an argument. Here we build a throwaway database, a Flask test client, and a few
ready-made users, so individual tests stay short and focused.

Key idea: tests must NEVER touch the real ``data.db``. We point the app at a
temporary SQLite file (via the DATABASE_URI env var) BEFORE importing the app,
create the tables fresh for each test, and drop them afterwards. So every test
starts from a clean, empty database and can't corrupt your real data.
"""

import os
import tempfile

import pytest

# --- Redirect the app to a temporary database -----------------------------
# This MUST run before "import app", because app.py reads DATABASE_URI at import
# time to decide which database to connect to.
_db_fd, _db_path = tempfile.mkstemp(suffix=".db")
os.environ["DATABASE_URI"] = f"sqlite:///{_db_path}"
# The CSRF guard compares the request Origin against this value, so we pin it.
os.environ.setdefault("FRONTEND_ORIGIN", "http://localhost:5173")

import app as app_module  # noqa: E402  (import after env setup, on purpose)
from app import app as flask_app, FRONTEND_ORIGIN  # noqa: E402
from models import db, User, Post  # noqa: E402

# The password every test user is created with, so login helpers can reuse it.
TEST_PASSWORD = "password123"


@pytest.fixture
def app():
    """A Flask app bound to a fresh, empty database for one test.

    ``db.create_all()`` builds all tables before the test runs; ``db.drop_all()``
    wipes them after, so tests can't leak data into each other.
    """
    flask_app.config.update(TESTING=True)
    with flask_app.app_context():
        db.create_all()
        yield flask_app
        db.session.remove()
        db.drop_all()


@pytest.fixture(autouse=True)
def _reset_rate_limiter():
    """Clear the in-memory login rate limiter between tests.

    ``autouse=True`` means this runs for EVERY test automatically. The limiter
    is a module-level dict; without resetting it, failed-login counts from one
    test would bleed into the next and cause false 429s.
    """
    app_module._login_failures.clear()
    yield
    app_module._login_failures.clear()


def _make_client(app):
    """Build a test client that always sends a valid Origin header.

    The CSRF guard rejects mutating requests whose Origin != FRONTEND_ORIGIN,
    so we set it once here for the whole client instead of on every call.
    """
    client = app.test_client()
    client.environ_base["HTTP_ORIGIN"] = FRONTEND_ORIGIN
    return client


@pytest.fixture
def client(app):
    """An unauthenticated test client (no session cookie)."""
    return _make_client(app)


@pytest.fixture
def user(app):
    """A registered user 'Alice' with a known password."""
    u = User(name="Alice", email="alice@example.com", username="alice")
    u.set_password(TEST_PASSWORD)
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture
def other_user(app):
    """A second registered user 'Bob' — used for 'someone else' scenarios."""
    u = User(name="Bob", email="bob@example.com", username="bob")
    u.set_password(TEST_PASSWORD)
    db.session.add(u)
    db.session.commit()
    return u


@pytest.fixture
def auth_client(app, user):
    """A test client already logged in as 'Alice' (carries her session cookie)."""
    client = _make_client(app)
    resp = client.post(
        "/api/auth/login",
        json={"email": user.email, "password": TEST_PASSWORD},
    )
    assert resp.status_code == 200, "login fixture failed to authenticate"
    return client


@pytest.fixture
def make_post(app):
    """Factory: create a post directly in the DB for a given user.

    Returns a function so a test can make as many posts as it needs, e.g.
    ``make_post(user, title="Hi")``.
    """
    def _make(owner, title="A title", body="<p>Some body text</p>"):
        post = Post(user_id=owner.id, item=title, body=body)
        db.session.add(post)
        db.session.commit()
        return post
    return _make
