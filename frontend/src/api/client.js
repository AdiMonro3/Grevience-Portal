import axios from "axios";

export const API_URL = (import.meta.env.VITE_API_URL || "http://localhost:8000").replace(/\/$/, "");

const TOKEN_KEY = "gp_token";

export const tokenStore = {
  get: () => localStorage.getItem(TOKEN_KEY),
  set: (token) => localStorage.setItem(TOKEN_KEY, token),
  clear: () => localStorage.removeItem(TOKEN_KEY),
};

export const api = axios.create({ baseURL: API_URL });

// Attach the JWT to every request
api.interceptors.request.use((config) => {
  const token = tokenStore.get();
  if (token) config.headers.Authorization = `Bearer ${token}`;
  return config;
});

// Expired / invalid token -> log out (AuthContext registers the handler)
let onUnauthorized = null;
export function setUnauthorizedHandler(fn) {
  onUnauthorized = fn;
}
api.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error.response?.status === 401 && tokenStore.get() && onUnauthorized) onUnauthorized();
    return Promise.reject(error);
  },
);

/** Media paths come back as "/media/..." - prefix them with the API host. */
export function mediaUrl(path) {
  if (!path) return null;
  return path.startsWith("http") ? path : `${API_URL}${path}`;
}

/** Turn any axios / FastAPI error into one readable sentence. */
export function errorMessage(error, fallback = "Something went wrong. Please try again.") {
  const detail = error?.response?.data?.detail;
  if (typeof detail === "string") return detail;
  if (Array.isArray(detail)) {
    return detail
      .map((d) => {
        const field = d.loc?.filter((p) => p !== "body").join(".");
        const msg = (d.msg || "").replace(/^Value error, /, "");
        return field ? `${field}: ${msg}` : msg;
      })
      .join("; ");
  }
  if (error?.code === "ERR_NETWORK") return `Cannot reach the server at ${API_URL}. Is the API running?`;
  return fallback;
}
