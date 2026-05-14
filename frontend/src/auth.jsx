import { createContext, useContext, useState, useCallback, useEffect } from "react";
import * as api from "./api";

const STORAGE_KEY = "currentUser";

function readStoredUser() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(readStoredUser);

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
      persist(null);
    }
  }, [persist]);

  const clearUser = useCallback(() => persist(null), [persist]);

  const updateUser = useCallback((next) => persist(next), [persist]);

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

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside <AuthProvider>");
  return ctx;
}
