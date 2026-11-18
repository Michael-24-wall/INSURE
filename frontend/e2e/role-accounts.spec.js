import { readFileSync } from "node:fs";
import path from "node:path";
import { expect, test } from "@playwright/test";
import { backendDir } from "./backend-config.mjs";
import { apiLogin, bearer, newLoggedInPage } from "./helpers";

const credentials = JSON.parse(
  readFileSync(path.join(backendDir, ".test-accounts.e2e.json"), "utf8")
).accounts.filter((account) => account.password);

for (const account of credentials) {
  test(`${account.label} can sign in and reach its workspace`, async ({ browser, request }) => {
    const session = await newLoggedInPage(browser, account);
    await expect(session.page).toHaveURL(new RegExp(`${account.home.replace("/", "\\/")}($|/)`));
    await expect(session.page.getByText(account.role_label, { exact: true }).first()).toBeVisible();

    const token = await apiLogin(request, account);
    const response = await request.get("/api/v1/auth/me/", { headers: bearer(token) });
    expect(response.ok(), `GET /auth/me/ failed for ${account.email}`).toBeTruthy();
    expect((await response.json()).role).toBe(account.role);

    await session.context.close();
  });
}

test("finance test account cannot access platform-only ledger controls", async ({ request }) => {
  const finance = credentials.find((account) => account.key === "finance");
  const customer = credentials.find((account) => account.key === "customer");
  expect(finance && customer).toBeTruthy();

  const financeToken = await apiLogin(request, finance);
  const dashboard = await request.get("/api/v1/finance/dashboard/", {
    headers: bearer(financeToken),
  });
  expect(dashboard.status()).toBe(200);

  const ledger = await request.get("/api/v1/finance/ledger/balances/", {
    headers: bearer(financeToken),
  });
  expect(ledger.status()).toBe(403);

  const customerToken = await apiLogin(request, customer);
  const customerLedger = await request.get("/api/v1/finance/ledger/balances/", {
    headers: bearer(customerToken),
  });
  expect(customerLedger.status()).toBe(403);
});
