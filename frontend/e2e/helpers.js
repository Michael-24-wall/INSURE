import { expect } from "@playwright/test";

export const ACCOUNTS = {
  admin: { email: "e2e.admin@example.com", password: "E2eAdmin@12345", home: "/admin" },
  customer: { email: "e2e.customer@example.com", password: "E2eCustomer@12345", home: "/app" },
  customer2: { email: "e2e.customer2@example.com", password: "E2eCustomer@12345", home: "/app" },
  provider: { email: "e2e.provider@example.com", password: "E2eProvider@12345", home: "/provider" },
  dealer: { email: "e2e.dealer@example.com", password: "E2eDealer@12345", home: "/dealer" },
};

export async function login(page, account) {
  await page.goto("/login");
  await page.getByRole("textbox", { name: /^Email address/ }).fill(account.email);
  await page.getByRole("textbox", { name: /^Password/ }).fill(account.password);
  await page.getByRole("button", { name: "Sign in", exact: true }).click();
  await expect(page).toHaveURL(new RegExp(`${account.home.replace("/", "\\/")}($|/)`));
}

export async function newLoggedInPage(browser, account) {
  const context = await browser.newContext();
  const page = await context.newPage();
  await login(page, account);
  return { context, page };
}

export async function apiLogin(request, account) {
  const response = await request.post("/api/v1/auth/login/", {
    data: { email: account.email, password: account.password },
  });
  expect(response.ok(), `API login failed for ${account.email}: ${await response.text()}`).toBeTruthy();
  const body = await response.json();
  expect(body.otp_required).toBeFalsy();
  return body.access;
}

export function bearer(token) {
  return { Authorization: `Bearer ${token}` };
}

export async function listResult(request, token, url) {
  const response = await request.get(url, { headers: bearer(token) });
  expect(response.ok(), `GET ${url} failed: ${await response.text()}`).toBeTruthy();
  return response.json();
}

export async function waitForApi(request, token, url, predicate, timeout = 15_000) {
  const started = Date.now();
  let last;
  while (Date.now() - started < timeout) {
    last = await listResult(request, token, url);
    if (predicate(last)) return last;
    await new Promise((resolve) => setTimeout(resolve, 250));
  }
  throw new Error(`Timed out waiting for ${url}; last response: ${JSON.stringify(last)}`);
}

export async function registerViaUi(page, type, form) {
  await page.goto("/register");
  const label = type === "provider" ? "Insurer" : type === "dealer" ? "Dealership" : "Customer";
  await page.getByRole("button", { name: label, exact: true }).click();
  await page.getByLabel("First name").fill(form.firstName);
  await page.getByLabel("Last name").fill(form.lastName);
  await page.getByLabel(/^Email address/).fill(form.email);
  await page.getByLabel("Phone number").fill("+254700000123");
  await page.getByLabel(/^Password/).fill(form.password);
  if (form.organizationName) {
    const orgLabel = type === "dealer" ? "Registered dealership name" : "Registered company name";
    await page.getByLabel(orgLabel).fill(form.organizationName);
    await page.getByLabel("Your position").fill("E2E Manager");
  }
  await page.getByRole("checkbox").check();
  const button = type === "provider" ? "Create provider account" : type === "dealer" ? "Create dealership account" : "Create customer account";
  await page.getByRole("button", { name: button }).click();
  await expect(page.getByRole("dialog").getByRole("heading", { name: "Account created" })).toBeVisible();
  await page.getByRole("button", { name: "Verify email now" }).click();
  await expect(page.getByRole("dialog").getByRole("heading", { name: "Email verified" })).toBeVisible();
  await page.getByRole("button", { name: "Continue to sign in" }).click();
  await expect(page).toHaveURL(/\/login$/);
}

export async function verifyOrganizationViaUi(page, organizationName) {
  await page.goto("/admin/organizations");
  await page.getByPlaceholder("Search organizations").fill(organizationName);
  const row = page.getByRole("row").filter({ hasText: organizationName });
  await expect(row).toBeVisible();
  await row.getByRole("button", { name: "Verify" }).click();
  const dialog = page.getByRole("dialog");
  await expect(dialog.getByRole("heading", { name: "Verify organization" })).toBeVisible();
  await dialog.getByRole("button", { name: "Verify", exact: true }).click();
  await expect(row.getByText("Verified", { exact: true })).toBeVisible();
}
