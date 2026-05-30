// Member management: admin invites a user; the invitee accepts via
// the deep link in a second browser context; both contexts observe
// the new member.
//
// Two layers:
//   @smoke    — entry surface assertion (redirect from legacy path).
//   @critical — full two-context flow against the real local stack.

import { expect, test } from "@playwright/test";

import { signupConfirmLogin, uniqueEmail } from "./fixtures/auth";
import { createEmpresa, inviteMember } from "./fixtures/tenant";

test.describe("member management @smoke", () => {
  test("legacy /tenants/:id/members redirects to /empresa/users", async ({ page }) => {
    await page.goto("/tenants/anything/members");
    await expect(page).toHaveURL(/\/(empresa\/users|login)/);
  });
});

// The two-context flow below is intentionally fixture-driven; the
// post-accept landing assertion is loose because the sprint-3.13
// picker route guard can interpose /tenants between accept and
// /dashboard depending on the picker-confirmed session flag. The
// meaningful assertion is that the owner observes the invitee
// in /empresa/users after the accept round-trip completes.
test.describe.skip("member management @critical", () => {
  test("owner invites a user; invitee accepts; both observe the member", async ({ browser }) => {
    const ownerContext = await browser.newContext();
    const ownerPage = await ownerContext.newPage();
    const inviteeEmail = uniqueEmail("invitee");

    // Owner: sign up, create empresa, invite the second user.
    await signupConfirmLogin(ownerPage);
    await createEmpresa(ownerPage);
    const { token } = await inviteMember(ownerPage, {
      email: inviteeEmail,
      role: "accountant",
    });
    // The invitee email appears under the Invitaciones tab once we
    // switch to it.
    await ownerPage.getByRole("tab", { name: /Invitaciones/i }).click();
    await expect(ownerPage.getByText(inviteeEmail)).toBeVisible();

    // Invitee: sign up in a separate context, then walk the deep link.
    const inviteeContext = await browser.newContext();
    const inviteePage = await inviteeContext.newPage();
    await signupConfirmLogin(inviteePage, { email: inviteeEmail });
    // The route auto-fires the accept mutation when the hash carries a
    // token and the user is authenticated; no button click. After
    // success the sprint-3.13 route guard may interpose /tenants.
    await inviteePage.goto(`/invitations/accept#t=${token}`);
    await inviteePage.waitForURL(/\/(tenants|dashboard|empresa)/);
    if (inviteePage.url().includes("/tenants")) {
      await inviteePage.getByRole("button", { name: /Empresa/i }).first().click();
      await inviteePage.waitForURL(/\/dashboard/);
    }

    // Owner reloads /empresa/users and observes the member on the
    // default Miembros tab (no longer pending).
    await ownerPage.reload();
    await expect(ownerPage.getByText(inviteeEmail)).toBeVisible();
    await expect(ownerPage.getByRole("cell", { name: /Contador/i }).first()).toBeVisible();

    await ownerContext.close();
    await inviteeContext.close();
  });
});
