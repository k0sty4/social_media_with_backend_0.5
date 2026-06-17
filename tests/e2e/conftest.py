"""Fixtures for end-to-end (browser) tests.

These tests drive the REAL app in a real browser. To do that we spin up two
throwaway servers as subprocesses:
  * the Flask backend on a test port, against a temporary empty database
  * the Vite dev server (the React frontend) on a test port, pointed at that
    backend

When the session ends, both servers are shut down. Nothing touches your real
data.db or your normal ports (5001 / 5173).
"""

import os
import socket
import subprocess
import sys
import tempfile
import time
import urllib.request

import pytest

# Ports chosen to NOT clash with your normal dev servers (5001 / 5173).
BACKEND_PORT = 5055
FRONTEND_PORT = 5180
BASE_URL = f"http://localhost:{FRONTEND_PORT}"

_THIS_DIR = os.path.dirname(__file__)
PROJECT_ROOT = os.path.abspath(os.path.join(_THIS_DIR, "..", ".."))
FRONTEND_DIR = os.path.join(PROJECT_ROOT, "frontend")


def _port_open(port: int) -> bool:
    """True if something is accepting TCP connections on this port."""
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.settimeout(0.5)
        return s.connect_ex(("127.0.0.1", port)) == 0


def _wait_http(url: str, timeout: float) -> bool:
    """Poll a URL until it answers (any HTTP status) or we time out."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        try:
            urllib.request.urlopen(url, timeout=1)
            return True
        except urllib.error.HTTPError:
            return True  # any HTTP response means the server is up
        except Exception:
            time.sleep(0.4)
    return False


@pytest.fixture(scope="session")
def live_servers():
    """Start backend + frontend for the whole E2E session, then tear them down."""
    # --- backend on a temp database, no external seeding -------------------
    db_fd, db_path = tempfile.mkstemp(suffix=".db")
    backend_env = {
        **os.environ,
        "DATABASE_URI": f"sqlite:///{db_path}",
        # The browser will live at BASE_URL, so the CSRF/CORS origin must match.
        "FRONTEND_ORIGIN": BASE_URL,
    }
    backend_code = (
        "from app import app, db\n"
        "with app.app_context():\n"
        "    db.create_all()\n"
        f"app.run(port={BACKEND_PORT}, use_reloader=False)\n"
    )
    backend = subprocess.Popen(
        [sys.executable, "-c", backend_code],
        cwd=PROJECT_ROOT, env=backend_env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    # --- frontend (Vite) pointed at the test backend ----------------------
    frontend_env = {
        **os.environ,
        "VITE_API_BASE": f"http://localhost:{BACKEND_PORT}",
    }
    frontend = subprocess.Popen(
        ["npm", "run", "dev", "--", "--port", str(FRONTEND_PORT), "--strictPort"],
        cwd=FRONTEND_DIR, env=frontend_env,
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
    )

    try:
        backend_up = _wait_http(f"http://localhost:{BACKEND_PORT}/", timeout=20)
        frontend_up = _wait_http(BASE_URL, timeout=40)
        if not (backend_up and frontend_up):
            pytest.skip("E2E servers did not start in time (need Node + deps).")
        yield {"base_url": BASE_URL, "backend_port": BACKEND_PORT}
    finally:
        for proc in (frontend, backend):
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
        os.close(db_fd)
        os.remove(db_path)


@pytest.fixture
def page(live_servers):
    """A fresh Chromium page for one test (headless)."""
    from playwright.sync_api import sync_playwright
    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        context = browser.new_context(base_url=live_servers["base_url"])
        pg = context.new_page()
        yield pg
        context.close()
        browser.close()
