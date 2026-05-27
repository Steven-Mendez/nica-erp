// apps/web/src/features/auth/components/AuthLayout.tsx
//
// Two-column split layout used by every auth route (login / signup / confirm /
// forgot / reset). Modeled on the shadcn `login-02` block: brand corner top-
// left, centred form in the left column, decorative panel on the right that
// collapses on mobile.

import { Link } from "@tanstack/react-router";
import type { ReactNode } from "react";

interface AuthLayoutProps {
  children: ReactNode;
}

export const AuthLayout = ({ children }: AuthLayoutProps) => {
  return (
    <div className="grid min-h-svh lg:grid-cols-2">
      <div className="flex flex-col gap-4 p-6 md:p-10">
        <div className="flex justify-center gap-2 md:justify-start">
          <Link to="/" className="flex items-center gap-2 font-medium">
            <div className="flex h-6 w-6 items-center justify-center rounded-md bg-primary text-primary-foreground">
              <span className="text-sm font-bold">N</span>
            </div>
            Nica ERP
          </Link>
        </div>
        <div className="flex flex-1 items-center justify-center">
          <div className="w-full max-w-xs">{children}</div>
        </div>
      </div>
      <div className="relative hidden lg:block bg-background">
        <div className="absolute inset-0 bg-gradient-to-tr from-primary via-primary/85 to-primary/60 dark:from-primary/25 dark:via-primary/60 dark:to-primary" />
        <div className="absolute inset-x-0 bottom-0 h-1/2 bg-gradient-to-t from-black/45 via-black/15 to-transparent" />
        <div className="absolute inset-0 flex flex-col justify-end p-10 text-primary-foreground">
          <blockquote className="space-y-2">
            <p className="text-lg italic">
              &ldquo;Pequeñas y medianas empresas de Nicaragua merecen un ERP serio, simple y
              accesible.&rdquo;
            </p>
            <footer className="text-sm opacity-80">— Nica ERP</footer>
          </blockquote>
        </div>
      </div>
    </div>
  );
};
