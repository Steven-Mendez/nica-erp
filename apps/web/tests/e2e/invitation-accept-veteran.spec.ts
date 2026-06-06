// Veteran-user accept: a user already authenticated in their own
// empresa A accepts an invitation to a different empresa B. The
// response from POST /v1/invitations/accept omits `tokens` because
// the caller already has an `active_tenant` claim, the SPA does NOT
// rotate session tokens, and the user stays inside empresa A after
// the accept. Empresa B becomes available as a switch target on the
// sidebar's empresa switcher but is not auto-selected.

import { expect, test } from "@playwright/test";

import { signupConfirmLogin, uniqueEmail } from "./fixtures/auth";
import { createEmpresa, inviteMember } from "./fixtures/tenant";

test.describe("invitation accept (veteran user) @critical", () => {
  test("user with active empresa A accepts an invite to B; stays in A", async ({ browser }) => {
    // ── Owner of empresa B sets up the invitation. ──────────────────
    const ownerBContext = await browser.newContext();
    const ownerBPage = await ownerBContext.newPage();
    const veteranEmail = uniqueEmail("veteran");
    await signupConfirmLogin(ownerBPage);
    const { name: empresaBName } = await createEmpresa(ownerBPage);

    // ── Veteran: signs up, creates their own empresa A. ─────────────
    const veteranContext = await browser.newContext();
    const veteranPage = await veteranContext.newPage();
    await signupConfirmLogin(veteranPage, { email: veteranEmail });
    const { name: empresaAName } = await createEmpresa(veteranPage);
    // Confirm A is the active empresa on the sidebar before the
    // invitation lands. The sidebar TenantSwitcher renders the active
    // empresa as the text content of a dropdown trigger button
    // (accessible name is `<empresa> <role>`).
    await expect(veteranPage.getByRole("button", { name: new RegExp(empresaAName) })).toBeVisible();

    // ── Owner B issues the invitation to the veteran's address. ─────
    const { token } = await inviteMember(ownerBPage, {
      email: veteranEmail,
      role: "accountant",
    });

    // ── Veteran opens the invitation link while authenticated in A.
    //    The accept POST runs immediately (hash-fragment + auth path)
    //    and returns `tokens=null` because A is already the active
    //    empresa. The route navigates to /dashboard with the JWT
    //    unchanged.
    await veteranPage.goto(`/invitations/accept#t=${token}`);
    await veteranPage.waitForURL(/\/dashboard/);

    // ── Active empresa is still A — no silent switch. ───────────────
    await expect(veteranPage.getByRole("button", { name: new RegExp(empresaAName) })).toBeVisible();

    // Empresa B is available as a switch target — the membership was
    // created server-side, only the active_tenant claim was preserved.
    await veteranPage.getByRole("button", { name: new RegExp(empresaAName) }).click();
    await expect(veteranPage.getByRole("menuitem", { name: empresaBName })).toBeVisible();

    await ownerBContext.close();
    await veteranContext.close();
  });
});
