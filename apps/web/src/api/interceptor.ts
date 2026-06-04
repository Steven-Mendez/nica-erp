// apps/web/src/api/interceptor.ts
//
// Single-retry 401 interceptor.
//
// On a 401 response the interceptor:
//   1. calls POST /v1/auth/refresh with the in-memory refresh token, ONCE;
//   2. on success, updates the token store and retries the original request,
//      ONCE;
//   3. on failure (refresh non-2xx, or retried request still 401), clears
//      the token store and invokes the registered onAuthLost callback so the
//      shell can navigate to /login.
//
// A per-request `__authRetried` flag (carried on a wrapping RequestInit type)
// ensures we never retry more than once for a single original request, which
// prevents the cascading-401 infinite-loop scenario from the spec.
//
// 401s from requests that never carried a bearer (the in-memory access token
// store was empty) are passthrough errors. Public endpoints like
// `/v1/auth/confirm-signup`, `/v1/auth/login`, and `/v1/auth/password/reset`
// return 401 to mean "wrong input" (bad OTP, bad credentials, used token);
// there is no session to lose, so the interceptor MUST NOT fire the
// auth-lost branch. The caller surfaces the 401 via `FormErrorAlert` /
// `messageForProblem`. The `__bearerAttached` flag on RetriableInit
// discriminates the two cases — it is set by `attachAuth` only when the
// `Authorization` header is actually added.
//
// The router is intentionally NOT imported here. The shell registers a
// callback via setOnAuthLost so this layer remains testable in isolation.

import { clear, getAccessToken, setTokens } from "@/api/tokenStore";

let onAuthLost: (() => void) | null = null;

export const setOnAuthLost = (cb: () => void): void => {
  onAuthLost = cb;
};

interface RetriableInit extends RequestInit {
  __authRetried?: boolean;
  __bearerAttached?: boolean;
}

const baseUrl = (): string => import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

/**
 * Direct passthrough to `fetch`, never attaches the bearer token, never retries.
 * Used by the unauthenticated auth endpoints and (internally) by the refresh
 * call below.
 */
export const rawFetch = (input: RequestInfo | URL, init?: RequestInit): Promise<Response> => {
  return fetch(input, init);
};

const attachAuth = (input: RequestInfo | URL, init: RetriableInit): RetriableInit => {
  const token = getAccessToken();
  if (token === null) return init;
  // When `input` is a Request (the path openapi-fetch takes), its headers
  // must be merged in — passing `init.headers` alone to `fetch(request, init)`
  // would replace the Request's headers wholesale, dropping Content-Type.
  const base = input instanceof Request ? input.headers : (init.headers ?? {});
  const headers = new Headers(base);
  headers.set("Authorization", `Bearer ${token}`);
  return { ...init, headers, __bearerAttached: true };
};

interface RefreshTokenBundle {
  access_token: string;
  id_token: string;
  token_type: "Bearer";
}

let refreshPromise: Promise<boolean> | null = null;

/**
 * Attempts a single refresh via the `nica_erp_rt` httpOnly cookie. Returns
 * true if the token store was updated, false otherwise. Never throws.
 * Concurrent calls are deduplicated so only one network request fires.
 */
const tryRefresh = async (): Promise<boolean> => {
  if (refreshPromise !== null) return refreshPromise;

  refreshPromise = (async () => {
    let response: Response;
    try {
      response = await rawFetch(`${baseUrl()}/v1/auth/refresh`, {
        method: "POST",
        // The browser ships the httpOnly `nica_erp_rt` cookie that
        // carries the refresh token. The body is empty — the SPA no
        // longer has any JS-readable copy of the refresh credential.
        credentials: "include",
        headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: "{}",
      });
    } catch {
      return false;
    }

    if (!response.ok) return false;

    let body: RefreshTokenBundle;
    try {
      body = (await response.json()) as RefreshTokenBundle;
    } catch {
      return false;
    }

    if (typeof body.access_token !== "string" || typeof body.id_token !== "string") {
      return false;
    }

    setTokens({ access: body.access_token, id: body.id_token });
    return true;
  })();

  try {
    return await refreshPromise;
  } finally {
    refreshPromise = null;
  }
};

const handleAuthLost = (): void => {
  clear();
  if (onAuthLost !== null) onAuthLost();
};

/**
 * Boot-time recovery: attempt one cookie-backed refresh before the router
 * mounts. The SPA cannot inspect the httpOnly `nica_erp_rt` cookie from
 * JavaScript, so we always try once and let the API return 401 if no valid
 * refresh credential is present. On 401 we land on the unauthenticated
 * shell (no error toast — same UX as a logged-out visitor).
 */
export const bootRefresh = async (): Promise<boolean> => {
  const ok = await tryRefresh();
  if (!ok) clear();
  return ok;
};

/**
 * Auth-aware fetch.
 *
 * - Attaches Authorization: Bearer <accessToken> from the in-memory store.
 * - On a 401 from a request that DID carry a bearer, attempts ONE refresh +
 *   ONE retry. If both fail (or no refresh token is available), clears the
 *   token store and fires the registered onAuthLost callback.
 * - On a 401 from a request that did NOT carry a bearer (e.g. /v1/auth/login,
 *   /v1/auth/confirm-signup, /v1/auth/password/reset), returns the 401 to
 *   the caller as-is — the endpoint is just reporting "wrong input" and the
 *   route component surfaces it via FormErrorAlert. No refresh attempt, no
 *   auth-lost redirect.
 * - Never recurses: the bearer-attached retry is dispatched with
 *   __authRetried=true, so even if it also returns 401 we bail out instead
 *   of looping.
 */
export const fetchWithAuth = async (
  input: RequestInfo | URL,
  init: RetriableInit = {},
): Promise<Response> => {
  const attached = attachAuth(input, init);
  const first = await fetch(input, attached);
  if (first.status !== 401) return first;

  // No bearer was attached → this 401 is the endpoint speaking, not auth.
  // Surface it to the caller without touching the token store or redirecting.
  if (attached.__bearerAttached !== true) {
    return first;
  }

  // Already retried for this original request? Surface the 401 and route out.
  if (init.__authRetried === true) {
    handleAuthLost();
    return first;
  }

  const refreshed = await tryRefresh();
  if (!refreshed) {
    handleAuthLost();
    return first;
  }

  const retried = await fetch(input, attachAuth(input, { ...init, __authRetried: true }));
  if (retried.status === 401) {
    handleAuthLost();
  }
  return retried;
};
