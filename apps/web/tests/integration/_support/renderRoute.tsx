// Integration test render helper.
//
// Wraps a route component in a fresh QueryClient. The router is intentionally
// NOT mounted at this layer: every authenticated guard reads `getAccessToken`
// from `@/api/tokenStore`, so an integration test sets that up via
// `tokenStore.setTokens(...)` (or leaves it cleared for the anonymous case)
// and then renders the route component. This keeps integration tests
// independent of the full route tree, which is exercised at the e2e layer.
//
// Pair this helper with the MSW server in `tests/integration/msw/server.ts`:
// the default handlers cover the happy path; per-spec overrides via
// `server.use(http.<verb>(...))` cover the error paths.

import type { ReactElement, ReactNode } from "react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { render, type RenderResult } from "@testing-library/react";

const makeClient = (): QueryClient =>
  new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 0 },
      mutations: { retry: false },
    },
  });

interface RenderOptions {
  client?: QueryClient;
  wrapper?: (children: ReactNode) => ReactElement;
}

export interface RenderWithProvidersResult extends RenderResult {
  client: QueryClient;
}

export const renderWithProviders = (
  ui: ReactElement,
  opts: RenderOptions = {},
): RenderWithProvidersResult => {
  const client = opts.client ?? makeClient();
  const wrap = (children: ReactNode): ReactElement =>
    opts.wrapper ? opts.wrapper(children) : (children as ReactElement);
  const utils = render(<QueryClientProvider client={client}>{wrap(ui)}</QueryClientProvider>);
  return Object.assign(utils, { client });
};
