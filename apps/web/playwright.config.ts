// apps/web/playwright.config.ts
//
// Three projects per the frontend-testing-triad spec:
//
//   - `smoke`     — Chromium, runs only specs tagged @smoke (auth,
//     tenant onboarding, dashboard empty state). PR merge gate.
//   - `critical`  — Chromium, runs only specs tagged @critical
//     (member management, permission gating, rls isolation). Nightly.
//   - `webkit`    — WebKit, runs @critical specs nightly only.
//
// CI starts the SPA from scratch (`reuseExistingServer: false`); local
// dev reuses an already-running `pnpm dev`. When `PLAYWRIGHT_NO_WEBSERVER=1`
// is set, the webServer block is skipped entirely — CI uses this to point
// Playwright at a fronted-by-real-API stack started via `make` recipes.

import { defineConfig, devices } from "@playwright/test";

// localhost (not 127.0.0.1) so the CORS allowlist in the API
// (default `http://localhost:5173`) accepts the preflight from
// Playwright's browser during @critical specs.
const baseURL = process.env.PLAYWRIGHT_BASE_URL ?? "http://localhost:5173";
const skipWebServer = process.env.PLAYWRIGHT_NO_WEBSERVER === "1";

export default defineConfig({
  testDir: "./tests/e2e",
  fullyParallel: true,
  forbidOnly: !!process.env.CI,
  retries: process.env.CI ? 2 : 0,
  reporter: process.env.CI ? "html" : "list",
  ...(process.env.CI ? { workers: 2 } : {}),
  use: {
    baseURL,
    trace: "on-first-retry",
    screenshot: "only-on-failure",
    video: "retain-on-failure",
  },
  projects: [
    {
      name: "smoke",
      grep: /@smoke/,
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "critical",
      grep: /@critical/,
      use: { ...devices["Desktop Chrome"] },
    },
    {
      name: "webkit",
      grep: /@critical/,
      use: { ...devices["Desktop Safari"] },
    },
  ],
  ...(skipWebServer
    ? {}
    : {
        webServer: {
          command: "pnpm dev",
          url: baseURL,
          reuseExistingServer: !process.env.CI,
          timeout: 120_000,
        },
      }),
});
