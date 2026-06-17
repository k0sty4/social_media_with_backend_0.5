"""Database seeding + one-time SQLite migrations.

The only place that talks to the external JSONPlaceholder API — and only at
startup, to populate the local DB with sample users. After that everything is
local. ``ensure_auth_columns`` patches an older data.db with columns added later.
"""

import random
from datetime import datetime, timedelta

import requests

from models import db, User, Post
from content import random_title, random_body

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
