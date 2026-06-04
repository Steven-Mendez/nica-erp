// apps/web/src/app.tsx
//
// Application shell: TanStack Query provider + TanStack Router provider.
//
// We register a single onAuthLost callback that routes the user back to
// /login when the 401 interceptor gives up (refresh failed or retried
// request still 401). The callback is registered exactly once at module
// load — not inside a component effect — to keep the interceptor module
// independently testable.
//
// On mount, the shell waits for `bootRefresh` to resolve before mounting
// the router. If a refresh token survived in sessionStorage, this exchanges
// it for a fresh access token so a page reload keeps the user signed in.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { useEffect, useState } from "react";
import { Toaster } from "sonner";
import { bootRefresh, setOnAuthLost } from "@/api/interceptor";
import { router } from "@/router";
import { ThemeProvider } from "@/components/theme-provider";
import { OverlayMutexProvider } from "@/components/overlay-mutex";
import { TooltipProvider } from "@/components/ui/tooltip";

setOnAuthLost(() => {
  void router.navigate({ to: "/login" });
});

export function App() {
  const [client] = useState(
    () =>
      new QueryClient({
        defaultOptions: {
          queries: {
            // Treat data as fresh for 60s. With the default of 0, every mount
            // of a component using useQuery triggers a refetch — wasteful for
            // the auth shell where /me changes rarely.
            staleTime: 60_000,
            // Tab focus refetches add noise without buying much for an
            // operator ERP; routes that need live polling (e.g. /healthz)
            // opt back in via `refetchInterval`.
            refetchOnWindowFocus: false,
            retry: 1,
          },
        },
      }),
  );
  // Always attempt one cookie-backed refresh on mount: the SPA cannot
  // inspect the httpOnly `nica_erp_rt` cookie from JS, so a fresh load
  // calls /v1/auth/refresh once and lets the API decide.
  const [bootReady, setBootReady] = useState(false);

  useEffect(() => {
    if (bootReady) return;
    let cancelled = false;
    void bootRefresh().finally(() => {
      if (!cancelled) setBootReady(true);
    });
    return () => {
      cancelled = true;
    };
  }, [bootReady]);

  return (
    <ThemeProvider defaultTheme="system" storageKey="nica-erp-theme">
      <OverlayMutexProvider>
        <QueryClientProvider client={client}>
          <TooltipProvider>{bootReady ? <RouterProvider router={router} /> : null}</TooltipProvider>
          {/*
           * Single Sonner Toaster mount for the whole app. `richColors` opts
           * in to the green/red theming for success/error variants; the
           * default `aria-live="polite"` semantics are already set by the
           * library, so screen readers announce the toast without preempting
           * the user's current task.
           */}
          <Toaster richColors position="top-right" />
        </QueryClientProvider>
      </OverlayMutexProvider>
    </ThemeProvider>
  );
}
