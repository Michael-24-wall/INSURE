import { expect, test } from "@playwright/test";
import {
  ACCOUNTS,
  apiLogin,
  bearer,
  listResult,
  login,
  newLoggedInPage,
  waitForApi,
} from "./helpers";

test("customer application moves from quotation to paid and issued policy", async ({ browser, request, page }) => {
  const customerToken = await apiLogin(request, ACCOUNTS.customer);
  const requests = await listResult(request, customerToken, "/api/v1/quotation-requests/?search=QR-E2E-CUSTOMER&page_size=100");
  const quoteRequest = requests.results.find((item) => item.request_number === "QR-E2E-CUSTOMER");
  expect(quoteRequest, "seed quotation request should exist").toBeTruthy();

  const provider = await newLoggedInPage(browser, ACCOUNTS.provider);

  await login(page, ACCOUNTS.customer);
  await page.goto(`/app/quotes/${quoteRequest.id}`);
  await expect(page.getByRole("heading", { name: "Comprehensive cover" })).toBeVisible();
  await expect(page.getByText("E2E Comprehensive Cover")).toBeVisible();

  await page.getByRole("button", { name: /Select offer/ }).click();
  await expect(page).toHaveURL(/\/app\/applications\/[0-9a-f-]+/);
  const applicationId = page.url().split("/").pop();
  await expect(page.getByRole("heading", { name: /KDE 100E/ })).toBeVisible();

  await page.getByRole("button", { name: "Submit application" }).click();
  await expect(page.getByText("Submitted", { exact: true }).first()).toBeVisible();
  await waitForApi(
    request,
    customerToken,
    `/api/v1/applications/${applicationId}/`,
    (app) => app.status === "submitted"
  );

  await provider.page.goto(`/provider/applications/${applicationId}`);
  await expect(provider.page.getByText("Submitted", { exact: true }).first()).toBeVisible();
  await provider.page.getByRole("button", { name: "Approve", exact: true }).first().click();
  const approveDialog = provider.page.getByRole("dialog");
  await expect(approveDialog.getByRole("heading", { name: "Approve application" })).toBeVisible();
  await approveDialog.getByLabel("Notes (optional)").fill("E2E approval");
  await approveDialog.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(provider.page.getByText("Approved", { exact: true }).first()).toBeVisible();

  await page.reload();
  await expect(page.getByRole("button", { name: "Pay premium" }).first()).toBeVisible();
  await page.getByRole("button", { name: "Pay premium" }).first().click();
  const paymentDialog = page.getByRole("dialog");
  await expect(paymentDialog.getByRole("heading", { name: "Pay your premium" })).toBeVisible();
  await paymentDialog.getByLabel("Payment method").selectOption("bank");
  await paymentDialog.getByRole("button", { name: "Initiate payment" }).click();

  const pending = await waitForApi(
    request,
    customerToken,
    `/api/v1/payments/?application=${applicationId}&page_size=20`,
    (data) => data.results.some((item) => item.status === "pending" || item.status === "processing")
  );
  const payment = pending.results.find((item) => item.status === "pending" || item.status === "processing");
  expect(payment).toBeTruthy();

  await provider.page.goto("/provider/payments");
  const paymentRow = provider.page.getByRole("row").filter({ hasText: payment.reference });
  await expect(paymentRow).toBeVisible();
  await paymentRow.getByRole("button", { name: "Verify" }).click();
  const verifyDialog = provider.page.getByRole("dialog");
  await expect(verifyDialog.getByRole("heading", { name: "Verify payment" })).toBeVisible();
  await verifyDialog.getByLabel("Provider / transaction reference").fill(`E2E-BANK-${Date.now()}`);
  await verifyDialog.getByRole("button", { name: "Confirm payment" }).click();
  await expect(paymentRow.getByText("Succeeded", { exact: true })).toBeVisible();

  await provider.page.goto(`/provider/applications/${applicationId}`);
  await expect(provider.page.getByRole("button", { name: "Issue policy" })).toBeVisible();
  await provider.page.getByRole("button", { name: "Issue policy" }).click();
  const issueDialog = provider.page.getByRole("dialog");
  await expect(issueDialog.getByRole("heading", { name: "Issue policy" })).toBeVisible();
  await issueDialog.getByLabel("Provider reference").fill("E2E-POLICY-REF");
  await issueDialog.getByRole("button", { name: "Issue policy" }).click();
  await expect(provider.page).toHaveURL(/\/provider\/policies\/[0-9a-f-]+/);
  const policyId = provider.page.url().split("/").pop();
  await expect(provider.page.getByRole("button", { name: "Certificate" })).toBeVisible();

  await page.goto(`/app/policies/${policyId}`);
  await expect(page.getByText("Active", { exact: true }).first()).toBeVisible();
  await expect(page.getByText("E2E-POLICY-REF")).toBeVisible();
  const certificate = page.getByRole("button", { name: "Certificate" });
  await expect(certificate).toBeVisible();
  const downloadPromise = page.waitForEvent("download");
  await certificate.click();
  const download = await downloadPromise;
  expect(download.suggestedFilename()).toMatch(/\.pdf$/);
  await download.delete();

  const policy = await listResult(request, customerToken, `/api/v1/policies/${policyId}/`);
  expect(policy.status).toBe("active");
  expect(policy.provider_reference).toBe("E2E-POLICY-REF");

  await provider.context.close();
});

test("RBAC and tenant isolation are enforced by the API", async ({ request }) => {
  const adminToken = await apiLogin(request, ACCOUNTS.admin);
  const customerToken = await apiLogin(request, ACCOUNTS.customer);
  const customer2Token = await apiLogin(request, ACCOUNTS.customer2);
  const dealerToken = await apiLogin(request, ACCOUNTS.dealer);

  const allRequests = await listResult(request, adminToken, "/api/v1/quotation-requests/?page_size=100");
  const allApplications = await listResult(request, adminToken, "/api/v1/applications/?page_size=100");
  const allVehicles = await listResult(request, adminToken, "/api/v1/vehicles/?page_size=100");

  const otherRequest = allRequests.results.find((item) => item.request_number === "QR-E2E-CUSTOMER2");
  const otherApplication = allApplications.results.find((item) => item.application_number === "APP-E2E-CUSTOMER2");
  const otherVehicle = allVehicles.results.find((item) => item.registration_number === "KDE 200F");
  expect(otherRequest && otherApplication && otherVehicle).toBeTruthy();

  for (const url of [
    `/api/v1/quotation-requests/${otherRequest.id}/`,
    `/api/v1/applications/${otherApplication.id}/`,
    `/api/v1/vehicles/${otherVehicle.id}/`,
  ]) {
    const response = await request.get(url, { headers: bearer(customerToken) });
    expect(response.status(), `${url} must be hidden from another customer`).toBe(404);
  }

  const ownRequest = (await listResult(request, customer2Token, "/api/v1/quotation-requests/?search=QR-E2E-CUSTOMER2&page_size=100")).results
    .find((item) => item.request_number === "QR-E2E-CUSTOMER2");
  expect(ownRequest).toBeTruthy();

  const dealerPeek = await request.get(`/api/v1/quotation-requests/${ownRequest.id}/`, { headers: bearer(dealerToken) });
  expect(dealerPeek.status(), "dealer must not see unrelated customer quotations").toBe(404);

  const ledger = await request.get("/api/v1/finance/ledger/balances/", { headers: bearer(customerToken) });
  expect(ledger.status()).toBe(403);

  const anonymous = await request.get("/api/v1/payments/");
  expect(anonymous.status()).toBe(401);
});
