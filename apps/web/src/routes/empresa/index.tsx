// /empresa — Vista general. Re-uses the four-section Revisión card
// from the wizard and renders the soft-creation banner when any
// fiscal field is still NULL.

import { Link, useNavigate } from "@tanstack/react-router";
import { useEffect } from "react";
import { AppShell } from "@/components/app-shell";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Separator } from "@/components/ui/separator";
import { Skeleton } from "@/components/ui/skeleton";
import { useMeQuery } from "@/features/auth/api/hooks";
import { useTenantQuery } from "@/features/tenants/api/hooks";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <section>
      <h3 className="mb-2 text-xs uppercase tracking-wide text-muted-foreground">{title}</h3>
      <dl className="grid gap-x-4 gap-y-2 sm:grid-cols-2">{children}</dl>
    </section>
  );
}

function Datum({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="space-y-0.5">
      <dt className="text-xs text-muted-foreground">{label}</dt>
      <dd className="text-sm font-medium">{value}</dd>
    </div>
  );
}

function fmtDate(iso: string | null | undefined): string {
  if (iso === null || iso === undefined || iso === "") return "—";
  return iso;
}

export function EmpresaIndexRoute() {
  useDocumentTitle("Empresa");
  const navigate = useNavigate();
  const me = useMeQuery();
  const activeTenantId = me.data?.active_tenant ?? null;
  const tenant = useTenantQuery(activeTenantId ?? "");

  useEffect(() => {
    if (me.isLoading) return;
    if (activeTenantId === null) {
      void navigate({ to: "/tenants" });
    }
  }, [me.isLoading, activeTenantId, navigate]);

  if (me.isError) throw me.error;
  if (tenant.isError) throw tenant.error;

  if (activeTenantId === null || tenant.isLoading || tenant.data === undefined) {
    return (
      <AppShell>
        <div className="mx-auto max-w-3xl space-y-4 p-4">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-64 w-full" />
        </div>
      </AppShell>
    );
  }

  const t = tenant.data;
  const incomplete =
    t.ruc === null ||
    t.ruc === undefined ||
    t.fiscal_address === null ||
    t.fiscal_address === undefined;
  const dgi = t.authorization_dgi ?? null;

  return (
    <AppShell>
      <div className="mx-auto max-w-3xl space-y-4 p-4">
        <h1 className="text-2xl font-semibold">{t.name}</h1>

        {incomplete ? (
          <Alert>
            <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
              <span>Completa los datos fiscales de tu empresa para emitir facturas.</span>
              <Link to="/empresa/settings" className="font-medium underline underline-offset-4">
                Completar ahora
              </Link>
            </AlertDescription>
          </Alert>
        ) : null}

        <Card>
          <CardHeader>
            <CardTitle>Revisión</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <Section title="Identidad">
              <Datum label="Nombre" value={t.name} />
              <Datum
                label="RUC"
                value={
                  t.ruc !== null && t.ruc !== undefined && t.ruc !== "" ? (
                    <span className="font-mono">{t.ruc}</span>
                  ) : (
                    <Badge variant="secondary">Pendiente</Badge>
                  )
                }
              />
            </Section>
            <Separator />
            <Section title="Régimen fiscal">
              <Datum
                label="Régimen"
                value={
                  t.regime === "general" ? (
                    "Régimen general"
                  ) : t.regime === "cuota_fija" ? (
                    "Cuota fija"
                  ) : t.regime === "pequeno_contribuyente" ? (
                    "Pequeño contribuyente"
                  ) : (
                    <Badge variant="secondary">Pendiente</Badge>
                  )
                }
              />
              <Datum
                label="Municipio"
                value={
                  t.municipality !== null &&
                  t.municipality !== undefined &&
                  t.municipality !== "" ? (
                    t.municipality
                  ) : (
                    <Badge variant="secondary">Pendiente</Badge>
                  )
                }
              />
              <Datum
                label="Retenedor"
                value={
                  <Badge variant={t.is_withholder ? "default" : "secondary"}>
                    {t.is_withholder ? "Sí" : "No"}
                  </Badge>
                }
              />
            </Section>
            <Separator />
            <Section title="Autorización DGI">
              <Datum
                label="Número"
                value={
                  dgi !== null && dgi.number !== "" ? (
                    <span className="font-mono">{dgi.number}</span>
                  ) : (
                    <Badge variant="secondary">Pendiente</Badge>
                  )
                }
              />
              <Datum
                label="Vigencia"
                value={
                  dgi !== null ? (
                    `${fmtDate(dgi.valid_from)} → ${fmtDate(dgi.valid_to)}`
                  ) : (
                    <Badge variant="secondary">Pendiente</Badge>
                  )
                }
              />
            </Section>
            <Separator />
            <Section title="Dirección">
              <Datum
                label="Dirección fiscal"
                value={
                  t.fiscal_address !== null &&
                  t.fiscal_address !== undefined &&
                  t.fiscal_address !== "" ? (
                    t.fiscal_address
                  ) : (
                    <Badge variant="secondary">Pendiente</Badge>
                  )
                }
              />
            </Section>
          </CardContent>
        </Card>
      </div>
    </AppShell>
  );
}
