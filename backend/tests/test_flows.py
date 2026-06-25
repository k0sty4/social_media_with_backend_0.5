"""Flow / scenario tests — full user journeys across several endpoints.

These exercise the system the way a real user would: sign up, post, follow,
search. They prove the pieces work TOGETHER, not just in isolation.
"""

from tests.conftest import _make_client, TEST_PASSWORD


def test_signup_then_post_appears_in_global_feed(client):
    """Journey: register → (auto logged in) → create a post → see it in the feed."""
    # 1. Sign up — the server sets the session cookie on this same client.
    r = client.post("/api/auth/register", json={
        "name": "Newbie", "email": "newbie@example.com", "password": "password123",
    })
    assert r.status_code == 201

    # 2. Create a post (no separate login needed — register signed us in).
    r = client.post("/api/posts", data={
        "title": "Hello world", "body": "<p>my first post</p>",
    }, content_type="multipart/form-data")
    assert r.status_code == 201

    # 3. The post shows up in the global feed.
    feed = client.get("/api/posts?scope=all").get_json()
    assert any(p["title"] == "Hello world" for p in feed["items"])


def test_login_create_edit_persists(auth_client, user):
    """Journey: create a post, then edit it; the change persists in the feed."""
    created = auth_client.post("/api/posts", data={
        "title": "Draft", "body": "<p>v1</p>",
    }, content_type="multipart/form-data").get_json()

    auth_client.patch(f"/api/posts/{created['id']}", json={"title": "Final"})

    feed = auth_client.get("/api/posts?scope=all").get_json()
    titles = {p["title"] for p in feed["items"]}
    assert "Final" in titles
    assert "Draft" not in titles


def test_follow_then_unfollow_changes_following_feed(app, user, other_user, make_post):
    """Journey: B posts → A follows B → B's post is in A's following feed →
    A unfollows → it's gone."""
    make_post(other_user, title="Bob speaks")
    alice = _make_client(app)
    alice.post("/api/auth/login", json={"email": user.email, "password": TEST_PASSWORD})

    # Before following: empty following feed.
    assert alice.get("/api/posts?scope=following").get_json()["items"] == []

    # Follow → post appears.
    alice.post(f"/api/users/{other_user.id}/follow")
    items = alice.get("/api/posts?scope=following").get_json()["items"]
    assert any(p["title"] == "Bob speaks" for p in items)

    # Unfollow → gone again.
    alice.delete(f"/api/users/{other_user.id}/follow")
    assert alice.get("/api/posts?scope=following").get_json()["items"] == []


def test_logout_blocks_posting_until_login_again(client, user):
    """Journey: log in → log out → posting is blocked (401) → log back in → works."""
    client.post("/api/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    client.post("/api/auth/logout")

    blocked = client.post("/api/posts", data={
        "title": "x", "body": "<p>x</p>",
    }, content_type="multipart/form-data")
    assert blocked.status_code == 401

    client.post("/api/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    ok = client.post("/api/posts", data={
        "title": "back", "body": "<p>back</p>",
    }, content_type="multipart/form-data")
    assert ok.status_code == 201


def test_register_then_searchable(client):
    """Journey: a newly registered user can immediately be found via search."""
    client.post("/api/auth/register", json={
        "name": "Findable Person", "email": "findable@example.com", "password": "password123",
    })
    results = client.get("/api/search?q=Findable").get_json()
    assert any(u["name"] == "Findable Person" for u in results)
