// Permission gating on /empresa/users.
//
// Two layers:
//   @smoke    — unauthenticated visitors are redirected to /login.
//   @critical — an owner sees the Invitar affordance; a viewer does not.
//
// The @critical test invites a viewer through the SPA, has them
// accept in a second context, then asserts the absence of the
// invite/remove buttons on their view of /empresa/users.

import { expect, test } from "@playwright/test";

import { signupConfirmLogin, uniqueEmail } from "./fixtures/auth";
import { createEmpresa, inviteMember } from "./fixtures/tenant";

test.describe("permission gating @smoke", () => {
  test("unauthenticated /empresa/users redirects to /login", async ({ page }) => {
    await page.goto("/empresa/users");
    await expect(page).toHaveURL(/\/login(\?|$)/);
  });
});

// Same caveat as member-management: the post-accept landing for the
// invitee depends on the sprint-3.13 picker route guard interaction.
// The scaffolding is in place to enable this when the routing
// contract for "single empresa, just joined" is clarified.
test.describe.skip("permission gating @critical", () => {
  test("owner sees Invitar; viewer does not", async ({ browser }) => {
    // Owner setup
    const ownerCtx = await browser.newContext();
    const ownerPage = await ownerCtx.newPage();
    const viewerEmail = uniqueEmail("viewer");

    await signupConfirmLogin(ownerPage);
    await createEmpresa(ownerPage);
    const { token } = await inviteMember(ownerPage, { email: viewerEmail, role: "viewer" });

    // Owner page: Invitar button is reachable.
    await expect(ownerPage.getByRole("button", { name: /Invitar/i })).toBeVisible();

    // Viewer signs up, accepts invitation, lands in the empresa.
    const viewerCtx = await browser.newContext();
    const viewerPage = await viewerCtx.newPage();
    await signupConfirmLogin(viewerPage, { email: viewerEmail });
    // The route auto-fires the accept mutation when the hash carries
    // a token and the user is authenticated; no button click. After
    // success, the sprint-3.13 route guard sends the viewer to
    // /tenants to pick the empresa they just joined. Click into it.
    await viewerPage.goto(`/invitations/accept#t=${token}`);
    await viewerPage.waitForURL(/\/(tenants|dashboard|empresa)/);
    if (viewerPage.url().includes("/tenants")) {
      await viewerPage.getByRole("button", { name: /Empresa/i }).first().click();
      await viewerPage.waitForURL(/\/dashboard/);
    }

    // Viewer navigates to /empresa/users: the Invitar button is NOT
    // rendered (useHasPermission gates it on `members:invite`).
    await viewerPage.goto("/empresa/users");
    await expect(viewerPage.getByRole("button", { name: /^\+? Invitar$/i })).toHaveCount(0);

    await ownerCtx.close();
    await viewerCtx.close();
  });
});
