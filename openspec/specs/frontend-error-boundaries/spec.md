# frontend-error-boundaries Specification

## Purpose
TBD - created by archiving change harden-tenant-isolation-and-errors. Update Purpose after archive.
## Requirements
### Requirement: The root route defines an errorComponent and a notFoundComponent

`apps/web/src/routes/__root.tsx` SHALL configure `rootRoute` with both
an `errorComponent` and a `notFoundComponent`. Neither callback may
throw under any of the four error categories below, and both MUST
render Spanish copy.

The four categories the root `errorComponent` MUST handle:

1. `ApiProblem` with `status === 403` → render `RouteForbiddenCard`.
2. `ApiProblem` with `status === 404` → render `RouteNotFoundCard`.
3. `ZodError` (instance check against the `zod` package) → render
   `RouteSchemaErrorCard`.
4. Any other thrown value → render `RouteRuntimeErrorCard`.

The `notFoundComponent` SHALL render `RouteNotFoundCard` regardless of
authentication state.

#### Scenario: 403 from a child loader renders the forbidden card, not a white screen

- **WHEN** a route loader throws an `ApiProblem` with `status: 403`
- **THEN** the fallback renders the Spanish forbidden card with a
  recovery link, and the React tree does not crash to a white screen

#### Scenario: Zod failure renders the schema-error card

- **WHEN** a route loader's response parsing throws a `ZodError`
- **THEN** the fallback renders the Spanish schema-error card with the
  copy `"La respuesta del servidor no tiene el formato esperado."`

#### Scenario: Unknown error renders the generic runtime card

- **WHEN** a route loader throws a value that is neither an
  `ApiProblem` nor a `ZodError`
- **THEN** the fallback renders the generic runtime card with the copy
  `"Ocurrió un error inesperado."`

#### Scenario: Navigation to an unknown path renders the not-found card

- **WHEN** the operator navigates to `/foobar` (no matching route)
- **THEN** the fallback renders the Spanish not-found card and offers
  a `Volver al inicio` recovery link

### Requirement: Fallback components render Spanish copy and offer an authentication-aware recovery link

Every fallback card MUST render in Spanish and offer an authentication-aware recovery link. Each card (`RouteForbiddenCard`, `RouteNotFoundCard`, `RouteSchemaErrorCard`, `RouteRuntimeErrorCard`) SHALL:

- Render entirely in Spanish.
- Include a single primary action button whose target is:
  - `/dashboard` if the in-memory token store reports a non-null
    access token at render time.
  - `/login` otherwise.
- Avoid issuing any data fetches, calling `useMeQuery`, or relying on
  any hook that can throw or suspend.
- Be pure functions over the error value plus the synchronous
  `getAccessToken()` reading.

#### Scenario: Authenticated operator gets a back-to-dashboard link

- **WHEN** the fallback card renders and the token store has a
  non-null access token
- **THEN** the primary action navigates to `/dashboard`

#### Scenario: Unauthenticated operator gets a back-to-login link

- **WHEN** the fallback card renders and the token store returns
  `null` for the access token
- **THEN** the primary action navigates to `/login`

#### Scenario: Fallback does not re-fetch data

- **WHEN** any fallback card renders
- **THEN** no XHR / fetch is issued from inside the fallback component
  tree

### Requirement: The AppShell layout owns an in-shell errorComponent

The AppShell layout route SHALL declare its own `errorComponent` that renders the fallback card inside the shell. The route or route group that wraps authenticated pages in `<AppShell>` MUST keep the sidebar, header, and active-tenant badge visible for 403 / 404 / Zod failures that originate from child loaders. The root `errorComponent` is only reached when
the AppShell itself fails or for unauthenticated routes.

#### Scenario: Child-loader 403 keeps the AppShell mounted

- **WHEN** an empresa-scoped route's loader throws a 403 because the
  operator was removed mid-session
- **THEN** the sidebar and header remain visible while the main
  content area renders `RouteForbiddenCard`

#### Scenario: AppShell-itself failure escapes to the root boundary

- **WHEN** the AppShell's own loader throws (e.g. `/v1/me` 403)
- **THEN** the root `errorComponent` renders the bare-shell fallback,
  matching the `/login` chrome rather than the AppShell chrome

