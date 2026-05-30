import { useEffect, type ReactNode } from "react";
import { useRouterState } from "@tanstack/react-router";
import { AppSidebar } from "@/components/app-sidebar/app-sidebar";
import { SidebarInset } from "@/components/app-sidebar/sidebar";
import { SidebarProvider } from "@/components/app-sidebar/sidebar-context";
import { SiteHeader } from "./site-header";

const LAST_APP_ROUTE_KEY = "nica-erp:last-app-route";

export function AppShell({ children }: { children: ReactNode }) {
  const routerState = useRouterState({ select: (s) => ({ pathname: s.location.pathname }) });
  const pathname = routerState.pathname;

  // Remember the last in-app route the operator was on so the
  // /account `← Volver` link can return them here.
  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.sessionStorage.setItem(LAST_APP_ROUTE_KEY, pathname);
    } catch {
      // ignore
    }
  }, [pathname]);

  return (
    <SidebarProvider>
      <div className="flex min-h-screen w-full bg-background">
        <AppSidebar />
        <SidebarInset>
          <SiteHeader />
          <main className="flex-1 p-4 md:p-6">{children}</main>
        </SidebarInset>
      </div>
    </SidebarProvider>
  );
}
