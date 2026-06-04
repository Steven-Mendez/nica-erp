import { Link, useRouterState } from "@tanstack/react-router";
import { useHasPermission } from "@/api/useHasPermission";
import { ChevronRight } from "lucide-react";
import {
  Boxes,
  Building2,
  FileBarChart,
  LayoutDashboard,
  Settings,
  ShoppingCart,
} from "lucide-react";
import { TenantSwitcher } from "./tenant-switcher";
import {
  Sidebar,
  SidebarContent,
  SidebarGroup,
  SidebarGroupLabel,
  SidebarHeader,
  SidebarMenu,
  SidebarMenuButton,
  SidebarMenuItem,
  SidebarMenuSub,
  SidebarMenuSubButton,
  SidebarMenuSubItem,
} from "./sidebar";
import { useSidebar, useSidebarSection } from "./sidebar-context";

type NavItem = {
  label: string;
  to: string;
  icon: typeof LayoutDashboard;
  match?: (path: string) => boolean;
};

type SubItem = { label: string; to: string };

const NAV_ITEMS: NavItem[] = [
  { label: "Resumen", to: "/dashboard", icon: LayoutDashboard },
  { label: "Ventas", to: "/sales", icon: ShoppingCart },
  { label: "Inventario", to: "/inventory", icon: Boxes },
  { label: "Reportes", to: "/reports", icon: FileBarChart },
  { label: "Configuración", to: "/settings", icon: Settings },
];

const EMPRESA_PARENT = {
  label: "Empresa",
  icon: Building2,
  sectionKey: "empresa",
  parentPath: "/empresa",
};

// Spanish labels per Spanish-UI rule; English paths per route rule.
const EMPRESA_CHILDREN: SubItem[] = [
  { label: "Vista general", to: "/empresa" },
  { label: "Usuarios", to: "/empresa/users" },
  { label: "Configuración", to: "/empresa/settings" },
];

function isActive(itemTo: string, match: NavItem["match"], pathname: string): boolean {
  if (match !== undefined) return match(pathname);
  return pathname === itemTo;
}

function EmpresaSection({ pathname }: { pathname: string }) {
  const { state } = useSidebar();
  const parentActive = pathname === "/empresa" || pathname.startsWith("/empresa/");
  const section = useSidebarSection(EMPRESA_PARENT.sectionKey, parentActive);
  const Icon = EMPRESA_PARENT.icon;
  const canReadMembers = useHasPermission("members:read");
  const canWriteTenant = useHasPermission("tenant:write");

  return (
    <SidebarMenuItem>
      <SidebarMenuButton
        active={parentActive}
        icon={<Icon className="h-4 w-4" aria-hidden="true" />}
        aria-expanded={section.open}
        aria-controls="sidebar-section-empresa"
        title={EMPRESA_PARENT.label}
        onClick={section.toggle}
      >
        <span className="flex items-center justify-between">
          <span className="truncate">{EMPRESA_PARENT.label}</span>
          <ChevronRight
            className={`h-3.5 w-3.5 shrink-0 transition-transform ${
              section.open ? "rotate-90" : ""
            }`}
            aria-hidden="true"
          />
        </span>
      </SidebarMenuButton>
      {state === "expanded" && section.open ? (
        <SidebarMenuSub id="sidebar-section-empresa">
          {EMPRESA_CHILDREN.map((child) => {
            if (child.to === "/empresa/users" && !canReadMembers) return null;
            if (child.to === "/empresa/settings" && !canWriteTenant) return null;

            const active =
              child.to === "/empresa"
                ? pathname === "/empresa"
                : pathname === child.to || pathname.startsWith(`${child.to}/`);
            return (
              <SidebarMenuSubItem key={child.to}>
                <Link to={child.to}>
                  <SidebarMenuSubButton active={active} label={child.label} />
                </Link>
              </SidebarMenuSubItem>
            );
          })}
        </SidebarMenuSub>
      ) : null}
    </SidebarMenuItem>
  );
}

export function AppSidebar() {
  const { state } = useSidebar();
  const routerState = useRouterState({ select: (s) => ({ pathname: s.location.pathname }) });
  const pathname = routerState.pathname;

  return (
    <Sidebar>
      <SidebarHeader>
        <TenantSwitcher />
      </SidebarHeader>
      <SidebarContent>
        <SidebarGroup>
          <SidebarGroupLabel>Espacio de trabajo</SidebarGroupLabel>
          <SidebarMenu>
            {NAV_ITEMS.map((item) => {
              const Icon = item.icon;
              const active = isActive(item.to, item.match, pathname);
              return (
                <SidebarMenuItem key={item.to}>
                  <Link
                    to={item.to}
                    className="block"
                    aria-label={state === "collapsed" ? item.label : undefined}
                  >
                    <SidebarMenuButton
                      active={active}
                      icon={<Icon className="h-4 w-4" aria-hidden="true" />}
                      label={item.label}
                    />
                  </Link>
                </SidebarMenuItem>
              );
            })}
            <EmpresaSection pathname={pathname} />
          </SidebarMenu>
        </SidebarGroup>
      </SidebarContent>
    </Sidebar>
  );
}
