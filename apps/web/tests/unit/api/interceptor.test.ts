// apps/web/tests/unit/api/interceptor.test.ts
//
// Covers the three scenarios from the frontend-shell spec for the 401
// interceptor:
//   1. 401 -> refresh succeeds -> retry returns 200
//   2. 401 -> refresh fails -> onAuthLost fires and tokens are cleared
//   3. cascading 401s -> at most one refresh + one retry, then bail out
//
// The global `fetch` is stubbed via vi.fn() so nothing hits the network.

import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

interface FetchCall {
  url: string;
  init: RequestInit | undefined;
}

const jsonResponse = (status: number, body: unknown): Response => {
  return new Response(JSON.stringify(body), {
    status,
    headers: { "Content-Type": "application/json" },
  });
};

const okResponse = (body: unknown = { ok: true }): Response => jsonResponse(200, body);
const unauthorizedResponse = (): Response => jsonResponse(401, { detail: "nope" });

describe("fetchWithAuth interceptor", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  afterEach(() => {
    vi.restoreAllMocks();
  });

  it("401 -> refresh succeeds -> retry returns 200", async () => {
    const { setTokens, getAccessToken } = await import("@/api/tokenStore");
    const { fetchWithAuth, setOnAuthLost } = await import("@/api/interceptor");

    setTokens({ access: "old-access", refresh: "old-refresh", id: "old-id" });
    const onAuthLost = vi.fn();
    setOnAuthLost(onAuthLost);

    const calls: FetchCall[] = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      calls.push({ url, init });
      if (url.endsWith("/v1/auth/refresh")) {
        return jsonResponse(200, {
          access_token: "new-access",
          refresh_token: "new-refresh",
          id_token: "new-id",
          token_type: "Bearer",
        });
      }
      // First call to /v1/me: 401. Second call (retry): 200.
      const previousMeCalls = calls.filter((c) => c.url.endsWith("/v1/me")).length;
      if (previousMeCalls === 1) return unauthorizedResponse();
      return okResponse({ id: "u1", email: "u@example.com" });
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await fetchWithAuth("http://api.test/v1/me");

    expect(response.status).toBe(200);
    const refreshCalls = calls.filter((c) => c.url.endsWith("/v1/auth/refresh"));
    expect(refreshCalls).toHaveLength(1);
    const meCalls = calls.filter((c) => c.url.endsWith("/v1/me"));
    expect(meCalls).toHaveLength(2);

    // After refresh the new access token must have been stashed in the store.
    expect(getAccessToken()).toBe("new-access");
    // And the retry must have used it in the Authorization header.
    const retryHeaders = new Headers(meCalls[1]?.init?.headers ?? {});
    expect(retryHeaders.get("Authorization")).toBe("Bearer new-access");

    expect(onAuthLost).not.toHaveBeenCalled();
  });

  it("refresh fails -> onAuthLost fires and tokens are cleared", async () => {
    const { setTokens, getAccessToken } = await import("@/api/tokenStore");
    const { fetchWithAuth, setOnAuthLost } = await import("@/api/interceptor");

    setTokens({ access: "a", refresh: "r", id: "i" });
    const onAuthLost = vi.fn();
    setOnAuthLost(onAuthLost);

    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/v1/auth/refresh")) return unauthorizedResponse();
      return unauthorizedResponse();
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await fetchWithAuth("http://api.test/v1/me");

    expect(response.status).toBe(401);
    expect(onAuthLost).toHaveBeenCalledTimes(1);
    expect(getAccessToken()).toBeNull();
  });

  it("never retries more than once even when every response is 401", async () => {
    const { setTokens } = await import("@/api/tokenStore");
    const { fetchWithAuth, setOnAuthLost } = await import("@/api/interceptor");

    setTokens({ access: "a", refresh: "r", id: "i" });
    const onAuthLost = vi.fn();
    setOnAuthLost(onAuthLost);

    const calls: FetchCall[] = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      calls.push({ url, init });
      if (url.endsWith("/v1/auth/refresh")) {
        // Refresh "succeeds" so the interceptor proceeds to the retry path —
        // but the retried request still returns 401. We must NOT trigger
        // another refresh on that second 401.
        return jsonResponse(200, {
          access_token: "new-access",
          refresh_token: "new-refresh",
          id_token: "new-id",
          token_type: "Bearer",
        });
      }
      return unauthorizedResponse();
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await fetchWithAuth("http://api.test/v1/me");

    expect(response.status).toBe(401);

    const refreshCalls = calls.filter((c) => c.url.endsWith("/v1/auth/refresh"));
    expect(refreshCalls).toHaveLength(1);

    const meCalls = calls.filter((c) => c.url.endsWith("/v1/me"));
    expect(meCalls).toHaveLength(2);

    expect(onAuthLost).toHaveBeenCalledTimes(1);
  });

  it("attaches Authorization: Bearer when a token is present", async () => {
    const { setTokens } = await import("@/api/tokenStore");
    const { fetchWithAuth, setOnAuthLost } = await import("@/api/interceptor");

    setTokens({ access: "abc", refresh: "r", id: "i" });
    setOnAuthLost(vi.fn());

    const calls: FetchCall[] = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      calls.push({ url, init });
      return okResponse();
    });
    vi.stubGlobal("fetch", fetchMock);

    await fetchWithAuth("http://api.test/v1/me");

    const headers = new Headers(calls[0]?.init?.headers ?? {});
    expect(headers.get("Authorization")).toBe("Bearer abc");
  });

  it("omits Authorization when no token is in the store", async () => {
    const { clear } = await import("@/api/tokenStore");
    const { fetchWithAuth, setOnAuthLost } = await import("@/api/interceptor");

    clear();
    setOnAuthLost(vi.fn());

    const calls: FetchCall[] = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      calls.push({ url, init });
      return okResponse();
    });
    vi.stubGlobal("fetch", fetchMock);

    await fetchWithAuth("http://api.test/v1/me");

    const headers = new Headers(calls[0]?.init?.headers ?? {});
    expect(headers.get("Authorization")).toBeNull();
  });
});
