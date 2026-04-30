# Profile Explorer

React (Vite + Material UI) frontend with a Flask + SQLite backend.

## Architecture

```
frontend (React + MUI, Vite)  ──HTTP──▶  backend (Flask)  ──ORM──▶  SQLite (data.db)
                                              │
                                              └──(seed once per startup, +10 users)──▶  jsonplaceholder.typicode.com
```

- The **frontend** is a single-page React app (`frontend/`) styled with Material UI.
- The **backend** is a small Flask JSON API (`app.py`) backed by a local SQLite DB.
- On every backend startup the DB is seeded with 10 more users (with 3–6 posts each)
  pulled from JSONPlaceholder. Delete `data.db` to start fresh.

## Project structure

```
profile_parser/
├── app.py                 # Flask JSON API
├── models.py              # SQLAlchemy models (User, Post)
├── content.py             # Random post-title / post-body pool
├── requirements.txt       # Python dependencies
├── data.db                # SQLite (auto-created, git-ignored)
└── frontend/
    ├── index.html
    ├── package.json
    ├── vite.config.js
    ├── .env.example       # copy to .env to override the API base URL
    └── src/
        ├── main.jsx
        ├── App.jsx        # routes
        ├── api.js         # backend client (fetchPosts, fetchUsers, ...)
        ├── components/
        │   ├── TopBar.jsx     # MUI AppBar + Toolbar (Home / Users / About / Login)
        │   ├── SinglePost.jsx # MUI Card with Read More expand
        │   └── Feed.jsx       # MUI Grid + CircularProgress + Load More
        └── pages/
            ├── Home.jsx       # renders <Feed/>
            ├── Users.jsx
            ├── UserDetail.jsx
            ├── About.jsx
            └── Login.jsx
```

## How to run

You need **two terminals** — one for the backend, one for the frontend.

### 1. Backend (Flask)

```bash
cd profile_parser
python3 -m venv venv
source venv/bin/activate       # Windows: venv\Scripts\activate
pip install -r requirements.txt
python app.py
```

The API will be available at <http://127.0.0.1:5001>.

### 2. Frontend (React + Vite)

```bash
cd profile_parser/frontend
npm install
npm run dev
```

The app will open at <http://localhost:5173>.

### Configuring the API base URL (optional)

The frontend defaults to `http://127.0.0.1:5001`. To override:

```bash
cd profile_parser/frontend
cp .env.example .env
# edit .env, set VITE_API_BASE=...
```

## API endpoints

| Method | Path | Description |
| --- | --- | --- |
| GET | `/api/posts?page=N&per_page=10` | Paginated feed (consumed by `<Feed/>`) |
| GET | `/api/users` | All users with post preview |
| GET | `/api/user/<id>` | Single user by id |
| GET | `/api/users/<id>/posts?page=N&per_page=10` | Posts for a single user |
| GET | `/api/random-user` | One random user |
| GET | `/api/search?q=<query>` | Name/email search (case-insensitive) |

## Tech stack

- **Frontend**: React 19, Vite, Material UI 9, React Router 7
- **Backend**: Python 3, Flask, Flask-SQLAlchemy, Flask-CORS
- **DB**: SQLite (via SQLAlchemy 2.x)
- **Seed source**: jsonplaceholder.typicode.com (users only, once per startup)
