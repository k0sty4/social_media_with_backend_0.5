// Thin wrapper around fetch() for talking to the Flask backend.
//
// Every request goes through `api()` so we can:
//   * attach `credentials: "include"` (sends the HttpOnly session cookie),
//   * notice 401 responses centrally and tell AuthProvider to drop its
//     cached user (see `setOnUnauthorized`).

const API_BASE = import.meta.env.VITE_API_BASE || "http://localhost:5001";

// AuthProvider registers a callback at mount time. When any request gets
// a 401, we invoke it so the UI can clear the locally cached user without
// every caller having to handle the case.
let onUnauthorized = null;
export function setOnUnauthorized(fn) {
  onUnauthorized = fn;
}

async function api(path, options = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    credentials: "include",
    ...options,
  });
  if (response.status === 401 && onUnauthorized) {
    onUnauthorized();
  }
  return response;
}

// GET helper that throws on non-2xx; the thrown Error carries `.status`
// so callers can distinguish 401 vs 404 vs 5xx.
async function apiJson(path, options = {}) {
  const response = await api(path, options);
  if (!response.ok) {
    const err = new Error(`Request failed: ${response.status}`);
    err.status = response.status;
    throw err;
  }
  return response.json();
}

// --- Read endpoints (public) ---------------------------------------------

export function fetchPosts(page = 1, perPage = 10) {
  return apiJson(`/api/posts?page=${page}&per_page=${perPage}`);
}

export function fetchUsers() {
  return apiJson(`/api/users`);
}

export function fetchUser(id) {
  return apiJson(`/api/user/${id}`);
}

export function fetchUserPosts(id, page = 1, perPage = 10) {
  return apiJson(`/api/users/${id}/posts?page=${page}&per_page=${perPage}`);
}

export function searchUsers(query) {
  return apiJson(`/api/search?q=${encodeURIComponent(query)}`);
}

// --- Mutating helper ------------------------------------------------------
// Same pattern as apiJson but sends a JSON body. Carries the server-provided
// error message on `err.message` when available.
async function jsonBody(path, method, body) {
  const response = await api(path, {
    method,
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) {
    const err = new Error(data.error || `Request failed: ${response.status}`);
    err.status = response.status;
    throw err;
  }
  return data;
}

// --- Auth endpoints -------------------------------------------------------

export function register({ name, email, password }) {
  return jsonBody("/api/auth/register", "POST", { name, email, password });
}

export function login({ email, password }) {
  return jsonBody("/api/auth/login", "POST", { email, password });
}

export function logout() {
  return jsonBody("/api/auth/logout", "POST", {});
}

export function changePassword({ current_password, new_password }) {
  return jsonBody("/api/auth/change-password", "POST", { current_password, new_password });
}

// --- Authenticated mutations ---------------------------------------------

export function updatePost(id, { title, body }) {
  return jsonBody(`/api/posts/${id}`, "PATCH", { title, body });
}

export function updateUser(id, fields) {
  return jsonBody(`/api/user/${id}`, "PATCH", fields);
}
