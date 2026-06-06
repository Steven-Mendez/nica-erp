import { Link } from "@tanstack/react-router";
import { Building2, ChevronsUpDown, Plus } from "lucide-react";
import { Skeleton } from "@/components/ui/skeleton";
import {
  DropdownMenu,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuLabel,
  DropdownMenuSeparator,
  DropdownMenuShortcut,
  DropdownMenuTrigger,
} from "@/components/ui/dropdown-menu";
import { useMyTenantsQuery, useSwitchTenantMutation } from "@/features/tenants/api/hooks";
import { useMeQuery } from "@/features/auth/api/hooks";
import { router } from "@/router";
import { useSidebar } from "./sidebar-context";
import { SidebarMenu, SidebarMenuItem } from "./sidebar";

import { roleLabel } from "@/features/tenants/lib/role-labels";

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

  const handleChange = (next: string) => {
    if (!next || next === activeId) return;
    // The refresh token rides in the httpOnly `nica_erp_rt` cookie,
    // shipped via `credentials: include` on the openapi-fetch client.
    switchMut.mutate(
      { tenantId: next, input: {} },
      {
        onSuccess: () => {
          void router.invalidate();
        },
      },
    );
  };

  return (
    <SidebarMenu className="w-full">
      <SidebarMenuItem>
        <DropdownMenu>
          <DropdownMenuTrigger asChild disabled={switchMut.isPending}>
            <div
              role="button"
              tabIndex={0}
              aria-label={active ? `Empresa activa: ${active.name}` : "Empresa activa"}
              className="flex w-full cursor-pointer items-center gap-2 rounded-md p-2 text-left text-sm hover:bg-sidebar-accent hover:text-sidebar-accent-foreground data-[state=collapsed]:justify-center data-[state=open]:bg-sidebar-accent data-[state=open]:text-sidebar-accent-foreground"
              data-state={state}
            >
              <span
                className="flex size-8 shrink-0 items-center justify-center rounded-lg bg-sidebar-primary text-sidebar-primary-foreground"
                title={active?.name ?? "Empresa"}
              >
                <Building2 className="size-4" />
              </span>
              <div
                data-state={state}
                className="grid flex-1 text-left text-sm leading-tight data-[state=collapsed]:hidden"
              >
                <span className="truncate font-semibold">{active?.name ?? "Empresa"}</span>
                <span className="truncate text-xs text-sidebar-foreground/60">
                  {switchMut.isPending ? "Cambiando..." : active ? roleLabel(active.role) : "—"}
                </span>
              </div>
              <ChevronsUpDown
                data-state={state}
                className="ml-auto size-4 text-sidebar-foreground/50 data-[state=collapsed]:hidden"
              />
            </div>
          </DropdownMenuTrigger>
          <DropdownMenuContent
            className="w-[var(--radix-dropdown-menu-trigger-width)] min-w-56 rounded-lg"
            align="start"
            side={state === "collapsed" ? "right" : "bottom"}
            sideOffset={4}
          >
            <DropdownMenuLabel className="text-xs text-muted-foreground">
              Empresas
            </DropdownMenuLabel>
            {items.map((item, i) => (
              <DropdownMenuItem
                key={item.tenant_id}
                onClick={() => handleChange(item.tenant_id)}
                className="gap-2 p-2"
              >
                <div className="flex size-6 items-center justify-center rounded-sm border bg-background">
                  <Building2 className="size-3.5 shrink-0" />
                </div>
                {item.name}
                {i < 9 && <DropdownMenuShortcut>⌘{i + 1}</DropdownMenuShortcut>}
              </DropdownMenuItem>
            ))}
            <DropdownMenuSeparator />
            <DropdownMenuItem className="gap-2 p-2" asChild>
              <Link to="/tenants/new">
                <div className="flex size-6 items-center justify-center rounded-md border bg-background">
                  <Plus className="size-4" />
                </div>
                <div className="font-medium text-muted-foreground">Crear empresa</div>
              </Link>
            </DropdownMenuItem>
          </DropdownMenuContent>
        </DropdownMenu>
      </SidebarMenuItem>
    </SidebarMenu>
  );
}
