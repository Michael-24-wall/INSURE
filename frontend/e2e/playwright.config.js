import { defineConfig, devices } from "@playwright/test";
import {
  backendDir,
  backendEnv,
  backendHealthUrl,
  backendUrl,
  e2eFrontendUrl,
  frontendDir,
  python,
} from "./backend-config.mjs";

const webServerOutput = process.env.PW_WS_INHERIT ? "inherit" : "pipe";

export default defineConfig({
  testDir: ".",
  testMatch: "**/*.spec.js",
  fullyParallel: false,
  workers: 1,
  timeout: 180_000,
  expect: { timeout: 15_000 },
  reporter: [["list"]],
  use: {
    baseURL: e2eFrontendUrl,
    trace: "retain-on-failure",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "chromium",
      use: { ...devices["Desktop Chrome"], channel: "chrome" },
    },
  ],
  webServer: [
    {
      command: `"${python}" manage.py runserver 127.0.0.1:8001 --noreload --skip-checks`,
      cwd: backendDir,
      env: backendEnv(),
      url: backendHealthUrl,
      timeout: 180_000,
      reuseExistingServer: !process.env.CI,
      stdout: webServerOutput,
      stderr: webServerOutput,
    },
    {
      command: "npm run dev -- --host 127.0.0.1 --port 5174 --strictPort",
      cwd: frontendDir,
      env: {
        ...process.env,
        VITE_API_PROXY_TARGET: backendUrl,
      },
      url: e2eFrontendUrl,
      timeout: 120_000,
      reuseExistingServer: !process.env.CI,
      stdout: webServerOutput,
      stderr: webServerOutput,
    },
  ],
});
