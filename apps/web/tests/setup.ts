// apps/web/tests/setup.ts
// Vitest setup: register @testing-library/jest-dom matchers so toBeInTheDocument()
// and friends are available in every test without per-file imports.
import "@testing-library/jest-dom/vitest";
import { beforeEach } from "vitest";

// Clear both storages before every test so per-test setup never leaks
// into the next case (picker-confirmed flag, sidebar collapse state,
// etc. all live in storage).
beforeEach(() => {
  window.localStorage.clear();
  window.sessionStorage.clear();
});
