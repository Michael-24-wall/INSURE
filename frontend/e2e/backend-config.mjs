import path from "node:path";
import { fileURLToPath } from "node:url";

const here = path.dirname(fileURLToPath(import.meta.url));

export const frontendDir = path.resolve(here, "..");
export const backendDir = path.resolve(frontendDir, "..", "backend");
export const backendUrl = "http://127.0.0.1:8001";
export const backendHealthUrl = `${backendUrl}/health/`;
export const e2eFrontendUrl = "http://127.0.0.1:5174";
export const databasePath = path.join(backendDir, "e2e.sqlite3");
export const mediaPath = path.join(backendDir, "e2e-media");

const defaultFrontendOrigins = "http://localhost:5173,http://127.0.0.1:5173";

function e2eOrigins(value) {
  const origins = new Set(
    (value || defaultFrontendOrigins)
      .split(",")
      .map((origin) => origin.trim())
      .filter(Boolean)
  );
  origins.add(e2eFrontendUrl);
  origins.add("http://localhost:5174");
  return [...origins].join(",");
}

const defaultPython =
  process.platform === "win32"
    ? path.join(backendDir, ".venv", "Scripts", "python.exe")
    : path.join(backendDir, ".venv", "bin", "python");

export const python = process.env.PYTHON || defaultPython;

export function backendEnv(extra = {}) {
  return {
    ...process.env,
    DATABASE_URL: `sqlite:///${databasePath.replaceAll("\\", "/")}`,
    MEDIA_ROOT: mediaPath,
    DJANGO_DEBUG: "True",
    DJANGO_ALLOWED_HOSTS: "127.0.0.1,localhost",
    FRONTEND_URL: e2eFrontendUrl,
    CORS_ALLOWED_ORIGINS: e2eOrigins(process.env.CORS_ALLOWED_ORIGINS),
    CSRF_TRUSTED_ORIGINS: e2eOrigins(process.env.CSRF_TRUSTED_ORIGINS),
    THROTTLE_ANON: "100000/minute",
    THROTTLE_USER: "100000/minute",
    THROTTLE_AUTH: "100000/minute",
    THROTTLE_WEBHOOK: "100000/minute",
    THROTTLE_AI: "100000/minute",
    THROTTLE_SEARCH: "100000/minute",
    ...extra,
  };
}
