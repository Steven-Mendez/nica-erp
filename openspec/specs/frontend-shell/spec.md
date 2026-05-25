# frontend-shell Specification

## Purpose
TBD - created by archiving change add-frontend-walking-skeleton. Update Purpose after archive.
## Requirements
### Requirement: Vite entry HTML loads the React bundle

The frontend SHALL ship an `apps/web/index.html` that Vite serves as the application entry. The entry MUST declare UTF-8 encoding, a responsive viewport meta tag, a document title of `nica-erp`, and a single root mount point with `id="root"`. The HTML MUST load `/src/main.tsx` as an ES module and MUST NOT hard-code colour utility classes on the `<body>` element (presentation comes from the Tailwind base layer).

#### Scenario: Vite serves the entry HTML

- **WHEN** `pnpm dev` is running and an HTTP GET is issued to `http://localhost:5173/`
- **THEN** the server responds `200 OK` with HTML containing `<div id="root"></div>`, `<title>nica-erp</title>`, and a `<script type="module" src="/src/main.tsx">` reference

#### Scenario: Entry HTML defers presentation to the base layer

- **WHEN** the project is inspected at `apps/web/index.html`
- **THEN** the `<body>` element carries no Tailwind utility classes (background and foreground colour come from the `body { @apply bg-background text-foreground ... }` rule in `src/styles/globals.css`)

### Requirement: React root is rendered under StrictMode with a single App component

`apps/web/src/main.tsx` SHALL locate the `#root` element, throw a descriptive error if it is missing, and mount `<App />` inside `<StrictMode>` via `createRoot`. It MUST import `@/styles/globals.css` at module top level so the stylesheet is bundled with the entry chunk.

#### Scenario: Root element missing aborts boot

- **WHEN** `apps/web/index.html` is loaded but the `#root` element has been removed
- **THEN** `main.tsx` throws an Error with message `"Missing #root element"` rather than silently failing

#### Scenario: StrictMode wraps the application

- **WHEN** `main.tsx` is read
- **THEN** the rendered tree is `<StrictMode><App /></StrictMode>` and `@/styles/globals.css` is imported at module scope

### Requirement: App component provides the TanStack Query client

`apps/web/src/app.tsx` SHALL export a single React component `App` that constructs a `QueryClient` exactly once per component instance (via `useState` initializer) and wraps the application tree in `<QueryClientProvider>`. The provider MUST wrap the sprint-00 `IndexRoute`. The router is not mounted in sprint 00; routing arrives in a later sprint.

#### Scenario: QueryClient is created lazily and stably

- **WHEN** `App` mounts
- **THEN** `new QueryClient()` runs once via `useState(() => new QueryClient())` so the client survives re-renders without reinstantiation

#### Scenario: IndexRoute renders inside the query provider

- **WHEN** `App` is rendered into a happy-dom tree under test
- **THEN** the rendered output contains the `IndexRoute` markup nested inside a `QueryClientProvider`

### Requirement: Path alias `@/` resolves to `apps/web/src`

Both Vite and TypeScript SHALL resolve the import specifier `@/*` to `apps/web/src/*`. Source code MUST consume sibling modules through this alias (e.g. `import { IndexRoute } from "@/routes/index"`) rather than long relative paths, so files can move without churning imports.

#### Scenario: Vite resolves the alias at runtime

- **WHEN** any module imports `@/styles/globals.css` or `@/app`
- **THEN** Vite resolves the specifier to `apps/web/src/styles/globals.css` / `apps/web/src/app.tsx` via `resolve.alias` in `vite.config.ts`

#### Scenario: TypeScript resolves the alias at compile time

- **WHEN** `pnpm typecheck` runs
- **THEN** `tsc` resolves `@/*` to `./src/*` via `compilerOptions.paths` in `apps/web/tsconfig.json` and reports no `cannot find module '@/...'` errors

