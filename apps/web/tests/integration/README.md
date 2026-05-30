# Frontend integration tests

The integration lane renders feature flows with the **real** TanStack
Router + a fresh `QueryClient` + an MSW server typed against the
committed OpenAPI schema. Compared to the unit lane this is slower
(MSW lifecycle, real DOM trees), but catches a class of regression
that no Zod test will: wiring bugs, request shape drift, cache
invalidation mistakes, accessibility regressions.

## When to write an integration spec

- A route lands a form or a list view.
- A hook's invalidation set changes shape.
- An RBAC affordance gate gets re-wired.
- A redirect rule in `src/lib/route-guard.ts` changes.
- Any time a unit test would have to mock a `QueryClient` or a router
  to assert behaviour — that's a sign the test belongs here.

## Layout

```
tests/integration/
├── _support/
│   ├── renderRoute.tsx          # QueryClient wrapper helper
│   └── expectNoA11yViolations.ts  # axe-core matcher
├── msw/
│   ├── server.ts                # setupServer(...handlers)
│   └── handlers.ts              # createOpenApiHttp<paths>() defaults
├── api/                         # API infra exercised end-to-end
├── components/                  # shell + sidebar + identity-layout
├── features/                    # per-slice flows
├── routes/                      # one .spec.tsx per src/routes/*.tsx
└── setup.ts                     # MSW lifecycle (listen/reset/close)
```

`pnpm test:layout` enforces that nothing from this lane leaks back
into `tests/unit/`.

## Writing handlers

Default handlers live in `msw/handlers.ts`. Per-spec overrides go
inline with `server.use(http.<verb>(...))`:

```ts
import { server } from "@/../tests/integration/msw/server";
import { http } from "@/../tests/integration/msw/handlers";

it("renders the 422 banner when the password policy rejects", async () => {
  server.use(
    http.post("/v1/auth/register", ({ response }) =>
      response(422).json({
        type: "about:blank",
        title: "Password rejected",
        status: 422,
        code: "auth.password_too_weak",
      }),
    ),
  );
  // ...
});
```

`afterEach(() => server.resetHandlers())` (in `setup.ts`) restores the
baseline between tests.

## Accessibility

Every route spec asserts axe-core has no violations:

```ts
import { expectNoA11yViolations } from "../_support/expectNoA11yViolations";

it("/login is wcag2aa-clean", async () => {
  const { container } = renderWithProviders(<LoginRoute />);
  await expectNoA11yViolations(container);
});
```

## Coverage ratchet

Coverage thresholds in `apps/web/vite.config.ts` start at the locked
baseline. To ratchet after a backfill PR has measurably raised
coverage:

```bash
cd apps/web
pnpm exec vitest run --coverage --update
```

That flag flips `coverage.thresholds.autoUpdate` for the run and
rewrites the floor in `vite.config.ts`. **CI never runs this** — only
the local maintainer recipe does, on a green run, in a PR dedicated
to the ratchet.

## Verification matrix

`pnpm test:matrix` regenerates
`apps/web/coverage/verification-matrix.json` and exits non-zero if
any inventory entry (route, hook, schema, shared component) maps to
zero tests. The artefact is uploaded by the `integration` CI job so
the question "is feature X tested?" has a one-click answer on every
PR run page.
