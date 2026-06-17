"""Users blueprint: directory, single profile, profile editing, search,
random user, and follow / unfollow.
"""

from flask import Blueprint, jsonify, request
from sqlalchemy import func

from models import db, User, Follow
from auth import current_user

users_bp = Blueprint("users", __name__)

PROFILE_EDITABLE = ("name", "bio", "phone", "website", "company", "avatar_seed")


@users_bp.route("/api/users", methods=["GET"])
def api_users():
    """Return every user in the local DB with profile + post preview."""
    viewer = current_user()
    viewer_id = viewer.id if viewer else None
    users = db.session.scalars(db.select(User).order_by(User.id)).all()
    return jsonify([
        u.to_public_dict(include_posts=True, viewer_id=viewer_id) for u in users
    ])


@users_bp.route("/api/random-user", methods=["GET"])
def random_user_endpoint():
    """Return a single random user. 404 if the DB is empty."""
    user = db.session.scalar(db.select(User).order_by(func.random()).limit(1))
    if user is None:
        return jsonify({"error": "No users in the database yet"}), 404
    viewer = current_user()
    return jsonify(user.to_public_dict(
        include_posts=True, viewer_id=viewer.id if viewer else None,
    ))


@users_bp.route("/api/user/<int:user_id>", methods=["GET"])
def get_user(user_id):
    """Return one user by id with profile fields and a small post preview."""
    user = db.session.get(User, user_id)
    if user is None:
        return jsonify({"error": "User not found"}), 404
    viewer = current_user()
    return jsonify(user.to_public_dict(
        include_posts=True, viewer_id=viewer.id if viewer else None,
    ))


@users_bp.route("/api/search", methods=["GET"])
def search_users():
    """Case-insensitive substring search across user name, username and email."""
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


@users_bp.route("/api/user/<int:user_id>", methods=["PATCH"])
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


@users_bp.route("/api/users/<int:user_id>/follow", methods=["POST", "DELETE"])
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
