import { chromium } from "playwright";
import fs from "node:fs";

const BASE = "http://127.0.0.1:5173";
const OUT = new URL("./shots/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
fs.mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ channel: "chrome", headless: true });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();
const consoleErrors = [], badResponses = [];
page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text()); });
page.on("response", (r) => { if (r.status() >= 400) badResponses.push(`${r.status()} ${r.request().method()} ${r.url()}`); });

function log(s, l, e = "") { console.log(`${s} ${l}${e ? " :: " + e : ""}`); }

// Wait out the login throttle window (10/min per IP).
log("INFO", "waiting 65s for login throttle window to clear");
await page.waitForTimeout(65000);

async function login(email, pw, home) {
  await page.goto(BASE + "/login", { waitUntil: "networkidle" });
  await page.getByRole("textbox", { name: /^Email address/ }).fill(email);
  await page.getByRole("textbox", { name: /^Password/ }).fill(pw);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL(new RegExp(home.replace("/", "\\/") + "($|/)"), { timeout: 15000 });
}

// Admin dashboard pages
try {
  await login("admin@autoinssure.local", "Admin@12345", "/admin");
  for (const [name, path] of [["users", "/admin/users"], ["organizations", "/admin/organizations"], ["audit", "/admin/audit"], ["settings", "/admin/settings"]]) {
    await page.goto(BASE + path, { waitUntil: "networkidle" });
    await page.waitForTimeout(800);
    await page.screenshot({ path: OUT + `07-admin-${name}.png`, fullPage: true });
    log("PASS", `admin ${name}`, path);
  }
} catch (e) { log("FAIL", "admin dashboard pages", e.message.split("\n")[0]); }

// UI logout (customer) via avatar -> Sign out
await page.evaluate(() => localStorage.clear());
try {
  await login("customer@example.com", "Customer@12345", "/app");
  await page.goto(BASE + "/profile", { waitUntil: "networkidle" });
  const avatar = page.locator("header").locator("button").filter({ has: page.locator("svg.lucide-chevron-down") });
  await avatar.click();
  await page.getByRole("button", { name: "Sign out" }).click();
  await page.waitForURL(/\/login/, { timeout: 10000 });
  const cleared = await page.evaluate(() => !localStorage.getItem("autoinssure.access"));
  log(cleared ? "PASS" : "FAIL", "ui logout (avatar -> Sign out)", `url=${page.url()} tokenCleared=${cleared}`);
} catch (e) { log("FAIL", "ui logout", e.message.split("\n")[0]); }

// Agent / inspector / claims dashboards (remaining roles not yet screenshotted)
for (const [role, email, pw, home, path] of [
  ["agent", "agent@example.com", "Agent@12345", "/agent", "/agent/commissions"],
  ["inspector", "inspector@example.com", "Inspector@12345", "/inspector", "/inspector/inspections"],
  ["claims_officer", "claims@example.com", "Claims@12345", "/claims", "/claims"],
]) {
  await page.evaluate(() => localStorage.clear());
  try {
    await login(email, pw, home);
    await page.goto(BASE + path, { waitUntil: "networkidle" });
    await page.waitForTimeout(800);
    await page.screenshot({ path: OUT + `03-${role}.png`, fullPage: true });
    log("PASS", `${role} page`, path);
  } catch (e) { log("FAIL", `${role} page`, e.message.split("\n")[0]); }
}

await browser.close();
console.log("\n===== SUMMARY =====");
console.log("console errors:", consoleErrors.length);
consoleErrors.forEach((e) => console.log("  CE:", e));
console.log("4xx/5xx:", badResponses.length);
badResponses.forEach((e) => console.log("  HTTP:", e));
