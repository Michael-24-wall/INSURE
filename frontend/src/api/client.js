import axios from "axios";

export const TOKEN_KEY = "autoinssure.access";
export const REFRESH_KEY = "autoinssure.refresh";
export const USER_KEY = "autoinssure.user";

const baseURL = import.meta.env.VITE_API_URL || "/api/v1";

const api = axios.create({
  baseURL,
  timeout: 45000,
});

// A bare instance used only for token refresh so we never recurse through the
// response interceptor.
const refreshApi = axios.create({ baseURL, timeout: 45000 });

api.interceptors.request.use((config) => {
  const access = localStorage.getItem(TOKEN_KEY);
  if (access) config.headers.Authorization = `Bearer ${access}`;
  return config;
});

let refreshPromise = null;

async function refreshAccessToken() {
  const refresh = localStorage.getItem(REFRESH_KEY);
  if (!refresh) throw new Error("No refresh token");
  const { data } = await refreshApi.post("/auth/token/refresh/", { refresh });
  localStorage.setItem(TOKEN_KEY, data.access);
  if (data.refresh) localStorage.setItem(REFRESH_KEY, data.refresh);
  return data.access;
}

function clearStoredSession() {
  localStorage.removeItem(TOKEN_KEY);
  localStorage.removeItem(REFRESH_KEY);
  localStorage.removeItem(USER_KEY);
}

api.interceptors.response.use(
  (response) => response,
  async (error) => {
    const original = error.config;
    const status = error.response?.status;
    const isAuthEndpoint = original?.url?.includes("/auth/login/") || original?.url?.includes("/auth/token/refresh/");

    if (status === 401 && !isAuthEndpoint && !original?._retry && localStorage.getItem(REFRESH_KEY)) {
      original._retry = true;
      try {
        refreshPromise = refreshPromise || refreshAccessToken();
        const access = await refreshPromise;
        refreshPromise = null;
        original.headers.Authorization = `Bearer ${access}`;
        return api(original);
      } catch (refreshError) {
        refreshPromise = null;
        clearStoredSession();
        window.dispatchEvent(new CustomEvent("autoinssure:auth-expired"));
        return Promise.reject(refreshError);
      }
    }

    if (status === 401 && localStorage.getItem(TOKEN_KEY)) {
      clearStoredSession();
      window.dispatchEvent(new CustomEvent("autoinssure:auth-expired"));
    }

    return Promise.reject(error);
  },
);

export function listData(payload) {
  if (Array.isArray(payload)) return payload;
  if (Array.isArray(payload?.results)) return payload.results;
  return [];
}

export function pageCount(payload) {
  if (Array.isArray(payload)) return payload.length;
  return payload?.count ?? listData(payload).length;
}

export function getErrorMessage(error) {
  const data = error?.response?.data;
  if (!data) return error?.message || "Something went wrong. Please try again.";
  if (typeof data === "string") return data;
  if (data.detail) return data.detail;
  if (data.error) {
    const detail = data.error.details;
    if (detail && typeof detail === "object") {
      const first = Object.entries(detail)[0];
      if (first) {
        const [field, value] = first;
        const text = Array.isArray(value) ? value.join(" ") : String(value);
        return field === "non_field_errors" || field === "detail" ? text : `${field.replace(/_/g, " ")}: ${text}`;
      }
    }
    return data.error.message || "Request failed.";
  }
  if (data.non_field_errors) return [].concat(data.non_field_errors).join(" ");
  const first = Object.entries(data).find(([, value]) => value);
  if (first) {
    const [field, value] = first;
    const text = Array.isArray(value) ? value.join(" ") : String(value);
    return field === "detail" ? text : `${field.replace(/_/g, " ")}: ${text}`;
  }
  return "Request failed.";
}

function apiDownloadPath(path) {
  if (typeof path === "string" && path.startsWith("/api/v1/")) {
    return path.slice("/api/v1".length);
  }
  return path;
}

export async function downloadFile(path, filename = "document") {
  const response = await api.get(apiDownloadPath(path), { responseType: "blob" });
  const url = URL.createObjectURL(response.data);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  URL.revokeObjectURL(url);
}

export function downloadCsv(path, filename) {
  return downloadFile(path, filename);
}

export default api;
