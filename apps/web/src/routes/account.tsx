import { Link } from "@tanstack/react-router";
import { IdentityLayout } from "@/components/identity-layout/identity-layout";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { AuthLayout } from "@/features/auth/components/AuthLayout";
import { useMeQuery } from "@/features/auth/api/hooks";
import { useMyTenantsQuery } from "@/features/tenants/api/hooks";
import { getAccessToken } from "@/api/tokenStore";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

export function AccountRoute() {
  useDocumentTitle("Cuenta");
  const hasToken = getAccessToken() !== null;
  const meQuery = useMeQuery();
  const tenantsQuery = useMyTenantsQuery();

  if (!hasToken) {
    return (
      <AuthLayout>
        <Card>
          <CardHeader>
            <CardTitle>No has iniciado sesión</CardTitle>
            <CardDescription>Inicia sesión para ver tu cuenta.</CardDescription>
          </CardHeader>
          <CardContent>
            <Link
              to="/login"
              className={buttonVariants({ variant: "default", className: "w-full" })}
            >
              Ir a iniciar sesión
            </Link>
          </CardContent>
        </Card>
      </AuthLayout>
    );
  }

  const me = meQuery.data;
  const activeTenantId = me?.active_tenant ?? null;
  const activeTenant =
    tenantsQuery.data?.items.find((item) => item.tenant_id === activeTenantId) ?? null;
  const permissions = me?.permissions ?? [];

  return (
    <IdentityLayout>
      <div className="mx-auto max-w-3xl space-y-6">
        <div>
          <h1 className="text-2xl font-semibold">Cuenta</h1>
          <p className="text-sm text-muted-foreground">
            Tu perfil, la empresa activa y tus permisos.
          </p>
        </div>

        {meQuery.isError ? (
          <Alert variant="destructive">
            <AlertDescription>No se pudo cargar tu perfil.</AlertDescription>
          </Alert>
        ) : null}

        <Card>
          <CardHeader>
            <CardTitle>Perfil</CardTitle>
            <CardDescription>Cargado desde /v1/me.</CardDescription>
          </CardHeader>
          <CardContent>
            {meQuery.isLoading || me === undefined ? (
              <Skeleton className="h-24 w-full" />
            ) : (
              <dl className="grid grid-cols-[max-content_1fr] gap-x-4 gap-y-2 text-sm">
                <dt className="font-medium text-muted-foreground">id</dt>
                <dd className="font-mono text-xs">{me.id}</dd>
                <dt className="font-medium text-muted-foreground">email</dt>
                <dd>{me.email}</dd>
                <dt className="font-medium text-muted-foreground">display_name</dt>
                <dd>{me.display_name ?? "—"}</dd>
                <dt className="font-medium text-muted-foreground">locale</dt>
                <dd>{me.locale ?? "—"}</dd>
                <dt className="font-medium text-muted-foreground">timezone</dt>
                <dd>{me.timezone ?? "—"}</dd>
              </dl>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Empresa activa</CardTitle>
            <CardDescription>La empresa asociada a tu sesión.</CardDescription>
          </CardHeader>
          <CardContent className="text-sm">
            {meQuery.isLoading || tenantsQuery.isLoading ? (
              <Skeleton className="h-12 w-full" />
            ) : activeTenant === null ? (
              <div className="space-y-2 text-muted-foreground">
                <p>Sin empresa activa.</p>
                <Link
                  to="/tenants/new"
                  className={buttonVariants({ variant: "outline", className: "w-fit" })}
                >
                  Crear empresa
                </Link>
              </div>
            ) : (
              <div className="flex flex-wrap items-center gap-3">
                <div>
                  <p className="font-medium">{activeTenant.name}</p>
                  <p className="font-mono text-xs text-muted-foreground">
                    {activeTenant.tenant_id}
                  </p>
                </div>
                <Badge variant="secondary" className="capitalize">
                  {activeTenant.role}
                </Badge>
              </div>
            )}
          </CardContent>
        </Card>

        <Card>
          <CardHeader>
            <CardTitle>Permisos</CardTitle>
            <CardDescription>Acciones permitidas en la empresa activa.</CardDescription>
          </CardHeader>
          <CardContent>
            {meQuery.isLoading ? (
              <Skeleton className="h-20 w-full" />
            ) : permissions.length === 0 ? (
              <p className="text-sm text-muted-foreground">Sin permisos.</p>
            ) : (
              <ul className="grid grid-cols-1 gap-1 text-sm sm:grid-cols-2">
                {permissions.map((code) => (
                  <li key={code} className="font-mono text-xs">
                    {code}
                  </li>
                ))}
              </ul>
            )}
          </CardContent>
        </Card>
      </div>
    </IdentityLayout>
  );
}
