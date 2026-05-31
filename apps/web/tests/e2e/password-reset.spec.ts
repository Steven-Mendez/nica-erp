// Password reset: a user requests a recovery code from /forgot-password,
// uses it to set a new password from /reset-password, then logs in with
// the new password. Drives the SPA end-to-end through the real backend
// and Mailpit; no API shortcuts.
//
// Two layers:
//   @smoke    — entry surface assertion. Runs on every PR.
//   @critical — full forgot → reset → re-login flow against the real
//               local stack.

import { expect, test } from "@playwright/test";

import { E2E_PASSWORD, resetPassword, signupConfirmLogin } from "./fixtures/auth";

test.describe("password reset @smoke", () => {
  test("the forgot-password form renders for unauthenticated visitors", async ({ page }) => {
    await page.goto("/forgot-password");
    await expect(page.getByRole("heading", { name: /Recupera tu contraseña/i })).toBeVisible();
    await expect(page.getByLabel(/Correo/i)).toBeVisible();
    await expect(page.getByRole("button", { name: /Enviar código/i })).toBeVisible();
  });
});

test.describe("password reset @critical", () => {
  test("user resets their password and logs in with the new one", async ({ page, context }) => {
    // 1. Bootstrap a confirmed account. signupConfirmLogin leaves the
    //    SPA on /onboarding for a fresh user (no empresa = no sidebar /
    //    logout button), so we clear session state directly instead of
    //    clicking through the UI.
    const { email } = await signupConfirmLogin(page);

    // 2. Drop all auth state so /forgot-password starts from an
    //    anonymous surface, matching the real operator path.
    await context.clearCookies();
    await page.evaluate(() => {
      window.localStorage.clear();
      window.sessionStorage.clear();
    });

    // 3. Drive the recovery flow against the real Mailpit-delivered code.
    const newPassword = "Reset1234!@xy";
    expect(newPassword).not.toBe(E2E_PASSWORD);
    await resetPassword(page, { email, newPassword });

    // 4. Log in with the new password. The post-login destination is
    //    /onboarding (no empresa yet); what matters is that we left
    //    /login at all.
    await page.waitForSelector("input#email", { state: "visible" });
    await page.locator("input#email").fill(email);
    await page.locator("input#password").fill(newPassword);
    await page.getByRole("button", { name: /Iniciar sesión/i }).click();
    await page.waitForURL((url) => !/\/login/.test(url.pathname));

    // 5. And the OLD password no longer works — sanity check that the
    //    reset actually rotated server-side, not just locally. Clear
    //    state again and try to log in with the old password.
    await context.clearCookies();
    await page.evaluate(() => {
      window.localStorage.clear();
      window.sessionStorage.clear();
    });
    await page.goto("/login");
    await page.locator("input#email").fill(email);
    await page.locator("input#password").fill(E2E_PASSWORD);
    await page.getByRole("button", { name: /Iniciar sesión/i }).click();
    // The destructive alert appears (auto-retries up to the default
    // timeout) and the URL never leaves /login. Both assertions are
    // necessary: the alert alone could be a lingering banner, the URL
    // alone could be a slow nav.
    await expect(page.getByText(/No se pudo iniciar sesión/i)).toBeVisible();
    await expect(page).toHaveURL(/\/login(\?|$)/);
  });
});
