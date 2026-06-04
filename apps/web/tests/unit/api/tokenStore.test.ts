// apps/web/tests/unit/api/tokenStore.test.ts
//
// Verifies the in-memory token store behaviour:
// - access AND id tokens live in memory only
// - the refresh token is NOT held by the store at all — it rides in the
//   `nica_erp_rt` httpOnly cookie set by the API; the SPA must never have
//   a JS-readable copy of it (audit F-011)
// - clear() resets every accessor and never touches sessionStorage

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const LEGACY_STORAGE_KEY = "nica-erp:refresh-token";

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
    expect(store.getIdToken()).toBeNull();
  });

  it("round-trips access + id tokens through setTokens / get*", async () => {
    const store = await import("@/api/tokenStore");
    store.setTokens({ access: "a", id: "i" });
    expect(store.getAccessToken()).toBe("a");
    expect(store.getIdToken()).toBe("i");
  });

  it("never writes the refresh token to sessionStorage (legacy key remains empty)", async () => {
    const store = await import("@/api/tokenStore");
    store.setTokens({ access: "a", id: "i" });
    // The legacy `nica-erp:refresh-token` key must stay absent: the
    // cookie carrier is now the only persistent surface.
    expect(window.sessionStorage.getItem(LEGACY_STORAGE_KEY)).toBeNull();
    // And no other key on sessionStorage should leak a JWT-shaped value.
    const all = Object.values({ ...window.sessionStorage });
    expect(all.some((v) => typeof v === "string" && v.startsWith("eyJ"))).toBe(false);
  });

  it("does NOT persist the access or id token", async () => {
    const store = await import("@/api/tokenStore");
    store.setTokens({ access: "a", id: "i" });
    const all = Object.entries({ ...window.sessionStorage });
    expect(all.some(([, v]) => v === "a")).toBe(false);
    expect(all.some(([, v]) => v === "i")).toBe(false);
  });

  it("clear() resets every accessor and leaves sessionStorage untouched", async () => {
    const store = await import("@/api/tokenStore");
    store.setTokens({ access: "a", id: "i" });
    window.sessionStorage.setItem("unrelated", "keep-me");
    store.clear();
    expect(store.getAccessToken()).toBeNull();
    expect(store.getIdToken()).toBeNull();
    // We must not blow away unrelated sessionStorage entries.
    expect(window.sessionStorage.getItem("unrelated")).toBe("keep-me");
    // And the legacy key must remain absent (we never wrote it).
    expect(window.sessionStorage.getItem(LEGACY_STORAGE_KEY)).toBeNull();
  });

  it("a simulated reload loses all in-memory tokens; recovery happens via the cookie + bootRefresh, not via storage", async () => {
    const first = await import("@/api/tokenStore");
    first.setTokens({ access: "a", id: "i" });
    expect(first.getAccessToken()).toBe("a");

    vi.resetModules();

    const second = await import("@/api/tokenStore");
    // Module-scoped state is gone. Recovery now relies on the cookie
    // ridden by `bootRefresh()` calling /v1/auth/refresh.
    expect(second.getAccessToken()).toBeNull();
    expect(second.getIdToken()).toBeNull();
  });
});
