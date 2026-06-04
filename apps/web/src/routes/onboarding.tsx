// apps/web/src/routes/onboarding.tsx
//
// Shown to authenticated users with zero memberships. Two CTAs:
//
//   1. Crear empresa  → routes to the tenant-create wizard.
//   2. Tengo invitación → input to paste an invitation token.
//
// The paste-token flow lives inline; when the user submits the
// token the SPA POSTs to /v1/invitations/accept with the token in
// the body (per ADR-0031).

import { useNavigate } from "@tanstack/react-router";
import { useState } from "react";
import { ArrowRight } from "lucide-react";
import { Logo } from "@/components/logo";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { useAcceptInvitationMutation } from "@/features/tenants/api/hooks";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

export function OnboardingRoute() {
  useDocumentTitle("Comenzar");
  const navigate = useNavigate();
  const [token, setToken] = useState("");
  const [tokenError, setTokenError] = useState<string | null>(null);
  const acceptMut = useAcceptInvitationMutation();

  const handleAccept = (e: React.FormEvent<HTMLFormElement>): void => {
    e.preventDefault();
    setTokenError(null);
    const trimmed = token.trim();
    if (trimmed.length === 0) {
      setTokenError("Pega el código de invitación que recibiste por correo.");
      return;
    }
    acceptMut.mutate(trimmed, {
      onSuccess: () => {
        void navigate({ to: "/" });
      },
      onError: (err) => {
        setTokenError(err.message ?? "Código inválido o expirado.");
      },
    });
  };

  return (
    <div className="flex min-h-screen items-center justify-center bg-background px-4 py-12">
      <div className="w-full max-w-md space-y-8">
        <div className="flex flex-col items-center text-center">
          <Logo size={32} withWordmark className="font-medium" />
          <h1 className="mt-6 text-2xl font-semibold tracking-tight">Crea tu primera empresa</h1>
          <p className="mt-2 text-sm text-muted-foreground">Empecemos por crear tu empresa.</p>
        </div>

        <Button
          type="button"
          className="w-full"
          size="lg"
          onClick={() => void navigate({ to: "/tenants/new" })}
        >
          Crear empresa
          <ArrowRight className="ml-2 h-4 w-4" />
        </Button>

        <div className="relative">
          <div className="absolute inset-0 flex items-center" aria-hidden="true">
            <div className="w-full border-t border-border" />
          </div>
          <div className="relative flex justify-center">
            <span className="bg-background px-3 text-xs uppercase tracking-wide text-muted-foreground">
              o si te invitaron
            </span>
          </div>
        </div>

        <div className="space-y-3">
          <div className="space-y-1 text-center">
            <h2 className="text-sm font-semibold">¿Tienes un código de invitación?</h2>
            <p className="text-xs text-muted-foreground">
              Pega el código que te enviaron para unirte a una empresa existente.
            </p>
          </div>
          <form onSubmit={handleAccept} className="space-y-3">
            <div className="flex gap-2">
              <Input
                value={token}
                onChange={(e) => setToken(e.target.value)}
                placeholder="Pega tu código"
                aria-label="Código de invitación"
                autoComplete="off"
                className="flex-1"
              />
              <Button type="submit" variant="secondary" disabled={acceptMut.isPending}>
                {acceptMut.isPending ? "Validando..." : "Unirme"}
              </Button>
            </div>
            {tokenError ? (
              <Alert variant="destructive">
                <AlertDescription>{tokenError}</AlertDescription>
              </Alert>
            ) : null}
          </form>
        </div>
      </div>
    </div>
  );
}
