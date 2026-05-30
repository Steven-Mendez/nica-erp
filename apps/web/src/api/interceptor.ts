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
// The router is intentionally NOT imported here. The shell registers a
// callback via setOnAuthLost so this layer remains testable in isolation.

import { clear, getAccessToken, getRefreshToken, setTokens } from "@/api/tokenStore";

let onAuthLost: (() => void) | null = null;

export const setOnAuthLost = (cb: () => void): void => {
  onAuthLost = cb;
};

interface RetriableInit extends RequestInit {
  __authRetried?: boolean;
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
  return { ...init, headers };
};

interface RefreshTokenBundle {
  access_token: string;
  refresh_token: string;
  id_token: string;
  token_type: "Bearer";
}

/**
 * Attempts a single refresh using the in-memory refresh token. Returns true if
 * the token store was updated, false otherwise. Never throws.
 */
const tryRefresh = async (): Promise<boolean> => {
  const refreshToken = getRefreshToken();
  if (refreshToken === null) return false;

  let response: Response;
  try {
    response = await rawFetch(`${baseUrl()}/v1/auth/refresh`, {
      method: "POST",
      headers: { "Content-Type": "application/json", Accept: "application/json" },
      body: JSON.stringify({ refresh_token: refreshToken }),
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

  if (
    typeof body.access_token !== "string" ||
    typeof body.refresh_token !== "string" ||
    typeof body.id_token !== "string"
  ) {
    return false;
  }

  setTokens({ access: body.access_token, refresh: body.refresh_token, id: body.id_token });
  return true;
};

const handleAuthLost = (): void => {
  clear();
  if (onAuthLost !== null) onAuthLost();
};

/**
 * Boot-time recovery: if a refresh token survived in sessionStorage (page
 * reload, new tab restored from the session), exchange it for a fresh access
 * token before the router mounts. Clears the persisted token on failure so a
 * dead refresh token does not keep producing /v1/auth/refresh calls on every
 * reload.
 */
export const bootRefresh = async (): Promise<boolean> => {
  if (getRefreshToken() === null) return false;
  const ok = await tryRefresh();
  if (!ok) clear();
  return ok;
};

/**
 * Auth-aware fetch.
 *
 * - Attaches Authorization: Bearer <accessToken> from the in-memory store.
 * - On a 401 response, attempts ONE refresh + ONE retry.
 * - Never recurses: the second attempt is dispatched with __authRetried=true,
 *   so even if it also returns 401 we bail out instead of looping.
 */
export const fetchWithAuth = async (
  input: RequestInfo | URL,
  init: RetriableInit = {},
): Promise<Response> => {
  const first = await fetch(input, attachAuth(input, init));
  if (first.status !== 401) return first;

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
