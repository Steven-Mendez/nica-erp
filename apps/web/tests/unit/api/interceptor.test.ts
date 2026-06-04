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

    setTokens({ access: "old-access", id: "old-id" });
    const onAuthLost = vi.fn();
    setOnAuthLost(onAuthLost);

    const calls: FetchCall[] = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      calls.push({ url, init });
      if (url.endsWith("/v1/auth/refresh")) {
        return jsonResponse(200, {
          access_token: "new-access",
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

    setTokens({ access: "a", id: "i" });
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

    setTokens({ access: "a", id: "i" });
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

    setTokens({ access: "abc", id: "i" });
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

  it("preserves Request headers (e.g. Content-Type) when attaching Authorization", async () => {
    // Regression: openapi-fetch passes a Request object as `input`. If
    // attachAuth builds headers from `init.headers` alone, the Request's
    // Content-Type is lost and the server receives the body as non-JSON,
    // producing a 422 "Input should be a valid dictionary or object".
    const { setTokens } = await import("@/api/tokenStore");
    const { fetchWithAuth, setOnAuthLost } = await import("@/api/interceptor");

    setTokens({ access: "abc", id: "i" });
    setOnAuthLost(vi.fn());

    const calls: FetchCall[] = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      calls.push({ url, init });
      return okResponse();
    });
    vi.stubGlobal("fetch", fetchMock);

    const request = new Request("http://api.test/v1/me", {
      method: "PATCH",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ display_name: "Ada" }),
    });
    await fetchWithAuth(request);

    const headers = new Headers(calls[0]?.init?.headers ?? {});
    expect(headers.get("Authorization")).toBe("Bearer abc");
    expect(headers.get("Content-Type")).toBe("application/json");
  });

  it("bootRefresh: always issues one cookie-backed POST and returns false on 401", async () => {
    // The SPA cannot see the httpOnly `nica_erp_rt` cookie from JS, so
    // boot ALWAYS attempts one refresh. The API decides via the cookie
    // header whether the call succeeds.
    const { clear, getAccessToken } = await import("@/api/tokenStore");
    const { bootRefresh } = await import("@/api/interceptor");

    clear();
    const calls: FetchCall[] = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      calls.push({ url, init });
      return unauthorizedResponse();
    });
    vi.stubGlobal("fetch", fetchMock);

    const ok = await bootRefresh();

    expect(ok).toBe(false);
    expect(calls.filter((c) => c.url.endsWith("/v1/auth/refresh"))).toHaveLength(1);
    // Cookie must be shipped via credentials:"include" and the body must
    // be an empty object (no refresh_token leaking into JS-readable JSON).
    const refreshCall = calls[0];
    expect(refreshCall?.init?.credentials).toBe("include");
    expect(refreshCall?.init?.body).toBe("{}");
    expect(getAccessToken()).toBeNull();
  });

  it("bootRefresh: cookie-backed refresh succeeds → access + id tokens are hydrated", async () => {
    // Simulate a reload: in-memory state is gone. The browser still
    // owns the `nica_erp_rt` cookie (invisible to JS); a 200 response
    // proves the API accepted it.
    const { getAccessToken } = await import("@/api/tokenStore");
    const { bootRefresh } = await import("@/api/interceptor");

    expect(getAccessToken()).toBeNull();

    const fetchMock = vi.fn(async (input: RequestInfo | URL) => {
      const url = typeof input === "string" ? input : input.toString();
      if (url.endsWith("/v1/auth/refresh")) {
        return jsonResponse(200, {
          access_token: "boot-access",
          id_token: "boot-id",
          token_type: "Bearer",
        });
      }
      return okResponse();
    });
    vi.stubGlobal("fetch", fetchMock);

    const ok = await bootRefresh();

    expect(ok).toBe(true);
    expect(getAccessToken()).toBe("boot-access");
    // Refresh credential must never land in any JS-readable surface.
    expect(window.sessionStorage.getItem("nica-erp:refresh-token")).toBeNull();
  });

  it("bootRefresh: on 401 the in-memory store is cleared (cookie cleanup is the server's job)", async () => {
    const { setTokens, getAccessToken } = await import("@/api/tokenStore");
    const { bootRefresh } = await import("@/api/interceptor");

    // Pretend an earlier mount left a stale access token in memory.
    setTokens({ access: "stale-access", id: "stale-id" });

    const fetchMock = vi.fn(async () => unauthorizedResponse());
    vi.stubGlobal("fetch", fetchMock);

    const ok = await bootRefresh();

    expect(ok).toBe(false);
    expect(getAccessToken()).toBeNull();
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

  it("401 without bearer is passthrough: no refresh, no onAuthLost, no redirect", async () => {
    // Regression: wrong OTP on /confirm, wrong credentials on /login, used
    // reset token on /reset-password all return 401 from public endpoints.
    // The interceptor MUST surface that 401 to the caller (so FormErrorAlert
    // can render) without firing the "session lost" branch, since there is
    // no session to lose.
    const { clear } = await import("@/api/tokenStore");
    const { fetchWithAuth, setOnAuthLost } = await import("@/api/interceptor");

    clear();
    const onAuthLost = vi.fn();
    setOnAuthLost(onAuthLost);

    const calls: FetchCall[] = [];
    const fetchMock = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
      const url = typeof input === "string" ? input : input.toString();
      calls.push({ url, init });
      return unauthorizedResponse();
    });
    vi.stubGlobal("fetch", fetchMock);

    const response = await fetchWithAuth("http://api.test/v1/auth/confirm-signup", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ email: "a@b.test", code: "000000" }),
    });

    expect(response.status).toBe(401);
    expect(onAuthLost).not.toHaveBeenCalled();
    // No refresh call should have fired.
    const refreshCalls = calls.filter((c) => c.url.endsWith("/v1/auth/refresh"));
    expect(refreshCalls).toHaveLength(0);
    // Exactly one network call (the original) — no retry.
    expect(calls).toHaveLength(1);
    // The original request never carried an Authorization header.
    const headers = new Headers(calls[0]?.init?.headers ?? {});
    expect(headers.get("Authorization")).toBeNull();
  });
});
