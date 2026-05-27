// apps/web/src/api/healthz.ts
//
// `/healthz` returns an untyped dict in the OpenAPI schema (FastAPI default
// for `dict[str, Any]`), so we hand-type the runtime shape we care about. The
// `useHealthz` TanStack hook polls every 30 s.

import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";

export interface HealthzResponse {
  status: string;
  version: string;
  git_sha: string;
  db: string;
  alembic_revision: string | null;
}

export const fetchHealthz = async (): Promise<HealthzResponse> => {
  const result = await api.GET("/healthz", {});
  if (result.data === undefined) {
    throw new Error(`/healthz failed: ${result.response.status}`);
  }
  return result.data as unknown as HealthzResponse;
};

export const useHealthz = () => {
  return useQuery({
    queryKey: ["healthz"],
    queryFn: fetchHealthz,
    refetchInterval: 30_000,
    retry: 1,
  });
};
