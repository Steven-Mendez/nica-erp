// Tenant (empresa) fixtures for Playwright e2e specs.
//
// Drives the SPA through `/tenants/new` using the soft-creation path:
// only `name` is required. Tests that need a fully fiscalized empresa
// can extend by stepping through the wizard's other pages — the
// wizard primitives (Select, Checkbox, DatePicker) all expose
// accessible labels we can hit by role.

import type { Page } from "@playwright/test";

import { waitForEmail, extractInviteToken } from "./mailpit";

/** Create an empresa with name only via the wizard's "Saltar y crear" path. */
export async function createEmpresa(
  page: Page,
  opts: { name?: string } = {},
): Promise<{ name: string }> {
  const name = opts.name ?? `Empresa e2e ${Math.random().toString(36).slice(2, 8)}`;

  // Navigate directly — /tenants/new is reachable from /onboarding
  // (brand-new user, no memberships) and from /tenants (returning user
  // via the "+ Nueva empresa" CTA). Skipping the in-between click keeps
  // the fixture indifferent to which entry point the caller is on.
  if (!page.url().includes("/tenants/new")) {
    await page.goto("/tenants/new");
  }

  await page.getByLabel("Nombre", { exact: false }).fill(name);
  await page.getByRole("button", { name: /Saltar y crear|Crear empresa/i }).click();

  // Land on /dashboard once the wizard switches into the new empresa.
  await page.waitForURL(/\/dashboard/);
  return { name };
}

/** Spanish labels for the role <Select> on /empresa/users (closed set). */
const ROLE_OPTION_LABEL = {
  viewer: /Visualizador/i,
  salesperson: /Vendedor/i,
  accountant: /Contador/i,
  admin: /Administrador/i,
} as const satisfies Record<string, RegExp>;

/**
 * Invite a member from the active empresa context. Returns the
 * invitation token harvested from Mailpit.
 */
export async function inviteMember(
  page: Page,
  opts: { email: string; role?: keyof typeof ROLE_OPTION_LABEL },
): Promise<{ token: string }> {
  const before = new Date(Date.now() - 1_000);

  await page.goto("/empresa/users");
  await page.getByRole("button", { name: /Invitar/i }).click();
  await page.getByLabel(/Correo/i).fill(opts.email);
  if (opts.role) {
    await page.getByLabel(/Rol/i).click();
    await page.getByRole("option", { name: ROLE_OPTION_LABEL[opts.role] }).click();
  }
  await page.getByRole("button", { name: /Enviar invitación|Invitar/i }).click();
  // Dialog closes once the POST returns; the invitee email lives under
  // the Invitaciones tab, not the default Miembros one. The Mailpit
  // round-trip below is the durable proof that the invite landed. We
  // filter by subject ("invitación") so the veteran-user flow (where
  // the invitee already received a signup confirmation email to the
  // same address) does not match the older confirmation message.
  const message = await waitForEmail({
    email: opts.email,
    since: before,
    subjectIncludes: "invitación",
  });
  return { token: extractInviteToken(message) };
}
