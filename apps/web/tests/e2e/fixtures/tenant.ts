// Tenant (empresa) fixtures for Playwright e2e specs.
//
// Drives the SPA through `/tenants/new` (sprint 3.12 wizard) using the
// soft-creation path: only `name` is required. Tests that need a fully
// fiscalized empresa can extend by stepping through the wizard's other
// pages — the wizard primitives (Select, Checkbox, DatePicker) all
// expose accessible labels we can hit by role.

import { expect, type Page } from "@playwright/test";

import { waitForEmail, extractInviteToken } from "./mailpit";

/** Create an empresa with name only via the wizard's "Saltar y crear" path. */
export async function createEmpresa(
  page: Page,
  opts: { name?: string } = {},
): Promise<{ name: string }> {
  const name = opts.name ?? `Empresa e2e ${Math.random().toString(36).slice(2, 8)}`;

  // The picker (force-tenant-picker-and-back-link, sprint 3.13) forces
  // /tenants on every fresh session. From there the "+ Nueva empresa"
  // CTA opens /tenants/new.
  if (!page.url().includes("/tenants/new")) {
    await page.goto("/tenants");
    await page.getByRole("link", { name: /Nueva empresa/i }).click();
    await page.waitForURL(/\/tenants\/new/);
  }

  await page.getByLabel(/Nombre/i).fill(name);
  await page.getByRole("button", { name: /Saltar y crear|Crear empresa/i }).click();

  // Land on /dashboard once the wizard switches into the new empresa.
  await page.waitForURL(/\/dashboard/);
  return { name };
}

/**
 * Invite a member from the active empresa context. Returns the
 * invitation token harvested from Mailpit.
 */
export async function inviteMember(
  page: Page,
  opts: { email: string; role?: "viewer" | "salesperson" | "accountant" | "admin" },
): Promise<{ token: string }> {
  const before = new Date(Date.now() - 1_000);

  await page.goto("/empresa/users");
  await page.getByRole("button", { name: /Invitar/i }).click();
  await page.getByLabel(/Correo/i).fill(opts.email);
  if (opts.role) {
    await page.getByLabel(/Rol/i).click();
    await page.getByRole("option", { name: new RegExp(opts.role, "i") }).click();
  }
  await page.getByRole("button", { name: /Enviar invitación|Invitar/i }).click();
  await expect(page.getByText(opts.email)).toBeVisible();

  const message = await waitForEmail({ email: opts.email, since: before });
  return { token: extractInviteToken(message) };
}
