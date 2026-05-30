// RLS isolation: two simultaneous browser contexts signed into two
// distinct empresas. Neither observes the other's invitations
// through the SPA.
//
// Two layers:
//   @smoke    — unauthenticated /empresa redirects to /login.
//   @critical — two contexts, two owners, two empresas; user B does
//               not see user A's pending invitations.

import { expect, test } from "@playwright/test";

import { signupConfirmLogin, uniqueEmail } from "./fixtures/auth";
import { createEmpresa, inviteMember } from "./fixtures/tenant";

test.describe("rls isolation @smoke", () => {
  test("unauthenticated /empresa returns to /login (cannot cross-peek)", async ({ page }) => {
    await page.goto("/empresa");
    await expect(page).toHaveURL(/\/login(\?|$)/);
  });
});

test.describe("rls isolation @critical", () => {
  test("user B does not see user A's pending invitations from the SPA", async ({ browser }) => {
    const aCtx = await browser.newContext();
    const bCtx = await browser.newContext();
    const aPage = await aCtx.newPage();
    const bPage = await bCtx.newPage();
    const aInvitee = uniqueEmail("a-invitee");

    // A creates empresa and invites someone — pending invitation lives
    // under empresa A's tenant_id.
    await signupConfirmLogin(aPage);
    await createEmpresa(aPage);
    await inviteMember(aPage, { email: aInvitee, role: "viewer" });
    await aPage.getByRole("tab", { name: /Invitaciones/i }).click();
    await expect(aPage.getByText(aInvitee)).toBeVisible();

    // B creates a different empresa and visits /empresa/users.
    await signupConfirmLogin(bPage);
    await createEmpresa(bPage);
    await bPage.goto("/empresa/users");
    await bPage.getByRole("tab", { name: /Invitaciones/i }).click();

    // A's invitee email MUST NOT appear in B's view — RLS hides it at
    // the API layer, and the SPA cannot manufacture it.
    await expect(bPage.getByText(aInvitee)).toHaveCount(0);

    await aCtx.close();
    await bCtx.close();
  });
});
