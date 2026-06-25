"""Enrichment seeding — makes the local site look lively for demos.

Unlike ``seed.py`` (which pulls a fixed set of users from JSONPlaceholder once
at startup), this script works purely on the local DB and can be run any time:

  cd backend
  python seed_more.py

It does three things, all reusing existing helpers/models:
  1. tops up each user's posts to a natural-looking count,
  2. builds a random follow graph so follower/following counts aren't empty,
  3. attaches the existing uploaded images to a share of image-less posts.

Safe to re-run: follows are de-duplicated against the composite PK, posts simply
accumulate up to the target, and only image-less posts get a picture.
"""

import os
import random
from datetime import datetime, timedelta

from app import app                       # reuse the already-configured app + db
from models import db, User, Post, Follow
from content import random_title, random_body
from config import UPLOAD_DIR, ALLOWED_IMAGE_EXT

# Tunables — tweak these to make the site fuller or sparser.
TARGET_POSTS_PER_USER = (6, 12)   # ensure each user ends up with this many posts
FOLLOWS_PER_USER = (3, 8)         # how many others each user follows
IMAGE_RATIO = 0.30                # share of image-less posts that get a picture


def _available_images():
    """List uploaded image filenames already sitting under UPLOAD_DIR."""
    try:
        names = os.listdir(UPLOAD_DIR)
    except FileNotFoundError:
        return []
    return [n for n in names if n.rsplit(".", 1)[-1].lower() in ALLOWED_IMAGE_EXT]


def topup_posts(users):
    """Add posts so every user reaches a random target count. Returns count added."""
    added = 0
    for u in users:
        want = random.randint(*TARGET_POSTS_PER_USER)
        for _ in range(max(0, want - len(u.posts))):
            # Stagger over the last ~30 days so the feed's "time ago" looks real.
            age = timedelta(minutes=random.randint(5, 60 * 24 * 30))
            u.posts.append(Post(
                item=random_title(),
                body=random_body(),
                created_at=datetime.utcnow() - age,
            ))
            added += 1
    return added


def add_follows(users):
    """Give each user a handful of (de-duplicated) follows. Returns count added."""
    ids = [u.id for u in users]
    added = 0
    for u in users:
        others = [i for i in ids if i != u.id]            # never follow yourself
        k = min(len(others), random.randint(*FOLLOWS_PER_USER))
        for followee_id in random.sample(others, k):
            if not Follow.exists(u.id, followee_id):       # composite-PK guard
                db.session.add(Follow(follower_id=u.id, followee_id=followee_id))
                added += 1
    return added


def attach_images():
    """Hang existing uploaded images on a share of image-less posts."""
    images = _available_images()
    if not images:
        return 0
    blank = db.session.scalars(db.select(Post).where(Post.image.is_(None))).all()
    pick = random.sample(blank, min(len(blank), int(len(blank) * IMAGE_RATIO)))
    for post in pick:
        post.image = random.choice(images)
    return len(pick)


def main():
    with app.app_context():
        users = db.session.scalars(db.select(User).order_by(User.id)).all()
        if not users:
            print("No users yet — run the app once to seed users first.")
            return
        posts = topup_posts(users)
        follows = add_follows(users)
        images = attach_images()
        db.session.commit()
        print(f"Enriched DB: +{posts} posts, +{follows} follows, "
              f"{images} posts got an image. ({len(users)} users total)")


if __name__ == "__main__":
    main()
