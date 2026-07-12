"""End-to-end flow tests — multi-step journeys through the real UI.

These complement ``test_e2e_happy.py`` (single-action happy paths) with longer
sequences: log in with an existing account, edit a post, and log out. Like the
happy-path suite they drive a real Chromium browser against a live backend +
frontend. Run with:  pytest -m e2e
"""

import json
import urllib.request
import uuid

import pytest

pytestmark = pytest.mark.e2e


def _unique_email():
    return f"user_{uuid.uuid4().hex[:10]}@example.com"


def _register_via_api(backend_port, name, email, password="password123"):
    """Create an account straight through the API (register is CSRF-exempt)."""
    body = json.dumps({"name": name, "email": email, "password": password}).encode()
    req = urllib.request.Request(
        f"http://localhost:{backend_port}/api/auth/register",
        data=body,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    urllib.request.urlopen(req, timeout=5)


def _register_via_ui(page, name, email, password="password123"):
    page.goto("/register")
    page.get_by_label("Name").fill(name)
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Sign up").click()
    page.get_by_role("button", name="Logout").wait_for(timeout=10000)


def _login_via_ui(page, email, password="password123"):
    page.goto("/login")
    page.get_by_label("Email").fill(email)
    page.get_by_label("Password").fill(password)
    page.get_by_role("button", name="Sign in").click()
    page.get_by_role("button", name="Logout").wait_for(timeout=10000)


# --- 1. Log in with an existing account ------------------------------------

def test_login_existing_account(page, live_servers):
    """Create a user via the API, then sign in through the /login form."""
    email = _unique_email()
    _register_via_api(live_servers["backend_port"], "Returning User", email)

    _login_via_ui(page, email)
    assert page.get_by_text("Returning User").is_visible()


# --- 2. Edit one of your own posts -----------------------------------------

def test_edit_own_post(page):
    """Sign up → publish a post → edit its title → the new title shows in feed."""
    _register_via_ui(page, "Editor", _unique_email())

    page.goto("/")
    page.get_by_role("button", name="New Post").click()
    original = f"Original {uuid.uuid4().hex[:6]}"
    page.get_by_label("Title").fill(original)
    page.locator("[contenteditable]").click()
    page.keyboard.type("First draft body")
    page.get_by_role("button", name="Post").click()
    page.get_by_text(original).wait_for(timeout=10000)

    # Enter edit mode, change the title, save.
    page.get_by_role("button", name="Edit").first.click()
    updated = f"Updated {uuid.uuid4().hex[:6]}"
    page.get_by_label("Title").fill(updated)
    page.get_by_role("button", name="Save").click()

    page.get_by_text(updated).wait_for(timeout=10000)
    assert page.get_by_text(updated).is_visible()


# --- 3. Log out ------------------------------------------------------------

def test_logout_returns_to_signed_out_state(page):
    """After logout the TopBar shows Login/Register again, not Logout."""
    _register_via_ui(page, "Leaver", _unique_email())

    page.get_by_role("button", name="Logout").click()
    # Signed-out TopBar exposes the Login control again.
    page.get_by_role("link", name="Login").wait_for(timeout=10000)
    assert page.get_by_role("button", name="Logout").count() == 0
