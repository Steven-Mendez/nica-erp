// Integration lane setup: MSW server lifecycle.
//
// Lifecycle pattern from https://mswjs.io/docs/integrations/node:
//   - listen before all
//   - resetHandlers after each (clears per-test server.use overrides)
//   - close after all

import { afterAll, afterEach, beforeAll } from "vitest";
import { server } from "./msw/server";

beforeAll(() => server.listen({ onUnhandledRequest: "error" }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
