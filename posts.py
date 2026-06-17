"""Posts blueprint: the feed, a user's posts, image serving, and create/edit.

The feed supports two scopes (global / following) and pagination; bodies are
sanitised on write; images are saved to disk under UPLOAD_DIR with random names.
"""

import os
import uuid

from flask import Blueprint, jsonify, request, send_from_directory
from werkzeug.utils import secure_filename

from models import db, User, Post, Follow
from sanitize import sanitize_html, strip_tags
from auth import current_user
from config import UPLOAD_DIR, ALLOWED_IMAGE_EXT, PAGE_SIZE

posts_bp = Blueprint("posts", __name__)


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


@posts_bp.route("/api/posts", methods=["GET"])
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


@posts_bp.route("/api/users/<int:user_id>/posts", methods=["GET"])
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


@posts_bp.route("/api/uploads/<path:filename>", methods=["GET"])
def serve_upload(filename):
    """Serve an uploaded post image. ``send_from_directory`` confines the
    lookup to ``UPLOAD_DIR``, so a crafted ``filename`` can't escape it."""
    return send_from_directory(UPLOAD_DIR, filename)


@posts_bp.route("/api/posts", methods=["POST"])
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


@posts_bp.route("/api/posts/<int:post_id>", methods=["PATCH"])
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
