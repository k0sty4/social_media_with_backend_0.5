# Profile Explorer

React (Vite + Material UI) frontend with a Flask + SQLite backend. Cookie-based
auth (no JWT, no tokens in the response body), users can edit only their own
posts and profile.

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

## Project structure

```
profile_parser/
├── app.py                # Flask JSON API (auth, posts, users, profile)
├── models.py             # SQLAlchemy models: User, Post, Session
├── content.py            # Random post-title / post-body pool
├── requirements.txt
├── data.db               # SQLite (auto-created, git-ignored)
└── frontend/
    ├── package.json
    ├── vite.config.js
    ├── .env.example      # copy to .env to override the API base URL
    └── src/
        ├── main.jsx
        ├── App.jsx       # routes
        ├── api.js        # backend client + global 401 interceptor
        ├── auth.jsx      # AuthProvider, useAuth() hook
        ├── components/
        │   ├── TopBar.jsx
        │   ├── SinglePost.jsx   # inline post editor for own posts
        │   └── Feed.jsx
        └── pages/
            ├── Home.jsx
            ├── Users.jsx
            ├── UserDetail.jsx   # profile + Edit profile + Change password
            ├── About.jsx
            ├── Login.jsx
            └── Register.jsx
```

## How to run

Two terminals — one for the backend, one for the frontend.

### 1. Backend (Flask)

```bash
cd profile_parser
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

## API endpoints

### Public

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/posts?page=N&per_page=10` | Paginated global feed |
| GET | `/api/users` | All users with post preview |
| GET | `/api/user/<id>` | Single user by id |
| GET | `/api/users/<id>/posts?page=N&per_page=10` | Posts for a user |
| GET | `/api/random-user` | One random user |
| GET | `/api/search?q=<query>` | Name/email search |

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
| PATCH | `/api/user/<id>` | `401` unauth · `404` if id ≠ your id · `200` on success. Editable: `name, bio, phone, website, company, avatar_seed`. `email` / `password` not editable here. |
| PATCH | `/api/posts/<id>` | `401` unauth · `404` if missing or not yours · `200` on success. Editable: `title, body`. |

## Tech stack

- **Frontend**: React 19, Vite, Material UI 9, React Router 7
- **Backend**: Python 3, Flask, Flask-SQLAlchemy, Flask-CORS, werkzeug (scrypt)
- **DB**: SQLite (via SQLAlchemy 2.x)
- **Seed source**: jsonplaceholder.typicode.com (users only, once per startup)
