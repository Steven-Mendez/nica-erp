// Fallback path on /confirm: when the password hand-off from /signup
// has been lost (hard reload of /confirm, direct entry to /confirm via
// URL, etc.), the route SHALL NOT include the password on the
// confirm-signup POST and SHALL navigate to /login on success — the
// user can finish the signup manually from there.

import { expect, test } from "@playwright/test";

import { E2E_PASSWORD, uniqueEmail } from "./fixtures/auth";
import { extractOtp, waitForEmail } from "./fixtures/mailpit";

test.describe("signup → confirm fallback @critical", () => {
  test("hard-reload of /confirm falls back to /login", async ({ page }) => {
    const email = uniqueEmail("confirm-fallback");
    const before = new Date(Date.now() - 1_000);

    // Walk through /signup so the backend has an account waiting to be
    // confirmed; the in-memory password hand-off lives in the
    // post-register navigation callback, so a reload of /confirm will
    // wipe it.
    await page.goto("/signup");
    await page.getByLabel("Correo").fill(email);
    await page.getByLabel("Contraseña", { exact: true }).fill(E2E_PASSWORD);
    await page.getByLabel("Confirmar contraseña").fill(E2E_PASSWORD);
    await page.getByRole("button", { name: /Crear cuenta/i }).click();
    await page.waitForURL(/\/confirm/);

    // Hard reload — drops the in-memory password hand-off. From here
    // on the page behaves like a direct /confirm entry: no password
    // available, fall back to the historical /login navigation.
    await page.reload();

    const confirmEmail = await waitForEmail({
      email,
      since: before,
      subjectIncludes: "confirma",
    });
    const otp = extractOtp(confirmEmail);
    await page.locator("input[autocomplete='one-time-code']").first().focus();
    await page.keyboard.type(otp);

    // Listen for unhandled JS errors during the submit + navigation —
    // the fallback path must not crash.
    const consoleErrors: string[] = [];
    page.on("pageerror", (err) => consoleErrors.push(err.message));

    await page.getByRole("button", { name: /^Confirmar$/i }).click();
    await page.waitForURL(/\/login/);
    expect(consoleErrors).toEqual([]);

    // The user can finish manually from /login. Pre-filled email is
    // not part of the fallback contract; we only assert the page
    // landed there.
    await expect(page.getByLabel(/Correo/i)).toBeVisible();
  });
});
