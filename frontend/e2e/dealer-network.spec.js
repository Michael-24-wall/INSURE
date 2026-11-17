import { expect, test } from "@playwright/test";
import {
  ACCOUNTS,
  apiLogin,
  listResult,
  newLoggedInPage,
  waitForApi,
} from "./helpers";

test("dealer partnership, customer quotation and commission flow", async ({ browser, request }) => {
  const providerToken = await apiLogin(request, ACCOUNTS.provider);
  const dealerToken = await apiLogin(request, ACCOUNTS.dealer);

  const provider = await newLoggedInPage(browser, ACCOUNTS.provider);
  await provider.page.goto("/provider/network");
  await expect(provider.page.getByRole("heading", { name: "Dealer partnerships" })).toBeVisible();

  await provider.page.getByRole("tab", { name: "Requests" }).click();
  const requestRow = provider.page.getByText("E2E Metro Motors → E2E Alpha Insurance").locator("..").locator("..");
  await expect(requestRow).toBeVisible();
  await requestRow.getByRole("button", { name: "Approve" }).click();
  await waitForApi(
    request,
    providerToken,
    "/api/v1/business-network/partnerships/?page_size=100",
    (data) => data.results.some((item) => item.dealership_name === "E2E Metro Motors" && item.status === "active")
  );

  await provider.page.getByRole("tab", { name: "My partnerships" }).click();
  const partnershipRow = provider.page.getByText("E2E Metro Motors").locator("..").locator("..");
  await expect(partnershipRow.getByText("Active", { exact: true })).toBeVisible();
  await partnershipRow.getByRole("button", { name: "Commission terms" }).click();
  const termsDialog = provider.page.getByRole("dialog");
  await expect(termsDialog.getByRole("heading", { name: /Commission terms/ })).toBeVisible();
  await termsDialog.getByLabel("Rate (%)").fill("12.5");
  await termsDialog.getByRole("button", { name: "Save", exact: true }).click();
  await expect(termsDialog).toBeHidden();

  const partnership = (await listResult(request, providerToken, "/api/v1/business-network/partnerships/?page_size=100"))
    .results.find((item) => item.dealership_name === "E2E Metro Motors" && item.status === "active");
  expect(partnership.commission_terms.at(-1).rate).toBe("12.50");

  const dealer = await newLoggedInPage(browser, ACCOUNTS.dealer);
  await dealer.page.goto("/dealer");
  await expect(dealer.page.getByRole("heading", { name: "Connect your dealership to trusted insurers." })).toBeVisible();
  await dealer.page.getByRole("tab", { name: "Inventory" }).click();
  const vehicleCard = dealer.page.locator(".surface").filter({ hasText: "Mazda CX-5 (2021)" });
  await expect(vehicleCard).toBeVisible();
  await vehicleCard.getByRole("button", { name: "Quote", exact: true }).click();

  const quoteDialog = dealer.page.getByRole("dialog");
  await expect(quoteDialog.getByRole("heading", { name: /Request quotation/ })).toBeVisible();
  await quoteDialog.getByLabel("Insurer").selectOption({ label: "E2E Alpha Insurance" });
  await quoteDialog.getByPlaceholder("Search customer by name, email or phone").fill("e2e.customer2@example.com");
  await quoteDialog.locator("button").filter({ hasText: "e2e.customer2@example.com" }).click();
  await quoteDialog.getByRole("button", { name: "Submit request" }).click();
  await expect(quoteDialog).toBeHidden();

  const dealerRequests = await waitForApi(
    request,
    dealerToken,
    "/api/v1/quotation-requests/?page_size=100&ordering=-created_at",
    (data) => data.results.some((item) => item.vehicle_summary?.registration_number === "KDE 300G")
  );
  const dealerRequest = dealerRequests.results.find((item) => item.vehicle_summary?.registration_number === "KDE 300G");

  await dealer.page.goto(`/dealer/quotes/${dealerRequest.id}`);
  await expect(dealer.page.getByText("E2E Comprehensive Cover")).toBeVisible();
  await dealer.page.getByRole("button", { name: /Select offer/ }).click();
  await expect(dealer.page).toHaveURL(/\/dealer\/applications\/[0-9a-f-]+/);
  const applicationId = dealer.page.url().split("/").pop();
  await expect(dealer.page.getByText("Submitted", { exact: true }).first()).toBeVisible();

  const customerToken = await apiLogin(request, ACCOUNTS.customer2);
  const customer = await newLoggedInPage(browser, ACCOUNTS.customer2);
  await customer.page.goto(`/app/applications/${applicationId}`);
  await expect(customer.page.getByRole("heading", { name: /KDE 300G/ })).toBeVisible();

  await provider.page.goto(`/provider/applications/${applicationId}`);
  await provider.page.getByRole("button", { name: "Approve", exact: true }).first().click();
  const approveDialog = provider.page.getByRole("dialog");
  await approveDialog.getByLabel("Notes (optional)").fill("Dealer application approved");
  await approveDialog.getByRole("button", { name: "Confirm", exact: true }).click();
  await expect(provider.page.getByText("Approved", { exact: true }).first()).toBeVisible();

  await customer.page.reload();
  await customer.page.getByRole("button", { name: "Pay premium" }).first().click();
  const paymentDialog = customer.page.getByRole("dialog");
  await paymentDialog.getByLabel("Payment method").selectOption("bank");
  await paymentDialog.getByRole("button", { name: "Initiate payment" }).click();

  const pending = await waitForApi(
    request,
    customerToken,
    `/api/v1/payments/?application=${applicationId}&page_size=20`,
    (data) => data.results.some((item) => item.status === "pending" || item.status === "processing")
  );
  const payment = pending.results.find((item) => item.status === "pending" || item.status === "processing");

  await provider.page.goto("/provider/payments");
  const paymentRow = provider.page.getByRole("row").filter({ hasText: payment.reference });
  await paymentRow.getByRole("button", { name: "Verify" }).click();
  const verifyDialog = provider.page.getByRole("dialog");
  await verifyDialog.getByLabel("Provider / transaction reference").fill(`E2E-DEALER-BANK-${Date.now()}`);
  await verifyDialog.getByRole("button", { name: "Confirm payment" }).click();
  await expect(paymentRow.getByText("Succeeded", { exact: true })).toBeVisible();

  await provider.page.goto(`/provider/applications/${applicationId}`);
  await provider.page.getByRole("button", { name: "Issue policy" }).click();
  const issueDialog = provider.page.getByRole("dialog");
  await issueDialog.getByLabel("Provider reference").fill("E2E-DEALER-POLICY");
  await issueDialog.getByRole("button", { name: "Issue policy" }).click();
  await expect(provider.page).toHaveURL(/\/provider\/policies\/[0-9a-f-]+/);
  const policyId = provider.page.url().split("/").pop();

  const policy = await listResult(request, providerToken, `/api/v1/policies/${policyId}/`);
  const commissions = await listResult(
    request,
    dealerToken,
    `/api/v1/payments/commissions/?policy=${policyId}&page_size=20`
  );
  expect(commissions.results).toHaveLength(1);
  const commission = commissions.results[0];
  const expected = Math.round(Number(policy.premium) * 0.125 * 100) / 100;
  expect(Number(commission.rate)).toBe(12.5);
  expect(Number(commission.amount)).toBe(expected);

  const finance = await listResult(request, providerToken, "/api/v1/finance/dashboard/");
  expect(Number(finance.premium_earned_recognized)).toBeGreaterThan(0);
  expect(Number(finance.commissions_outstanding)).toBeGreaterThan(0);

  await provider.page.goto("/provider");
  await expect(provider.page.getByText("Premium earned", { exact: true })).toBeVisible();
  await expect(provider.page.getByText("Commissions outstanding", { exact: true })).toBeVisible();

  await provider.context.close();
  await dealer.context.close();
  await customer.context.close();
});
