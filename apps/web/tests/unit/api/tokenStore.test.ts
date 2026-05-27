// apps/web/tests/unit/api/tokenStore.test.ts
//
// Verifies the in-memory token store behaviour:
// - returns null when empty
// - setTokens / get* round-trips
// - clear() resets every accessor to null
// - simulated reload (vi.resetModules + dynamic re-import) loses state

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

describe("tokenStore", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  afterEach(() => {
    vi.resetModules();
  });

  it("returns null for every accessor before any token is set", async () => {
    const store = await import("@/api/tokenStore");
    expect(store.getAccessToken()).toBeNull();
    expect(store.getRefreshToken()).toBeNull();
    expect(store.getIdToken()).toBeNull();
  });

  it("round-trips tokens through setTokens / get*", async () => {
    const store = await import("@/api/tokenStore");
    store.setTokens({ access: "a", refresh: "r", id: "i" });
    expect(store.getAccessToken()).toBe("a");
    expect(store.getRefreshToken()).toBe("r");
    expect(store.getIdToken()).toBe("i");
  });

  it("clear() resets every accessor to null", async () => {
    const store = await import("@/api/tokenStore");
    store.setTokens({ access: "a", refresh: "r", id: "i" });
    store.clear();
    expect(store.getAccessToken()).toBeNull();
    expect(store.getRefreshToken()).toBeNull();
    expect(store.getIdToken()).toBeNull();
  });

  it("simulated reload (module reset) loses all state", async () => {
    const first = await import("@/api/tokenStore");
    first.setTokens({ access: "a", refresh: "r", id: "i" });
    expect(first.getAccessToken()).toBe("a");

    vi.resetModules();

    const second = await import("@/api/tokenStore");
    expect(second.getAccessToken()).toBeNull();
    expect(second.getRefreshToken()).toBeNull();
    expect(second.getIdToken()).toBeNull();
  });
});
