"""API tests for post creation and editing (requirements e + "can edit post").

The "can edit" block is the heart of the authorisation story:
  * the author can edit their own post
  * a different user CANNOT (gets 404, which hides the post's existence)
  * a guest CANNOT (gets 401)
"""

from io import BytesIO

from models import db, Post
from tests.conftest import _make_client, TEST_PASSWORD


def _login_as(app, user):
    """Helper: a fresh client logged in as the given user."""
    c = _make_client(app)
    c.post("/api/auth/login", json={"email": user.email, "password": TEST_PASSWORD})
    return c


# --- Creating posts --------------------------------------------------------

def test_create_post_text_only(auth_client):
    resp = auth_client.post("/api/posts", data={
        "title": "My first post",
        "body": "<p>Hello <b>world</b></p>",
    }, content_type="multipart/form-data")
    assert resp.status_code == 201
    data = resp.get_json()
    assert data["title"] == "My first post"
    assert "<b>world</b>" in data["body"]
    assert data["image"] is None


def test_create_post_with_image(auth_client):
    """A post can carry an uploaded image; the response exposes its URL."""
    fake_png = (BytesIO(b"\x89PNG\r\n\x1a\n fake image bytes"), "pic.png")
    resp = auth_client.post("/api/posts", data={
        "title": "With image",
        "body": "<p>look</p>",
        "image": fake_png,
    }, content_type="multipart/form-data")
    assert resp.status_code == 201
    assert resp.get_json()["image"] is not None  # a URL was returned


def test_create_post_requires_auth(client):
    resp = client.post("/api/posts", data={
        "title": "x", "body": "<p>x</p>",
    }, content_type="multipart/form-data")
    assert resp.status_code == 401


def test_create_post_empty_title(auth_client):
    resp = auth_client.post("/api/posts", data={
        "title": "  ", "body": "<p>x</p>",
    }, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_create_post_empty_body(auth_client):
    """A body that is only markup (no text) is rejected."""
    resp = auth_client.post("/api/posts", data={
        "title": "Title", "body": "<p></p>",
    }, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_create_post_bad_image_type(auth_client):
    bad = (BytesIO(b"not an image"), "evil.exe")
    resp = auth_client.post("/api/posts", data={
        "title": "Title", "body": "<p>x</p>", "image": bad,
    }, content_type="multipart/form-data")
    assert resp.status_code == 400


def test_create_post_sanitises_body(auth_client):
    """A <script> in the body is stripped before storage."""
    resp = auth_client.post("/api/posts", data={
        "title": "XSS", "body": "<p>hi</p><script>alert(1)</script>",
    }, content_type="multipart/form-data")
    assert resp.status_code == 201
    assert "<script" not in resp.get_json()["body"]


# --- Editing posts: the authorisation matrix ("can edit") ------------------

def test_owner_can_edit_own_post(auth_client, user, make_post):
    """The author edits their own post — allowed."""
    post = make_post(user, title="Original")
    resp = auth_client.patch(f"/api/posts/{post.id}", json={"title": "Edited"})
    assert resp.status_code == 200
    assert resp.get_json()["title"] == "Edited"


def test_other_user_cannot_edit_post(app, user, other_user, make_post):
    """A DIFFERENT user editing someone else's post gets 404 (existence hidden)."""
    post = make_post(user, title="Alice's post")
    bob = _login_as(app, other_user)
    resp = bob.patch(f"/api/posts/{post.id}", json={"title": "Hacked"})
    assert resp.status_code == 404
    # And the post is unchanged in the DB.
    assert db.session.get(Post, post.id).item == "Alice's post"


def test_guest_cannot_edit_post(client, user, make_post):
    """An unauthenticated caller editing any post gets 401."""
    post = make_post(user)
    resp = client.patch(f"/api/posts/{post.id}", json={"title": "Hacked"})
    assert resp.status_code == 401


def test_edit_nonexistent_post(auth_client):
    resp = auth_client.patch("/api/posts/99999", json={"title": "x"})
    assert resp.status_code == 404


def test_edit_empty_title_rejected(auth_client, user, make_post):
    post = make_post(user)
    resp = auth_client.patch(f"/api/posts/{post.id}", json={"title": "   "})
    assert resp.status_code == 400


def test_edit_empty_body_rejected(auth_client, user, make_post):
    post = make_post(user)
    resp = auth_client.patch(f"/api/posts/{post.id}", json={"body": "<p></p>"})
    assert resp.status_code == 400


def test_edit_resanitises_body(auth_client, user, make_post):
    """Editing re-runs sanitisation, so injected markup can't sneak in."""
    post = make_post(user)
    resp = auth_client.patch(f"/api/posts/{post.id}", json={
        "body": "<p>clean</p><script>alert(1)</script>",
    })
    assert resp.status_code == 200
    assert "<script" not in resp.get_json()["body"]
