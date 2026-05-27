// apps/web/src/routes/__root.tsx
//
// Root route definition (code-based router). Lives in its own file so the
// individual route files can import it without pulling in the full route tree
// (which would create a circular import with `src/router.ts`).

import { Outlet, createRootRoute } from "@tanstack/react-router";

export const rootRoute = createRootRoute({
  component: () => <Outlet />,
});
