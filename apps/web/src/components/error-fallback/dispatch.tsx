// Routes a thrown loader/component value to the right fallback card.
//
// The four categories — forbidden / not-found / schema-error / runtime —
// are intentionally small. Anything not matching the first three falls
// through to the generic runtime card; no silent narrowing of error
// shapes. Per the design, the helper must remain pure: no fetches,
// no hooks that suspend, no `useMeQuery` (the failure may itself be
// `/me` failing).

import { ZodError } from "zod";
import { RouteForbiddenCard } from "./route-forbidden-card";
import { RouteNotFoundCard } from "./route-not-found-card";
import { RouteRuntimeErrorCard } from "./route-runtime-error-card";
import { RouteSchemaErrorCard } from "./route-schema-error-card";

// Duck-typed because the backend's `ApiError` is declared per-slice
// (auth and tenants each export their own class with identical shape).
// Recognising by `.name === "ApiError"` + a numeric `.status` avoids a
// cross-slice import here.
const isApiError = (error: unknown): error is { name: string; status: number } => {
  return (
    error instanceof Error &&
    error.name === "ApiError" &&
    "status" in error &&
    typeof (error as { status: unknown }).status === "number"
  );
};

export function dispatchRouteError(error: unknown): JSX.Element {
  if (isApiError(error)) {
    if (error.status === 403) return <RouteForbiddenCard />;
    if (error.status === 404) return <RouteNotFoundCard />;
  }
  if (error instanceof ZodError) {
    return <RouteSchemaErrorCard />;
  }
  return <RouteRuntimeErrorCard />;
}
