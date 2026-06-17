"""API tests for the feed (requirement d): global feed, following feed,
pagination, and per-user post lists.
"""

from models import db, Follow
from tests.conftest import _make_client, TEST_PASSWORD


def _login_as(app, user):
    c = _make_client(app)
    c.post("/api/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    return c


# --- Global feed -----------------------------------------------------------

def test_global_feed_returns_posts(client, user, make_post):
    make_post(user, title="Post A")
    make_post(user, title="Post B")
    resp = client.get("/api/posts?scope=all")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["total"] == 2
    assert len(data["items"]) == 2


def test_global_feed_newest_first(client, user, make_post):
    """Posts come back newest-first (highest id first)."""
    p1 = make_post(user, title="Older")
    p2 = make_post(user, title="Newer")
    items = client.get("/api/posts?scope=all").get_json()["items"]
    assert items[0]["id"] == p2.id
    assert items[1]["id"] == p1.id


def test_feed_pagination(client, user, make_post):
    """per_page limits the page size and has_more flags whether more remain."""
    for i in range(15):
        make_post(user, title=f"Post {i}")

    page1 = client.get("/api/posts?scope=all&page=1&per_page=10").get_json()
    assert len(page1["items"]) == 10
    assert page1["has_more"] is True

    page2 = client.get("/api/posts?scope=all&page=2&per_page=10").get_json()
    assert len(page2["items"]) == 5
    assert page2["has_more"] is False


def test_feed_no_duplicate_across_pages(client, user, make_post):
    """Page 1 and page 2 contain different posts (no overlap)."""
    for i in range(15):
        make_post(user, title=f"Post {i}")
    ids1 = {p["id"] for p in client.get("/api/posts?page=1&per_page=10").get_json()["items"]}
    ids2 = {p["id"] for p in client.get("/api/posts?page=2&per_page=10").get_json()["items"]}
    assert ids1.isdisjoint(ids2)


# --- Following feed --------------------------------------------------------

def test_following_feed_requires_auth(client):
    resp = client.get("/api/posts?scope=following")
    assert resp.status_code == 401


def test_following_feed_shows_only_followed(app, user, other_user, make_post):
    """The following feed contains posts by followed users and excludes others."""
    # Bob writes a post; Alice does too.
    make_post(other_user, title="Bob's post")
    make_post(user, title="Alice's own post")

    # Alice follows Bob.
    db.session.add(Follow(follower_id=user.id, followee_id=other_user.id))
    db.session.commit()

    alice = _login_as(app, user)
    items = alice.get("/api/posts?scope=following").get_json()["items"]
    titles = {p["title"] for p in items}
    assert "Bob's post" in titles          # followed → included
    assert "Alice's own post" not in titles  # not followed (yourself) → excluded


def test_following_feed_empty_when_following_nobody(auth_client, other_user, make_post):
    make_post(other_user, title="Bob's post")
    items = auth_client.get("/api/posts?scope=following").get_json()["items"]
    assert items == []


# --- Per-user post list ----------------------------------------------------

def test_user_posts_endpoint(client, user, other_user, make_post):
    """GET /api/users/<id>/posts returns only that user's posts."""
    make_post(user, title="Alice 1")
    make_post(user, title="Alice 2")
    make_post(other_user, title="Bob 1")

    data = client.get(f"/api/users/{user.id}/posts").get_json()
    assert data["total"] == 2
    titles = {p["title"] for p in data["items"]}
    assert titles == {"Alice 1", "Alice 2"}


def test_user_posts_unknown_user(client):
    resp = client.get("/api/users/99999/posts")
    assert resp.status_code == 404
