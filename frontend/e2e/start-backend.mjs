import { spawn, spawnSync } from "node:child_process";
import path from "node:path";
import { fileURLToPath } from "node:url";
import {
  backendDir,
  backendEnv,
  databasePath,
  mediaPath,
  python,
} from "./backend-config.mjs";

const here = path.dirname(fileURLToPath(import.meta.url));
const prepare = spawnSync(process.execPath, [path.join(here, "prepare-backend.mjs")], {
  stdio: "inherit",
});

if (prepare.error) {
  console.error(`E2E backend preparation failed: ${prepare.error.message}`);
  process.exit(1);
}
if (prepare.status !== 0) {
  process.exit(prepare.status || 1);
}

const server = spawn(
  python,
  ["manage.py", "runserver", "127.0.0.1:8001", "--noreload", "--skip-checks"],
  {
    cwd: backendDir,
    env: backendEnv(),
    stdio: "inherit",
  }
);

let stopping = false;

function stop() {
  if (stopping || !server.pid) return;
  stopping = true;

  if (process.platform === "win32") {
    spawnSync("taskkill", ["/pid", String(server.pid), "/t", "/f"], { stdio: "ignore" });
    return;
  }

  server.kill("SIGTERM");
}

process.on("SIGINT", stop);
process.on("SIGTERM", stop);
process.on("exit", stop);

server.on("error", (error) => {
  console.error(`E2E backend failed to start: ${error.message}`);
  process.exit(1);
});

server.on("exit", (code) => {
  process.exit(code ?? 0);
});

console.log(`E2E backend: ${python} manage.py runserver 127.0.0.1:8001`);
console.log(`Database: ${databasePath}`);
console.log(`Media: ${mediaPath}`);
