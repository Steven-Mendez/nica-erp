# frontend-toolchain Specification

## Purpose
TBD - created by archiving change add-frontend-walking-skeleton. Update Purpose after archive.
## Requirements
### Requirement: Package scripts cover the sprint-00 developer loop

`apps/web/package.json` SHALL define the scripts `dev`, `build`, `preview`, `typecheck`, `lint`, `format`, `format:check`, `test`, `test:run`, and `gen:api`. The `build` script MUST run `tsc --noEmit` before `vite build` so type errors block a production bundle. The `gen:api` script MUST invoke `openapi-typescript` against `http://localhost:8000/openapi.json` and write the result to `src/api/schema.d.ts`. The package MUST declare `"type": "module"` and pin Node `>=22 <25` via the `engines` field.

#### Scenario: dev script runs Vite

- **WHEN** `pnpm dev` is invoked from `apps/web/`
- **THEN** Vite starts and serves the SPA on port 5173

#### Scenario: build script type-checks before bundling

- **WHEN** `pnpm build` is invoked
- **THEN** the script runs `tsc --noEmit && vite build`, and exits with a non-zero status if `tsc` reports any error

#### Scenario: gen:api hits the running API

- **WHEN** the API is running on `http://localhost:8000` and `pnpm gen:api` is invoked
- **THEN** `openapi-typescript` fetches `http://localhost:8000/openapi.json` and writes `apps/web/src/api/schema.d.ts`

### Requirement: TypeScript configuration enforces strict and explicit module semantics

`apps/web/tsconfig.json` MUST enable `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `verbatimModuleSyntax`, `isolatedModules`, `noImplicitOverride`, `noFallthroughCasesInSwitch`, `noUnusedLocals`, `noUnusedParameters`, and `useDefineForClassFields`. It MUST target `ES2022` with `module: "ESNext"`, `moduleResolution: "Bundler"`, `jsx: "react-jsx"`, and `noEmit: true`. The `paths` map MUST bind `@/*` to `./src/*` and `types` MUST include `vite/client`, `vitest/globals`, and `@testing-library/jest-dom`.

#### Scenario: typecheck passes with strict flags

- **WHEN** `pnpm typecheck` is invoked against a clean tree
- **THEN** `tsc --noEmit` exits zero and the four named flags (`strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `verbatimModuleSyntax`) are all `true` in `tsconfig.json`

#### Scenario: optional properties cannot accept undefined assignment

- **WHEN** code attempts `const x: { foo?: string } = { foo: undefined }`
- **THEN** `tsc` reports an error because `exactOptionalPropertyTypes` distinguishes optional-absence from `undefined`

### Requirement: Tailwind is wired to shadcn theme tokens

`apps/web/tailwind.config.ts` MUST enable `darkMode: ["class"]` and content-scan `./index.html` and `./src/**/*.{ts,tsx}`. The `theme.extend.colors` map MUST expose every shadcn token (`background`, `foreground`, `card`, `popover`, `primary`, `secondary`, `muted`, `accent`, `destructive`, `border`, `input`, `ring`) bound to its corresponding CSS variable via `hsl(var(--<token>))`. `theme.extend.borderRadius` MUST expose `lg`, `md`, `sm` derived from `var(--radius)`. PostCSS MUST load `tailwindcss` and `autoprefixer`.

#### Scenario: Production CSS resolves theme tokens through CSS variables

- **WHEN** `pnpm build` produces `dist/assets/index-*.css`
- **THEN** the bundle contains `hsl(var(--background))`, `hsl(var(--card))`, `hsl(var(--border))`, `hsl(var(--muted-foreground))`, `hsl(var(--primary))`, `hsl(var(--destructive))`, and `hsl(var(--ring))` (i.e. the tokens are wired, not hard-coded slate utilities)

#### Scenario: Dark mode is class-gated

- **WHEN** a developer adds `class="dark"` to a parent element
- **THEN** Tailwind switches to dark-mode utilities and the `.dark` block in `src/styles/globals.css` overrides the variable values

### Requirement: shadcn primitives are themed and located under `components/ui/`

`apps/web/components.json` MUST declare `style: "default"`, `tsx: true`, `tailwind.config: "tailwind.config.ts"`, `tailwind.css: "src/styles/globals.css"`, `baseColor: "slate"`, `cssVariables: true`, `aliases.components: "@/components"`, and `aliases.utils: "@/lib/utils"`. The file MUST NOT declare `$schema` (the public shadcn schema URL trips editor "untrusted schema" warnings in sandboxed environments and is not required by the shadcn CLI). The sprint-00 deliverables MUST ship at least the `Card`, `Badge`, and `Skeleton` primitives under `apps/web/src/components/ui/`, each adapted to the project's `forwardRef` + `HTMLAttributes` pattern. Card surface utilities MUST use `bg-card text-card-foreground border` (not hard-coded `bg-white text-slate-*`). The Badge component MUST expose the default shadcn variants (`default`, `secondary`, `destructive`, `outline`) and SHOULD additionally expose semantic variants `ok`, `warn`, `danger` for status presentation. The Skeleton component MUST render a `<div data-slot="skeleton">` with the base classes `animate-pulse rounded-md bg-muted` and accept a `className` override that callers use to set `h-*`/`w-*`/`inline-block` at the use site. The `cn(...)` helper MUST live at `apps/web/src/lib/utils.ts` and combine `clsx` + `tailwind-merge`.

#### Scenario: components.json points the shadcn CLI at the right files

- **WHEN** a future sprint runs `pnpm dlx shadcn-ui@latest add <component>`
- **THEN** the CLI reads `components.json`, writes the new primitive under `@/components/ui/`, and uses `@/lib/utils#cn` for class merging

#### Scenario: Card uses theme tokens

- **WHEN** `<Card>` is rendered
- **THEN** the produced className contains `bg-card`, `text-card-foreground`, and `border` (no `bg-white` or `text-slate-900` literals)

#### Scenario: Badge offers semantic state variants

- **WHEN** `<Badge variant="ok">` and `<Badge variant="danger">` are used
- **THEN** the rendered className differs (e.g. emerald vs red palette) and TypeScript infers the variant from the `cva` definition

### Requirement: Global stylesheet defines light and dark token sets

`apps/web/src/styles/globals.css` MUST load Tailwind layers (`@tailwind base/components/utilities`). Under `@layer base`, the `:root` selector MUST define HSL values for every token consumed by Tailwind (`--background`, `--foreground`, `--card`, `--card-foreground`, `--popover`, `--popover-foreground`, `--primary`, `--primary-foreground`, `--secondary`, `--secondary-foreground`, `--muted`, `--muted-foreground`, `--accent`, `--accent-foreground`, `--destructive`, `--destructive-foreground`, `--border`, `--input`, `--ring`, `--radius`). A `.dark` selector MUST override the same set with a dark palette. The base layer MUST apply `border-border` to every element and `bg-background text-foreground antialiased` to `<body>`.

#### Scenario: Base layer paints the body

- **WHEN** the application is rendered in a browser
- **THEN** the body computes its background from `hsl(var(--background))` and its colour from `hsl(var(--foreground))` without any utility classes on the `<body>` element

#### Scenario: Dark palette is defined

- **WHEN** `globals.css` is inspected
- **THEN** a `.dark { ... }` block declares dark-mode values for every variable defined under `:root`

### Requirement: ESLint flat config enforces TypeScript hygiene and feature isolation

`apps/web/eslint.config.js` MUST use `typescript-eslint`'s `tseslint.config` helper, extend `@eslint/js`'s `recommended` and `typescript-eslint`'s `recommended` configs, register `eslint-plugin-react-hooks` with its `recommended` rules, and apply to `**/*.{ts,tsx}`. It MUST set `@typescript-eslint/no-explicit-any` to `error`. It MUST configure `no-restricted-imports` to forbid any import path matching `**/features/*/**` with a clarifying message that cross-feature imports are not allowed and that sharing happens through `src/api`, `src/lib`, or `src/components`. It MUST ignore `dist`, `node_modules`, and the generated `src/api/schema.d.ts`.

#### Scenario: Lint forbids `any`

- **WHEN** code introduces `const x: any = 1` and `pnpm lint` runs
- **THEN** ESLint exits non-zero with `@typescript-eslint/no-explicit-any`

#### Scenario: Lint forbids cross-feature imports

- **WHEN** a module imports from `@/features/foo/internal` from outside its own feature folder
- **THEN** ESLint exits non-zero with the configured `no-restricted-imports` message

### Requirement: Prettier configuration and code style

`apps/web/.prettierrc.json` MUST declare `semi: true`, `singleQuote: false`, `trailingComma: "all"`, `printWidth: 100`, `tabWidth: 2`, `useTabs: false`. Both `format` and `format:check` package scripts MUST shell out to `prettier`.

#### Scenario: Format check accepts well-formatted code

- **WHEN** `pnpm format:check` runs against a clean tree
- **THEN** the command exits zero with no diff suggestions

### Requirement: Vitest runs under happy-dom with testing-library matchers

`apps/web/vite.config.ts` MUST configure the `test` block with `globals: true`, `environment: "happy-dom"`, `setupFiles: ["./tests/setup.ts"]`, and `include: ["tests/**/*.test.{ts,tsx}"]` so Vitest collects exclusively from the tests tree (no co-located `*.test.*` files under `src/`). `apps/web/tests/setup.ts` MUST register `@testing-library/jest-dom/vitest`. All frontend tests SHALL live under `apps/web/tests/{unit,integration,e2e}/`, mirroring the `src/` package layout (e.g. `src/routes/index.tsx` is tested by `tests/unit/routes/index.test.tsx`). `apps/web/tsconfig.json` `include` MUST list both `src` and `tests` so the type-checker sees the test sources. The `test` package script MUST run `vitest` (watch mode) and `test:run` MUST run `vitest run`.

#### Scenario: Tests have DOM matchers available

- **WHEN** a test calls `expect(element).toBeInTheDocument()`
- **THEN** the matcher is defined because `@testing-library/jest-dom/vitest` was loaded by the configured setup file

#### Scenario: Tests run under happy-dom

- **WHEN** `pnpm test:run` is invoked
- **THEN** Vitest reports `environment: happy-dom` and DOM globals (`document`, `window`) are available without explicit imports

### Requirement: Typed OpenAPI fetch client is the documented API surface

`apps/web/src/api/client.ts` MUST construct an `openapi-fetch` client via `createClient`, reading the base URL from `import.meta.env.VITE_API_BASE_URL` and defaulting to `http://localhost:8000`. Until `pnpm gen:api` is run, the client MAY be instantiated with a placeholder type (`Record<string, never>`) and a hand-written `fetchHealthz(): Promise<HealthzResponse>` MAY co-exist as a temporary bridge. After `pnpm gen:api` produces `src/api/schema.d.ts`, the client MUST be re-typed to `createClient<paths>()` and any hand-written fetch helpers MUST be replaced with calls through the typed client. The `VITE_API_BASE_URL` env contract MUST be documented in `apps/web/.env.local.example`.

#### Scenario: Base URL falls back when env var is unset

- **WHEN** the SPA boots without `VITE_API_BASE_URL` defined
- **THEN** API calls target `http://localhost:8000` (the documented default)

#### Scenario: Generated schema replaces the placeholder client type

- **WHEN** `pnpm gen:api` has produced `src/api/schema.d.ts`
- **THEN** `client.ts` instantiates `createClient<paths>()` and the hand-written `fetchHealthz` is removed in favour of the typed client

### Requirement: Continuous integration runs the web checks on every push

`.github/workflows/web-checks.yml` MUST run on `push` to `main` and on every `pull_request` whose changes touch `apps/web/**` or the workflow file itself. The job MUST execute under `apps/web/` working directory and consist of the following steps in order: checkout, install pnpm (version 9), install Node from `.nvmrc` with pnpm cache keyed on `apps/web/pnpm-lock.yaml`, run `pnpm install --frozen-lockfile`, then run `pnpm typecheck`, `pnpm lint`, `pnpm format:check`, and `pnpm test:run`. The workflow MUST NOT deploy anything (per [ADR-0023](../../../../docs/adr/0023-no-ci-cd-mvp.md)).

The third-party actions used by both `web-checks.yml` and `api-checks.yml` MUST be pinned to the current latest major as published by each action's maintainer (verifiable via Context7 / each action's README): `actions/checkout@v6`, `actions/setup-node@v6`, `pnpm/action-setup@v6`, and `astral-sh/setup-uv@v8`. Pinning to a major that GitHub has marked deprecated (currently anything running on Node.js 20) is forbidden.

#### Scenario: PR touching the web app triggers the workflow

- **WHEN** a pull request modifies a file under `apps/web/`
- **THEN** GitHub Actions runs `web-checks` and the job fails if any of typecheck, lint, format:check, or test:run exits non-zero

#### Scenario: Lockfile is honoured

- **WHEN** the CI job installs dependencies
- **THEN** it runs `pnpm install --frozen-lockfile` so an out-of-date `pnpm-lock.yaml` fails the build rather than silently regenerating

#### Scenario: No deprecated action versions

- **WHEN** the workflow runs on a GitHub-hosted runner
- **THEN** the run logs do NOT contain the "Node.js 20 actions are deprecated" warning, because every `uses:` line resolves to a major running on node24

### Requirement: Pre-commit hooks guard the web tree locally

`.pre-commit-config.yaml` MUST register two local hooks for the web app: `web-typecheck` running `cd apps/web && pnpm typecheck` on changes to `^apps/web/.*\.(ts|tsx)$`, and `web-lint` running `cd apps/web && pnpm lint` on changes to `^apps/web/.*\.(ts|tsx|js|jsx)$`. Both hooks MUST set `pass_filenames: false` because the underlying commands operate on the whole project. The hooks MUST be installable via `make hooks` (which delegates to `pre-commit install`).

#### Scenario: Editing a web TS file triggers the typecheck hook

- **WHEN** a developer stages a change to `apps/web/src/routes/index.tsx` and runs `git commit`
- **THEN** `pre-commit` runs the `web-typecheck` hook and blocks the commit if `pnpm typecheck` exits non-zero

#### Scenario: Editing only backend code does not run web hooks

- **WHEN** a developer stages a change to `apps/api/src/bootstrap/api.py` and runs `git commit`
- **THEN** the `web-typecheck` and `web-lint` hooks are skipped (their `files` filter does not match)

### Requirement: `.gitignore` MUST NOT swallow `apps/web/src/lib/`

The root `.gitignore` is seeded from the [GitHub Python template](https://github.com/github/gitignore/blob/main/Python.gitignore) and contains a generic `lib/` rule for setuptools build artefacts. That rule MUST be neutralised for `apps/web/src/lib/` (the shadcn helpers directory referenced by `components.json` aliases `@/lib/utils`). The neutralisation MUST take the form of an explicit negation pair (directory then contents) placed below the original Python rules, with a comment that records the reason. Other `lib/` paths (Python build outputs in `apps/api/` or future services) MUST continue to be ignored.

#### Scenario: shadcn helper is tracked

- **WHEN** a fresh clone of the repo is checked out
- **THEN** `apps/web/src/lib/utils.ts` is present on disk and tracked by git (`git ls-files apps/web/src/lib/utils.ts` is non-empty)

#### Scenario: Python build artefacts stay ignored

- **WHEN** a developer accidentally creates `apps/api/build/lib/` (setuptools output)
- **THEN** `git status` does NOT list the directory because the original `lib/` rule still matches non-frontend paths

