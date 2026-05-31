import type { ReactNode } from "react";
import { Link } from "@tanstack/react-router";
import { AccountMenu } from "@/components/account-menu";
import { Logo } from "@/components/logo";
import { ThemeToggle } from "@/components/theme-toggle";

export function BrandHeader() {
  return (
    <header className="sticky top-0 z-20 flex h-14 shrink-0 items-center justify-between gap-2 border-b bg-background/95 px-4 backdrop-blur supports-[backdrop-filter]:bg-background/80">
      <Link
        to="/tenants"
        className="inline-flex items-center gap-2 focus:outline-hidden focus-visible:ring-2 focus-visible:ring-ring rounded-md"
        aria-label="Ir a tus empresas"
      >
        <Logo size={28} withWordmark />
      </Link>
      <div className="flex items-center gap-1">
        <ThemeToggle />
        <AccountMenu />
      </div>
    </header>
  );
}

export function BrandLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen w-full flex-col bg-background">
      <BrandHeader />
      <main className="flex-1">{children}</main>
    </div>
  );
}
