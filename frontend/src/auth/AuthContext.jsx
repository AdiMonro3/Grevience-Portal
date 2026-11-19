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

  const startSession = useCallback((data) => {
    tokenStore.set(data.access_token);
    setSignedOut(false);
    setUser(data.user);
    return data.user;
  }, []);

  const login = useCallback(
    async (email, password) => {
      // /auth/login is an OAuth2 form: username + password
      const body = new URLSearchParams({ username: email, password });
      const { data } = await api.post("/auth/login", body);
      return startSession(data);
    },
    [startSession],
  );

  /** `credential` is the ID token from Google's Sign in button; the API verifies it. */
  const loginWithGoogle = useCallback(
    async (credential) => {
      const { data } = await api.post("/auth/google", { credential });
      return startSession(data);
    },
    [startSession],
  );

  /** Creates the account only. The user logs in afterwards. */
  const register = useCallback(async (payload) => {
    const { data } = await api.post("/auth/register", payload);
    return data;
  }, []);

  const value = useMemo(
    () => ({ user, setUser, loading, signedOut, login, loginWithGoogle, register, logout }),
    [user, loading, signedOut, login, loginWithGoogle, register, logout],
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
