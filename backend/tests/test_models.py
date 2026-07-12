"""Unit tests for model helper methods and the content pool.

These exercise the serialisation / helper logic on the SQLAlchemy models
directly (no HTTP), plus the tiny ``content`` module used to seed posts.
They complement the endpoint tests, which only reach these helpers indirectly.
"""

from datetime import datetime, timedelta

from models import db, User, Post, Follow, Session
import content


# --- User.avatar_url -------------------------------------------------------

def test_avatar_url_uses_seed_when_set():
    """A custom ``avatar_seed`` is embedded verbatim in the DiceBear URL."""
    u = User(name="X", email="x@x.com", avatar_seed="pikachu")
    assert "seed=pikachu" in u.avatar_url()


def test_avatar_url_falls_back_to_user_id(app, user):
    """With no seed, the URL falls back to a stable ``user<id>`` seed."""
    assert user.avatar_seed is None
    assert f"seed=user{user.id}" in user.avatar_url()


# --- Post.created_iso ------------------------------------------------------

def test_created_iso_has_utc_z_suffix(app, user, make_post):
    """The ISO string ends in ``Z`` so the browser parses it as UTC."""
    post = make_post(user)
    iso = post.created_iso()
    assert iso.endswith("Z")
    # Round-trips back to a datetime once the Z is dropped.
    datetime.fromisoformat(iso[:-1])


def test_created_iso_falls_back_to_epoch_for_legacy_row():
    """A row with no timestamp (legacy data) reports the Unix epoch, not a crash."""
    post = Post(user_id=1, item="t", body="<p>b</p>", created_at=None)
    assert post.created_iso() == "1970-01-01T00:00:00Z"


# --- User.to_public_dict ---------------------------------------------------

def test_public_dict_never_exposes_password_hash(app, user):
    """The serialiser must never leak the password hash under any key."""
    user.set_password("password123")
    db.session.commit()
    data = user.to_public_dict(include_posts=True)
    assert "password_hash" not in data
    assert "password123" not in str(data)


def test_public_dict_includes_post_count_and_preview(app, user, make_post):
    """With ``include_posts`` the dict carries a capped preview + full count."""
    for i in range(7):
        make_post(user, title=f"post {i}")
    data = user.to_public_dict(include_posts=True)
    assert data["postCount"] == 7
    assert len(data["posts"]) == 5  # preview is capped at 5


def test_public_dict_is_following_reflects_viewer(app, user, other_user):
    """``isFollowing`` is True only when the viewer follows this user."""
    db.session.add(Follow(follower_id=other_user.id, followee_id=user.id))
    db.session.commit()
    assert user.to_public_dict(viewer_id=other_user.id)["isFollowing"] is True
    assert user.to_public_dict(viewer_id=user.id)["isFollowing"] is False
    assert user.to_public_dict(viewer_id=None)["isFollowing"] is False


# --- Post serialisers ------------------------------------------------------

def test_post_to_api_dict_shape(app, user, make_post):
    """``to_api_dict`` uses the JSONPlaceholder-style keys the frontend expects."""
    post = make_post(user, title="Hello")
    d = post.to_api_dict()
    assert d["userId"] == user.id
    assert d["title"] == "Hello"
    assert set(d) == {"userId", "id", "title", "body", "image", "created_at"}


def test_post_to_dict_includes_author_name(app, user, make_post):
    """``to_dict`` (debug shape) resolves the author's display name."""
    post = make_post(user, title="Hi")
    assert post.to_dict()["user_name"] == user.name


# --- Follow.exists ---------------------------------------------------------

def test_follow_exists_false_for_missing_edge(app, user, other_user):
    assert Follow.exists(user.id, other_user.id) is False


def test_follow_exists_true_after_follow(app, user, other_user):
    db.session.add(Follow(follower_id=user.id, followee_id=other_user.id))
    db.session.commit()
    assert Follow.exists(user.id, other_user.id) is True


def test_follow_exists_false_on_none_ids(app):
    """Guard: a missing viewer/target id never counts as a follow."""
    assert Follow.exists(None, 1) is False
    assert Follow.exists(1, None) is False


# --- follower / following counts -------------------------------------------

def test_follow_counts(app, user, other_user):
    """user follows other_user → counts reflect the single directed edge."""
    db.session.add(Follow(follower_id=user.id, followee_id=other_user.id))
    db.session.commit()
    assert other_user.follower_count() == 1
    assert user.following_count() == 1
    assert other_user.following_count() == 0
    assert user.follower_count() == 0


# --- Session.is_expired ----------------------------------------------------

def test_session_is_expired():
    past = Session(token="a", user_id=1, expires_at=datetime.utcnow() - timedelta(hours=1))
    future = Session(token="b", user_id=1, expires_at=datetime.utcnow() + timedelta(hours=1))
    assert past.is_expired() is True
    assert future.is_expired() is False


# --- content pool ----------------------------------------------------------

def test_random_title_from_pool():
    assert content.random_title() in content.POST_TITLES


def test_random_body_uses_pool_snippets():
    """A generated body is built from one or two of the curated snippets."""
    body = content.random_body()
    assert any(snippet in body for snippet in content.POST_BODIES)
    assert body.strip() != ""
