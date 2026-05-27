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

const emailSearchSchema = z.object({
  email: z.string().email().optional(),
});

const indexRoute = createRoute({
  getParentRoute: () => rootRoute,
  path: "/",
  beforeLoad: () => {
    throw redirect({ to: "/login" });
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
  component: lazyRouteComponent(() => import("@/routes/me"), "MeRoute"),
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
]);

export const router = createRouter({ routeTree });

declare module "@tanstack/react-router" {
  interface Register {
    router: typeof router;
  }
}
