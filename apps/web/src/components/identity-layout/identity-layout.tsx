// Thin chrome for identity-scoped routes (e.g. /account). The
// dashboard's full sidebar would imply "you are inside an empresa",
// but the account scope is *user*-scoped, so we render only a
// minimal top bar with a `← Volver` link on the left and the
// `TenantSwitcher` chip on the right.

import type { ReactNode } from "react";
import { useNavigate } from "@tanstack/react-router";
import { TenantSwitcher } from "@/components/app-sidebar/tenant-switcher";
import { SidebarProvider } from "@/components/app-sidebar/sidebar-context";

const LAST_APP_ROUTE_KEY = "nica-erp:last-app-route";

function readLastAppRoute(): string {
  if (typeof window === "undefined") return "/dashboard";
  try {
    return window.sessionStorage.getItem(LAST_APP_ROUTE_KEY) ?? "/dashboard";
  } catch {
    return "/dashboard";
  }
}

export function IdentityLayout({ children }: { children: ReactNode }) {
  const navigate = useNavigate();
  const goBack = (): void => {
    const target = readLastAppRoute();
    void navigate({ to: target as "/dashboard" });
  };

  // TenantSwitcher hits useSidebar; wrap in a SidebarProvider so the
  // chip can render without an AppShell parent.
  return (
    <SidebarProvider>
      <div className="flex min-h-screen w-full flex-col bg-background">
        <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center justify-between gap-2 border-b bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/80">
          <button
            type="button"
            onClick={goBack}
            className="text-sm text-muted-foreground hover:text-foreground"
            data-testid="identity-back-link"
          >
            ← Volver
          </button>
          <div className="w-64 max-w-[18rem]">
            <TenantSwitcher />
          </div>
        </header>
        <main className="flex-1 p-4 md:p-6">{children}</main>
      </div>
    </SidebarProvider>
  );
}

export { LAST_APP_ROUTE_KEY };
