"""SQLAlchemy models for the Profile Explorer app.

Each class below maps to one SQL table. SQLAlchemy reads these class
definitions and generates the SQL `CREATE TABLE` statements, as well as
the SELECT / INSERT / UPDATE / DELETE that runs when we touch the
objects — so there is no hand-written SQL in the rest of the codebase.
"""

from flask_sqlalchemy import SQLAlchemy

# Shared SQLAlchemy handle. `app.py` binds it with `db.init_app(app)`.
db = SQLAlchemy()


class User(db.Model):
    """A member stored in the local database.

    Extra profile fields (username, phone, website, company, bio) are
    seeded from JSONPlaceholder on startup so the UI can render full
    profile cards without ever hitting the external API at request time.
    """

    __tablename__ = "users"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    name = db.Column(db.String, nullable=False)
    email = db.Column(db.String, nullable=False)
    # Everything below is optional — seeded when available, otherwise NULL.
    username = db.Column(db.String)
    phone = db.Column(db.String)
    website = db.Column(db.String)
    company = db.Column(db.String)
    bio = db.Column(db.String)

    posts = db.relationship(
        "Post",
        backref="author",
        cascade="all, delete-orphan",
        order_by="Post.id.desc()",
    )

    def avatar_url(self):
        """Deterministic DiceBear URL based on the local id."""
        return f"https://api.dicebear.com/7.x/avataaars/svg?seed=user{self.id}"

    def to_public_dict(self, include_posts=False):
        """Full JSON shape used by `/api/*` endpoints and profile card."""
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
        }
        if include_posts:
            # `.posts` is ordered newest-first via the relationship.
            data["posts"] = [p.to_api_dict() for p in self.posts[:5]]
            data["postCount"] = len(self.posts)
        return data

    def to_dict(self):
        """Short shape used by the members directory template."""
        return {"id": self.id, "name": self.name, "email": self.email}


class Post(db.Model):
    """A post authored by a single User. `item` stores the title."""

    __tablename__ = "posts"

    id = db.Column(db.Integer, primary_key=True, autoincrement=True)
    user_id = db.Column(
        db.Integer, db.ForeignKey("users.id"), nullable=False, index=True
    )
    item = db.Column(db.String, nullable=False)
    body = db.Column(db.Text, nullable=False)

    def to_dict(self):
        """Shape used by feed templates (includes author name for display)."""
        return {
            "id": self.id,
            "user_id": self.user_id,
            "item": self.item,
            "body": self.body,
            "user_name": self.author.name if self.author else None,
        }

    def to_api_dict(self):
        """Shape used by legacy `/api/*` responses (matches JSONPlaceholder).

        Kept compatible with the old JSONPlaceholder format so the
        existing frontend (`static/script.js`) works without changes.
        """
        return {
            "userId": self.user_id,
            "id": self.id,
            "title": self.item,
            "body": self.body,
        }
