// apps/web/src/routes/me.tsx
//
// Authenticated profile view — shadcn dashboard-card pattern. GET /v1/me is
// disabled while no token is in memory (post-reload state) so the SPA never
// fires a guaranteed-401 request on cold start.

import { Link } from "@tanstack/react-router";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import {
  Card,
  CardContent,
  CardDescription,
  CardFooter,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { AuthLayout } from "@/features/auth/components/AuthLayout";
import { useLogoutMutation, useMeQuery } from "@/features/auth/api/hooks";
import { getAccessToken } from "@/api/tokenStore";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

export function MeRoute() {
  useDocumentTitle("Your account");
  const hasToken = getAccessToken() !== null;
  const meQuery = useMeQuery();
  const logoutMutation = useLogoutMutation();

  if (!hasToken) {
    return (
      <AuthLayout>
        <Card>
          <CardHeader>
            <CardTitle>Not signed in</CardTitle>
            <CardDescription>You need to be signed in to view this page.</CardDescription>
          </CardHeader>
          <CardFooter>
            <Link
              to="/login"
              className={buttonVariants({ variant: "default", className: "w-full" })}
            >
              Go to sign in
            </Link>
          </CardFooter>
        </Card>
      </AuthLayout>
    );
  }

  return (
    <AuthLayout>
      <Card>
        <CardHeader>
          <CardTitle>Your account</CardTitle>
          <CardDescription>Loaded from /v1/me.</CardDescription>
        </CardHeader>
        <CardContent className="space-y-3 text-sm">
          {meQuery.isLoading ? (
            <Skeleton className="h-24 w-full" />
          ) : meQuery.isError ? (
            <Alert variant="destructive">
              <AlertDescription>Could not load your profile.</AlertDescription>
            </Alert>
          ) : meQuery.data !== undefined ? (
            <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-2">
              <dt className="font-medium text-muted-foreground">id</dt>
              <dd className="font-mono text-xs">{meQuery.data.id}</dd>
              <dt className="font-medium text-muted-foreground">email</dt>
              <dd>{meQuery.data.email}</dd>
              <dt className="font-medium text-muted-foreground">display_name</dt>
              <dd>{meQuery.data.display_name ?? "—"}</dd>
              <dt className="font-medium text-muted-foreground">locale</dt>
              <dd>{meQuery.data.locale ?? "—"}</dd>
              <dt className="font-medium text-muted-foreground">timezone</dt>
              <dd>{meQuery.data.timezone ?? "—"}</dd>
              <dt className="font-medium text-muted-foreground">active_tenant</dt>
              <dd>{meQuery.data.active_tenant ?? "—"}</dd>
            </dl>
          ) : null}
        </CardContent>
        <CardFooter className="flex-col gap-2">
          <Button
            type="button"
            variant="outline"
            className="w-full"
            onClick={() => logoutMutation.mutate()}
            disabled={logoutMutation.isPending}
          >
            {logoutMutation.isPending ? "Signing out..." : "Sign out"}
          </Button>
        </CardFooter>
      </Card>
    </AuthLayout>
  );
}
