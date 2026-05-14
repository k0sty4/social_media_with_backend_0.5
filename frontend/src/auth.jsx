// Auth state for the SPA.
//
// The server cookie is the real source of truth: the browser sends it on
// every fetch, and the backend decides what the caller is allowed to do.
// This module keeps a *cached* copy of the user profile in localStorage so
// the UI knows the current name/id without an extra round-trip on page
// load. If the server cookie ever stops being valid (expired, revoked,
// password changed elsewhere), the first 401 from the API clears this
// cache via the global interceptor in `api.js`.

import { createContext, useContext, useState, useCallback, useEffect } from "react";
import * as api from "./api";

const STORAGE_KEY = "currentUser";

// Hydrate the cached user from localStorage on first render. Wrapped in
// try/catch because a corrupted JSON value would otherwise crash the app.
function readStoredUser() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

const AuthContext = createContext(null);

// Wraps the app and provides `useAuth()` to every descendant.
export function AuthProvider({ children }) {
  const [user, setUser] = useState(readStoredUser);

  // Update both React state and localStorage in one place so they never
  // drift apart.
  const persist = useCallback((value) => {
    setUser(value);
    if (value) {
      localStorage.setItem(STORAGE_KEY, JSON.stringify(value));
    } else {
      localStorage.removeItem(STORAGE_KEY);
    }
  }, []);

  const login = useCallback(async (credentials) => {
    const data = await api.login(credentials);
    persist(data);
    return data;
  }, [persist]);

  const register = useCallback(async (data) => {
    const created = await api.register(data);
    persist(created);
    return created;
  }, [persist]);

  const logout = useCallback(async () => {
    try {
      await api.logout();
    } finally {
      // Always drop the local cache, even if the network call failed —
      // the user clicked Logout, we should honour that.
      persist(null);
    }
  }, [persist]);

  // Hard reset of the cached user. Used by the 401 interceptor and by the
  // UI when the server returns an unrecoverable auth error.
  const clearUser = useCallback(() => persist(null), [persist]);

  // Replace the cached user (e.g. after the user edits their own name on
  // the profile page — the TopBar should reflect the new name immediately).
  const updateUser = useCallback((next) => persist(next), [persist]);

  // Register clearUser as the global 401 handler at mount, unregister on
  // unmount so we don't keep a stale closure alive.
  useEffect(() => {
    api.setOnUnauthorized(clearUser);
    return () => api.setOnUnauthorized(null);
  }, [clearUser]);

  return (
    <AuthContext.Provider value={{ user, login, register, logout, clearUser, updateUser }}>
      {children}
    </AuthContext.Provider>
  );
}

// Hook used by components that need to read or mutate auth state.
export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
