// /empresa/settings — empresa fiscal-data editor. Prefills the
// four-section form from the active empresa's payload and writes
// back via `useUpdateActiveTenantMutation`. Permission gating
// (`tenant.update`) lives inside the form component so the route
// stays a thin wrapper.

import { AppShell } from "@/components/app-shell";
import { Skeleton } from "@/components/ui/skeleton";
import { useMeQuery } from "@/features/auth/api/hooks";
import { useTenantQuery } from "@/features/tenants/api/hooks";
import { EmpresaFiscalSettingsForm } from "@/features/tenants/components/empresa-fiscal-settings-form";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

export function EmpresaConfiguracionRoute() {
  useDocumentTitle("Configuración de la empresa");
  const me = useMeQuery();
  const activeId = me.data?.active_tenant ?? "";
  const tenant = useTenantQuery(activeId);

  if (me.isError) throw me.error;
  if (tenant.isError) throw tenant.error;

  return (
    <AppShell>
      {tenant.isLoading || tenant.data === undefined ? (
        <div className="mx-auto flex max-w-3xl flex-col gap-4 py-8">
          <Skeleton className="h-8 w-1/2" />
          <Skeleton className="h-40 w-full" />
          <Skeleton className="h-40 w-full" />
        </div>
      ) : (
        <EmpresaFiscalSettingsForm tenant={tenant.data} />
      )}
    </AppShell>
  );
}
