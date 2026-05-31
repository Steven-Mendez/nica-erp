import { Link } from "@tanstack/react-router";
import { Building2 } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import { getRefreshToken } from "@/api/tokenStore";
import { useMyTenantsQuery, useSwitchTenantMutation } from "@/features/tenants/api/hooks";
import { useMeQuery } from "@/features/auth/api/hooks";
import { router } from "@/router";
import { useSidebar } from "./sidebar-context";

export function TenantSwitcher() {
  const tenants = useMyTenantsQuery();
  const me = useMeQuery();
  const switchMut = useSwitchTenantMutation();
  const { state } = useSidebar();

  if (tenants.isLoading) {
    return <Skeleton className="h-10 w-full" />;
  }
  if (tenants.isError || tenants.data === undefined) {
    return null;
  }

  const items = tenants.data.items;
  const activeId = me.data?.active_tenant ?? null;
  const active = items.find((item) => item.tenant_id === activeId) ?? null;

  if (items.length === 0) {
    return (
      <Link
        to="/tenants/new"
        title="Sin empresa activa"
        data-state={state}
        className="flex w-full items-center gap-2 rounded-md p-2 text-sm text-sidebar-foreground/80 hover:bg-sidebar-accent hover:text-sidebar-accent-foreground data-[state=collapsed]:justify-center data-[state=collapsed]:p-0"
      >
        <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground">
          <Building2 className="h-4 w-4" />
        </span>
        <span
          data-state={state}
          className="flex-1 truncate text-left data-[state=collapsed]:hidden"
        >
          Sin empresa activa
        </span>
      </Link>
    );
  }

  const handleChange = (event: React.ChangeEvent<HTMLSelectElement>) => {
    const next = event.target.value;
    if (!next || next === activeId) return;
    const refresh = getRefreshToken();
    if (refresh === null) return;
    switchMut.mutate(
      { tenantId: next, input: { refresh_token: refresh } },
      {
        onSuccess: () => {
          void router.invalidate();
        },
      },
    );
  };

  return (
    <div
      className="flex w-full items-center gap-2 data-[state=collapsed]:justify-center"
      data-state={state}
    >
      <span
        className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground"
        title={active?.name ?? "Empresa"}
      >
        <Building2 className="h-4 w-4" />
      </span>
      <div
        data-state={state}
        className="flex min-w-0 flex-1 flex-col data-[state=collapsed]:hidden"
      >
        <label htmlFor="tenant-switcher" className="sr-only">
          Empresa activa
        </label>
        <select
          id="tenant-switcher"
          className="-mx-1 truncate rounded-md bg-transparent px-1 py-0.5 text-sm font-medium text-sidebar-foreground hover:bg-sidebar-accent focus:outline-hidden focus:ring-1 focus:ring-sidebar-ring"
          value={activeId ?? ""}
          onChange={handleChange}
          disabled={switchMut.isPending}
        >
          {items.map((item) => (
            <option key={item.tenant_id} value={item.tenant_id}>
              {item.name} · {item.role}
            </option>
          ))}
        </select>
        <span className="truncate text-xs text-sidebar-foreground/60">
          {switchMut.isPending ? "Cambiando..." : (active?.role ?? "—")}
        </span>
      </div>
    </div>
  );
}
