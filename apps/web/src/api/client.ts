// apps/web/src/api/client.ts
import createClient from "openapi-fetch";

const baseUrl = import.meta.env.VITE_API_BASE_URL ?? "http://localhost:8000";

// Replace the type parameter with `import('./schema').paths` after the typed
// schema has been generated with `pnpm gen:api` against the running API.
export const api = createClient<Record<string, never>>({ baseUrl });

export interface HealthzResponse {
  status: string;
  version: string;
  git_sha: string;
  db: string;
  alembic_revision: string | null;
}

export async function fetchHealthz(): Promise<HealthzResponse> {
  const response = await fetch(`${baseUrl}/healthz`, {
    headers: { Accept: "application/json" },
  });
  if (!response.ok) {
    throw new Error(`/healthz failed: ${response.status}`);
  }
  return (await response.json()) as HealthzResponse;
}
