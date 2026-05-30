// MSW Node server for the integration lane. Lifecycle hooks are wired in
// `tests/integration/setup.ts` per the MSW Node integration guide:
// https://mswjs.io/docs/integrations/node

import { setupServer } from "msw/node";
import { handlers } from "./handlers";

export const server = setupServer(...handlers);
