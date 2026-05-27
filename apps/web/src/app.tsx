// apps/web/src/app.tsx
//
// Application shell: TanStack Query provider + TanStack Router provider.
//
// We register a single onAuthLost callback that routes the user back to
// /login when the 401 interceptor gives up (refresh failed or retried
// request still 401). The callback is registered exactly once at module
// load — not inside a component effect — to keep the interceptor module
// independently testable.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { RouterProvider } from "@tanstack/react-router";
import { useState } from "react";
import { setOnAuthLost } from "@/api/interceptor";
import { router } from "@/router";
import { ThemeProvider } from "@/components/theme-provider";

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
  return (
    <ThemeProvider defaultTheme="system" storageKey="nica-erp-theme">
      <QueryClientProvider client={client}>
        <RouterProvider router={router} />
      </QueryClientProvider>
    </ThemeProvider>
  );
}
