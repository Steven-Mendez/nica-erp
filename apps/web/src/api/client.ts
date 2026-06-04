// apps/web/src/api/client.ts
//
// Typed openapi-fetch client. The `paths` type is regenerated from
// `/openapi.json` via `pnpm gen:api` and committed alongside the frontend
// changes that consume it.
//
// All requests go through `fetchWithAuth` so the in-memory access token is
// attached when present and the single-retry 401 → refresh → retry flow is
// uniform across every endpoint. Unauthenticated endpoints (login, register,
// refresh, etc.) carry no token in store, so `fetchWithAuth` is a no-op for
// them on the request path; on a 401 response from them (e.g. wrong
// credentials) the refresh attempt fails fast because there is no refresh
// token to use, and the original 401 surfaces unchanged for the route to
// render.

import createClient from "openapi-fetch";
import { fetchWithAuth } from "@/api/interceptor";
import type { paths } from "@/api/schema";

const baseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

export const api = createClient<paths>({
  baseUrl,
  fetch: fetchWithAuth,
  // Audit F-005: send credentials on every call so the browser ships
  // the httpOnly ``nica_erp_rt`` cookie back to /v1/auth/refresh and
  // /v1/auth/logout. Other endpoints ignore the cookie (it is path-
  // scoped to /v1/auth) so this is a no-op outside the auth surface.
  credentials: "include",
});

export type Paths = paths;
