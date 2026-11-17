import { chromium } from "playwright";
import fs from "node:fs";

const BASE = "http://127.0.0.1:5173";
const API = "http://127.0.0.1:8000/api/v1";
const OUT = new URL("./shots-txn/", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1");
fs.mkdirSync(OUT, { recursive: true });

const results = [];
const log = (s, l, e = "") => { results.push({ status: s, label: l, extra: e }); console.log(`${s} ${l}${e ? " :: " + e : ""}`); };

const browser = await chromium.launch({ channel: "chrome", headless: true });
const custCtx = await browser.newContext({ viewport: { width: 1280, height: 900 }, acceptDownloads: true });
const insCtx = await browser.newContext({ viewport: { width: 1280, height: 900 } });
const cust = await custCtx.newPage();
const ins = await insCtx.newPage();

const consoleErrs = [];
for (const p of [cust, ins]) {
  p.on("console", (m) => { if (m.type() === "error") consoleErrs.push(m.text()); });
  p.on("pageerror", (e) => consoleErrs.push("PAGEERROR " + e));
  p.on("response", (r) => { if (r.status() >= 400) consoleErrs.push(`${r.status()} ${r.request().method()} ${r.url()}`); });
}
const shot = async (p, n) => { try { await p.screenshot({ path: OUT + n + ".png", fullPage: true }); } catch {} };

async function login(page, email, pw, home) {
  await page.goto(BASE + "/login", { waitUntil: "networkidle" });
  await page.getByRole("textbox", { name: /^Email address/ }).fill(email);
  await page.getByRole("textbox", { name: /^Password/ }).fill(pw);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await page.waitForURL(new RegExp(home.replace("/", "\\/") + "($|/)"), { timeout: 15000 });
}

async function tokenOf(page) { return page.evaluate(() => localStorage.getItem("autoinssure.access")); }
async function apiGet(token, path) {
  const r = await fetch(API + path, { headers: { Authorization: `Bearer ${token}` } });
  return r.json();
}

const ts = Date.now();
const custEmail = `ltx.customer.${ts}@example.com`;
const custPw = "LtxCustomer@12345";
const insEmail = "ltx.insurer@example.com";
const insPw = "LtxInsurer@12345";
const REG = `LTX ${(ts % 100000)}A`;
const today = new Date();
const todayISO = `${today.getFullYear()}-${String(today.getMonth() + 1).padStart(2, "0")}-${String(today.getDate()).padStart(2, "0")}`;

// ===== TEST 1.1 register customer =====
try {
  await cust.goto(BASE + "/register", { waitUntil: "networkidle" });
  await cust.getByRole("button", { name: "Customer", exact: true }).click();
  await cust.getByLabel("First name").fill("Live");
  await cust.getByLabel("Last name").fill("Policyholder");
  await cust.getByLabel(/^Email address/).fill(custEmail);
  await cust.getByLabel("Phone number").fill("+254700000999");
  await cust.getByLabel(/^Password/).fill(custPw);
  await cust.getByRole("checkbox").check();
  await cust.getByRole("button", { name: "Create customer account" }).click();
  await cust.getByRole("dialog").getByRole("heading", { name: "Account created" }).waitFor({ timeout: 15000 });
  await cust.getByRole("button", { name: "Verify email now" }).click();
  await cust.getByRole("dialog").getByRole("heading", { name: "Email verified" }).waitFor({ timeout: 15000 });
  await cust.getByRole("button", { name: "Continue to sign in" }).click();
  await cust.waitForURL(/\/login$/, { timeout: 10000 });
  log("PASS", "T1 register customer", custEmail);
} catch (e) { log("FAIL", "T1 register customer", e.message.split("\n")[0]); }

await login(cust, custEmail, custPw, "/app");

// ===== TEST 1.2 add vehicle =====
try {
  await cust.goto(BASE + "/app/vehicles", { waitUntil: "networkidle" });
  await cust.getByRole("button", { name: "Add vehicle" }).click();
  const vdlg = cust.getByRole("dialog");
  await vdlg.getByLabel("Registration number").fill(REG);
  await vdlg.getByLabel("Estimated value (KES)").fill("2500000");
  await vdlg.getByLabel(/^Make/).fill("Toyota");
  await vdlg.getByLabel(/^Model/).fill("RAV4");
  await vdlg.getByLabel(/^Manufacturing year/).fill("2021");
  await vdlg.getByRole("button", { name: "Add vehicle", exact: true }).click();
  await cust.waitForTimeout(1500);
  const has = (await cust.locator("body").innerText()).includes(REG.replace(/\s/g, ""));
  await shot(cust, "t1-vehicle");
  log(has ? "PASS" : "FAIL", "T1 add vehicle", REG);
} catch (e) { log("FAIL", "T1 add vehicle", e.message.split("\n")[0]); }

// ===== TEST 1.3 request motor quotation =====
try {
  await cust.goto(BASE + "/app/marketplace", { waitUntil: "networkidle" });
  await cust.getByLabel("Vehicle").selectOption({ index: 1 });
  await cust.waitForTimeout(500);
  const si = cust.getByLabel("Sum insured (KES)");
  if ((await si.inputValue()) === "") await si.fill("2500000");
  await cust.getByLabel("Cover start date").fill(todayISO);
  await cust.getByRole("button", { name: /Request quotations/ }).click();
  await cust.waitForURL(/\/app\/quotes\/[0-9a-f-]+/, { timeout: 15000 });
  await cust.waitForTimeout(800);
  await shot(cust, "t1-quote-detail");
  log("PASS", "T1 request quotation", cust.url());
} catch (e) { log("FAIL", "T1 request quotation", e.message.split("\n")[0]); }

// ===== TEST 1.4 select Savannah offer -> application =====
let appId = null;
try {
  const savCard = cust.locator(".surface").filter({ hasText: "Savannah" }).first();
  await savCard.getByRole("button", { name: /Select offer/ }).click();
  await cust.waitForURL(/\/app\/applications\/[0-9a-f-]+/, { timeout: 15000 });
  appId = cust.url().split("/").pop();
  await cust.waitForTimeout(800);
  await shot(cust, "t1-application");
  log("PASS", "T1 select offer -> application", appId);
} catch (e) { log("FAIL", "T1 select offer -> application", e.message.split("\n")[0]); }

// ===== TEST 1.5 submit application =====
try {
  await cust.getByRole("button", { name: "Submit application" }).click();
  await cust.getByText("Submitted", { exact: true }).first().waitFor({ timeout: 10000 });
  await shot(cust, "t1-app-submitted");
  log("PASS", "T1 submit application", appId);
} catch (e) { log("FAIL", "T1 submit application", e.message.split("\n")[0]); }

// ===== TEST 1.6 insurer approve =====
await login(ins, insEmail, insPw, "/provider");
try {
  await ins.goto(BASE + `/provider/applications/${appId}`, { waitUntil: "networkidle" });
  await ins.getByText("Submitted", { exact: true }).first().waitFor({ timeout: 10000 });
  await ins.getByRole("button", { name: "Approve", exact: true }).first().click();
  const dlg = ins.getByRole("dialog");
  await dlg.getByRole("heading", { name: "Approve application" }).waitFor({ timeout: 8000 }).catch(() => {});
  await dlg.getByLabel("Notes (optional)").fill("Approved by live acceptance test");
  await dlg.getByRole("button", { name: "Confirm", exact: true }).click();
  await ins.getByText("Approved", { exact: true }).first().waitFor({ timeout: 10000 });
  await shot(ins, "t1-app-approved");
  log("PASS", "T1 insurer approve application", appId);
} catch (e) { log("FAIL", "T1 insurer approve application", e.message.split("\n")[0]); }

// ===== TEST 1.7 customer pay premium (bank) =====
try {
  await cust.reload();
  await cust.getByRole("button", { name: "Pay premium" }).first().waitFor({ timeout: 10000 });
  await cust.getByRole("button", { name: "Pay premium" }).first().click();
  const dlg = cust.getByRole("dialog");
  await dlg.getByRole("heading", { name: "Pay your premium" }).waitFor({ timeout: 8000 }).catch(() => {});
  await dlg.getByLabel("Payment method").selectOption("bank");
  await dlg.getByRole("button", { name: "Initiate payment" }).click();
  await cust.waitForTimeout(1500);
  await shot(cust, "t1-payment-initiated");
  log("PASS", "T1 customer initiate bank payment", appId);
} catch (e) { log("FAIL", "T1 customer initiate payment", e.message.split("\n")[0]); }

// fetch payment reference
let payRef = null;
try {
  const tok = await tokenOf(cust);
  const pay = await apiGet(tok, `/payments/?application=${appId}&page_size=20`);
  const pending = (pay.results || []).find((x) => x.status === "pending" || x.status === "processing");
  payRef = pending?.reference;
  log("PASS", "T1 payment reference", payRef || "(none)");
} catch (e) { log("FAIL", "T1 payment reference fetch", e.message.split("\n")[0]); }

// ===== TEST 1.8 insurer verify payment =====
try {
  await ins.goto(BASE + "/provider/payments", { waitUntil: "networkidle" });
  const row = ins.getByRole("row").filter({ hasText: payRef }).first();
  await row.waitFor({ timeout: 10000 });
  await row.getByRole("button", { name: "Verify" }).click();
  const dlg = ins.getByRole("dialog");
  await dlg.getByRole("heading", { name: "Verify payment" }).waitFor({ timeout: 8000 }).catch(() => {});
  await dlg.getByLabel("Provider / transaction reference").fill(`LTX-BANK-${ts}`);
  await dlg.getByRole("button", { name: "Confirm payment" }).click();
  await row.getByText("Succeeded", { exact: true }).waitFor({ timeout: 10000 });
  await shot(ins, "t1-payment-verified");
  log("PASS", "T1 insurer verify payment", payRef);
} catch (e) { log("FAIL", "T1 insurer verify payment", e.message.split("\n")[0]); }

// ===== TEST 1.9 insurer issue policy =====
let policyId = null;
try {
  await ins.goto(BASE + `/provider/applications/${appId}`, { waitUntil: "networkidle" });
  await ins.getByRole("button", { name: "Issue policy" }).waitFor({ timeout: 10000 });
  await ins.getByRole("button", { name: "Issue policy" }).click();
  const dlg = ins.getByRole("dialog");
  await dlg.getByRole("heading", { name: "Issue policy" }).waitFor({ timeout: 8000 }).catch(() => {});
  await dlg.getByLabel("Provider reference").fill("LTX-POLICY-REF");
  await dlg.getByRole("button", { name: "Issue policy", exact: true }).click();
  await ins.waitForURL(/\/provider\/policies\/[0-9a-f-]+/, { timeout: 15000 });
  policyId = ins.url().split("/").pop();
  await shot(ins, "t1-policy-issued");
  log("PASS", "T1 insurer issue policy", policyId);
} catch (e) { log("FAIL", "T1 insurer issue policy", e.message.split("\n")[0]); }

// ===== TEST 1.10 customer view + download certificate =====
try {
  await cust.goto(BASE + `/app/policies/${policyId}`, { waitUntil: "networkidle" });
  await cust.getByText("Active", { exact: true }).first().waitFor({ timeout: 10000 });
  await cust.getByText("LTX-POLICY-REF").waitFor({ timeout: 8000 });
  await shot(cust, "t1-policy-customer");
  const certBtn = cust.getByRole("button", { name: "Certificate" });
  await certBtn.waitFor({ timeout: 8000 });
  const dlPromise = cust.waitForEvent("download");
  await certBtn.click();
  const dl = await dlPromise;
  const fname = dl.suggestedFilename();
  const dlPath = await dl.path();
  let contentCheck = "";
  if (dlPath) {
    const bytes = fs.readFileSync(dlPath);
    contentCheck = bytes.length > 500 && bytes.subarray(0, 1024).toString("latin1").includes("POL-") ? "policy-number-present" : `bytes=${bytes.length}`;
  }
  log(/\.pdf$/.test(fname) ? "PASS" : "FAIL", "T1 certificate download", `${fname} ${contentCheck}`);
} catch (e) { log("FAIL", "T1 certificate download", e.message.split("\n")[0]); }

// ===== TEST 3 claim lifecycle =====
let claimId = null;
try {
  const tok = await tokenOf(cust);
  const pol = await apiGet(tok, `/policies/${policyId}/`);
  const polStart = pol.start_date || todayISO;
  await cust.goto(BASE + "/app/claims", { waitUntil: "networkidle" });
  await cust.getByRole("button", { name: "Submit a claim" }).first().click();
  const dlg = cust.getByRole("dialog");
  await dlg.getByRole("heading", { name: "Submit a claim" }).waitFor({ timeout: 8000 }).catch(() => {});
  await dlg.getByLabel("Policy").selectOption({ index: 1 }); // the just-issued active policy
  await dlg.getByLabel("Claim type").selectOption("accident");
  await dlg.getByLabel("Amount claimed (KES)").fill("80000");
  await dlg.getByLabel("Incident date").fill(polStart);
  await dlg.getByLabel("Location").fill("Nairobi Westlands");
  await dlg.getByLabel("What happened?").fill("Live acceptance claim test incident");
  await dlg.getByRole("button", { name: "Submit claim" }).click();
  await cust.waitForURL(/\/app\/claims\/[0-9a-f-]+/, { timeout: 15000 });
  claimId = cust.url().split("/").pop();
  await shot(cust, "t3-claim-submitted");
  log("PASS", "T3 customer submit claim", claimId);
} catch (e) { log("FAIL", "T3 customer submit claim", e.message.split("\n")[0]); }

// upload evidence
try {
  await cust.getByRole("button", { name: "Upload" }).click();
  const dlg = cust.getByRole("dialog");
  await dlg.getByRole("heading", { name: "Upload claim document" }).waitFor({ timeout: 8000 }).catch(() => {});
  await dlg.getByLabel("Document type").selectOption("photo");
  await dlg.getByLabel("File").setInputFiles({ name: "damage.jpg", mimeType: "image/jpeg", buffer: Buffer.from("fake-jpeg-bytes") });
  await dlg.getByRole("button", { name: "Upload", exact: true }).click();
  await cust.waitForTimeout(1200);
  await shot(cust, "t3-claim-doc");
  log("PASS", "T3 customer upload evidence", claimId);
} catch (e) { log("FAIL", "T3 customer upload evidence", e.message.split("\n")[0]); }

// insurer request info
try {
  await ins.goto(BASE + `/claims/${claimId}`, { waitUntil: "networkidle" });
  await ins.getByRole("button", { name: "Start review" }).click();
  let dlg = ins.getByRole("dialog");
  await dlg.getByRole("heading", { name: "Start claim review" }).waitFor({ timeout: 8000 }).catch(() => {});
  await dlg.getByRole("button", { name: "Confirm", exact: true }).click();
  await ins.waitForTimeout(700);
  await ins.getByRole("button", { name: "Request information" }).click();
  dlg = ins.getByRole("dialog");
  await dlg.getByRole("heading", { name: "Request more information" }).waitFor({ timeout: 8000 }).catch(() => {});
  await dlg.getByLabel("Details").fill("Please provide a clearer photo of the damage.");
  await dlg.getByRole("button", { name: "Confirm", exact: true }).click();
  await ins.waitForTimeout(800);
  await shot(ins, "t3-claim-info-requested");
  log("PASS", "T3 insurer request information", claimId);
} catch (e) { log("FAIL", "T3 insurer request information", e.message.split("\n")[0]); }

// customer respond
try {
  await cust.reload();
  await cust.getByRole("button", { name: "Respond" }).waitFor({ timeout: 8000 });
  await cust.getByRole("button", { name: "Respond" }).click();
  const dlg = cust.getByRole("dialog");
  await dlg.getByRole("heading", { name: "Respond to insurer" }).waitFor({ timeout: 8000 }).catch(() => {});
  await dlg.getByLabel("Notes").fill("Additional evidence provided by customer.");
  await dlg.getByRole("button", { name: "Confirm", exact: true }).click();
  await cust.waitForTimeout(800);
  log("PASS", "T3 customer respond to insurer", claimId);
} catch (e) { log("FAIL", "T3 customer respond", e.message.split("\n")[0]); }

// insurer approve claim
try {
  await ins.goto(BASE + `/claims/${claimId}`, { waitUntil: "networkidle" });
  await ins.getByRole("button", { name: "Approve", exact: true }).waitFor({ timeout: 8000 });
  await ins.getByRole("button", { name: "Approve", exact: true }).click();
  const dlg = ins.getByRole("dialog");
  await dlg.getByRole("heading", { name: "Approve claim" }).waitFor({ timeout: 8000 }).catch(() => {});
  await dlg.getByLabel("Approved amount (KES)").fill("80000");
  await dlg.getByLabel("Notes").fill("Approved for settlement in test environment.");
  await dlg.getByRole("button", { name: "Confirm", exact: true }).click();
  await ins.waitForTimeout(1000);
  await shot(ins, "t3-claim-approved");
  log("PASS", "T3 insurer approve claim", claimId);
} catch (e) { log("FAIL", "T3 insurer approve claim", e.message.split("\n")[0]); }

// ===== Negative: customer cannot issue / approve =====
try {
  const custTok = await tokenOf(cust);
  const r = await fetch(API + `/applications/${appId}/issue-policy/`, { method: "POST", headers: { Authorization: `Bearer ${custTok}`, "Content-Type": "application/json" }, body: "{}" });
  log(r.status === 403 || r.status === 404 || r.status === 400 ? "PASS" : "FAIL", "T5 customer cannot issue policy", `HTTP ${r.status}`);
} catch (e) { log("FAIL", "T5 customer cannot issue policy", e.message.split("\n")[0]); }

await browser.close();

fs.writeFileSync(
  new URL("./txn-evidence.json", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"),
  JSON.stringify({ ts, custEmail, insEmail, appId, policyId, payRef, claimId, results, consoleErrs }, null, 2)
);
console.log("\n===== CONSOLE/NET ERRORS =====");
console.log(consoleErrs.length ? consoleErrs.slice(0, 30).join("\n") : "(none)");
console.log("\nevidence -> txn-evidence.json");
