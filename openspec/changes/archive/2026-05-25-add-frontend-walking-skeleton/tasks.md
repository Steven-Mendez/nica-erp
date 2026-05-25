## 1. Toolchain & configuration

- [x] 1.1 Pin `apps/web/package.json` scripts: `dev`, `build` (`tsc --noEmit && vite build`), `preview`, `typecheck`, `lint`, `format`, `format:check`, `test`, `test:run`, `gen:api`
- [x] 1.2 Declare `"type": "module"` and `engines.node: ">=22 <25"` in `package.json`
- [x] 1.3 Install runtime deps (sprint-00 minimum): `react`, `react-dom`, `@tanstack/react-query`, `@tanstack/react-router`, `openapi-fetch`, `class-variance-authority`, `clsx`, `tailwind-merge`, `lucide-react`, `sonner`, `zod`
- [x] 1.4 Install dev deps: `typescript`, `vite`, `@vitejs/plugin-react`, `tailwindcss`, `postcss`, `autoprefixer`, `eslint`, `typescript-eslint`, `eslint-plugin-react-hooks`, `globals`, `prettier`, `vitest`, `happy-dom`, `@testing-library/react`, `@testing-library/jest-dom`, `openapi-typescript`, `@types/node`, `@types/react`, `@types/react-dom`
- [x] 1.5 `apps/web/tsconfig.json`: enable `strict`, `noUncheckedIndexedAccess`, `exactOptionalPropertyTypes`, `verbatimModuleSyntax`, `isolatedModules`, `noImplicitOverride`, `noFallthroughCasesInSwitch`, `noUnusedLocals`, `noUnusedParameters`, `useDefineForClassFields`; target `ES2022`, `module: ESNext`, `moduleResolution: Bundler`, `jsx: react-jsx`, `noEmit: true`; bind `@/*` → `./src/*`; types: `vite/client`, `vitest/globals`, `@testing-library/jest-dom`
- [x] 1.6 `apps/web/vite.config.ts`: register `@vitejs/plugin-react`, alias `@/` → `src/`, server port 5173, test block (`globals: true`, `environment: "happy-dom"`, `setupFiles: ["./tests/setup.ts"]`, `include: ["tests/**/*.test.{ts,tsx}"]`)
- [x] 1.7 `apps/web/postcss.config.js`: load `tailwindcss` and `autoprefixer`
- [x] 1.8 `apps/web/tailwind.config.ts`: `darkMode: ["class"]`, content scan `index.html` + `src/**/*.{ts,tsx}`, extend `theme.colors` with `hsl(var(--<token>))` for `background`, `foreground`, `border`, `input`, `ring`, `primary`, `secondary`, `destructive`, `muted`, `accent`, `popover`, `card` (incl. `*-foreground`), extend `borderRadius` from `var(--radius)`
- [x] 1.9 `apps/web/components.json`: `style: "default"`, `tsx: true`, `baseColor: "slate"`, `cssVariables: true`, point at `tailwind.config.ts` + `src/styles/globals.css`, aliases `@/components` and `@/lib/utils`
- [x] 1.10 `apps/web/eslint.config.js` (flat): extend `@eslint/js#recommended` + `typescript-eslint#recommended`, register `eslint-plugin-react-hooks` recommended, ignore `dist`/`node_modules`/`src/api/schema.d.ts`, set `@typescript-eslint/no-explicit-any: error`, configure `no-restricted-imports` to forbid `**/features/*/**` with cross-feature message
- [x] 1.11 `apps/web/.prettierrc.json`: `semi: true`, `singleQuote: false`, `trailingComma: all`, `printWidth: 100`, `tabWidth: 2`, `useTabs: false`
- [x] 1.12 `apps/web/.env.local.example`: document `VITE_API_BASE_URL=http://localhost:8000` and `VITE_APP_ENV=local`
- [x] 1.13 `apps/web/tests/setup.ts`: import `@testing-library/jest-dom/vitest`. `apps/web/tsconfig.json` `include` MUST list both `src` and `tests` so the type-checker covers the test sources.

## 2. Application shell

- [x] 2.1 `apps/web/index.html`: UTF-8 + viewport meta, `<title>nica-erp</title>`, `<div id="root"></div>`, `<script type="module" src="/src/main.tsx">`, no Tailwind utility classes on `<body>`
- [x] 2.2 `apps/web/src/main.tsx`: import `@/styles/globals.css`, look up `#root`, throw `Error("Missing #root element")` if missing, `createRoot(...).render(<StrictMode><App /></StrictMode>)`
- [x] 2.3 `apps/web/src/app.tsx`: export `App`, lazily construct `QueryClient` via `useState(() => new QueryClient())`, wrap children in `<QueryClientProvider>`, render `<IndexRoute />` (no router mounted yet)
- [x] 2.4 `apps/web/src/lib/utils.ts`: export `cn(...inputs: ClassValue[])` combining `clsx` and `tailwind-merge`

## 3. shadcn primitives & global stylesheet

- [x] 3.1 `apps/web/src/styles/globals.css`: load `@tailwind base/components/utilities`; under `@layer base`, declare full HSL token set under `:root` (`--background`, `--foreground`, `--card`, `--card-foreground`, `--popover`, `--popover-foreground`, `--primary`, `--primary-foreground`, `--secondary`, `--secondary-foreground`, `--muted`, `--muted-foreground`, `--accent`, `--accent-foreground`, `--destructive`, `--destructive-foreground`, `--border`, `--input`, `--ring`, `--radius`); declare the same set under `.dark` with a dark palette; apply `@apply border-border` to `*` and `@apply bg-background text-foreground antialiased` to `body`
- [x] 3.2 `apps/web/src/components/ui/card.tsx`: export `Card`, `CardHeader`, `CardTitle`, `CardDescription`, `CardContent`; use `bg-card text-card-foreground border` on Card surface and `text-muted-foreground` on `CardDescription` (no `bg-white`/`text-slate-*` literals)
- [x] 3.3 `apps/web/src/components/ui/badge.tsx`: `cva` table with variants `default`, `secondary`, `destructive`, `outline` bound to theme tokens, plus semantic variants `ok`, `warn`, `danger`; export `Badge` and `BadgeProps`
- [x] 3.4 `apps/web/src/components/ui/skeleton.tsx`: shadcn Skeleton primitive adapted to the project's `forwardRef` + `HTMLAttributes` pattern; renders `<div data-slot="skeleton">` with `animate-pulse rounded-md bg-muted` and accepts a `className` override (size utilities — `h-4 w-16 inline-block` etc. — are supplied by the caller)
- [x] 3.5 Remove `$schema` from `apps/web/components.json` (avoids editor "untrusted schema" warnings; not required by the shadcn CLI)

## 4. Healthz read-out

- [x] 4.1 `apps/web/src/api/client.ts`: instantiate `openapi-fetch` client with `VITE_API_BASE_URL` (default `http://localhost:8000`); export `HealthzResponse` interface (`status`, `version`, `git_sha`, `db: string`, `alembic_revision: string | null`); export `fetchHealthz(): Promise<HealthzResponse>` issuing GET with `Accept: application/json` and throwing on non-OK
- [x] 4.2 `apps/web/src/api/healthz.ts`: export `useHealthz()` calling `useQuery({ queryKey: ["healthz"], queryFn: fetchHealthz, refetchInterval: 30_000, retry: 1 })`
- [x] 4.3 `apps/web/src/routes/index.tsx`: render shadcn `Card` (title "nica-erp", description "Backend health, read from /healthz.") with `<dl>` two-column grid; drive every cell from `FieldState = loading | unreachable | value`; use `text-muted-foreground` / `text-foreground` (no slate literals); use `bg-muted` skeleton

## 5. Verification

- [x] 5.1 Write `apps/web/tests/unit/routes/index.test.tsx` (mirroring `src/routes/index.tsx`; import the route via `@/routes/index`): mock `@/api/healthz` to return a fully populated response, assert `ok` badge, `0.1.0`, `abcdef0`, `0001_shared_kernel` are rendered
- [x] 5.2 `pnpm typecheck` exits zero
- [x] 5.3 `pnpm lint` exits zero
- [x] 5.4 `pnpm test:run` reports 1 file / 1 test passing
- [x] 5.5 `pnpm build` produces a `dist/` bundle and the built CSS contains `hsl(var(--background))` and at least the 7 named tokens (background, card, border, muted-foreground, primary, destructive, ring)
- [x] 5.6 `pnpm dev` serves `http://localhost:5173/` returning the entry HTML, `/src/main.tsx`, and `/src/styles/globals.css` with status 200

## 6. Continuous integration & pre-commit hooks

- [x] 6.1 `.github/workflows/web-checks.yml`: trigger on `push` to `main` and `pull_request` paths `apps/web/**` + the workflow file; job runs under `apps/web/`; steps: checkout → `pnpm/action-setup@v4` (version 9) → `actions/setup-node@v4` using `.nvmrc` with pnpm cache keyed on `apps/web/pnpm-lock.yaml` → `pnpm install --frozen-lockfile` → `pnpm typecheck` → `pnpm lint` → `pnpm format:check` → `pnpm test:run`
- [x] 6.2 `.pre-commit-config.yaml`: register `web-typecheck` (runs `cd apps/web && pnpm typecheck`, files `^apps/web/.*\.(ts|tsx)$`, `pass_filenames: false`) and `web-lint` (runs `cd apps/web && pnpm lint`, files `^apps/web/.*\.(ts|tsx|js|jsx)$`, `pass_filenames: false`)

## 7. Spec drift reconciliation (run after every code change in `apps/web/`)

- [x] 7.1 Re-run `openspec validate add-frontend-walking-skeleton --strict` and fix any drift
- [x] 7.2 If implementation diverges from a spec scenario, update *either* the impl or the scenario in the same commit; do not let them drift
