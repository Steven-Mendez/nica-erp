// Smoke test that the /health route renders (the only route reachable
// without authentication besides the auth flows).

import { expect, test } from "@playwright/test";

test("health page is reachable unauthenticated @smoke", async ({ page }) => {
  await page.goto("/health");
  // The dashboard route has a beforeLoad guard; /health does not, so
  // the page renders without redirecting to /login.
  await expect(page).toHaveURL(/\/health$/);
});
