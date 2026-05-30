// Tenant onboarding: a freshly registered user creates their first
// empresa via `/tenants/new` and lands on the empresa dashboard.
//
// Two layers:
//   @smoke    — entry surface assertion. Runs on every PR; no backend
//               required (the form renders before any data load).
//   @critical — full fixture-driven flow against the real local stack.
//               Requires docker compose + uvicorn + pnpm dev; CI brings
//               them up in a dedicated job.

import { expect, test } from "@playwright/test";

import { signupConfirmLogin } from "./fixtures/auth";
import { createEmpresa } from "./fixtures/tenant";

test.describe("tenant onboarding @smoke", () => {
  test("the new-tenant form renders for unauthenticated visitors", async ({ page }) => {
    await page.goto("/tenants/new");
    await expect(page.getByLabel(/Nombre/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /Continuar/i })).toBeVisible();
  });
});

test.describe("tenant onboarding @critical", () => {
  test("first-time user creates an empresa and lands on dashboard", async ({ page }) => {
    await signupConfirmLogin(page);
    const { name } = await createEmpresa(page);
    await expect(page).toHaveURL(/\/dashboard/);
    // The active empresa is the selected <option> in the sidebar
    // TenantSwitcher (a native combobox). Asserting the selected
    // option's text contains the empresa name keeps the test agnostic
    // to whether the sidebar renders the name in a separate visible
    // chip.
    await expect(page.getByRole("combobox", { name: /Empresa activa/i })).toContainText(name);
  });
});
