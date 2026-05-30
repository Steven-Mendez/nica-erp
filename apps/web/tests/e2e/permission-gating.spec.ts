// Permission gating: a viewer and an admin see different affordances
// on /empresa/users. Tagged @critical — nightly only until fixtures
// can issue tokens with the two roles.

import { expect, test } from "@playwright/test";

test.describe("permission gating @critical", () => {
  test("unauthenticated /empresa/users redirects to /login", async ({ page }) => {
    await page.goto("/empresa/users");
    await expect(page).toHaveURL(/\/login(\?|$)/);
  });
});
