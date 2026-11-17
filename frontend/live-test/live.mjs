import { chromium } from "playwright";
import fs from "node:fs";

const BASE = "http://127.0.0.1:5173";
const OUT = new URL("./shots/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
fs.mkdirSync(OUT, { recursive: true });

const results = [];
function log(status, label, extra = "") {
  results.push({ status, label, extra });
  console.log(`${status} ${label}${extra ? " :: " + extra : ""}`);
}

const browser = await chromium.launch({ channel: "chrome", headless: true });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();

const consoleErrors = [];
const pageErrors = [];
const badResponses = [];
page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text()); });
page.on("pageerror", (e) => pageErrors.push(String(e)));
page.on("response", (r) => { if (r.status() >= 400) badResponses.push(`${r.status()} ${r.request().method()} ${r.url()}`); });

async function shot(name) { try { await page.screenshot({ path: OUT + name + ".png", fullPage: true }); } catch {} }

async function login(email, password, home) {
  await page.goto(BASE + "/login", { waitUntil: "networkidle" });
  await page.getByRole("textbox", { name: /^Email address/ }).fill(email);
  await page.getByRole("textbox", { name: /^Password/ }).fill(password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL(new RegExp(home.replace("/", "\\/") + "($|/)"), { timeout: 15000 });
}

async function logout() {
  await page.evaluate(() => localStorage.clear());
  await page.goto(BASE + "/login", { waitUntil: "networkidle" });
}

async function uiLogout() {
  // Click the user avatar menu, then "Sign out".
  await page.goto(BASE + "/profile", { waitUntil: "networkidle" });
  await page.locator("header").getByRole("button").first().click();
  await page.getByRole("button", { name: "Sign out" }).click();
  await page.waitForURL(/\/login/, { timeout: 10000 });
}

// --- 1. Landing + public pages ---
try {
  await page.goto(BASE + "/", { waitUntil: "networkidle" });
  await shot("01-landing-desktop");
  log("PASS", "landing", "title=" + (await page.title()));
} catch (e) { log("FAIL", "landing", e.message.split("\n")[0]); }

// --- 2. Registration (fresh customer) ---
const suffix = Date.now();
const regEmail = `live.customer.${suffix}@example.com`;
const regPw = "LiveCustomer@12345";
try {
  await page.goto(BASE + "/register", { waitUntil: "networkidle" });
  await page.getByRole("button", { name: "Customer", exact: true }).click();
  await page.getByLabel("First name").fill("Live");
  await page.getByLabel("Last name").fill("Tester");
  await page.getByLabel(/^Email address/).fill(regEmail);
  await page.getByLabel("Phone number").fill("+254700000123");
  await page.getByLabel(/^Password/).fill(regPw);
  await page.getByRole("checkbox").check();
  await page.getByRole("button", { name: "Create customer account" }).click();
  await page.getByRole("dialog").getByRole("heading", { name: "Account created" }).waitFor({ timeout: 15000 });
  await shot("02-register-created");
  await page.getByRole("button", { name: "Verify email now" }).click();
  await page.getByRole("dialog").getByRole("heading", { name: "Email verified" }).waitFor({ timeout: 15000 });
  await page.getByRole("button", { name: "Continue to sign in" }).click();
  await page.waitForURL(/\/login$/, { timeout: 10000 });
  log("PASS", "register customer", regEmail);
} catch (e) { log("FAIL", "register customer", e.message.split("\n")[0]); }

// --- 3. Login as each role ---
const roles = [
  ["customer", "customer@example.com", "Customer@12345", "/app"],
  ["provider_admin", "insurer@example.com", "Insurer@12345", "/provider"],
  ["provider_staff", "staff@example.com", "Staff@12345", "/provider"],
  ["claims_officer", "claims@example.com", "Claims@12345", "/claims"],
  ["inspector", "inspector@example.com", "Inspector@12345", "/inspector"],
  ["agent", "agent@example.com", "Agent@12345", "/agent"],
  ["admin", "admin@autoinssure.local", "Admin@12345", "/admin"],
];
for (const [role, email, pw, home] of roles) {
  const before = consoleErrors.length + pageErrors.length;
  try {
    await login(email, pw, home);
    const url = page.url();
    await page.waitForTimeout(1500);
    await shot(`03-${role}`);
    log("PASS", `login ${role}`, url);
  } catch (e) {
    log("FAIL", `login ${role}`, e.message.split("\n")[0]);
  }
  await logout();
}

// --- 4. Marketplace categories (customer) ---
try {
  await login("customer@example.com", "Customer@12345", "/app");
  await page.goto(BASE + "/app/marketplace", { waitUntil: "networkidle" });
  const body = await page.content();
  const hasLive = body.includes("Live");
  const hasExpanding = body.includes("Expanding");
  await shot("04-marketplace");
  log(hasLive && hasExpanding ? "PASS" : "FAIL", "marketplace categories", `live=${hasLive} expanding=${hasExpanding}`);
} catch (e) { log("FAIL", "marketplace categories", e.message.split("\n")[0]); }

// --- 5. Customer dashboard pages ---
try {
  for (const [name, path] of [["vehicles", "/app/vehicles"], ["policies", "/app/policies"], ["claims", "/app/claims"], ["payments", "/app/payments"], ["profile", "/profile"], ["notifications", "/notifications"]]) {
    await page.goto(BASE + path, { waitUntil: "networkidle" });
    await page.waitForTimeout(800);
    await shot(`05-cust-${name}`);
    log("PASS", `customer ${name}`, path);
  }
} catch (e) { log("FAIL", "customer dashboard pages", e.message.split("\n")[0]); }
await logout();

// --- 6. Provider dashboard pages ---
try {
  await login("insurer@example.com", "Insurer@12345", "/provider");
  for (const [name, path] of [["products", "/provider/products"], ["quotes", "/provider/quotes"], ["applications", "/provider/applications"], ["policies", "/provider/policies"], ["payments", "/provider/payments"], ["network", "/provider/network"], ["settings", "/provider/settings"]]) {
    await page.goto(BASE + path, { waitUntil: "networkidle" });
    await page.waitForTimeout(800);
    await shot(`06-prov-${name}`);
    log("PASS", `provider ${name}`, path);
  }
} catch (e) { log("FAIL", "provider dashboard pages", e.message.split("\n")[0]); }
await logout();

// --- 7. Admin dashboard pages ---
try {
  await login("admin@autoinssure.local", "Admin@12345", "/admin");
  for (const [name, path] of [["users", "/admin/users"], ["organizations", "/admin/organizations"], ["audit", "/admin/audit"], ["settings", "/admin/settings"]]) {
    await page.goto(BASE + path, { waitUntil: "networkidle" });
    await page.waitForTimeout(800);
    await shot(`07-admin-${name}`);
    log("PASS", `admin ${name}`, path);
  }
} catch (e) { log("FAIL", "admin dashboard pages", e.message.split("\n")[0]); }
await logout();

// --- 8. Negative / security ---
try {
  await page.goto(BASE + "/app", { waitUntil: "networkidle" });
  const unauthUrl = page.url();
  log(unauthUrl.includes("/login") ? "PASS" : "FAIL", "unauth /app redirect", unauthUrl);
} catch (e) { log("FAIL", "unauth /app redirect", e.message.split("\n")[0]); }

try {
  await login("customer@example.com", "Customer@12345", "/app");
  await page.goto(BASE + "/admin", { waitUntil: "networkidle" });
  const url = page.url();
  log(!url.includes("/admin") ? "PASS" : "FAIL", "customer blocked from /admin", url);
  await shot("08-neg-customer-admin");
} catch (e) { log("FAIL", "customer blocked from /admin", e.message.split("\n")[0]); }
await logout();

// --- 8b. UI logout (single role) ---
try {
  await login("customer@example.com", "Customer@12345", "/app");
  await uiLogout();
  log("PASS", "ui logout (avatar -> Sign out)", page.url());
} catch (e) { log("FAIL", "ui logout", e.message.split("\n")[0]); }

// --- 9. Responsive ---
try {
  for (const [w, h, tag] of [[390, 844, "mobile"], [820, 1180, "tablet"], [1440, 900, "desktop"]]) {
    await page.setViewportSize({ width: w, height: h });
    await page.goto(BASE + "/", { waitUntil: "networkidle" });
    await shot(`09-landing-${tag}`);
  }
  log("PASS", "responsive viewports", "390x844 / 820x1180 / 1440x900");
} catch (e) { log("FAIL", "responsive viewports", e.message.split("\n")[0]); }

await browser.close();

console.log("\n===== SUMMARY =====");
console.log("console errors:", consoleErrors.length);
consoleErrors.slice(0, 30).forEach((e) => console.log("  CE:", e));
console.log("page errors:", pageErrors.length);
pageErrors.slice(0, 10).forEach((e) => console.log("  PE:", e));
console.log("4xx/5xx responses:", badResponses.length);
badResponses.slice(0, 40).forEach((e) => console.log("  HTTP:", e));

fs.writeFileSync(
  new URL("./live-results.json", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"),
  JSON.stringify({ results, consoleErrors, pageErrors, badResponses }, null, 2)
);
console.log("\nresults written to live-results.json");
