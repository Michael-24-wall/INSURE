import { spawnSync } from "node:child_process";
import { existsSync, mkdirSync, rmSync } from "node:fs";
import {
  backendDir,
  backendEnv,
  backendHealthUrl,
  databasePath,
  mediaPath,
  python,
} from "./backend-config.mjs";

if (!existsSync(python)) {
  console.error(`Python interpreter not found: ${python}`);
  process.exit(1);
}

const env = backendEnv();

async function backendIsReady() {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 2_000);
  try {
    const response = await fetch(backendHealthUrl, { signal: controller.signal });
    return response.ok;
  } catch {
    return false;
  } finally {
    clearTimeout(timeout);
  }
}

function run(args, label) {
  const result = spawnSync(python, args, { cwd: backendDir, env, stdio: "inherit" });
  if (result.error) {
    console.error(`${label} failed: ${result.error.message}`);
    process.exit(1);
  }
  if (result.status !== 0) {
    console.error(`${label} failed with exit code ${result.status ?? "unknown"}.`);
    process.exit(result.status || 1);
  }
}

const existingBackend = await backendIsReady();

if (existingBackend) {
  console.log("Existing E2E backend detected; reseeding its isolated database.");
} else {
  rmSync(databasePath, { force: true });
  rmSync(mediaPath, { recursive: true, force: true });
  mkdirSync(mediaPath, { recursive: true });
}

run(["manage.py", "migrate", "--noinput"], "migrate");
run(["manage.py", "seed_e2e"], "seed_e2e");
run(["manage.py", "seed_test_accounts"], "seed_test_accounts");
