"""Authentication blueprint + shared auth helpers.

Routes: register, login, logout, change-password.
Also exports ``current_user`` (used by every other blueprint to identify the
caller) plus the session-cookie helpers, the token hasher, and the in-memory
login rate limiter.
"""

import hashlib
import secrets
import time
from collections import deque
from datetime import datetime
from threading import Lock

from flask import Blueprint, jsonify, request, make_response

from models import db, User, Session
from config import SESSION_COOKIE, SESSION_TTL, COOKIE_SECURE

auth_bp = Blueprint("auth", __name__)


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


# --- Session cookie helpers ------------------------------------------------

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


# --- Routes ----------------------------------------------------------------

@auth_bp.route("/api/auth/register", methods=["POST"])
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


@auth_bp.route("/api/auth/login", methods=["POST"])
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


@auth_bp.route("/api/auth/change-password", methods=["POST"])
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


@auth_bp.route("/api/auth/logout", methods=["POST"])
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
