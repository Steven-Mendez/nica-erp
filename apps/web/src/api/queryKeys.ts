// Shared TanStack Query keys for cross-feature reuse. Lives in src/api/
// (shared infra) so any slice can invalidate caches owned by another
// slice without crossing a forbidden feature boundary.

export const meQueryKey = ["auth", "me"] as const;
