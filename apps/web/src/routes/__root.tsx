// apps/web/src/routes/__root.tsx
//
// Root route definition (code-based router). Lives in its own file so the
// individual route files can import it without pulling in the full route tree
// (which would create a circular import with `src/router.ts`).
//
// `errorComponent` and `notFoundComponent` are the last-resort boundaries:
// they catch failures that escape the AppShell (router crash, root loader
// failure, garbage URLs). They render a bare-shell variant — the AppShell
// has its own `errorComponent` that keeps the sidebar context when a child
// loader fails inside the shell.

import { Outlet, createRootRoute } from "@tanstack/react-router";
import { BrandLayout } from "@/components/brand-header";
import { dispatchRouteError } from "@/components/error-fallback/dispatch";
import { RouteNotFoundCard } from "@/components/error-fallback/route-not-found-card";

export const rootRoute = createRootRoute({
  component: () => <Outlet />,
  errorComponent: ({ error }) => <BrandLayout>{dispatchRouteError(error)}</BrandLayout>,
  notFoundComponent: () => (
    <BrandLayout>
      <RouteNotFoundCard />
    </BrandLayout>
  ),
});
