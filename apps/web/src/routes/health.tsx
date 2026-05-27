// apps/web/src/routes/health.tsx
//
// Operator-facing health dashboard. Reads /healthz and renders status, db,
// version, git_sha, alembic_revision. Not linked from the auth UI — direct
// URL only, for debugging.

import { useHealthz } from "@/api/healthz";
import { Badge, type BadgeProps } from "@/components/ui/badge";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

type FieldState =
  | { kind: "loading" }
  | { kind: "unreachable" }
  | { kind: "value"; value: string | null };

function StatusCell({ state }: { state: FieldState }) {
  if (state.kind === "loading") return <Skeleton className="inline-block h-4 w-16" />;
  if (state.kind === "unreachable") return <Badge variant="danger">unreachable</Badge>;
  const value = state.value ?? "—";
  const variant: BadgeProps["variant"] = value === "ok" ? "ok" : "warn";
  return <Badge variant={variant}>{value}</Badge>;
}

function MonoCell({ state }: { state: FieldState }) {
  if (state.kind === "loading") return <Skeleton className="inline-block h-4 w-32" />;
  if (state.kind === "unreachable") return <Badge variant="outline">unknown</Badge>;
  return <span className="font-mono text-foreground">{state.value ?? "—"}</span>;
}

export function HealthRoute() {
  useDocumentTitle("System health");
  const { data, isLoading, isError } = useHealthz();
  const offline = isError || (!isLoading && !data);

  const fieldState = (value: string | null | undefined): FieldState => {
    if (isLoading) return { kind: "loading" };
    if (offline) return { kind: "unreachable" };
    return { kind: "value", value: value ?? null };
  };

  return (
    <main className="mx-auto flex min-h-screen max-w-2xl flex-col items-center justify-center p-8">
      <Card className="w-full">
        <CardHeader>
          <CardTitle>Nica ERP</CardTitle>
          <CardDescription>Backend health, read from /healthz.</CardDescription>
        </CardHeader>
        <CardContent>
          <dl className="grid grid-cols-[max-content_1fr] items-center gap-x-6 gap-y-3 text-sm">
            <dt className="font-medium text-muted-foreground">status</dt>
            <dd>
              <StatusCell state={fieldState(data?.status)} />
            </dd>

            <dt className="font-medium text-muted-foreground">db</dt>
            <dd>
              <StatusCell state={fieldState(data?.db)} />
            </dd>

            <dt className="font-medium text-muted-foreground">version</dt>
            <dd>
              <MonoCell state={fieldState(data?.version)} />
            </dd>

            <dt className="font-medium text-muted-foreground">git_sha</dt>
            <dd>
              <MonoCell state={fieldState(data?.git_sha)} />
            </dd>

            <dt className="font-medium text-muted-foreground">alembic_revision</dt>
            <dd>
              <MonoCell state={fieldState(data?.alembic_revision)} />
            </dd>
          </dl>
        </CardContent>
      </Card>
    </main>
  );
}
