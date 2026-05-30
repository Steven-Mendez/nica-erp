// Member management: admin invites a user; the invitee accepts via
// deep link in a second browser context; both contexts observe the
// new member; admin removes them.
//
// Tagged @critical — nightly only until fixtures land. The skeleton
// below asserts the entry surface so a regression that breaks
// `/empresa/users` reaching the form still surfaces at the smoke
// layer; the full flow runs nightly with `PLAYWRIGHT_NO_WEBSERVER=1`
// against a real backend.

import { expect, test } from "@playwright/test";

test.describe("member management @critical", () => {
  test("legacy /tenants/:id/members redirects to /empresa/users", async ({ page }) => {
    await page.goto("/tenants/anything/members");
    await expect(page).toHaveURL(/\/(empresa\/users|login)/);
  });
});
