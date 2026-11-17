import { chromium } from "playwright";

const BASE = "http://127.0.0.1:5173";
const browser = await chromium.launch({ channel: "chrome", headless: true });
const page = await (await browser.newContext({ viewport: { width: 1280, height: 900 } })).newPage();
const consoleErrors = [], badResponses = [];
page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text()); });
page.on("response", (r) => { if (r.status() >= 400) badResponses.push(`${r.status()} ${r.request().method()} ${r.url()}`); });
const log = (s, l, e = "") => console.log(`${s} ${l}${e ? " :: " + e : ""}`);

async function login() {
  await page.goto(BASE + "/login", { waitUntil: "networkidle" });
  await page.getByRole("textbox", { name: /^Email address/ }).fill("customer@example.com");
  await page.getByRole("textbox", { name: /^Password/ }).fill("Customer@12345");
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL(/\/app/, { timeout: 15000 });
}

try {
  await login();
  // Vehicles list should render seeded backend data
  await page.goto(BASE + "/app/vehicles", { waitUntil: "networkidle" });
  await page.waitForTimeout(1000);
  const vText = await page.locator("body").innerText();
  const hasKda = vText.includes("KDA 123A");
  const hasKcx = vText.includes("KCX 456B");
  log(hasKda && hasKcx ? "PASS" : "FAIL", "customer vehicles render seeded data", `KDA123A=${hasKda} KCX456B=${hasKcx}`);

  // Quotes list
  await page.goto(BASE + "/app/quotes", { waitUntil: "networkidle" });
  await page.waitForTimeout(1000);
  const qText = await page.locator("body").innerText();
  log(qText.includes("QR-DEMO") ? "PASS" : "FAIL", "customer quotes render seeded data", "QR-DEMO present");

  // Applications list
  await page.goto(BASE + "/app/applications", { waitUntil: "networkidle" });
  await page.waitForTimeout(1000);
  const aText = await page.locator("body").innerText();
  log(aText.includes("APP-DEMO") ? "PASS" : "FAIL", "customer applications render seeded data", "APP-DEMO present");
} catch (e) { log("FAIL", "data-render check", e.message.split("\n")[0]); }

await browser.close();
console.log("\nconsole errors:", consoleErrors.length, "| 4xx/5xx:", badResponses.length);
consoleErrors.forEach((e) => console.log("  CE:", e));
badResponses.forEach((e) => console.log("  HTTP:", e));
