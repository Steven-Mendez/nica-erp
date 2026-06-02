import { useRouterState } from "@tanstack/react-router";
import { Menu } from "lucide-react";
import { Button } from "@/components/ui/button";
import { Separator } from "@/components/ui/separator";
import { AccountMenu } from "@/components/account-menu";
import { ThemeToggle } from "@/components/theme-toggle";
import { useSidebar } from "@/components/app-sidebar/sidebar-context";
import { SIDEBAR_ROOT_ID } from "@/components/app-sidebar/sidebar";

type Crumb = { label: string; href: string };

const STATIC_LABELS: Record<string, string> = {
  dashboard: "Resumen",
  sales: "Ventas",
  inventory: "Inventario",
  reports: "Reportes",
  settings: "Configuración",
  tenants: "Empresas",
  account: "Cuenta",
  members: "Miembros",
  new: "Nueva",
  invitations: "Invitaciones",
  accept: "Aceptar",
  users: "Usuarios",
  empresa: "Empresa",
};

function titleize(segment: string): string {
  const known = STATIC_LABELS[segment];
  if (known !== undefined) return known;
  if (segment.length === 0) return "";
  return segment.charAt(0).toUpperCase() + segment.slice(1);
}

function buildBreadcrumbs(pathname: string): Crumb[] {
  const segments = pathname.split("/").filter((s) => s.length > 0);
  const crumbs: Crumb[] = [];
  let acc = "";
  for (const segment of segments) {
    acc = `${acc}/${segment}`;
    crumbs.push({ label: titleize(segment), href: acc });
  }
  return crumbs;
}

export function SiteHeader() {
  const { toggleMobile, toggle, state, mobileOpen } = useSidebar();
  const routerState = useRouterState({ select: (s) => ({ pathname: s.location.pathname }) });
  const crumbs = buildBreadcrumbs(routerState.pathname);

  return (
    <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center gap-2 border-b bg-background/95 px-3 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <Button
        variant="ghost"
        size="icon"
        className="md:hidden"
        aria-controls={SIDEBAR_ROOT_ID}
        aria-expanded={mobileOpen}
        aria-label={mobileOpen ? "Cerrar menú" : "Abrir menú"}
        onClick={toggleMobile}
      >
        <Menu className="h-4 w-4" aria-hidden="true" />
      </Button>
      <Button
        variant="ghost"
        size="icon"
        className="hidden md:inline-flex"
        aria-label={state === "expanded" ? "Contraer barra lateral" : "Expandir barra lateral"}
        onClick={toggle}
      >
        <Menu className="h-4 w-4" aria-hidden="true" />
      </Button>
      <Separator orientation="vertical" className="mx-1 h-5" />
      <nav
        aria-label="Ruta de navegación"
        className="flex min-w-0 flex-1 items-center gap-1 text-sm"
      >
        {crumbs.length === 0 ? (
          <span className="text-muted-foreground">Inicio</span>
        ) : (
          crumbs.map((crumb, idx) => (
            <span key={crumb.href} className="flex min-w-0 items-center gap-1">
              {idx > 0 ? <span className="text-muted-foreground">/</span> : null}
              <span
                className={
                  idx === crumbs.length - 1
                    ? "truncate font-medium"
                    : "truncate text-muted-foreground"
                }
              >
                {crumb.label}
              </span>
            </span>
          ))
        )}
      </nav>
      <ThemeToggle />
      <AccountMenu />
    </header>
  );
}
