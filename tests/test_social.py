"""API tests for social features (requirements c.i and c.ii):
user search and follow / unfollow.
"""

from tests.conftest import _make_client, TEST_PASSWORD


def _login_as(app, user):
    c = _make_client(app)
    c.post("/api/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    return c


# --- Search ----------------------------------------------------------------

def test_search_by_name(client, user):
    results = client.get("/api/search?q=Alice").get_json()
    assert any(u["name"] == "Alice" for u in results)


def test_search_by_username(client, user):
    results = client.get("/api/search?q=alice").get_json()
    assert any(u["id"] == user.id for u in results)


def test_search_by_email(client, user):
    results = client.get("/api/search?q=alice@example").get_json()
    assert any(u["id"] == user.id for u in results)


def test_search_is_case_insensitive(client, user):
    results = client.get("/api/search?q=ALICE").get_json()
    assert any(u["id"] == user.id for u in results)


def test_search_empty_query_returns_empty(client, user):
    assert client.get("/api/search?q=").get_json() == []


def test_search_no_match_returns_empty(client, user):
    assert client.get("/api/search?q=zzzznotfound").get_json() == []


# --- Follow / unfollow -----------------------------------------------------

def test_follow_user(app, user, other_user):
    alice = _login_as(app, user)
    resp = alice.post(f"/api/users/{other_user.id}/follow")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["isFollowing"] is True
    assert data["followersCount"] == 1  # Bob now has 1 follower


def test_unfollow_user(app, user, other_user):
    alice = _login_as(app, user)
    alice.post(f"/api/users/{other_user.id}/follow")
    resp = alice.delete(f"/api/users/{other_user.id}/follow")
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["isFollowing"] is False
    assert data["followersCount"] == 0


def test_cannot_follow_yourself(auth_client, user):
    resp = auth_client.post(f"/api/users/{user.id}/follow")
    assert resp.status_code == 400


def test_follow_requires_auth(client, other_user):
    resp = client.post(f"/api/users/{other_user.id}/follow")
    assert resp.status_code == 401


def test_follow_unknown_user(auth_client):
    resp = auth_client.post("/api/users/99999/follow")
    assert resp.status_code == 404


def test_follow_is_idempotent(app, user, other_user):
    """Following twice doesn't double the count."""
    alice = _login_as(app, user)
    alice.post(f"/api/users/{other_user.id}/follow")
    resp = alice.post(f"/api/users/{other_user.id}/follow")
    assert resp.get_json()["followersCount"] == 1


def test_follow_counts_reflect_relationship(app, user, other_user):
    """After Alice follows Bob: Alice.following == 1, Bob.followers == 1."""
    alice = _login_as(app, user)
    alice.post(f"/api/users/{other_user.id}/follow")

    alice_profile = alice.get(f"/api/user/{user.id}").get_json()
    bob_profile = alice.get(f"/api/user/{other_user.id}").get_json()
    assert alice_profile["followingCount"] == 1
    assert bob_profile["followersCount"] == 1
    assert bob_profile["isFollowing"] is True  # from Alice's viewpoint
