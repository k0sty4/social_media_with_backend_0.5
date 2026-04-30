"""Flask JSON API for Profile Explorer.

Data flow
---------
The external JSONPlaceholder API is used **only at seed time** to import
realistic profile details into our local SQLite database. After that the
API is fully self-contained:

    JSONPlaceholder --(seed once per run, +10 users)--> data.db --> JSON API --> React

The React frontend (in ``frontend/``) consumes the JSON endpoints below.
The legacy Jinja frontend lives in ``старый_фронт/`` as an archive.
"""

import os
import random

from flask import Flask, jsonify, request
from flask_cors import CORS
import requests
from sqlalchemy import func

from models import db, User, Post
from content import random_title, random_body


# ---------------------------------------------------------------------------
# Flask app + SQLAlchemy + CORS
# ---------------------------------------------------------------------------

app = Flask(__name__)
CORS(app)

DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")
app.config["SQLALCHEMY_DATABASE_URI"] = f"sqlite:///{DB_PATH}"
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False
db.init_app(app)


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

    for _ in range(count):
        src = random.choice(api_users)
        user = User(
            name=src.get("name", ""),
            email=src.get("email", ""),
            username=src.get("username"),
            phone=src.get("phone"),
            website=src.get("website"),
            company=(src.get("company") or {}).get("name"),
            bio=random.choice(RANDOM_BIOS),
        )
        for _ in range(random.randint(3, 6)):
            user.posts.append(Post(item=random_title(), body=random_body()))
        db.session.add(user)

    db.session.commit()
    print(f"Seeded {count} new users into the database.")


# ---------------------------------------------------------------------------
# JSON API
# ---------------------------------------------------------------------------

@app.route("/", methods=["GET"])
def api_root():
    """Landing endpoint listing available resources."""
    return jsonify({
        "name": "Profile Explorer API",
        "endpoints": [
            "GET /api/posts?page=N&per_page=10",
            "GET /api/users",
            "GET /api/user/<id>",
            "GET /api/users/<id>/posts?page=N&per_page=10",
            "GET /api/random-user",
            "GET /api/search?q=<query>",
        ],
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
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_db_with_new_users(10)
    app.run(debug=True, port=5001, use_reloader=False)
