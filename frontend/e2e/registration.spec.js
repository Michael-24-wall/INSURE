import { expect, test } from "@playwright/test";
import { ACCOUNTS, login, newLoggedInPage, registerViaUi, verifyOrganizationViaUi } from "./helpers";

const suffix = Date.now();

test("customer can register, verify email and sign in", async ({ page }) => {
  const account = {
    email: `e2e.customer.${suffix}@example.com`,
    password: "E2eNewCustomer@12345",
  };
  await registerViaUi(page, "customer", {
    firstName: "New",
    lastName: "Customer",
    ...account,
  });
  await login(page, { ...account, home: "/app" });
  await expect(page.getByText("Your protection, all in one place.")).toBeVisible();
});

test("insurer can register and platform admin verifies the organization", async ({ browser }) => {
  const email = `e2e.insurer.${suffix}@example.com`;
  const password = "E2eNewInsurer@12345";
  const organizationName = `E2E Onboard Insurer ${suffix}`;

  const registrant = await browser.newContext();
  const registerPage = await registrant.newPage();
  await registerViaUi(registerPage, "provider", {
    firstName: "New",
    lastName: "Insurer",
    email,
    password,
    organizationName,
  });
  await login(registerPage, { email, password, home: "/provider" });
  await expect(registerPage.getByText("Manage your insurance business.")).toBeVisible();

  const admin = await newLoggedInPage(browser, ACCOUNTS.admin);
  await verifyOrganizationViaUi(admin.page, organizationName);

  await registerPage.reload();
  await expect(registerPage).toHaveURL(/\/provider$/);
  await assertOrganizationStatus(admin.page, organizationName, "Verified");

  await registrant.close();
  await admin.context.close();
});

test("dealership can register and platform admin verifies the organization", async ({ browser }) => {
  const email = `e2e.dealer.${suffix}@example.com`;
  const password = "E2eNewDealer@12345";
  const organizationName = `E2E Onboard Dealer ${suffix}`;

  const registrant = await browser.newContext();
  const registerPage = await registrant.newPage();
  await registerViaUi(registerPage, "dealer", {
    firstName: "New",
    lastName: "Dealer",
    email,
    password,
    organizationName,
  });
  await login(registerPage, { email, password, home: "/dealer" });
  await expect(registerPage.getByText("Connect your dealership to trusted insurers.")).toBeVisible();

  const admin = await newLoggedInPage(browser, ACCOUNTS.admin);
  await verifyOrganizationViaUi(admin.page, organizationName);
  await assertOrganizationStatus(admin.page, organizationName, "Verified");

  await registrant.close();
  await admin.context.close();
});

async function assertOrganizationStatus(page, organizationName, status) {
  await page.goto("/admin/organizations");
  await page.getByPlaceholder("Search organizations").fill(organizationName);
  const row = page.getByRole("row").filter({ hasText: organizationName });
  await expect(row.getByText(status, { exact: true })).toBeVisible();
}
