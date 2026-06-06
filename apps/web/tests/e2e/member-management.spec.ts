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

test.describe("member management @critical", () => {
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
    // token and the user is authenticated; no button click. The accept
    // route sets the picker-confirmed flag itself, so we land on
    // /dashboard directly.
    await inviteePage.goto(`/invitations/accept#t=${token}`);
    await inviteePage.waitForURL(/\/dashboard/);

    // Owner reloads /empresa/users — the selected tab survives the
    // reload, so we click back to Miembros explicitly before asserting
    // the invitee shows up (no longer pending). Scope to the table to
    // avoid colliding with other places the email is rendered (e.g.
    // the account-menu caption when the owner happens to share an
    // email prefix, or future side-rail summaries).
    await ownerPage.reload();
    await ownerPage.getByRole("tab", { name: /Miembros/i }).click();
    await expect(ownerPage.getByRole("table").getByText(inviteeEmail)).toBeVisible();
    await expect(ownerPage.getByRole("cell", { name: /Contador/i }).first()).toBeVisible();

    await ownerContext.close();
    await inviteeContext.close();
  });
});
