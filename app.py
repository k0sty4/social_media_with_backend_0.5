"""Flask JSON API for Profile Explorer.

JSONPlaceholder is hit only at seed time to populate the local SQLite DB;
after that all reads/writes are local.
"""

import hashlib
import os
import random
import secrets
import time
from collections import deque
from datetime import datetime, timedelta
from threading import Lock

from flask import Flask, jsonify, request, make_response
from flask_cors import CORS
import requests
from sqlalchemy import func

from models import db, User, Post, Session
from content import random_title, random_body


def _hash_token(raw: str) -> str:
    # sha256 is enough — the token already has 256 bits of entropy, so we don't
    # need slow hashing here. Storing the hash means a DB leak doesn't hand the
    # attacker active sessions.
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
    return request.remote_addr or "unknown"


def _prune(q: deque, window: int) -> None:
    cutoff = time.time() - window
    while q and q[0] < cutoff:
        q.popleft()


def _login_rate_check(email: str):
    """Return an error message if the caller is over the limit, else None."""
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
    with _login_lock:
        now = time.time()
        _login_failures.setdefault(("ip", _client_ip()), deque()).append(now)
        _login_failures.setdefault(("email", email), deque()).append(now)


def _login_reset(email: str) -> None:
    # Only reset the per-email counter on success. Leaving the per-IP counter
    # alone stops "guess until success once, then resume" attacks.
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


SESSION_COOKIE = "session_id"
SESSION_TTL = timedelta(days=7)
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"


def _set_session_cookie(response, token: str):
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
    response.delete_cookie(SESSION_COOKIE, path="/")


def current_user():
    raw = request.cookies.get(SESSION_COOKIE)
    if not raw:
        return None
    session = db.session.get(Session, _hash_token(raw))
    if session is None:
        return None
    if session.is_expired():
        # Lazy GC: nuke the expired row on the spot so the table doesn't grow forever.
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
    # Reject mutating requests whose Origin doesn't match the configured
    # frontend. Browsers always set Origin on POST/PATCH/PUT/DELETE, so this
    # blocks classic CSRF (a malicious site can't forge the Origin header).
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
    try:
        response = requests.get(USERS_API, timeout=5)
        response.raise_for_status()
        return response.json()
    except requests.RequestException as e:
        print(f"Error fetching seed users: {e}")
        return []


def seed_db_with_new_users(count=10):
    """Append ``count`` new members (plus 3-6 posts each) to the local DB."""
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
            user.posts.append(Post(item=random_title(), body=random_body()))
        db.session.add(user)
        added += 1

    db.session.commit()
    print(f"Seeded {added} new users into the database.")


# ---------------------------------------------------------------------------
# JSON API
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET"])
def api_root():
    return jsonify({
        "name": "Profile Explorer API",
        "endpoints": {
            "public": [
                "GET  /api/posts?page=N&per_page=10",
                "GET  /api/users",
                "GET  /api/user/<id>",
                "GET  /api/users/<id>/posts?page=N&per_page=10",
                "GET  /api/random-user",
                "GET  /api/search?q=<query>",
            ],
            "auth": [
                "POST /api/auth/register",
                "POST /api/auth/login",
                "POST /api/auth/logout",
                "POST /api/auth/change-password",
            ],
            "authed": [
                "PATCH /api/user/<id>   (only your own)",
                "PATCH /api/posts/<id>  (only your own)",
            ],
        },
    })


@app.route("/api/posts", methods=["GET"])
def api_posts():
    """Paginated feed of posts with author email — consumed by React Feed."""
    try:
        page = max(1, int(request.args.get("page", 1)))
    except ValueError:
        page = 1
    try:
        per_page = max(1, min(100, int(request.args.get("per_page", PAGE_SIZE))))
    except ValueError:
        per_page = PAGE_SIZE

    pagination = db.paginate(
        db.select(Post).order_by(Post.id.desc()),
        page=page, per_page=per_page, error_out=False,
    )

    items = []
    for p in pagination.items:
        author = p.author
        items.append({
            "id": p.id,
            "title": p.item,
            "body": p.body,
            "user_id": p.user_id,
            "user_name": author.name if author else None,
            "email": author.email if author else None,
            "avatar": author.avatar_url() if author else None,
        })

    return jsonify({
        "items": items,
        "page": pagination.page,
        "per_page": per_page,
        "total": pagination.total,
        "has_more": pagination.has_next,
    })


@app.route("/api/users/<int:user_id>/posts", methods=["GET"])
def api_user_posts(user_id):
    """Paginated posts by a single user — consumed by the user-detail page."""
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

    items = [{
        "id": p.id,
        "title": p.item,
        "body": p.body,
        "user_id": p.user_id,
        "user_name": user.name,
        "email": user.email,
        "avatar": user.avatar_url(),
    } for p in pagination.items]

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
    users = db.session.scalars(db.select(User).order_by(User.id)).all()
    return jsonify([u.to_public_dict(include_posts=True) for u in users])


@app.route("/api/random-user", methods=["GET"])
def random_user_endpoint():
    user = db.session.scalar(db.select(User).order_by(func.random()).limit(1))
    if user is None:
        return jsonify({"error": "No users in the database yet"}), 404
    return jsonify(user.to_public_dict(include_posts=True))


@app.route("/api/user/<int:user_id>", methods=["GET"])
def get_user(user_id):
    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"error": "User not found"}), 404
    return jsonify(user.to_public_dict(include_posts=True))


@app.route("/api/search", methods=["GET"])
def search_users():
    query = request.args.get("q", "").strip()
    if not query:
        return jsonify([])

    pattern = f"%{query.lower()}%"
    stmt = db.select(User).where(
        db.or_(
            db.func.lower(User.name).like(pattern),
            db.func.lower(User.email).like(pattern),
        )
    ).order_by(User.id)
    users = db.session.scalars(stmt).all()

    return jsonify([
        {"id": u.id, "name": u.name, "email": u.email, "avatar": u.avatar_url()}
        for u in users
    ])


# ---------------------------------------------------------------------------
# Auth endpoints
# ---------------------------------------------------------------------------

@app.route("/api/auth/register", methods=["POST"])
def register():
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

@app.route("/api/posts/<int:post_id>", methods=["PATCH"])
def update_post(post_id):
    user = current_user()
    if user is None:
        return jsonify({"error": "authentication required"}), 401

    post = db.session.get(Post, post_id)
    # 404 covers both "missing" and "not yours" — we don't leak existence
    # of someone else's post to a logged-in stranger.
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
        body = body.strip()
        if not body:
            return jsonify({"error": "body cannot be empty"}), 400
        post.body = body
    if title is None and body is None:
        return jsonify({"error": "nothing to update"}), 400

    db.session.commit()
    return jsonify({
        "id": post.id,
        "user_id": post.user_id,
        "title": post.item,
        "body": post.body,
    })


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def ensure_auth_columns():
    # create_all() doesn't alter existing tables, so a pre-existing data.db
    # won't have password_hash / avatar_seed. Add them in place.
    from sqlalchemy import inspect, text

    inspector = inspect(db.engine)
    if "users" in inspector.get_table_names():
        columns = {c["name"] for c in inspector.get_columns("users")}
        with db.engine.begin() as conn:
            if "password_hash" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN password_hash VARCHAR"))
            if "avatar_seed" not in columns:
                conn.execute(text("ALTER TABLE users ADD COLUMN avatar_seed VARCHAR"))

    # Switch from plaintext session tokens to sha256-of-token. Any row whose
    # token isn't 64-char hex is from before the switch — wipe those so old
    # sessions don't bypass the new lookup. Users just have to log in again.
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
