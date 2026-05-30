// Tenant onboarding: a freshly registered user creates their first
// empresa via `/tenants/new` and lands on the empresa dashboard.
//
// Tagged @smoke — runs on every PR. The full fixture-driven flow lands
// in apps/web/tests/e2e/fixtures/{auth,tenant}.ts once the local IdP
// stack is wired to a CI-controllable mail sink; until then this spec
// asserts the entry surface that the journey starts from.

import { expect, test } from "@playwright/test";

test.describe("tenant onboarding @smoke", () => {
  test("the new-tenant form renders for unauthenticated visitors", async ({ page }) => {
    await page.goto("/tenants/new");
    await expect(page.getByLabel(/Nombre/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /Continuar/i })).toBeVisible();
  });
});
