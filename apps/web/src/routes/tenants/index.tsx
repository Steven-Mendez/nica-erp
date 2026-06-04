// /tenants — empresa picker. Forced on every fresh session by the
// route guard (`isPickerConfirmed()` is `false` until a switch fires
// `setPickerConfirmed()`). Cards are searchable, keyboard-activatable,
// and on click run the switch mutation then navigate to /dashboard.

import { useMemo, useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { useMyTenantsQuery, useSwitchTenantMutation } from "@/features/tenants/api/hooks";
import { useDocumentTitle } from "@/lib/useDocumentTitle";
import { setPickerConfirmed } from "@/lib/route-guard";
import { BrandLayout } from "@/components/brand-header";
import { roleLabel } from "@/features/tenants/lib/role-labels";

type Membership = {
  tenant_id: string;
  name: string;
  role: string;
};

function initialsOf(name: string): string {
  return name
    .split(/\s+/)
    .filter((s) => s.length > 0)
    .slice(0, 2)
    .map((s) => s.charAt(0).toUpperCase())
    .join("");
}

function MembershipCard({
  membership,
  disabled,
  onActivate,
}: {
  membership: Membership;
  disabled: boolean;
  onActivate: (tenantId: string) => void;
}) {
  const initials = initialsOf(membership.name);
  return (
    <Card
      role="button"
      tabIndex={0}
      aria-disabled={disabled}
      aria-label={`Seleccionar ${membership.name}`}
      onClick={() => {
        if (disabled) return;
        onActivate(membership.tenant_id);
      }}
      onKeyDown={(e) => {
        if (disabled) return;
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onActivate(membership.tenant_id);
        }
      }}
      className={`cursor-pointer transition-shadow hover:shadow-md focus:outline-hidden focus-visible:ring-2 focus-visible:ring-ring ${
        disabled ? "pointer-events-none opacity-60" : ""
      }`}
    >
      <CardContent className="flex items-start gap-3 p-4">
        <div className="size-9 rounded-md bg-muted text-sm font-semibold grid place-items-center">
          {initials}
        </div>
        <div className="flex-1 min-w-0 space-y-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-medium truncate">{membership.name}</span>
            <Badge variant="secondary">{roleLabel(membership.role)}</Badge>
          </div>
        </div>
      </CardContent>
    </Card>
  );
}

export function TenantsIndexRoute() {
  useDocumentTitle("Tus empresas");
  const navigate = useNavigate();
  const tenants = useMyTenantsQuery();
  const switchMut = useSwitchTenantMutation();
  const [query, setQuery] = useState("");

  const filtered = useMemo(() => {
    const items = tenants.data?.items ?? [];
    const q = query.trim().toLowerCase();
    if (q === "") return items;
    return items.filter((m) => m.name.toLowerCase().includes(q));
  }, [tenants.data, query]);

  const onActivate = (tenantId: string): void => {
    // The refresh token rides in the httpOnly `nica_erp_rt` cookie
    // shipped via `credentials: include` on the openapi-fetch client.
    switchMut.mutate(
      { tenantId, input: {} },
      {
        onSuccess: () => {
          setPickerConfirmed();
          void navigate({ to: "/dashboard" });
        },
      },
    );
  };

  return (
    <BrandLayout>
      <div className="mx-auto max-w-5xl space-y-6 p-6">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <h1 className="text-2xl font-semibold">Tus empresas</h1>
          <Link to="/tenants/new" className={buttonVariants({ variant: "default" })}>
            + Nueva empresa
          </Link>
        </div>

        {tenants.isLoading ? (
          <Skeleton className="h-32 w-full" />
        ) : tenants.isError ? (
          <Alert variant="destructive">
            <AlertDescription>No se pudieron cargar tus empresas.</AlertDescription>
          </Alert>
        ) : (tenants.data?.items.length ?? 0) === 0 ? (
          <Alert>
            <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
              <span>Aún no tienes empresas. Crea una para empezar a facturar.</span>
              <Link
                to="/tenants/new"
                className={buttonVariants({ variant: "outline", className: "w-fit" })}
              >
                Crear empresa
              </Link>
            </AlertDescription>
          </Alert>
        ) : (
          <>
            <Input
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Buscar una empresa…"
              aria-label="Buscar una empresa"
            />
            <div className="grid gap-3 grid-cols-1 md:grid-cols-2 lg:grid-cols-3">
              {filtered.map((m) => (
                <MembershipCard
                  key={m.tenant_id}
                  membership={m}
                  disabled={switchMut.isPending}
                  onActivate={onActivate}
                />
              ))}
            </div>
          </>
        )}
      </div>
    </BrandLayout>
  );
}
