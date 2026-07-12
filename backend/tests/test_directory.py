"""API tests for the public read endpoints that had no direct coverage:

  * ``GET /``               — the route catalog / landing endpoint
  * ``GET /api/users``      — the full user directory
  * ``GET /api/random-user``— a single random user (or 404 when the DB is empty)
"""

from models import db, Follow


# --- GET / (route catalog) -------------------------------------------------

def test_api_root_lists_endpoints(client):
    resp = client.get("/")
    assert resp.status_code == 200
    body = resp.get_json()
    assert body["name"] == "Profile Explorer API"
    # The catalog groups routes by access level.
    assert set(body["endpoints"]) == {"public", "auth", "authed"}


# --- GET /api/users (directory) -------------------------------------------

def test_users_directory_lists_everyone(client, user, other_user):
    resp = client.get("/api/users")
    assert resp.status_code == 200
    users = resp.get_json()
    assert {u["email"] for u in users} == {user.email, other_user.email}


def test_users_directory_never_leaks_password_hash(client, user):
    user.set_password("password123")
    db.session.commit()
    resp = client.get("/api/users")
    assert "password_hash" not in str(resp.get_json())


def test_users_directory_is_following_for_viewer(auth_client, user, other_user):
    """An authenticated viewer sees ``isFollowing`` set on users they follow."""
    db.session.add(Follow(follower_id=user.id, followee_id=other_user.id))
    db.session.commit()

    users = auth_client.get("/api/users").get_json()
    by_id = {u["id"]: u for u in users}
    assert by_id[other_user.id]["isFollowing"] is True
    assert by_id[user.id]["isFollowing"] is False


def test_users_directory_empty_db(client):
    assert client.get("/api/users").get_json() == []


# --- GET /api/random-user --------------------------------------------------

def test_random_user_returns_a_user(client, user):
    resp = client.get("/api/random-user")
    assert resp.status_code == 200
    assert resp.get_json()["id"] == user.id


def test_random_user_404_on_empty_db(client):
    resp = client.get("/api/random-user")
    assert resp.status_code == 404


def test_random_user_never_leaks_password_hash(client, user):
    user.set_password("password123")
    db.session.commit()
    resp = client.get("/api/random-user")
    assert "password_hash" not in str(resp.get_json())
