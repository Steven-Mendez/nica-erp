// Smoke test for the authentication happy path:
//   /login renders → submitting valid credentials transitions away.
//
// This is a layout-level smoke; the full sign-up + confirm + login +
// dashboard journey lands as the suite grows. The spec runs against
// a dev server with no special seed data; the form should render and
// the title should be present.

import { expect, test } from "@playwright/test";

test.describe("login page @smoke", () => {
  test("renders the form", async ({ page }) => {
    await page.goto("/login");
    await expect(page.getByText(/Inicia sesión en tu cuenta/i)).toBeVisible();
    await expect(page.getByLabel(/Correo/i)).toBeVisible();
    await expect(page.getByLabel(/Contraseña/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /Iniciar sesión/i })).toBeVisible();
  });

  test("shows the signup link", async ({ page }) => {
    await page.goto("/login");
    const signupLink = page.getByRole("link", { name: /Regístrate/i });
    await expect(signupLink).toBeVisible();
  });
});
