// In-shell error boundary for AppShell-bearing routes. Imported by
// `router.ts` and attached as the route-level `errorComponent` so a
// loader/render failure inside the dashboard area renders the fallback
// card without losing the sidebar context. The root route's own
// `errorComponent` covers failures that escape this layer (bare-shell
// variant on `/login` chrome).

import { AppShell } from "@/components/app-shell";
import { dispatchRouteError } from "@/components/error-fallback/dispatch";

export const InShellErrorBoundary = ({ error }: { error: unknown }) => (
  <AppShell>{dispatchRouteError(error)}</AppShell>
);
