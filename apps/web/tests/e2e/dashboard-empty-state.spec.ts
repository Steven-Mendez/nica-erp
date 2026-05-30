// Dashboard empty state for a newly registered user (no empresa yet).
// Tagged @smoke — runs on every PR.

import { expect, test } from "@playwright/test";

test.describe("dashboard empty state @smoke", () => {
  test("anonymous users are redirected to /login from /dashboard", async ({ page }) => {
    await page.goto("/dashboard");
    await expect(page).toHaveURL(/\/login(\?|$)/);
  });
});
