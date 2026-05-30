// apps/web/src/lib/route-guard.ts
//
// Decides where to send an authenticated user based on their profile
// + memberships, so the SPA never lands on /dashboard before:
//
//  1. The profile is complete (display_name set on /welcome).
//  2. The user has at least one accepted membership.
//  3. The operator has confirmed an empresa via the picker this
//     session (sessionStorage `nica-erp:picker-confirmed`).
//  4. An active tenant is selected (defensive fallback: caught if
//     the JWT lost `custom:active_tenant` after a refresh).
//
// The guard is consumed from `beforeLoad` in `router.ts`; failing
// the check throws a `redirect({ to })` so the destination route
// is never mounted.

import { getMe } from "@/features/auth/api/endpoints";
import { getMyTenants } from "@/features/tenants/api/endpoints";

export type GuardTarget = "/welcome" | "/onboarding" | "/tenants" | "/dashboard" | null;

export interface GuardOptions {
  /** Route the caller is trying to navigate to; informs which guards apply. */
  pathname: string;
}

/**
 * Routes exempt from the *display_name* probe (must be reachable while
 * the profile is still NULL).
 */
const WELCOME_EXEMPT = new Set(["/welcome", "/account", "/health"]);

/**
 * Routes exempt from the *needs-active-tenant* probe.
 */
const TENANT_EXEMPT = new Set([
  "/welcome",
  "/onboarding",
  "/tenants",
  "/tenants/new",
  "/account",
  "/health",
]);

// Session flag set when the operator has confirmed an empresa via the
// picker (or via /tenants/new → switch). Lives in sessionStorage so it
// dies with the tab — a fresh tab forces the picker again.
export const PICKER_FLAG_KEY = "nica-erp:picker-confirmed";

export function isPickerConfirmed(): boolean {
  if (typeof window === "undefined") return false;
  try {
    return window.sessionStorage.getItem(PICKER_FLAG_KEY) === "1";
  } catch {
    return false;
  }
}

export function setPickerConfirmed(): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.setItem(PICKER_FLAG_KEY, "1");
  } catch {
    // sessionStorage can throw in private windows; the active-tenant
    // probe in the guard still catches the unauthenticated case.
  }
}

export function clearPickerConfirmed(): void {
  if (typeof window === "undefined") return;
  try {
    window.sessionStorage.removeItem(PICKER_FLAG_KEY);
  } catch {
    // Same as above.
  }
}

/**
 * Returns the path the SPA should navigate to instead of the requested
 * route, or `null` if the requested route is allowed.
 *
 * Network: calls `/v1/me` and `/v1/tenants/me`. Both should be cached
 * by TanStack Query for the rest of the session.
 */
export async function nextRouteForCurrentState({ pathname }: GuardOptions): Promise<GuardTarget> {
  const me = await getMe();

  // First-login probe — display_name is the canonical "completed
  // profile" signal (locale is deferred per ADR-0033).
  if (me.display_name == null && !WELCOME_EXEMPT.has(pathname)) {
    return "/welcome";
  }

  // Membership probe.
  const memberships = await getMyTenants();
  const count = memberships.items.length;

  if (count === 0) {
    if (pathname === "/onboarding" || WELCOME_EXEMPT.has(pathname)) {
      return null;
    }
    return "/onboarding";
  }

  // Picker-confirmed probe. Without an explicit confirm this session,
  // force a trip through /tenants regardless of `custom:active_tenant`
  // — operators told us the sidebar chip was too easy to miss on day
  // one.
  if (!isPickerConfirmed() && !TENANT_EXEMPT.has(pathname)) {
    return "/tenants";
  }

  // Active tenant probe — defensive fallback for the case where the
  // flag is set but the JWT lost `custom:active_tenant` after a token
  // refresh.
  if ((me.active_tenant ?? null) === null && !TENANT_EXEMPT.has(pathname)) {
    return "/tenants";
  }

  return null;
}
