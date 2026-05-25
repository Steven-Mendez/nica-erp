## ADDED Requirements

### Requirement: `useHealthz` hook polls `/healthz` via TanStack Query

`apps/web/src/api/healthz.ts` MUST export a `useHealthz()` hook implemented with `@tanstack/react-query`'s `useQuery`. The query key MUST be `["healthz"]`. The fetcher MUST be `fetchHealthz` from `@/api/client` (or, once the typed client is in place, the equivalent typed call). The hook MUST set `refetchInterval: 30_000` and `retry: 1`, and MUST be typed against the `HealthzResponse` shape exported from the same module that owns the fetcher.

#### Scenario: Hook returns the healthz payload while polling every 30 s

- **WHEN** `useHealthz()` is consumed under a `QueryClientProvider`
- **THEN** TanStack Query invokes `fetchHealthz` on mount, refetches every 30,000 ms, retries at most once on failure, and exposes `data`, `isLoading`, `isError` to the caller

#### Scenario: Hook surfaces fetch failure

- **WHEN** `fetchHealthz` rejects (e.g. API down)
- **THEN** after the single retry the hook reports `isError: true` and leaves `data` undefined

### Requirement: `fetchHealthz` matches the API contract

`apps/web/src/api/client.ts` MUST export a `HealthzResponse` interface with the fields `status: string`, `version: string`, `git_sha: string`, `db: string`, and `alembic_revision: string | null`, and an async `fetchHealthz(): Promise<HealthzResponse>` that issues `GET ${baseUrl}/healthz` with `Accept: application/json`. The function MUST throw `Error` with a message containing the status code if the response is not ok.

#### Scenario: Happy path returns the typed payload

- **WHEN** `fetchHealthz()` is awaited against a healthy API
- **THEN** the resolved value matches `HealthzResponse` exactly (no extra mandatory fields) and `alembic_revision` accepts both a revision string and `null`

#### Scenario: HTTP failure throws

- **WHEN** the API responds with `500`
- **THEN** `fetchHealthz()` rejects with `Error("/healthz failed: 500")`

### Requirement: IndexRoute presents healthz state in a shadcn Card

`apps/web/src/routes/index.tsx` MUST export an `IndexRoute` React component that consumes `useHealthz()` and renders the five fields (`status`, `db`, `version`, `git_sha`, `alembic_revision`) inside a single shadcn `Card` (with `CardHeader`, `CardTitle: "nica-erp"`, `CardDescription: "Backend health, read from /healthz."`, and `CardContent`). The view MUST be centred in the viewport via Tailwind utilities (`mx-auto flex min-h-screen max-w-2xl flex-col items-center justify-center p-8`) and MUST use a two-column `<dl>` grid for the field rows. Labels MUST use `text-muted-foreground` (not hard-coded `slate-*` utilities).

#### Scenario: Card displays the five health fields

- **WHEN** `IndexRoute` is rendered with a successful healthz response
- **THEN** the DOM contains five `<dt>` labels: `status`, `db`, `version`, `git_sha`, `alembic_revision`, each paired with a `<dd>` value cell

#### Scenario: Labels use theme tokens, not slate utilities

- **WHEN** `apps/web/src/routes/index.tsx` is inspected
- **THEN** the `<dt>` elements carry `text-muted-foreground` and the mono value cells carry `text-foreground` (no `text-slate-600`, `text-slate-800`, or other raw slate classes remain on the labels)

### Requirement: Field cells follow a `loading | unreachable | value` state machine

Every cell in the IndexRoute MUST be driven by a discriminated union `FieldState = { kind: "loading" } | { kind: "unreachable" } | { kind: "value"; value: string | null }`. While `isLoading` is true the state MUST be `loading`. When the query has errored OR has resolved with no data, the state MUST be `unreachable`. Otherwise the state MUST be `value` carrying the field's payload (which MAY be `null` for `alembic_revision`).

#### Scenario: Loading state renders a skeleton, not text

- **WHEN** `useHealthz` reports `isLoading: true`
- **THEN** each cell renders the shadcn `Skeleton` primitive imported from `@/components/ui/skeleton` (base classes `animate-pulse rounded-md bg-muted`) with an `inline-block h-4 w-16` size for status cells and `inline-block h-4 w-32` for mono cells, instead of textual content

#### Scenario: Unreachable state surfaces a danger badge

- **WHEN** `useHealthz` reports `isError: true` or returns no data after loading completes
- **THEN** the `status` and `db` cells render `<Badge variant="danger">unreachable</Badge>` and the mono cells render `<Badge variant="outline">unknown</Badge>`

#### Scenario: Value state colours status by payload

- **WHEN** `useHealthz` resolves with `status: "ok"`
- **THEN** the `status` cell renders `<Badge variant="ok">ok</Badge>`; any other status string renders `<Badge variant="warn">…</Badge>`; missing values render `"—"`

### Requirement: IndexRoute is exercised by a unit test with a mocked hook

`apps/web/tests/unit/routes/index.test.tsx` MUST render `<IndexRoute />` (imported via the `@/routes/index` path alias) with `useHealthz` mocked (via `vi.mock("@/api/healthz")`) to return a successful, fully populated `HealthzResponse`. The test MUST assert that at least one `ok` badge is rendered AND that the mocked `alembic_revision`, `version`, and `git_sha` values appear in the DOM.

#### Scenario: Test runs under vitest and passes

- **WHEN** `pnpm test:run` is invoked
- **THEN** `tests/unit/routes/index.test.tsx` executes successfully, asserting `getAllByText("ok").length >= 1`, `getByText("0001_shared_kernel")`, `getByText("0.1.0")`, and `getByText("abcdef0")` are all present in the rendered DOM
