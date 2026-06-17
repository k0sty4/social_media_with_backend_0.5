"""Shared configuration constants.

Kept in its own module (with no Flask/DB imports) so every other module can
import these values without creating circular imports.
"""

import os
from datetime import timedelta

# Where the frontend runs — used for both CORS and the CSRF Origin check.
FRONTEND_ORIGIN = os.environ.get("FRONTEND_ORIGIN", "http://localhost:5173")

# DATABASE_URI lets the test suite point at a throwaway database instead of the
# real data.db; falls back to the local file for normal runs.
DB_PATH = os.path.join(os.path.dirname(__file__), "data.db")
DATABASE_URI = os.environ.get("DATABASE_URI", f"sqlite:///{DB_PATH}")

# Uploaded post images live on disk here (only the filename is stored in the DB).
UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "uploads")
ALLOWED_IMAGE_EXT = {"png", "jpg", "jpeg", "gif", "webp"}
MAX_CONTENT_LENGTH = 5 * 1024 * 1024  # reject uploads bigger than 5 MB

# Session cookie settings.
SESSION_COOKIE = "session_id"
SESSION_TTL = timedelta(days=7)
COOKIE_SECURE = os.environ.get("COOKIE_SECURE", "0") == "1"

# Default page size for paginated endpoints.
PAGE_SIZE = 10
