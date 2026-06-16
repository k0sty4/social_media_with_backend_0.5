"""Flask JSON API for Profile Explorer.

JSONPlaceholder is hit only at seed time to populate the local SQLite DB;
after that all reads/writes are local.
"""

import hashlib
import os
import random
import secrets
import time
import uuid
from collections import deque
from datetime import datetime, timedelta
from threading import Lock

from flask import Flask, jsonify, request, make_response, send_from_directory
from flask_cors import CORS
import requests
from sqlalchemy import func
from werkzeug.utils import secure_filename

from models import db, User, Post, Follow, Session
from sanitize import sanitize_html, strip_tags
from content import random_title, random_body


def _hash_token(raw: str) -> str:
    """Return the sha256 hex digest of a session token.

    The cookie carries the raw 256-bit token; only this hash is persisted in
    the ``sessions`` table. A database leak therefore does not expose any
    live sessions — sha256 isn't reversible. We don't need a slow hash (like
    scrypt) here because the input already has 256 bits of entropy.
    """
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


# --- Login rate limiter ----------------------------------------------------
# Two independent windows so an attacker can't pivot around either limit:
#   - per-IP: blocks scripted brute force from one host
#   - per-email: blocks targeted guessing against a single account
# Stored in-memory. For a single-process Flask app this is fine; behind multiple
# workers you'd swap this for Redis.

LOGIN_IP_WINDOW = 60          # seconds
LOGIN_IP_MAX_FAILS = 10
LOGIN_EMAIL_WINDOW = 15 * 60
LOGIN_EMAIL_MAX_FAILS = 5

_login_failures = {}          # key -> deque[timestamp]
_login_lock = Lock()


def _client_ip() -> str:
    """Best-effort caller IP from the request. Behind a proxy this would also
    need to honor X-Forwarded-For, which is intentionally NOT trusted here."""
    return request.remote_addr or "unknown"


def _prune(q: deque, window: int) -> None:
    """Drop timestamps older than ``window`` seconds from ``q`` (in place)."""
    cutoff = time.time() - window
    while q and q[0] < cutoff:
        q.popleft()


def _login_rate_check(email: str):
    """Return an error message if the caller is over the login rate limit.

    Returns ``None`` when the attempt may proceed. The check is performed
    under a single mutex so the per-IP and per-email windows stay consistent.
    """
    with _login_lock:
        ip_q = _login_failures.get(("ip", _client_ip()))
        em_q = _login_failures.get(("email", email))
        if ip_q is not None:
            _prune(ip_q, LOGIN_IP_WINDOW)
            if len(ip_q) >= LOGIN_IP_MAX_FAILS:
                return "too many login attempts — try again later"
        if em_q is not None:
            _prune(em_q, LOGIN_EMAIL_WINDOW)
            if len(em_q) >= LOGIN_EMAIL_MAX_FAILS:
                return "too many login attempts — try again later"
        return None


def _login_record_failure(email: str) -> None:
    """Append the current timestamp to both the per-IP and per-email queues."""
    with _login_lock:
        now = time.time()
        _login_failures.setdefault(("ip", _client_ip()), deque()).append(now)
        _login_failures.setdefault(("email", email), deque()).append(now)


def _login_reset(email: str) -> None:
    """Clear the per-email failure history after a successful login.

    The per-IP counter is intentionally NOT reset — otherwise an attacker
    could "punch through" the IP limit by occasionally landing one valid
    credential and resuming guesses.
    """
    with _login_lock:
        _login_failures.pop(("email", email), None)


# ---------------------------------------------------------------------------
# Flask app + SQLAlchemy + CORS
# ---------------------------------------------------------------------------

app = Flask(__name__)

FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173")
CORS(app, supports_credentials=True, origins=[FRONTEND_ORIGIN])

DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)

# Uploaded post images live here. Kept out of the DB (we store only the
# filename) and served back via GET /api/uploads/<name>.
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
os.makedirs(UPLOAD_DIR, exist_ok=True)
ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "gif", "webp"}
# Reject anything bigger than 5 MB before it ever reaches a handler.
app.config["MAX_CONTENT_LENGTH"] = 5 * 1024 * 1024


SESSION_COOKIE = "session_id"
SESSION_TTL = timedelta(days=7)
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"


def _set_session_cookie(response, token: str):
    """Attach the session cookie to ``response`` with safe defaults.

    The cookie is HttpOnly (no JS access), SameSite=Lax (mitigates CSRF on
    top-level cross-site requests), and gets the Secure flag only when
    ``COOKIE_SECURE=1`` is set in the environment (i.e. behind HTTPS).
    """
    response.set_cookie(
        SESSION_COOKIE,
        token,
        max_age=int(SESSION_TTL.total_seconds()),
        httponly=True,
        secure=COOKIE_SECURE,
        samesite="Lax",
        path="/",
    )


def _clear_session_cookie(response):
    """Tell the browser to drop the session cookie (used on logout)."""
    response.delete_cookie(SESSION_COOKIE, path="/")


def current_user():
    """Return the ``User`` whose session cookie was sent, or ``None``.

    The cookie value is hashed with sha256 before lookup, so the row stored
    in ``sessions`` never matches the raw cookie. Expired rows are deleted
    on first touch (lazy GC), keeping the table from growing forever.
    """
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        return None
    session = db.session.get(Session, _hash_token(raw))
    if session is None:
        return None
    if session.is_expired():
        db.session.delete(session)
        db.session.commit()
        return None
    return session.user


# Login and register can't rely on an existing session to identify the caller,
# so they don't need CSRF protection — there's no privileged state to abuse.
# Everything else (logout, password change, profile/post edits) stays guarded.
CSRF_EXEMPT_PATHS = frozenset({"/api/auth/login", "/api/auth/register"})


@app.before_request
def csrf_guard():
    """CSRF protection for every mutating request.

    Browsers always attach the ``Origin`` header on POST/PATCH/PUT/DELETE
    requests, and a script on a third-party site cannot forge it. We compare
    the incoming Origin to ``FRONTEND_ORIGIN``; mismatch -> 403.
    """
    if request.method not in ("POST", "PATCH", "PUT", "DELETE"):
        return None
    if request.path in CSRF_EXEMPT_PATHS:
        return None
    origin = request.headers.get("Origin")
    if origin != FRONTEND_ORIGIN:
        return jsonify({"error": "invalid origin"}), 403
    return None


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

USERS_API = "https://jsonplaceholder.typicode.com/users"

RANDOM_BIOS = [
    "Loves solving real-world problems with clean and simple ideas.",
    "Enjoys building small projects that make daily tasks easier.",
    "Always curious about design, code quality, and user experience.",
    "Turns coffee into code and ideas into practical features.",
    "Focused on learning, experimenting, and improving every day.",
    "Prefers elegant solutions over complicated workflows.",
    "Passionate about technology, collaboration, and meaningful products.",
    "Finds joy in details, testing, and polishing final results.",
]

PAGE_SIZE = 10


# ---------------------------------------------------------------------------
# Seeding (the only place that talks to the external API)
# ---------------------------------------------------------------------------

def fetch_api_users():
    """Fetch the JSONPlaceholder users list. Returns ``[]`` on any error."""
    try:
        response = requests.get(USERS_API, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching seed users: {e}")
        return []


def seed_db_with_new_users(count=10):
    """Append ``count`` new members (each with 3–6 posts) to the local DB.

    Emails already present in ``users`` are skipped, so re-running this is
    safe and incremental. Called once at startup.
    """
    api_users = fetch_api_users()
    if not api_users:
        print("No users fetched from API, skipping seed.")
        return

    seen_emails = set(db.session.scalars(db.select(User.email)).all())
    candidates = list(api_users)
    random.shuffle(candidates)

    added = 0
    for src in candidates:
        if added >= count:
            break
        email = (src.get("email") or "").strip().lower()
        if not email or email in seen_emails:
            continue
        seen_emails.add(email)

        user = User(
            name=src.get("name", ""),
            email=email,
            username=src.get("username"),
            phone=src.get("phone"),
            website=src.get("website"),
            company=(src.get("company") or {}).get("name"),
            bio=random.choice(RANDOM_BIOS),
        )
        for _ in range(random.randint(3, 6)):
            # Stagger creation times over the last ~30 days so the feed's
            # "time ago" labels look natural rather than all "just now".
            age = timedelta(minutes=random.randint(5, 60 * 24 * 30))
            user.posts.append(Post(
                item=random_title(),
                body=random_body(),
                created_at=datetime.utcnow() - age,
            ))
        db.session.add(user)
        added += 1

    db.session.commit()
    print(f"Seeded {added} new users into the database.")


# ---------------------------------------------------------------------------
# JSON API
# ---------------------------------------------------------------------------

def _image_url(filename):
    """Absolute URL for an uploaded image filename, or ``None`` if unset."""
    if not filename:
        return None
    return f"{request.host_url}api/uploads/{filename}"


def _post_payload(post, author):
    """The single post shape every read endpoint returns to the frontend."""
    return {
        "id": post.id,
        "title": post.item,
        "body": post.body,
        "image": _image_url(post.image),
        "created_at": post.created_iso(),
        "user_id": post.user_id,
        "user_name": author.name if author else None,
        "email": author.email if author else None,
        "avatar": author.avatar_url() if author else None,
    }


@app.route("/", methods=["GET"])
def api_root():
    """Landing endpoint: returns the catalog of available routes."""
    return jsonify({
        "name": "Profile Explorer API",
        "endpoints": {
            "public": [
                "GET  /api/posts?page=N&per_page=10&scope=all|following",
                "GET  /api/users",
                "GET  /api/user/<id>",
                "GET  /api/users/<id>/posts?page=N&per_page=10",
                "GET  /api/random-user",
                "GET  /api/search?q=<query>",
                "GET  /api/uploads/<filename>",
            ],
            "auth": [
                "POST /api/auth/register",
                "POST /api/auth/login",
                "POST /api/auth/logout",
                "POST /api/auth/change-password",
            ],
            "authed": [
                "POST   /api/posts            (create — multipart, text + image)",
                "PATCH  /api/user/<id>        (only your own)",
                "PATCH  /api/posts/<id>       (only your own)",
                "POST   /api/users/<id>/follow",
                "DELETE /api/users/<id>/follow",
            ],
        },
    })


@app.route("/api/posts", methods=["GET"])
def api_posts():
    """Paginated feed of posts. ``scope`` selects which posts:

      * ``all`` (default) — the global feed, every user's posts
      * ``following``     — only posts by users the caller follows
        (requires a session; 401 otherwise)
    """
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1
    try:
        per_page = max(1, min(100, int(request.args.get("per_page", PAGE_SIZE))))
    except ValueError:
        per_page = PAGE_SIZE

    scope = request.args.get("scope", "all")
    stmt = db.select(Post).order_by(Post.id.desc())

    if scope == "following":
        viewer = current_user()
        if viewer is None:
            return jsonify({"error": "authentication required"}), 401
        followee_ids = db.select(Follow.followee_id).where(
            Follow.follower_id == viewer.id
        )
        stmt = (
            db.select(Post)
            .where(Post.user_id.in_(followee_ids))
            .order_by(Post.id.desc())
        )

    pagination = db.paginate(stmt, page=page, per_page=per_page, error_out=False)
    items = [_post_payload(p, p.author) for p in pagination.items]

    return jsonify({
        "items": items,
        "page": pagination.page,
        "per_page": per_page,
        "total": pagination.total,
        "has_more": pagination.has_next,
    })


@app.route("/api/users/<int:user_id>/posts", methods=["GET"])
def api_user_posts(user_id):
    """Paginated posts authored by a single user.

    Returns 404 if the user doesn't exist (no auth involved here — this is
    a public read endpoint).
    """
    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"error": "User not found"}), 404

    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1
    try:
        per_page = max(1, min(100, int(request.args.get("per_page", PAGE_SIZE))))
    except ValueError:
        per_page = PAGE_SIZE

    pagination = db.paginate(
        db.select(Post).where(Post.user_id == user_id).order_by(Post.id.desc()),
        page=page, per_page=per_page, error_out=False,
    )

    items = [_post_payload(p, user) for p in pagination.items]

    return jsonify({
        "items": items,
        "page": pagination.page,
        "per_page": per_page,
        "total": pagination.total,
        "has_more": pagination.has_next,
    })


@app.route("/api/users", methods=["GET"])
def api_users():
    """Return every user in the local DB with profile + post preview."""
    viewer = current_user()
    viewer_id = viewer.id if viewer else None
    users = db.session.scalars(db.select(User).order_by(User.id)).all()
    return jsonify([
        u.to_public_dict(include_posts=True, viewer_id=viewer_id) for u in users
    ])


@app.route("/api/random-user", methods=["GET"])
def random_user_endpoint():
    """Return a single random user. 404 if the DB is empty."""
    user = db.session.scalar(db.select(User).order_by(func.random()).limit(1))
    if user is None:
        return jsonify({"error": "No users in the database yet"}), 404
    viewer = current_user()
    return jsonify(user.to_public_dict(
        include_posts=True, viewer_id=viewer.id if viewer else None,
    ))


@app.route("/api/user/<int:user_id>", methods=["GET"])
def get_user(user_id):
    """Return one user by id with profile fields and a small post preview."""
    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"error": "User not found"}), 404
    viewer = current_user()
    return jsonify(user.to_public_dict(
        include_posts=True, viewer_id=viewer.id if viewer else None,
    ))


@app.route("/api/search", methods=["GET"])
def search_users():
    """Case-insensitive substring search across user name and email."""
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])

    pattern = f"%{query.lower()}%"
    stmt = db.select(User).where(
        db.or_(
            db.func.lower(User.name).like(pattern),
            db.func.lower(User.username).like(pattern),
            db.func.lower(User.email).like(pattern),
        )
    ).order_by(User.id)
    users = db.session.scalars(stmt).all()

    return jsonify([
        {"id": u.id, "name": u.name, "email": u.email, "avatar": u.avatar_url()}
        for u in users
    ])


@app.route("/api/uploads/<path:filename>", methods=["GET"])
def serve_upload(filename):
    """Serve an uploaded post image. ``send_from_directory`` confines the
    lookup to ``UPLOAD_DIR``, so a crafted ``filename`` can't escape it."""
    return send_from_directory(UPLOAD_DIR, filename)


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@app.route("/api/auth/register", methods=["POST"])
def register():
    """Create a new user and immediately sign them in.

    Body: ``{name, email, password}``. Responses:
      * 201 — created; session cookie set
      * 400 — missing field or password shorter than 8 chars
      * 409 — email already registered
    """
    data = request.get_json(silent=True) or {}
    name = (data.get("name") or "").strip()
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not name or not email or not password:
        return jsonify({"error": "name, email and password are required"}), 400
    if len(password) < 8:
        return jsonify({"error": "password must be at least 8 characters"}), 400

    existing = db.session.scalar(db.select(User).where(User.email == email))
    if existing is not None:
        return jsonify({"error": "email already registered"}), 409

    user = User(name=name, email=email)
    user.set_password(password)
    db.session.add(user)
    db.session.flush()

    raw_token = secrets.token_urlsafe(32)
    session = Session(
        token=_hash_token(raw_token),
        user_id=user.id,
        expires_at=datetime.utcnow() + SESSION_TTL,
    )
    db.session.add(session)
    db.session.commit()

    response = make_response(jsonify({
        "id": user.id, "name": user.name, "email": user.email,
    }), 201)
    _set_session_cookie(response, raw_token)
    return response


@app.route("/api/auth/login", methods=["POST"])
def login():
    """Verify credentials and start a session.

    Body: ``{email, password}``. Responses:
      * 200 — signed in; session cookie set
      * 400 — missing field
      * 401 — wrong email or password (deliberately the same message for
        both — never leak whether the email exists)
      * 429 — over the rate limit (per-IP or per-email)
    """
    data = request.get_json(silent=True) or {}
    email = (data.get("email") or "").strip().lower()
    password = data.get("password") or ""

    if not email or not password:
        return jsonify({"error": "email and password are required"}), 400

    blocked = _login_rate_check(email)
    if blocked is not None:
        # Bail out BEFORE the scrypt verify so a flood of guesses can't pin a CPU.
        return jsonify({"error": blocked}), 429

    user = db.session.scalar(db.select(User).where(User.email == email))
    if user is None or not user.check_password(password):
        _login_record_failure(email)
        return jsonify({"error": "invalid email or password"}), 401

    _login_reset(email)
    raw_token = secrets.token_urlsafe(32)
    session = Session(
        token=_hash_token(raw_token),
        user_id=user.id,
        expires_at=datetime.utcnow() + SESSION_TTL,
    )
    db.session.add(session)
    db.session.commit()

    response = make_response(jsonify({
        "id": user.id, "name": user.name, "email": user.email,
    }))
    _set_session_cookie(response, raw_token)
    return response


@app.route("/api/auth/change-password", methods=["POST"])
def change_password():
    """Change the signed-in user's password.

    Body: ``{current_password, new_password}``. Responses:
      * 200 — password changed; all OTHER sessions for this user are killed
      * 400 — missing field, new pwd < 8 chars, or new == current
      * 401 — not signed in OR current password is wrong
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "authentication required"}), 401

    data = request.get_json(silent=True) or {}
    current = data.get("current_password") or ""
    new_pwd = data.get("new_password") or ""

    if not current or not new_pwd:
        return jsonify({"error": "current_password and new_password are required"}), 400
    if len(new_pwd) < 8:
        return jsonify({"error": "new password must be at least 8 characters"}), 400
    if not user.check_password(current):
        return jsonify({"error": "current password is incorrect"}), 401
    if user.check_password(new_pwd):
        return jsonify({"error": "new password must differ from the current one"}), 400

    user.set_password(new_pwd)

    # Kill every OTHER session for this user — if the password was guessed and
    # an attacker had a live session, they lose it now. Keep the caller's own
    # session so the page doesn't immediately log itself out.
    raw = request.cookies.get(SESSION_COOKIE)
    keep_hash = _hash_token(raw) if raw else None
    db.session.execute(
        db.delete(Session).where(
            Session.user_id == user.id,
            Session.token != keep_hash,
        )
    )
    db.session.commit()
    return jsonify({"ok": True})


@app.route("/api/auth/logout", methods=["POST"])
def logout():
    """End the current session.

    Deletes the matching ``sessions`` row (if any) and clears the cookie.
    Always returns 200 — the operation is idempotent.
    """
    raw = request.cookies.get(SESSION_COOKIE)
    if raw:
        session = db.session.get(Session, _hash_token(raw))
        if session is not None:
            db.session.delete(session)
            db.session.commit()
    response = make_response(jsonify({"ok": True}))
    _clear_session_cookie(response)
    return response


# ---------------------------------------------------------------------------
# Profile mutations
# ---------------------------------------------------------------------------

PROFILE_EDITABLE = ("name", "bio", "phone", "website", "company", "avatar_seed")


@app.route("/api/user/<int:user_id>", methods=["PATCH"])
def update_user(user_id):
    """Update one's own profile fields.

    Editable: name, bio, phone, website, company, avatar_seed. ``email`` is
    intentionally not editable here (it is the login key) and ``password``
    has its own endpoint. Responses:
      * 200 — updated; the new public profile is returned
      * 400 — empty name or no editable field in body
      * 401 — not signed in
      * 404 — ``user_id`` is not the caller's id (info-hiding authz)
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "authentication required"}), 401
    # Same authz pattern as posts: 404 for "not yours" so we don't reveal
    # whether the other id exists.
    if user.id != user_id:
        return jsonify({"error": "user not found"}), 404

    data = request.get_json(silent=True) or {}
    touched = False
    for field in PROFILE_EDITABLE:
        if field not in data:
            continue
        value = data[field]
        if value is None:
            setattr(user, field, None)
        else:
            value = str(value).strip()
            if field == "name" and not value:
                return jsonify({"error": "name cannot be empty"}), 400
            setattr(user, field, value or None)
        touched = True

    if not touched:
        return jsonify({"error": "nothing to update"}), 400

    db.session.commit()
    return jsonify(user.to_public_dict(include_posts=False))


# ---------------------------------------------------------------------------
# Post mutations
# ---------------------------------------------------------------------------

def _save_image(file_storage):
    """Validate and persist an uploaded image. Returns ``(filename, error)``.

    Only a small set of image extensions is accepted; the stored name is a
    random uuid so a user-supplied filename can never collide or traverse
    paths. ``(None, None)`` means "no file was sent" (images are optional).
    """
    if file_storage is None or not file_storage.filename:
        return None, None
    original = secure_filename(file_storage.filename)
    ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
    if ext not in ALLOWED_IMAGE_EXT:
        return None, "unsupported image type"
    filename = f"{uuid.uuid4().hex}.{ext}"
    file_storage.save(os.path.join(UPLOAD_DIR, filename))
    return filename, None


@app.route("/api/posts", methods=["POST"])
def create_post():
    """Create a new post for the signed-in user.

    Accepts ``multipart/form-data`` (so an image can ride along):
      * ``title`` — plain text, required
      * ``body``  — rich-text HTML, required (sanitised server-side)
      * ``image`` — optional image file (png/jpg/gif/webp, <= 5 MB)

    Responses:
      * 201 — created; the full post payload is returned
      * 400 — missing/empty title or body, or a bad image
      * 401 — not signed in
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "authentication required"}), 401

    title = (request.form.get("title") or "").strip()
    body = sanitize_html(request.form.get("body") or "")

    if not title:
        return jsonify({"error": "title is required"}), 400
    # A body of only markup (e.g. "<p></p>") has no real content.
    if not strip_tags(body):
        return jsonify({"error": "body is required"}), 400

    filename, err = _save_image(request.files.get("image"))
    if err:
        return jsonify({"error": err}), 400

    post = Post(user_id=user.id, item=title, body=body, image=filename)
    db.session.add(post)
    db.session.commit()
    return jsonify(_post_payload(post, user)), 201


@app.route("/api/posts/<int:post_id>", methods=["PATCH"])
def update_post(post_id):
    """Update one of the caller's own posts.

    Editable: title, body (either or both). The body is re-sanitised on every
    write. Responses:
      * 200 — updated; the new post payload is returned
      * 400 — empty title/body or nothing to update
      * 401 — not signed in
      * 404 — post does not exist OR is owned by someone else (same code
        either way, so we never confirm the existence of a foreign post)
    """
    user = current_user()
    if user is None:
        return jsonify({"error": "authentication required"}), 401

    post = db.session.get(Post, post_id)
    if post is None or post.user_id != user.id:
        return jsonify({"error": "post not found"}), 404

    data = request.get_json(silent=True) or {}
    title = data.get("title")
    body = data.get("body")

    if title is not None:
        title = title.strip()
        if not title:
            return jsonify({"error": "title cannot be empty"}), 400
        post.item = title
    if body is not None:
        body = sanitize_html(body)
        if not strip_tags(body):
            return jsonify({"error": "body cannot be empty"}), 400
        post.body = body
    if title is None and body is None:
        return jsonify({"error": "nothing to update"}), 400

    db.session.commit()
    return jsonify(_post_payload(post, user))


# ---------------------------------------------------------------------------
# Follow / unfollow
# ---------------------------------------------------------------------------

@app.route("/api/users/<int:user_id>/follow", methods=["POST", "DELETE"])
def follow_user(user_id):
    """Follow (POST) or unfollow (DELETE) another user.

    Both verbs are idempotent — following twice or unfollowing someone you
    don't follow is a no-op that still returns the current counts. Responses:
      * 200 — ``{followersCount, followingCount, isFollowing}`` for the target
      * 400 — trying to follow yourself
      * 401 — not signed in
      * 404 — target user does not exist
    """
    viewer = current_user()
    if viewer is None:
        return jsonify({"error": "authentication required"}), 401

    target = db.session.get(User, user_id)
    if target is None:
        return jsonify({"error": "user not found"}), 404
    if target.id == viewer.id:
        return jsonify({"error": "you cannot follow yourself"}), 400

    edge = db.session.get(Follow, (viewer.id, target.id))
    if request.method == "POST":
        if edge is None:
            db.session.add(Follow(follower_id=viewer.id, followee_id=target.id))
            db.session.commit()
    else:  # DELETE
        if edge is not None:
            db.session.delete(edge)
            db.session.commit()

    return jsonify({
        "followersCount": target.follower_count(),
        "followingCount": target.following_count(),
        "isFollowing": Follow.exists(viewer.id, target.id),
    })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def ensure_auth_columns():
    """Idempotent in-place migrations for the local SQLite file.

    ``db.create_all()`` only creates missing tables, never alters existing
    ones. So when we add new columns (password_hash, avatar_seed) to
    ``users``, an old data.db needs explicit ``ALTER TABLE`` here.

    We also handle the one-time switch from plaintext session tokens to
    sha256-of-token. If any row in ``sessions`` has a token that isn't a
    64-char hex string, every row is wiped (users simply log in again).
    """
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    if "users" in inspector.get_table_names():
        columns = {c["name"] for c in inspector.get_columns("users")}
        with db.engine.begin() as conn:
            if "password_hash" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR"))
            if "avatar_seed" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN avatar_seed VARCHAR"))

    # posts gained an optional image and a created_at timestamp.
    if "posts" in inspector.get_table_names():
        post_cols = {c["name"] for c in inspector.get_columns("posts")}
        with db.engine.begin() as conn:
            if "image" not in post_cols:
                conn.execute(text("ALTER TABLE posts ADD COLUMN image VARCHAR"))
            if "created_at" not in post_cols:
                # SQLite can't ADD a non-constant default, so add it nullable
                # then backfill legacy rows with a stable, slightly-staggered
                # time (older ids look older) before the model treats it as
                # NOT NULL going forward.
                conn.execute(text("ALTER TABLE posts ADD COLUMN created_at DATETIME"))
                base = datetime.utcnow() - timedelta(days=7)
                rows = conn.execute(text("SELECT id FROM posts ORDER BY id")).fetchall()
                for offset, (pid,) in enumerate(rows):
                    ts = base + timedelta(minutes=offset)
                    conn.execute(
                        text("UPDATE posts SET created_at = :ts WHERE id = :id"),
                        {"ts": ts, "id": pid},
                    )

    if "sessions" in inspector.get_table_names():
        with db.engine.begin() as conn:
            rows = conn.execute(text("SELECT token FROM sessions")).fetchall()
            needs_wipe = any(
                len(r[0] or "") != 64 or any(c not in "0123456789abcdef" for c in (r[0] or ""))
                for r in rows
            )
            if needs_wipe:
                conn.execute(text("DELETE FROM sessions"))


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        ensure_auth_columns()
        seed_db_with_new_users(10)
    app.run(debug=True, port=5001, use_reloader=False)
