// Auth fixtures for Playwright e2e specs.
//
// Drives the real SPA through /signup → /confirm (OTP from Mailpit) →
// /login. NO API shortcuts: every action goes through a real form
// submission so the test surface stays honest about what the operator
// actually does. The fixtures assume the local stack is up:
//
//   docker compose up postgres mailpit
//   uv run alembic upgrade head
//   APP_ENV=local LOCAL_JWT_SECRET=<32+ chars> uv run uvicorn bootstrap.api:app
//   pnpm dev (in apps/web)
//
// In CI an equivalent job brings the same processes up before invoking
// Playwright with PLAYWRIGHT_NO_WEBSERVER=1.

import { expect, type Page } from "@playwright/test";

import { extractOtp, waitForEmail } from "./mailpit";

/** Default test password — meets the API's 12+ chars + classes policy. */
export const E2E_PASSWORD = "Demo1234!@xy";

/** Make a unique email per spec run to avoid cross-run interference. */
export function uniqueEmail(prefix: string): string {
  const suffix = Math.random().toString(36).slice(2, 10);
  return `${prefix}+${suffix}@test.dev`;
}

/**
 * Walk the full signup → confirm → login flow through the SPA.
 *
 * Returns the email used so callers can chain into tenant fixtures.
 */
export async function signupConfirmLogin(
  page: Page,
  opts: { email?: string; password?: string } = {},
): Promise<{ email: string; password: string }> {
  const email = opts.email ?? uniqueEmail("e2e");
  const password = opts.password ?? E2E_PASSWORD;
  const before = new Date(Date.now() - 1_000); // 1s of slack for clock drift

  // /signup
  await page.goto("/signup");
  await page.getByLabel(/Correo/i).fill(email);
  await page.getByLabel(/Contraseña/i).fill(password);
  await page.getByRole("button", { name: /Crear cuenta|Regístrate/i }).click();
  await page.waitForURL(/\/confirm/);

  // OTP from Mailpit
  const message = await waitForEmail({ email, since: before });
  const code = extractOtp(message);

  // /confirm — six-slot OTP input. The input-otp primitive renders a
  // hidden input the keyboard fills; typing into the visible slots
  // works in Chromium via `keyboard.type`. We focus the first slot
  // and type all six chars.
  const slots = page.locator("input[autocomplete='one-time-code']");
  await slots.first().focus();
  await page.keyboard.type(code);
  await page.getByRole("button", { name: /Confirmar/i }).click();
  await page.waitForURL(/\/login/);

  // /login
  await page.getByLabel(/Correo/i).fill(email);
  await page.getByLabel(/Contraseña/i).fill(password);
  await page.getByRole("button", { name: /Iniciar sesión/i }).click();

  // Post-login destination: /welcome (first-login profile capture) for a
  // brand-new account. Land there and complete it so the caller is on
  // /organizations / /tenants depending on memberships.
  await page.waitForURL(/\/welcome/);
  await page.getByLabel(/Nombre/i).fill("E2E User");
  await page.getByRole("button", { name: /Continuar|Guardar/i }).click();
  await page.waitForURL((url) => !/\/welcome/.test(url.pathname));

  return { email, password };
}

/**
 * Log out via the sidebar footer affordance. Asserts the SPA returns
 * to /login.
 */
export async function logout(page: Page): Promise<void> {
  await page.getByRole("button", { name: /Cerrar sesión|Sign out/i }).click();
  await expect(page).toHaveURL(/\/login(\?|$)/);
}
