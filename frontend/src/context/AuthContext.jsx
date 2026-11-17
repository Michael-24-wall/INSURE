import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import api, { REFRESH_KEY, TOKEN_KEY, USER_KEY } from "../api/client";
import { HOME_BY_ROLE } from "../lib/constants";

const AuthContext = createContext(null);

function readStoredUser() {
  try {
    const raw = localStorage.getItem(USER_KEY);
    return raw ? JSON.parse(raw) : null;
  } catch {
    return null;
  }
}

export function AuthProvider({ children }) {
  const [token, setToken] = useState(() => localStorage.getItem(TOKEN_KEY));
  const [user, setUser] = useState(readStoredUser);
  const [loading, setLoading] = useState(Boolean(token));

  const persistUser = useCallback((nextUser) => {
    setUser(nextUser);
    if (nextUser) localStorage.setItem(USER_KEY, JSON.stringify(nextUser));
    else localStorage.removeItem(USER_KEY);
  }, []);

  const clearSession = useCallback(() => {
    localStorage.removeItem(TOKEN_KEY);
    localStorage.removeItem(REFRESH_KEY);
    localStorage.removeItem(USER_KEY);
    setToken(null);
    setUser(null);
  }, []);

  const refresh = useCallback(async () => {
    if (!localStorage.getItem(TOKEN_KEY)) {
      setLoading(false);
      return null;
    }
    try {
      const { data } = await api.get("/auth/me/");
      setToken(localStorage.getItem(TOKEN_KEY));
      persistUser(data);
      return data;
    } catch {
      clearSession();
      return null;
    } finally {
      setLoading(false);
    }
  }, [clearSession, persistUser]);

  useEffect(() => {
    refresh();
  }, [refresh]);

  useEffect(() => {
    const onExpired = () => clearSession();
    window.addEventListener("autoinssure:auth-expired", onExpired);
    return () => window.removeEventListener("autoinssure:auth-expired", onExpired);
  }, [clearSession]);

  const storeSession = useCallback((data) => {
    localStorage.setItem(TOKEN_KEY, data.access);
    localStorage.setItem(REFRESH_KEY, data.refresh);
    localStorage.setItem(USER_KEY, JSON.stringify(data.user));
    setToken(data.access);
    setUser(data.user);
  }, []);

  const login = useCallback(async (email, password) => {
    const { data } = await api.post("/auth/login/", { email, password });
    if (data.otp_required) return data;
    storeSession(data);
    return data.user;
  }, [storeSession]);

  const verifyTwoFactor = useCallback(async (challenge, code) => {
    const { data } = await api.post("/auth/2fa/verify/", { challenge, code });
    storeSession(data);
    return data.user;
  }, [storeSession]);

  const logout = useCallback(async () => {
    try {
      await api.post("/auth/logout/", { refresh: localStorage.getItem(REFRESH_KEY) });
    } catch {
      // The local session must still be cleared if the server token is already invalid.
    }
    clearSession();
  }, [clearSession]);

  const value = useMemo(
    () => ({
      token,
      user,
      loading,
      isAuthenticated: Boolean(token && user),
      login,
      verifyTwoFactor,
      logout,
      refresh,
      setUser: persistUser,
      homePath: HOME_BY_ROLE[user?.role] || "/app",
    }),
    [token, user, loading, login, verifyTwoFactor, logout, refresh, persistUser]
  );

  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  const ctx = useContext(AuthContext);
  if (!ctx) throw new Error("useAuth must be used inside AuthProvider");
  return ctx;
}
