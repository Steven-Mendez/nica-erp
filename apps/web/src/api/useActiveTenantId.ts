// Shared hook returning the operator's currently active empresa id.
// Lives in src/api/ (shared infra) so any feature slice can gate
// per-tenant queries on a stable id without reaching into another
// slice. Mirrors the useHasPermission pattern: reads the same /v1/me
// cache key without owning the fetch.

import { useQuery } from "@tanstack/react-query";
import { api } from "@/api/client";
import { meQueryKey } from "@/api/queryKeys";
import type { components } from "@/api/schema";
import { getAccessToken } from "@/api/tokenStore";

type Me = components["schemas"]["MeResponse"];

const fetchMe = async (): Promise<Me> => {
  const result = await api.GET("/v1/me", {});
  if (result.error !== undefined || result.data === undefined) {
    throw new Error("Failed to load /v1/me");
  }
  return result.data;
};

export const useActiveTenantId = (): string | null => {
  const me = useQuery({
    queryKey: meQueryKey,
    queryFn: fetchMe,
    enabled: getAccessToken() !== null,
    staleTime: 30_000,
  });
  return me.data?.active_tenant ?? null;
};
