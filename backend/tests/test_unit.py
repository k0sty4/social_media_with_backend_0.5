"""Unit tests — each checks ONE function in isolation, with no database.

These are the "true" unit tests: pure functions in, expected value out. They're
fast and pinpoint exactly which helper broke.
"""

from sanitize import sanitize_html, strip_tags, _safe_href, MAX_LEN
from app import _hash_token
from models import User


# --- sanitize_html: the XSS defence for rich-text post bodies -------------

def test_sanitize_removes_script_tag():
    """The <script> TAG must never survive. Its inner text is kept but
    HTML-escaped, so it renders as plain text and can never execute."""
    dirty = "Hello <script>alert('xss')</script> world"
    clean = sanitize_html(dirty)
    assert "<script" not in clean        # the dangerous tag is gone
    assert "<script>" not in clean
    assert "Hello" in clean and "world" in clean


def test_sanitize_keeps_allowed_formatting():
    """Whitelisted tags (bold, italic) are preserved."""
    clean = sanitize_html("<b>bold</b> and <i>italic</i>")
    assert "<b>bold</b>" in clean
    assert "<i>italic</i>" in clean


def test_sanitize_blocks_javascript_links():
    """A javascript: URL in a link is stripped; safe links keep their href."""
    evil = sanitize_html('<a href="javascript:alert(1)">click</a>')
    assert "javascript:" not in evil

    safe = sanitize_html('<a href="https://example.com">click</a>')
    assert 'href="https://example.com"' in safe


def test_sanitize_empty_input():
    """Empty input returns an empty string, not an error."""
    assert sanitize_html("") == ""
    assert sanitize_html(None) == ""


def test_sanitize_strips_attributes_from_allowed_tags():
    """Even a whitelisted tag keeps NO attributes (onclick, style, class...)."""
    clean = sanitize_html('<p onclick="steal()" class="x">hi</p>')
    assert "onclick" not in clean
    assert "class" not in clean
    assert "<p>hi</p>" in clean


def test_sanitize_keeps_self_closing_br():
    """A self-closing ``<br/>`` survives as a ``<br>`` void element."""
    clean = sanitize_html("line<br/>break")
    assert "<br>" in clean
    assert "line" in clean and "break" in clean


def test_sanitize_preserves_nested_lists():
    """Nested block structure (ul > li) is kept intact."""
    clean = sanitize_html("<ul><li>one</li><li>two</li></ul>")
    assert clean.count("<li>") == 2
    assert "<ul>" in clean and "</ul>" in clean


def test_sanitize_drops_unknown_tag_but_keeps_text():
    """A non-whitelisted tag is removed but its text content is preserved."""
    clean = sanitize_html("<marquee>scroll</marquee>")
    assert "<marquee" not in clean
    assert "scroll" in clean


def test_sanitize_escapes_stray_angle_brackets():
    """Loose ``<`` / ``>`` in text are escaped so they can't form markup."""
    clean = sanitize_html("2 < 3 and 5 > 4")
    assert "&lt;" in clean and "&gt;" in clean


def test_sanitize_enforces_max_length():
    """Input beyond MAX_LEN is truncated before parsing (DoS / storage guard)."""
    huge = "a" * (MAX_LEN + 5000)
    assert len(sanitize_html(huge)) <= MAX_LEN


# --- strip_tags: plain-text projection used to detect "empty" posts -------

def test_strip_tags_returns_plain_text():
    assert strip_tags("<p>Hello <b>world</b></p>") == "Hello world"


def test_strip_tags_empty_markup_is_empty():
    """Markup with no real text strips down to nothing."""
    assert strip_tags("<p></p>") == ""
    assert strip_tags("<br>") == ""


# --- _safe_href: link scheme whitelist ------------------------------------

def test_safe_href_allows_http_https_mailto():
    assert _safe_href("http://example.com") is True
    assert _safe_href("https://example.com") is True
    assert _safe_href("mailto:a@b.com") is True


def test_safe_href_blocks_dangerous_schemes():
    assert _safe_href("javascript:alert(1)") is False
    assert _safe_href("data:text/html,evil") is False
    assert _safe_href("") is False


# --- _hash_token: session token hashing -----------------------------------

def test_hash_token_is_deterministic():
    """Same input → same hash (so we can look up a session by its token)."""
    assert _hash_token("abc") == _hash_token("abc")


def test_hash_token_changes_with_input_and_is_sha256():
    """Different input → different hash; output is a 64-char hex sha256."""
    assert _hash_token("abc") != _hash_token("abd")
    digest = _hash_token("abc")
    assert len(digest) == 64
    assert all(c in "0123456789abcdef" for c in digest)


# --- User.check_password: password hashing round-trip ----------------------

def test_check_password_round_trip():
    """The right password verifies, a wrong one doesn't — and the stored hash
    is never the plaintext password."""
    u = User(name="X", email="x@x.com")
    u.set_password("secret123")
    assert u.check_password("secret123") is True
    assert u.check_password("wrong") is False
    assert u.password_hash != "secret123"


def test_check_password_false_without_hash():
    """A user with no password (seed user) can never authenticate."""
    u = User(name="Seed", email="seed@x.com")
    assert u.check_password("anything") is False
