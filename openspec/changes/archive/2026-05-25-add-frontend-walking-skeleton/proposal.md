## Why

Sprint 00 (the walking skeleton) requires the SPA half of the system: a Vite/React app on `:5173` that consumes `GET /healthz` from the API, plus the toolchain (TypeScript strict, Tailwind, shadcn/ui, TanStack Query, openapi-fetch, vitest) that all subsequent sprints depend on. Without a formal spec, the contract between docs/sprints/00-walking-skeleton.md and the implementation in `apps/web/` is only enforced by manual inspection — we want the requirements captured as testable behavior so future sprints can extend (not duplicate) them.

## What Changes

- Introduce three new capabilities in `openspec/specs/` covering the frontend portion of the walking skeleton.
- Capture the frontend toolchain (build tooling, strict TS flags, theme tokens, package scripts, generated OpenAPI client) as enforceable requirements.
- Capture the read-only `/healthz` view (status, db, version, git_sha, alembic_revision rendered in a shadcn Card with a Badge) as a UI requirement with explicit loading / unreachable / value states.
- Capture the frontend application shell (Vite entry, React root, QueryClientProvider, `@/`-aliased imports, `globals.css` import) as a separate capability so later sprints can layer the router, auth shell, and i18n on top without redefining it.
- No backend changes; no new runtime dependencies beyond what sprint 00 already lists. Implementation already exists in `apps/web/` and will be reconciled against the spec.

## Capabilities

### New Capabilities
- `frontend-shell`: Vite + React application bootstrap — entry HTML, root render, providers, path aliasing, global stylesheet import.
- `frontend-toolchain`: package scripts, strict TypeScript config, Tailwind + shadcn theme wiring, ESLint/Prettier/Vitest configuration, typed API client generation.
- `healthz-readout`: the read-only `/healthz` consumer view — `useHealthz` hook, IndexRoute presentation with Card + Badge, loading / unreachable / value state contract.

### Modified Capabilities
<!-- none — there are no existing specs to delta -->

## Impact

- **Code**: `apps/web/**` (already exists; will be reconciled with the spec). No backend code is touched.
- **APIs**: consumes `GET /healthz` from the API (read-only). Contract: `{status, version, git_sha, db, alembic_revision}`.
- **Dependencies**: none added beyond the sprint-00 minimum list (`react`, `react-dom`, `@tanstack/react-query`, `@tanstack/react-router`, `openapi-fetch`, `tailwindcss`, `class-variance-authority`, `clsx`, `tailwind-merge`, `lucide-react`, `sonner`, `zod`; dev: `typescript`, `vite`, `@vitejs/plugin-react`, `eslint`, `prettier`, `vitest`, `openapi-typescript`).
- **Systems**: only the local dev environment. No AWS, no Terraform, no CI deploy (per ADR-0018, ADR-0020, ADR-0023).
