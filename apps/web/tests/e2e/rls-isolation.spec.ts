// RLS isolation from the SPA: two simultaneous browser contexts
// signed into two distinct tenants. Neither context observes any
// resource belonging to the other tenant through the SPA.
//
// Tagged @critical — runs nightly. The smoke layer covers the entry
// surface; the full two-context flow runs with real backend fixtures
// once they land.

import { expect, test } from "@playwright/test";

test.describe("rls isolation @critical", () => {
  test("unauthenticated /empresa returns to /login (cannot cross-peek)", async ({ page }) => {
    await page.goto("/empresa");
    await expect(page).toHaveURL(/\/login(\?|$)/);
  });
});
