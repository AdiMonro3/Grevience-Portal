import { createContext, useCallback, useContext, useEffect, useMemo, useState } from "react";
import { api, setUnauthorizedHandler, tokenStore } from "../api/client";

const AuthContext = createContext(null);

export function AuthProvider({ children }) {
  const [user, setUser] = useState(null);
  const [loading, setLoading] = useState(Boolean(tokenStore.get()));
  // true after clicking Logout: the next login should start fresh, not return
  // to the previous user's page. false when the token simply expired.
  const [signedOut, setSignedOut] = useState(false);

  const endSession = useCallback((explicit) => {
    tokenStore.clear();
    setSignedOut(explicit);
    setUser(null);
  }, []);
  const logout = useCallback(() => endSession(true), [endSession]);

  useEffect(() => {
    setUnauthorizedHandler(() => endSession(false));
    if (!tokenStore.get()) return;
    api
      .get("/auth/me")
      .then((res) => setUser(res.data))
      .catch(() => tokenStore.clear())
      .finally(() => setLoading(false));
  }, [endSession]);

  const login = useCallback(async (email, password) => {
    // /auth/login is an OAuth2 form: username + password
    const body = new URLSearchParams({ username: email, password });
    const { data } = await api.post("/auth/login", body);
    tokenStore.set(data.access_token);
    setSignedOut(false);
    setUser(data.user);
    return data.user;
  }, []);

  const register = useCallback(async (payload) => {
    const { data } = await api.post("/auth/register", payload);
    tokenStore.set(data.access_token);
    setSignedOut(false);
    setUser(data.user);
    return data.user;
  }, []);

  const value = useMemo(
    () => ({ user, setUser, loading, signedOut, login, register, logout }),
    [user, loading, signedOut, login, register, logout],
  );
  return <AuthContext.Provider value={value}>{children}</AuthContext.Provider>;
}

export function useAuth() {
  return useContext(AuthContext);
}

/** Where each role lands after login. */
export function homePathFor(user) {
  if (!user) return "/login";
  if (user.role === "officer") return "/officer";
  if (user.role === "admin") return "/admin/triage";
  return user.lat != null ? "/nearby" : "/location";
}
