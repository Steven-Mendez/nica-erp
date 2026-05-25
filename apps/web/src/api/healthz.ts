// apps/web/src/api/healthz.ts
import { useQuery } from "@tanstack/react-query";
import { fetchHealthz, type HealthzResponse } from "./client";

export function useHealthz() {
  return useQuery<HealthzResponse>({
    queryKey: ["healthz"],
    queryFn: fetchHealthz,
    refetchInterval: 30_000,
    retry: 1,
  });
}
