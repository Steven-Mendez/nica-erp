import { Link } from "@tanstack/react-router";
import { AppShell } from "@/components/app-shell";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { ActivityCard, SectionKpis, TrendCard } from "@/features/dashboard";
import { useMeQuery } from "@/features/auth/api/hooks";
import { useTenantQuery } from "@/features/tenants/api/hooks";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

function FiscalDataBanner({ tenantId }: { tenantId: string }) {
  const tenant = useTenantQuery(tenantId);
  if (tenant.data === undefined) return null;
  const incomplete =
    tenant.data.ruc === null ||
    tenant.data.ruc === undefined ||
    tenant.data.fiscal_address === null ||
    tenant.data.fiscal_address === undefined;
  if (!incomplete) return null;
  return (
    <div className="px-4 lg:px-6">
      <Alert>
        <AlertDescription className="flex flex-wrap items-center justify-between gap-3">
          <span>Completa los datos fiscales de tu empresa para emitir facturas.</span>
          <Link to="/empresa/settings" className="font-medium underline underline-offset-4">
            Completar ahora
          </Link>
        </AlertDescription>
      </Alert>
    </div>
  );
}

export function DashboardRoute() {
  useDocumentTitle("Resumen");
  const me = useMeQuery();
  const activeTenantId = me.data?.active_tenant ?? null;
  return (
    <AppShell>
      <div className="flex flex-col gap-4 py-4 md:gap-6 md:py-6">
        {activeTenantId !== null ? <FiscalDataBanner tenantId={activeTenantId} /> : null}
        <div className="px-4 lg:px-6">
          <h1 className="text-2xl font-semibold tracking-tight">Resumen</h1>
          <p className="text-sm text-muted-foreground">
            Aquí aparecerán los ingresos, cuentas por cobrar, stock en riesgo y productos top.
          </p>
        </div>

        <SectionKpis />

        <div className="grid grid-cols-1 gap-4 px-4 lg:grid-cols-3 lg:px-6">
          <div className="lg:col-span-2">
            <TrendCard />
          </div>
          <ActivityCard />
        </div>
      </div>
    </AppShell>
  );
}
