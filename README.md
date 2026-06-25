# Profile Explorer

React (Vite + Material UI) frontend with a Flask + SQLite backend. Cookie-based
auth (no JWT, no tokens in the response body), users can edit only their own
posts and profile.

## Features

- **Authentication** — sign-up, login, logout; passwords hashed with scrypt.
- **User profiles** — dedicated page per user with name, bio, avatar, follower
  / following counts, and the user's posts.
- **Search** — find users by username, name, or email.
- **Follow / unfollow** — directed follow graph; counts shown on each profile.
- **Feed** — two scopes: **Global** (all users) and **Following** (only people
  you follow), with **infinite scroll** (IntersectionObserver, no buttons).
- **Post creation** — title + a **WYSIWYG rich-text editor** (bold, italic,
  underline, links, lists) + optional **image upload**.
- **Timestamps** — every post shows relative "time ago" (e.g. "2 hours ago").

The database schema (ER diagram) is in **[SCHEMA.md](SCHEMA.md)**.

## Architecture

```
frontend (React + MUI, Vite)  ──HTTP+cookie──▶  backend (Flask)  ──ORM──▶  SQLite (data.db)
                                                     │
                                                     └──(seed once per startup)──▶  jsonplaceholder.typicode.com
```

- **Frontend** — single-page React app (`frontend/`) with Material UI.
- **Backend** — small Flask JSON API (`app.py`) on a local SQLite DB.
- On every backend startup the DB is seeded with 10 more users (3–6 posts each)
  pulled from JSONPlaceholder. Delete `data.db` to start fresh.

## Auth & security model

- **Passwords**: werkzeug `scrypt` with a random per-user salt. Even a full
  DB leak doesn't directly leak passwords.
- **Sessions**: server-side row in the `sessions` table. The cookie carries
  a 256-bit random token; the DB stores only its `sha256`. A DB leak doesn't
  hand the attacker live sessions either.
- **Cookie**: `HttpOnly`, `SameSite=Lax`, `Path=/`, `Max-Age=7 days`. Set
  `COOKIE_SECURE=1` env var when serving over HTTPS to add the `Secure` flag.
- **CSRF**: every mutating request must have `Origin == FRONTEND_ORIGIN`.
  Login and register are exempt (no privileged state to abuse).
- **Authn vs authz**: missing/expired session → `401`. A logged-in user
  touching a resource that isn't theirs → `404` (info-hiding, doesn't reveal
  whether the target exists).
- **Rate limiting on `/login`**: 10 fails/min per IP, 5 fails/15min per email.
  Trips before the scrypt verify so a flood can't pin a CPU.
- **CORS**: locked to `FRONTEND_ORIGIN` with `credentials: true`.
- **Rich-text XSS**: post bodies are HTML from a WYSIWYG editor, sanitised
  server-side (`sanitize.py`) against a strict tag whitelist — `<script>` and
  all attributes except a validated `href` are stripped before storage.
- **Uploads**: only image extensions (png/jpg/gif/webp) accepted, stored under
  a random uuid filename, capped at 5 MB (`MAX_CONTENT_LENGTH`).

## Project structure

```
profile_parser/
├── Makefile              # shortcuts: make backend / frontend / test / e2e
├── backend/              # self-contained Flask backend
│   ├── app.py            # Flask JSON API entry point (wires blueprints together)
│   ├── auth.py           # auth blueprint: register / login / logout / change-pw
│   ├── posts.py          # posts blueprint: feed, create/edit, image serving
│   ├── users.py          # users blueprint: profiles, search, follow/unfollow
│   ├── models.py         # SQLAlchemy models: User, Post, Follow, Session
│   ├── sanitize.py       # HTML whitelist sanitiser for rich-text post bodies
│   ├── content.py        # Random post-title / post-body pool
│   ├── config.py         # Shared config constants
│   ├── seed.py           # Startup seeding + one-time SQLite migrations
│   ├── SCHEMA.md         # Database ER diagram (Mermaid)
│   ├── requirements.txt
│   ├── requirements-dev.txt
│   ├── pytest.ini
│   ├── data.db           # SQLite (auto-created, git-ignored)
│   ├── uploads/          # Uploaded post images (auto-created, git-ignored)
│   └── tests/            # unit / API / flow tests (+ tests/e2e browser tests)
└── frontend/
    ├── package.json
    ├── vite.config.js
    ├── .env.example      # copy to .env to override the API base URL
    └── src/
        ├── main.jsx
        ├── App.jsx       # routes
        ├── api.js        # backend client + global 401 interceptor
        ├── auth.jsx      # AuthProvider, useAuth() hook
        ├── timeAgo.js    # relative "time ago" formatter
        ├── htmlText.js   # strip HTML → plain text (empty-body check)
        ├── components/
        │   ├── TopBar.jsx
        │   ├── SinglePost.jsx        # renders rich-text + image; inline editor
        │   ├── RichTextEditor.jsx    # dependency-free WYSIWYG editor
        │   ├── CreatePostDialog.jsx  # compose a post (title + body + image)
        │   └── Feed.jsx              # Global/Following tabs + infinite scroll
        └── pages/
            ├── Home.jsx
            ├── Users.jsx
            ├── UserDetail.jsx   # profile + follow + Edit profile + Change password
            ├── About.jsx
            ├── Login.jsx
            └── Register.jsx
```

## How to run

Two terminals — one for the backend, one for the frontend.

### 1. Backend (Flask)

```bash
cd profile_parser/backend
python3 -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py                     # listens on http://localhost:5001
```

By default the backend allows the frontend at `http://localhost:5173`.
Override with `FRONTEND_ORIGIN=http://localhost:5174 python app.py`.

### 2. Frontend (React + Vite)

```bash
cd profile_parser/frontend
npm install
npm run dev                       # http://localhost:5173
```

> **Important**: keep frontend and backend on the **same hostname**
> (both `localhost` or both `127.0.0.1`). `SameSite=Lax` treats those as
> different sites, so mixing them breaks the cookie.

### Configuring the API base URL (optional)

```bash
cd profile_parser/frontend
cp .env.example .env
# edit .env, default: VITE_API_BASE=http://localhost:5001
```

## Tests

All backend tests live in `backend/tests/` and run from the backend dir:

```bash
cd profile_parser/backend
pip install -r requirements-dev.txt
pytest                            # unit + API + flow tests (88 tests)
pytest -m e2e                     # browser end-to-end tests (starts its own servers)
```

The E2E tests need Node and a one-time `playwright install chromium`. From the
repo root the `Makefile` wraps these: `make test`, `make e2e`.

## API endpoints

### Public

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/posts?page=N&per_page=10&scope=all\|following` | Paginated feed (`following` needs auth) |
| GET | `/api/users` | All users with post preview |
| GET | `/api/user/<id>` | Single user by id (incl. follow counts) |
| GET | `/api/users/<id>/posts?page=N&per_page=10` | Posts for a user |
| GET | `/api/random-user` | One random user |
| GET | `/api/search?q=<query>` | Username / name / email search |
| GET | `/api/uploads/<filename>` | Serve an uploaded post image |

### Auth

| Method | Path | Body | Returns |
| --- | --- | --- | --- |
| POST | `/api/auth/register` | `{name, email, password}` | `201` + sets session cookie |
| POST | `/api/auth/login` | `{email, password}` | `200` + sets cookie · `401` · `429` |
| POST | `/api/auth/logout` | — | `200` + clears cookie |
| POST | `/api/auth/change-password` | `{current_password, new_password}` | `200` (kills all other sessions) · `401` · `400` |

### Authenticated mutations

| Method | Path | Authz |
| --- | --- | --- |
| POST | `/api/posts` | `401` unauth · `400` bad input · `201` on success. `multipart/form-data`: `title` (text), `body` (rich HTML, sanitised), optional `image` file. |
| PATCH | `/api/user/<id>` | `401` unauth · `404` if id ≠ your id · `200` on success. Editable: `name, bio, phone, website, company, avatar_seed`. `email` / `password` not editable here. |
| PATCH | `/api/posts/<id>` | `401` unauth · `404` if missing or not yours · `200` on success. Editable: `title, body`. |
| POST | `/api/users/<id>/follow` | `401` unauth · `400` self-follow · `404` no such user · `200` with counts. Idempotent. |
| DELETE | `/api/users/<id>/follow` | Same as above; unfollows. Idempotent. |

## Tech stack

- **Frontend**: React 19, Vite, Material UI 9, React Router 7
- **Backend**: Python 3, Flask, Flask-SQLAlchemy, Flask-CORS, werkzeug (scrypt)
- **DB**: SQLite (via SQLAlchemy 2.x)
- **Seed source**: jsonplaceholder.typicode.com (users only, once per startup)
