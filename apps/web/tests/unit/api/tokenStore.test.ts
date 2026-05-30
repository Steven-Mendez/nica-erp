// apps/web/tests/unit/api/tokenStore.test.ts
//
// Verifies the hybrid token store behaviour:
// - access AND id tokens live in memory only
// - the refresh token is persisted in sessionStorage so a reload (module
//   re-import) can still read it back
// - clear() resets every accessor AND removes the persisted entry

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const STORAGE_KEY = "nica-erp:refresh-token";

describe("tokenStore", () => {
  beforeEach(() => {
    vi.resetModules();
    window.sessionStorage.clear();
  });

  afterEach(() => {
    vi.resetModules();
    window.sessionStorage.clear();
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

  it("persists the refresh token to sessionStorage", async () => {
    const store = await import("@/api/tokenStore");
    store.setTokens({ access: "a", refresh: "r-persisted", id: "i" });
    expect(window.sessionStorage.getItem(STORAGE_KEY)).toBe("r-persisted");
  });

  it("does NOT persist the access or id token", async () => {
    const store = await import("@/api/tokenStore");
    store.setTokens({ access: "a", refresh: "r", id: "i" });
    // Only the refresh key should exist; nothing carrying the access/id bytes.
    const all = Object.entries({ ...window.sessionStorage });
    const containsAccess = all.some(([, v]) => v === "a");
    const containsId = all.some(([, v]) => v === "i");
    expect(containsAccess).toBe(false);
    expect(containsId).toBe(false);
  });

  it("clear() resets every accessor and removes the persisted refresh token", async () => {
    const store = await import("@/api/tokenStore");
    store.setTokens({ access: "a", refresh: "r", id: "i" });
    store.clear();
    expect(store.getAccessToken()).toBeNull();
    expect(store.getRefreshToken()).toBeNull();
    expect(store.getIdToken()).toBeNull();
    expect(window.sessionStorage.getItem(STORAGE_KEY)).toBeNull();
  });

  it("after a simulated reload, access/id are lost but the refresh token is recovered from sessionStorage", async () => {
    const first = await import("@/api/tokenStore");
    first.setTokens({ access: "a", refresh: "r", id: "i" });
    expect(first.getAccessToken()).toBe("a");

    vi.resetModules();

    const second = await import("@/api/tokenStore");
    expect(second.getAccessToken()).toBeNull();
    expect(second.getIdToken()).toBeNull();
    // Refresh survives the reload — this is what powers boot-time silent refresh.
    expect(second.getRefreshToken()).toBe("r");
  });
});
