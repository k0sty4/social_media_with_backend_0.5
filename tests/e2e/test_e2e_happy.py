"""End-to-end "happy path" tests — a real browser using the real UI.

These prove the whole stack works together: React UI → HTTP → Flask → DB.
Run with:  pytest -m e2e
(They start their own backend + frontend; see conftest.py.)
"""

import json
import urllib.request
import uuid

import pytest

pytestmark = pytest.mark.e2e


def _unique_email():
    """Each test registers a brand-new user so they never collide."""
    return f"user_{uuid.uuid4().hex[:10]}@example.com"


def _register_via_ui(page, name, email, password="password123"):
    """Drive the /register form and wait until we're signed in."""
    page.goto("/register")
    page.get_by_label("Name").fill(name)
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Sign up").click()
    # After signup the app redirects home and the TopBar shows a Logout button.
    page.get_by_role("button", name="Logout").wait_for(timeout=10000)


def _create_user_via_api(backend_port, name, email, password="password123"):
    """Create a second user directly through the backend API (no browser),
    so a test has someone else to find and follow. (register is CSRF-exempt.)"""
    body = json.dumps({"name": name, "email": email, "password": password}).encode()
    req = urllib.request.Request(
        f"http://localhost:{backend_port}/api/auth/register",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    urllib.request.urlopen(req, timeout=5)


# --- 1. Registration -------------------------------------------------------

def test_register_shows_name_in_topbar(page):
    """Sign up through the UI → the top bar greets the new user."""
    _register_via_ui(page, "Alice E2E", _unique_email())
    assert page.get_by_text("Alice E2E").is_visible()


# --- 2. Create a post ------------------------------------------------------

def test_create_post_appears_in_feed(page):
    """Sign up → open the composer → publish → the post shows in the feed."""
    _register_via_ui(page, "Poster", _unique_email())

    page.goto("/")
    page.get_by_role("button", name="New Post").click()

    title = f"My E2E post {uuid.uuid4().hex[:6]}"
    page.get_by_label("Title").fill(title)
    # The body is a contentEditable rich-text area (no <input>), so we click it
    # and type with the keyboard.
    page.locator("[contenteditable]").click()
    page.keyboard.type("Hello from a browser test")
    page.get_by_role("button", name="Post").click()

    # The new post's title becomes visible in the feed.
    page.get_by_text(title).wait_for(timeout=10000)
    assert page.get_by_text(title).is_visible()


# --- 3. Search + follow ----------------------------------------------------

def test_search_and_follow(page, live_servers):
    """Sign up as Alice, find Bob via search, open his profile, follow him,
    and watch his follower count go to 1."""
    bob_name = f"Bob_{uuid.uuid4().hex[:6]}"
    _create_user_via_api(live_servers["backend_port"], bob_name, _unique_email())

    _register_via_ui(page, "Alice Searcher", _unique_email())

    page.goto("/users")
    page.get_by_placeholder("Search by username, name or email…").fill(bob_name)
    page.get_by_text(bob_name).click()

    # On Bob's profile, follow him.
    page.get_by_role("button", name="Follow").click()
    # The followers chip updates to "1 followers".
    page.get_by_text("1 followers").wait_for(timeout=10000)
    assert page.get_by_text("1 followers").is_visible()
