"""API tests for user profiles (requirement b): viewing and editing a profile.
"""

from tests.conftest import _make_client, TEST_PASSWORD


def _login_as(app, user):
    c = _make_client(app)
    c.post("/api/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    return c


# --- Viewing a profile -----------------------------------------------------

def test_get_user_returns_profile_fields(client, user, make_post):
    make_post(user, title="Hi")
    data = client.get(f"/api/user/{user.id}").get_json()
    assert data["name"] == "Alice"
    assert "bio" in data
    assert "avatar" in data
    assert data["postCount"] == 1


def test_get_user_never_exposes_password_hash(client, user):
    data = client.get(f"/api/user/{user.id}").get_json()
    assert "password_hash" not in data
    assert "password" not in data


def test_get_user_has_follow_counts(client, user):
    data = client.get(f"/api/user/{user.id}").get_json()
    assert data["followersCount"] == 0
    assert data["followingCount"] == 0
    assert data["isFollowing"] is False


def test_get_unknown_user_404(client):
    assert client.get("/api/user/99999").status_code == 404


# --- Editing a profile -----------------------------------------------------

def test_owner_can_edit_profile(auth_client, user):
    resp = auth_client.patch(f"/api/user/{user.id}", json={
        "name": "Alice Cooper", "bio": "Rocker",
    })
    assert resp.status_code == 200
    data = resp.get_json()
    assert data["name"] == "Alice Cooper"
    assert data["bio"] == "Rocker"


def test_cannot_edit_other_users_profile(app, user, other_user):
    """Editing someone else's profile returns 404 (info-hiding authz)."""
    bob = _login_as(app, other_user)
    resp = bob.patch(f"/api/user/{user.id}", json={"name": "Hacked"})
    assert resp.status_code == 404


def test_edit_profile_requires_auth(client, user):
    resp = client.patch(f"/api/user/{user.id}", json={"name": "Hacked"})
    assert resp.status_code == 401


def test_edit_profile_empty_name_rejected(auth_client, user):
    resp = auth_client.patch(f"/api/user/{user.id}", json={"name": "   "})
    assert resp.status_code == 400


def test_edit_profile_ignores_email_field(auth_client, user):
    """email isn't in the editable whitelist, so it stays unchanged."""
    original = user.email
    resp = auth_client.patch(f"/api/user/{user.id}", json={
        "email": "newemail@example.com", "bio": "changed",
    })
    assert resp.status_code == 200
    assert resp.get_json()["email"] == original
