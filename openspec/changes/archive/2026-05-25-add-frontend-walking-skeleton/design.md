## Context

The sprint-00 walking skeleton (docs/sprints/00-walking-skeleton.md) defines a Vite + React SPA on `:5173` whose only job is to read `GET /healthz` from the API and render the response inside a shadcn/ui `Card` + `Badge`. The frontend half doubles as the foundation that every later sprint extends: auth shell (sprint 02), tenant scoping (sprint 03), forms (sprint 02), i18n (sprint 05). That implies three concerns are worth pinning now:

1. **Toolchain**: which scripts, configs, and pinned versions every later sprint can assume.
2. **Application shell**: how the React app is bootstrapped (entry HTML, root render, providers, path alias), so feature work plugs in without renegotiating the shape.
3. **A single read-only consumer view** (`/healthz`) that exercises the whole stack — query client, typed API surface, shadcn theme — and is the only feature delivered in sprint 00.

Implementation already exists in `apps/web/`. This design captures the contract; tasks reconcile drift.

## Goals / Non-Goals

**Goals:**
- Encode the frontend toolchain as enforceable requirements (TypeScript strict + 4 named flags, package scripts including `gen:api`, ESLint flat config, Vitest under happy-dom, shadcn theme tokens wired through Tailwind).
- Encode the `/healthz` view's three rendering states (`loading`, `unreachable`, `value`) so future refactors keep the contract.
- Keep the application shell minimal (root render + QueryClientProvider + single IndexRoute) — leave room for the router to enter in sprint 01+ without restructuring.

**Non-Goals:**
- TanStack **Router** wiring. The dep is installed per sprint 00's dep list, but no `<Router />` is mounted yet — the IndexRoute renders directly. Routing arrives in a later sprint.
- Generating `src/api/schema.d.ts` at this stage. The schema can only be generated against a running API (`pnpm gen:api`); sprint 00 ships an untyped `openapi-fetch` client and a hand-written `fetchHealthz`. Type-replacement is a follow-up.
- Dark-mode UI toggling. Theme tokens (including `.dark`) are wired so adding the toggle later is a one-component change, but no toggle ships in sprint 00.
- Sonner toasts, lucide icons, zod schemas in actual use. Deps are installed (sprint 00 minimum list) but consuming code lives in later sprints.

## Decisions

**1) Single IndexRoute, no `<Router />` mounted.**
The sprint 00 doc explicitly scopes the frontend to one view consuming `/healthz`. Mounting a router for one route is overhead that complicates the shell and the test. `@tanstack/react-router` is installed (per the doc's minimum dep list) so sprint 01+ can `createRouter` without a dep PR. Alternative considered: mount a single-route router immediately. Rejected — adds boilerplate and a route tree before there's a second route, and would have to be rewritten when file-based routing arrives.

**2) Untyped `openapi-fetch` client + hand-rolled `fetchHealthz`.**
`src/api/schema.d.ts` is generated only after the API is running (`pnpm gen:api`). Until then the typed client has no `paths` to bind to. The walking skeleton ships `createClient<Record<string, never>>({ baseUrl })` plus an explicit `fetchHealthz(): Promise<HealthzResponse>` that returns a hand-typed shape matching the API contract. Once `gen:api` runs against a real API the `Record<string, never>` is swapped for `paths` from `./schema` and `fetchHealthz` is rewritten on top of the typed client. Alternative: commit a stub `schema.d.ts`. Rejected — a stub schema lies about the API surface and the lie outlasts the sprint.

**3) shadcn theme tokens wired through CSS variables.**
`globals.css` declares the full HSL variable set (`--background`, `--foreground`, `--card`, `--popover`, `--primary`, `--secondary`, `--muted`, `--accent`, `--destructive`, `--border`, `--input`, `--ring`, `--radius`) under both `:root` and `.dark`. `tailwind.config.ts` re-exposes them as theme colors via `hsl(var(--*))`, so utilities like `bg-card`, `text-muted-foreground`, `border-border` resolve to the tokens. Without this wiring shadcn components fall back to broken classes the moment a future sprint runs the shadcn CLI to add a new primitive. Alternative considered: hard-code `slate-*` and skip the variables. Rejected — every shadcn component generated later would need manual rewrites, and we'd lose dark mode for free.

**4) Status-specific Badge variants (`ok` / `warn` / `danger`) alongside the shadcn defaults.**
The `/healthz` view needs semantic states the default shadcn Badge does not provide. Keep the upstream variants (`default`, `secondary`, `destructive`, `outline`) untouched and add three semantic variants in the same `cva` table. Alternative: a separate `<StatusBadge>` component. Rejected — duplicates `cva` plumbing for three classes.

**5) IndexRoute state machine: `loading` | `unreachable` | `value`.**
A single `FieldState` discriminated union drives every cell. `loading` → skeleton; `unreachable` → `danger` Badge / `outline` "unknown" Badge; `value` → `ok|warn` Badge for status fields, mono text for version/git_sha/alembic_revision. The test mocks `useHealthz` to return a `value` state and asserts the `ok` badge plus the revision string render. Alternative: per-field ad-hoc rendering. Rejected — five fields with three states each is 15 branches; the union compresses to 3.

**6) ESLint flat config, no React import-order rules, but cross-feature import ban.**
Sprint 00 has no `features/` directory yet, but the doc (and `09-frontend.md`) calls out feature isolation. Pre-emptively ban `**/features/*/**` cross-imports via `no-restricted-imports` so when feature folders land, the rule is already enforced. Alternative: defer until features exist. Rejected — easier to keep the rule green from day one than retrofit it.

## Risks / Trade-offs

- **Untyped API client until first `gen:api`** → Manual `HealthzResponse` interface in `src/api/client.ts` can drift from the FastAPI schema. Mitigation: comment in `client.ts` instructing the swap; `gen:api` script is the documented next step in the sprint-00 outcome.
- **`@tanstack/react-router` installed but unused** → bundle size paid for a dep we don't yet consume. Mitigation: <50 KB gz in practice, and Vite tree-shakes unused entry points; deferring the install would only push a future PR.
- **Manual reconciliation between this spec and the implementation** → drift can creep in if the implementation is edited without updating the spec. Mitigation: `openspec validate --strict` in pre-commit (later sprint), and `openspec list --specs` audited at sprint review.
- **Cross-feature import lint rule fires only on a path glob (`**/features/*/**`)** → relocation under a different folder name silently bypasses it. Mitigation: enforce the `features/` convention in `09-frontend.md` and a follow-up sprint adds a structural test once feature folders exist.

## Migration Plan

Not applicable. No deploy, no data migration, no user-visible behavior to roll back to — sprint 00 is greenfield local-only foundation. The "rollback" is `rm -rf apps/web && git checkout main`.
