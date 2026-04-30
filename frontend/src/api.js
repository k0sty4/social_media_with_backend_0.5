const API_BASE = import.meta.env.VITE_API_BASE || "http://127.0.0.1:5001";

export async function fetchPosts(page = 1, perPage = 10) {
  const response = await fetch(
    `${API_BASE}/api/posts?page=${page}&per_page=${perPage}`
  );
  if (!response.ok) {
    throw new Error(`Failed to fetch posts: ${response.status}`);
  }
  return response.json();
}

export async function fetchUsers() {
  const response = await fetch(`${API_BASE}/api/users`);
  if (!response.ok) {
    throw new Error(`Failed to fetch users: ${response.status}`);
  }
  return response.json();
}

export async function fetchUser(id) {
  const response = await fetch(`${API_BASE}/api/user/${id}`);
  if (!response.ok) {
    throw new Error(`Failed to fetch user: ${response.status}`);
  }
  return response.json();
}

export async function fetchUserPosts(id, page = 1, perPage = 10) {
  const response = await fetch(
    `${API_BASE}/api/users/${id}/posts?page=${page}&per_page=${perPage}`
  );
  if (!response.ok) {
    throw new Error(`Failed to fetch user posts: ${response.status}`);
  }
  return response.json();
}

export async function searchUsers(query) {
  const response = await fetch(
    `${API_BASE}/api/search?q=${encodeURIComponent(query)}`
  );
  if (!response.ok) {
    throw new Error(`Search failed: ${response.status}`);
  }
  return response.json();
}
