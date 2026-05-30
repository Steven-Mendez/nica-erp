// apps/web/src/router.ts
//
// Code-based TanStack Router setup.
//
// Every route's `createRoute` call lives here, separated from the component
// modules under `src/routes/*.tsx`. That separation matters for two reasons:
//
//   1. Vite Fast Refresh requires each module to export *either* React
//      components *or* non-component values, never both. Co-locating a Route
//      object with its component invalidates HMR on every edit; isolating the
//      route config into this single non-component module keeps the
//      component files Fast-Refresh-clean.
//   2. The router tree is a single graph — having it assembled in one place
//      (instead of fan-out via per-file Route exports) makes the route shape
//      reviewable at a glance.
//
// Route components are loaded via `lazyRouteComponent` so each route file is
// its own JS chunk. The first paint (typically /login) doesn't pay for the
// code behind /me, /health, /confirm, etc.

import { createRoute, createRouter, lazyRouteComponent, redirect } from "@tanstack/react-router";
import { z } from "zod";
import { rootRoute } from "@/routes/__root";
import { getAccessToken } from "@/api/tokenStore";
import { nextRouteForCurrentState } from "@/lib/route-guard";
import { PENDING_INVITE_KEY } from "@/routes/invitations/accept";

function popPendingInviteToken(): string | null {
  if (typeof window === "undefined") return null;
  try {
    const token = window.sessionStorage.getItem(PENDING_INVITE_KEY);
    if (token === null || token.length === 0) return null;
    window.sessionStorage.removeItem(PENDING_INVITE_KEY);
    return token;
  } catch {
    return null;
  }
}

const emailSearchSchema = z.object({
  email: z.string().email().optional(),
});

/**
 * Guard fired by every authenticated route's ``beforeLoad``. When the
 * user is not signed in it sends them to ``/login``; when they ARE
 * signed in but the onboarding state isn't ready (no profile, no
 * memberships, no active tenant), it redirects to the correct step.
 */
async function authenticatedGuard(pathname: string): Promise<void> {
  if (getAccessToken() === null) {
    throw redirect({ to: "/login" });
  }
  const next = await nextRouteForCurrentState({ pathname });
  if (next !== null && next !== pathname) {
    throw redirect({ to: next });
  }
}

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  beforeLoad: async () => {
    if (getAccessToken() === null) {
      throw redirect({ to: "/login" });
    }
    // If an invitation token was stashed pre-login (signup flow
    // started from `/invitations/accept#t=…`), redeem it now by
    // hopping back through the accept route — the hash drives the
    // POST, and on success we land on /dashboard.
    const pending = popPendingInviteToken();
    if (pending !== null) {
      throw redirect({ to: "/invitations/accept", hash: `t=${pending}` });
    }
    // Run the guard against ``/dashboard`` so the user lands there
    // when nothing else is pending.
    const next = await nextRouteForCurrentState({ pathname: "/dashboard" });
    throw redirect({ to: next ?? "/dashboard" });
  },
});

const healthRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/health",
  component: lazyRouteComponent(() => import("@/routes/health"), "HealthRoute"),
});

const loginRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/login",
  component: lazyRouteComponent(() => import("@/routes/login"), "LoginRoute"),
});

const signupRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/signup",
  validateSearch: emailSearchSchema,
  component: lazyRouteComponent(() => import("@/routes/signup"), "SignupRoute"),
});

const confirmRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/confirm",
  validateSearch: emailSearchSchema,
  component: lazyRouteComponent(() => import("@/routes/confirm"), "ConfirmRoute"),
});

const forgotPasswordRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/forgot-password",
  component: lazyRouteComponent(() => import("@/routes/forgot-password"), "ForgotPasswordRoute"),
});

const resetPasswordRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/reset-password",
  validateSearch: emailSearchSchema,
  component: lazyRouteComponent(() => import("@/routes/reset-password"), "ResetPasswordRoute"),
});

const meRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/me",
  beforeLoad: () => {
    throw redirect({ to: "/account" });
  },
});

const accountRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/account",
  beforeLoad: () => {
    if (getAccessToken() === null) {
      throw redirect({ to: "/login" });
    }
  },
  component: lazyRouteComponent(() => import("@/routes/account"), "AccountRoute"),
});

const welcomeRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/welcome",
  beforeLoad: () => {
    if (getAccessToken() === null) {
      throw redirect({ to: "/login" });
    }
  },
  component: lazyRouteComponent(() => import("@/routes/welcome"), "WelcomeRoute"),
});

const onboardingRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/onboarding",
  beforeLoad: async () => {
    await authenticatedGuard("/onboarding");
  },
  component: lazyRouteComponent(() => import("@/routes/onboarding"), "OnboardingRoute"),
});

const dashboardRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/dashboard",
  beforeLoad: async () => {
    await authenticatedGuard("/dashboard");
  },
  component: lazyRouteComponent(() => import("@/routes/dashboard"), "DashboardRoute"),
});

const salesRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/sales",
  beforeLoad: async () => {
    await authenticatedGuard("/sales");
  },
  component: lazyRouteComponent(() => import("@/routes/sales"), "SalesRoute"),
});

const inventoryRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/inventory",
  beforeLoad: async () => {
    await authenticatedGuard("/inventory");
  },
  component: lazyRouteComponent(() => import("@/routes/inventory"), "InventoryRoute"),
});

const reportsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/reports",
  beforeLoad: async () => {
    await authenticatedGuard("/reports");
  },
  component: lazyRouteComponent(() => import("@/routes/reports"), "ReportsRoute"),
});

const settingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/settings",
  beforeLoad: async () => {
    await authenticatedGuard("/settings");
  },
  component: lazyRouteComponent(() => import("@/routes/settings"), "SettingsRoute"),
});

const tenantsIndexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/tenants",
  beforeLoad: async () => {
    await authenticatedGuard("/tenants");
  },
  component: lazyRouteComponent(() => import("@/routes/tenants/index"), "TenantsIndexRoute"),
});

const tenantsNewRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/tenants/new",
  component: lazyRouteComponent(() => import("@/routes/tenants/new"), "TenantsNewRoute"),
});

// Legacy path-form route. The empresa section now lives under
// `/empresa/usuarios`; this redirect keeps any stale bookmarks
// pointing at the dashboard's members surface from 404ing.
const tenantMembersLegacyRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/tenants/$tenantId/members",
  beforeLoad: () => {
    throw redirect({ to: "/empresa/users" });
  },
});

const empresaIndexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/empresa",
  beforeLoad: async () => {
    await authenticatedGuard("/empresa");
  },
  component: lazyRouteComponent(() => import("@/routes/empresa/index"), "EmpresaIndexRoute"),
});

const empresaUsersRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/empresa/users",
  beforeLoad: async () => {
    await authenticatedGuard("/empresa/users");
  },
  component: lazyRouteComponent(() => import("@/routes/empresa/users"), "EmpresaUsuariosRoute"),
});

const empresaSettingsRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/empresa/settings",
  beforeLoad: async () => {
    await authenticatedGuard("/empresa/settings");
  },
  component: lazyRouteComponent(
    () => import("@/routes/empresa/settings"),
    "EmpresaConfiguracionRoute",
  ),
});

// Legacy editor path — kept as a redirect so old banner links land
// on the new /empresa/settings screen.
const empresaEditarLegacyRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/empresa/editar",
  beforeLoad: () => {
    throw redirect({ to: "/empresa/settings" });
  },
});

// New hash-token entry point. The component reads `location.hash`
// (`#t=<token>`) on mount, strips it, and runs the accept POST. If
// no hash is present and the user is authenticated, it shows a paste
// input. The legacy path-form route below stays in place for emails
// already in flight that still link to the old URL.
const acceptInvitationRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/invitations/accept",
  validateSearch: emailSearchSchema,
  component: lazyRouteComponent(
    () => import("@/routes/invitations/accept"),
    "AcceptInvitationRoute",
  ),
});

const acceptInvitationLegacyRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/invitations/$token/accept",
  beforeLoad: ({ params }) => {
    // Redirect old path-form links to the new hash-form so the token
    // does not stay in the path (logs, history, Referer).
    throw redirect({
      to: "/invitations/accept",
      hash: `t=${(params as { token: string }).token}`,
    });
  },
});

const routeTree = rootRoute.addChildren([
  indexRoute,
  healthRoute,
  loginRoute,
  signupRoute,
  confirmRoute,
  forgotPasswordRoute,
  resetPasswordRoute,
  meRoute,
  accountRoute,
  welcomeRoute,
  onboardingRoute,
  dashboardRoute,
  salesRoute,
  inventoryRoute,
  reportsRoute,
  settingsRoute,
  tenantsIndexRoute,
  tenantsNewRoute,
  tenantMembersLegacyRoute,
  empresaIndexRoute,
  empresaUsersRoute,
  empresaSettingsRoute,
  empresaEditarLegacyRoute,
  acceptInvitationRoute,
  acceptInvitationLegacyRoute,
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
