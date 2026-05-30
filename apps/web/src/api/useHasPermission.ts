// Shared hook for checking whether the current actor holds a permission.
// Lives in src/api/ (shared infra) so any feature slice can gate UI
// without reaching into another slice. Returns false while the /v1/me
// query is pending so a button doesn't flicker enabled on cold load.

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

export const useHasPermission = (code: string): boolean => {
  const me = useQuery({
    queryKey: meQueryKey,
    queryFn: fetchMe,
    enabled: getAccessToken() !== null,
    staleTime: 30_000,
  });
  return (me.data?.permissions ?? []).includes(code);
};
