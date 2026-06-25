"""Flask JSON API for Profile Explorer — application entry point.

This file only wires the app together: it creates the Flask app, configures the
database and CORS, installs the CSRF guard, and registers the three feature
blueprints (auth / posts / users). The actual endpoints live in those modules.

  auth.py   — register, login, logout, change-password (+ current_user, sessions)
  posts.py  — feed, create/edit posts, image serving
  users.py  — profiles, search, follow/unfollow
  seed.py   — startup seeding + one-time SQLite migrations
"""

import os

from flask import Flask, jsonify, request
from flask_cors import CORS

from models import db
from config import FRONTEND_ORIGIN, DATABASE_URI, UPLOAD_DIR, MAX_CONTENT_LENGTH
# _hash_token and _login_failures are re-exported here so the test suite can
# keep importing them from `app` after the split into blueprints.
from auth import auth_bp, _hash_token, _login_failures  # noqa: F401
from posts import posts_bp
from users import users_bp
from seed import ensure_auth_columns, seed_db_with_new_users

# ---------------------------------------------------------------------------
# Flask app + SQLAlchemy + CORS
# ---------------------------------------------------------------------------

app = Flask(__name__)

CORS(app, supports_credentials=True, origins=[FRONTEND_ORIGIN])

app.config["SQLALCHEMY_DATABASE_URI"] = DATABASE_URI
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
app.config["MAX_CONTENT_LENGTH"] = MAX_CONTENT_LENGTH
os.makedirs(UPLOAD_DIR, exist_ok=True)
db.init_app(app)


# ---------------------------------------------------------------------------
# CSRF protection (applies to every mutating request)
# ---------------------------------------------------------------------------

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
# Root + blueprints
# ---------------------------------------------------------------------------

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


app.register_blueprint(auth_bp)
app.register_blueprint(posts_bp)
app.register_blueprint(users_bp)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        ensure_auth_columns()
        seed_db_with_new_users(10)
    app.run(debug=True, port=5001, use_reloader=False)
