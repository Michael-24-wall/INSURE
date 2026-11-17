import fs from "node:fs";
const API = "http://127.0.0.1:8000/api/v1";
const results = [];
const log = (s, l, e = "") => { results.push({ status: s, label: l, extra: e }); console.log(`${s} ${l}${e ? " :: " + e : ""}`); };

async function login(email, pw) {
  const r = await fetch(API + "/auth/login/", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ email, password: pw }) });
  const b = await r.json();
  return b.access;
}
async function api(method, path, token, body) {
  const r = await fetch(API + path, { method, headers: { Authorization: `Bearer ${token}`, "Content-Type": "application/json" }, body: body ? JSON.stringify(body) : undefined });
  return r;
}

const ltxCust = await login("ltx.customer.1794908219083@example.com", "LtxCustomer@12345");
const demoCust = await login("customer@example.com", "Customer@12345");
const insurer = await login("ltx.insurer@example.com", "LtxInsurer@12345");

// get the ltx customer's own policy + the demo customer's policy
const ltxPol = (await api("GET", "/policies/?page_size=100", ltxCust)).status;
const demoPolicies = await (await api("GET", "/policies/?page_size=100", demoCust)).json();
const demoPolicy = demoPolicies.results?.find((p) => p.status === "active");
const ownPolicies = await (await api("GET", "/policies/?page_size=100", ltxCust)).json();
const ownPolicy = ownPolicies.results?.find((p) => p.status === "active");

// N1: customer cannot read another customer's policy
{
  const r = await api("GET", `/policies/${demoPolicy?.id}/`, ltxCust);
  log(r.status === 404 ? "PASS" : "FAIL", "N1 customer read other customer policy", `HTTP ${r.status}`);
}
// N2: customer cannot submit claim against another customer's policy
{
  const r = await api("POST", "/claims/", ltxCust, { policy: demoPolicy?.id, claim_type: "accident", incident_date: "2026-11-18", location: "X", description: "x", amount_claimed: 1000 });
  log(r.status === 400 || r.status === 403 || r.status === 404 ? "PASS" : "FAIL", "N2 claim against unrelated policy", `HTTP ${r.status}`);
}
// N3: insurer cannot read another insurer's application (Highland's)
{
  // find a Highland application via demo data: use a known application id from an earlier run
  const r = await api("GET", "/applications/?page_size=100", insurer);
  // ltx insurer (Savannah) can only list Savannah apps; verify none of the listed apps belong to Highland
  const body = await r.json();
  const leaked = (body.results || []).some((a) => a.insurer_name && a.insurer_name.includes("Highland"));
  log(!leaked && r.ok ? "PASS" : "FAIL", "N3 insurer sees only own insurer applications", leaked ? "LEAK: Highland app visible" : `HTTP ${r.status}`);
}
// N4: issue policy before verified payment (fresh app without payment)
{
  // use the ltx customer's already-issued app would be wrong; instead assert the issue endpoint requires APPROVED+paid via a submitted app
  const ownApps = await (await api("GET", "/applications/?page_size=100", ltxCust)).json();
  const sub = (ownApps.results || []).find((a) => a.status === "submitted");
  if (sub) {
    const r = await api("POST", `/applications/${sub.id}/issue-policy/`, insurer, { provider_reference: "X" });
    log(r.status >= 400 ? "PASS" : "FAIL", "N4 issue before approval/payment", `HTTP ${r.status}`);
  } else {
    log("NOT TESTED", "N4 issue before approval/payment", "no submitted application available");
  }
}
// N5: customer cannot approve a claim (claims are processed by insurer)
{
  const ownClaims = await (await api("GET", "/claims/?page_size=100", ltxCust)).json();
  const c = (ownClaims.results || [])[0];
  if (c) {
    const r = await api("POST", `/claims/${c.id}/approve/`, ltxCust, { approved_amount: 1, notes: "x" });
    log(r.status === 403 || r.status === 404 ? "PASS" : "FAIL", "N5 customer cannot approve claim", `HTTP ${r.status}`);
  } else log("NOT TESTED", "N5 customer cannot approve claim", "no claim");
}
// N6: manipulating a non-existent ID returns 404
{
  const r = await api("GET", "/policies/00000000-0000-0000-0000-000000000000/", ltxCust);
  log(r.status === 404 ? "PASS" : "FAIL", "N6 non-existent ID -> 404", `HTTP ${r.status}`);
}

fs.writeFileSync(new URL("./negative-results.json", import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"), JSON.stringify(results, null, 2));
console.log("\ndone");
