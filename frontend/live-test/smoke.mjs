import { chromium } from "playwright";
import fs from "node:fs";

const BASE = "http://127.0.0.1:5173";
const OUT = new URL("./shots/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
fs.mkdirSync(OUT, { recursive: true });

const browser = await chromium.launch({ channel: "chrome", headless: true });
const ctx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const page = await ctx.newPage();

const consoleErrors = [];
const pageErrors = [];
const failedRequests = [];
page.on("console", (m) => { if (m.type() === "error") consoleErrors.push(m.text()); });
page.on("pageerror", (e) => pageErrors.push(String(e)));
page.on("requestfailed", (r) => failedRequests.push(`${r.method()} ${r.url()} ${r.failure()?.errorText}`));
page.on("response", (r) => { if (r.status() >= 400) failedRequests.push(`${r.request().method()} ${r.url()} -> ${r.status()}`); });

async function visit(name, path) {
  try {
    const resp = await page.goto(BASE + path, { waitUntil: "networkidle", timeout: 30000 });
    const title = await page.title().catch(() => "");
    await page.screenshot({ path: OUT + name + ".png", fullPage: true });
    console.log(`PASS goto ${name} (${path}) status=${resp?.status()} title="${title}"`);
  } catch (e) {
    console.log(`FAIL goto ${name} (${path}): ${e.message?.split("\n")[0]}`);
  }
}

await visit("landing", "/");
await visit("login", "/login");
await visit("register", "/register");

console.log("--- console errors ---");
console.log(consoleErrors.length ? consoleErrors.join("\n") : "(none)");
console.log("--- page errors ---");
console.log(pageErrors.length ? pageErrors.join("\n") : "(none)");
console.log("--- failed/4xx requests ---");
console.log(failedRequests.length ? failedRequests.join("\n") : "(none)");

await browser.close();
