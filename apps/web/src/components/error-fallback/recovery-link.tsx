import { buttonVariants } from "@/components/ui/button";
import { getAccessToken } from "@/api/tokenStore";

// Recovery destination is auth-aware and resolved synchronously from
// the token store, NOT from `useMeQuery`. The /me query may have been
// the source of the boundary; reading it here would risk re-throwing
// inside the fallback. We render a plain <a> (not a TanStack <Link>)
// on purpose: the SPA may be in a half-broken state when this card
// renders, so a hard navigation that forces a fresh app boot is the
// recovery action we want — and it also keeps the fallback render
// independent of `RouterProvider`.
export function RecoveryLink({ children }: { children: React.ReactNode }) {
  const target = getAccessToken() !== null ? "/dashboard" : "/login";
  return (
    <a href={target} className={buttonVariants({ variant: "default" })}>
      {children}
    </a>
  );
}
