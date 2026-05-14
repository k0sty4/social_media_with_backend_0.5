"""SQLAlchemy models for the Profile Explorer app.

Three tables:
  * ``users``    — accounts (seed users have no password_hash and cannot log in)
  * ``posts``    — short text posts authored by a user
  * ``sessions`` — server-side sessions; the cookie carries the raw token,
                   only its sha256 is stored here.
"""

from datetime import datetime

from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash

# Shared instance — ``app.py`` calls ``db.init_app(app)`` to bind it.
db = SQLAlchemy()


class User(db.Model):
    """Application user. Combines seed profile data with auth credentials."""

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String, nullable=False)
    email = db.Column(db.String, nullable=False, unique=True, index=True)
    # NULL for seed users that never registered through the auth flow.
    password_hash = db.Column(db.String)
    username = db.Column(db.String)
    phone = db.Column(db.String)
    website = db.Column(db.String)
    company = db.Column(db.String)
    bio = db.Column(db.String)
    # Free-form string used as the DiceBear seed to pick an avatar. NULL
    # falls back to ``user<id>`` so seed users still get a stable picture.
    avatar_seed = db.Column(db.String)

    posts = db.relationship(
        "Post",
        backref="author",
        cascade="all, delete-orphan",
        order_by="Post.id.desc()",
    )
    sessions = db.relationship(
        "Session",
        backref="user",
        cascade="all, delete-orphan",
    )

    def set_password(self, password: str) -> None:
        """Hash and store ``password``. werkzeug picks scrypt with a random
        per-user salt by default; both end up inside ``password_hash``."""
        self.password_hash = generate_password_hash(password)

    def check_password(self, password: str) -> bool:
        """Return True iff ``password`` matches this user's stored hash.

        Returns False (without raising) if the user has no hash at all —
        seed users imported from JSONPlaceholder can never log in.
        """
        if not self.password_hash:
            return False
        return check_password_hash(self.password_hash, password)

    def avatar_url(self):
        """Build the DiceBear avatar URL for this user."""
        seed = self.avatar_seed or f"user{self.id}"
        return f"https://api.dicebear.com/7.x/avataaars/svg?seed={seed}"

    def to_public_dict(self, include_posts=False):
        """Serialise the user for the API. Never includes ``password_hash``."""
        data = {
            "id": self.id,
            "name": self.name,
            "username": self.username or "",
            "email": self.email,
            "phone": self.phone or "",
            "website": self.website or "",
            "company": self.company or "",
            "bio": self.bio or "",
            "avatar": self.avatar_url(),
            "avatar_seed": self.avatar_seed or "",
        }
        if include_posts:
            data["posts"] = [p.to_api_dict() for p in self.posts[:5]]
            data["postCount"] = len(self.posts)
        return data

    def to_dict(self):
        """Compact shape used in directory listings (name + email + id)."""
        return {"id": self.id, "name": self.name, "email": self.email}


class Post(db.Model):
    """A single short post. ``item`` is the title; ``body`` is the content."""

    __tablename__ = "posts"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    item = db.Column(db.String, nullable=False)
    body = db.Column(db.Text, nullable=False)

    def to_dict(self):
        """Shape used in admin/debug responses (includes author display name)."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "item": self.item,
            "body": self.body,
            "user_name": self.author.name if self.author else None,
        }

    def to_api_dict(self):
        """JSONPlaceholder-compatible shape used inside ``to_public_dict``."""
        return {
            "userId": self.user_id,
            "id": self.id,
            "title": self.item,
            "body": self.body,
        }


class Session(db.Model):
    """Server-side session. Primary key is ``sha256(raw_cookie_token)``."""

    __tablename__ = "sessions"

    token = db.Column(db.String, primary_key=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    expires_at = db.Column(db.DateTime, nullable=False)

    def is_expired(self) -> bool:
        """True if this session is past its expiry timestamp (UTC)."""
        return datetime.utcnow() >= self.expires_at
