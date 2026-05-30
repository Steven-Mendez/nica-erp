// /invitations/accept — token-less route that supports three entry
// modes per the welcome-flow spec:
//
//   1. Hash-fragment, authenticated: `#t=<token>` is read on mount,
//      the hash is stripped via `history.replaceState`, then the
//      accept POST runs and the SPA navigates to `/dashboard`.
//   2. Hash-fragment, unauthenticated: the token is fetched via
//      `GET /v1/invitations/{token}/preview` so the user lands on
//      `/signup` with the email pre-filled and the token stashed in
//      `sessionStorage` under `nica-erp:pending-invite`. The signup
//      flow picks the stash back up on the post-login bootstrap.
//   3. No hash, authenticated: a paste input takes the token; submit
//      runs the same accept POST.
//
// Note: the spec also covers a fully inline signup-confirm-login
// path; that lift is staged separately. This route ships the stash
// variant which preserves the operator UX (one signup flow, one
// click after signup) without re-implementing /signup + /confirm
// in-place.

import { useEffect, useRef, useState } from "react";
import { Link, useNavigate } from "@tanstack/react-router";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { AuthLayout } from "@/features/auth/components/AuthLayout";
import { useAcceptInvitationMutation } from "@/features/tenants/api/hooks";
import { previewInvitation } from "@/features/tenants/api/endpoints";
import { getAccessToken } from "@/api/tokenStore";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

export const PENDING_INVITE_KEY = "nica-erp:pending-invite";

function readHashToken(): string | null {
  if (typeof window === "undefined") return null;
  const hash = window.location.hash;
  if (!hash.startsWith("#t=")) return null;
  const token = hash.slice(3);
  return token.length > 0 ? token : null;
}

function stripHash(): void {
  if (typeof window === "undefined") return;
  window.history.replaceState(null, "", window.location.pathname + window.location.search);
}

type Mode =
  | { kind: "loading" }
  | { kind: "joining"; token: string }
  | { kind: "paste" }
  | { kind: "preview-error"; message: string };

export function AcceptInvitationRoute() {
  useDocumentTitle("Aceptar invitación");
  const navigate = useNavigate();
  const acceptMut = useAcceptInvitationMutation();
  const [mode, setMode] = useState<Mode>({ kind: "loading" });
  const [pasted, setPasted] = useState("");
  const [pasteError, setPasteError] = useState<string | null>(null);
  // Capture the hash token synchronously at first render so React
  // StrictMode's double-invoke of the effect does not see an empty
  // hash on its second pass (the first pass strips it).
  const [initialToken] = useState<string | null>(() => readHashToken());
  const processedRef = useRef(false);

  // Mode resolution on mount: hash + auth → accept; hash + no auth →
  // preview + stash + /signup; no hash + auth → paste; no hash + no
  // auth → /login.
  useEffect(() => {
    if (processedRef.current) return;
    processedRef.current = true;

    const token = initialToken;
    const authed = getAccessToken() !== null;

    if (token !== null) {
      stripHash();
      if (authed) {
        setMode({ kind: "joining", token });
        acceptMut.mutate(token, {
          onSuccess: () => {
            void navigate({ to: "/dashboard" });
          },
        });
      } else {
        // Unauthenticated hash flow: preview to get the email, stash
        // the token, then route to /signup with the email pre-filled.
        previewInvitation(token).then(
          (preview) => {
            try {
              window.sessionStorage.setItem(PENDING_INVITE_KEY, token);
            } catch {
              // sessionStorage write can throw in private windows; the
              // signup flow will degrade to "no pre-filled token" but
              // the user can paste it back on /invitations/accept.
            }
            void navigate({ to: "/signup", search: { email: preview.email } });
          },
          (err: unknown) => {
            const message = err instanceof Error ? err.message : "No se pudo cargar la invitación.";
            setMode({ kind: "preview-error", message });
          },
        );
      }
      return;
    }

    // No hash: paste path requires auth.
    if (!authed) {
      void navigate({ to: "/login" });
      return;
    }
    setMode({ kind: "paste" });
    // Run once on mount — re-runs would re-strip the hash, etc.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const submitPasted = (): void => {
    const token = pasted.trim();
    if (token.length === 0) {
      setPasteError("Pega el código de invitación.");
      return;
    }
    setPasteError(null);
    acceptMut.mutate(token, {
      onSuccess: () => {
        void navigate({ to: "/dashboard" });
      },
    });
  };

  return (
    <AuthLayout>
      <Card>
        <CardHeader>
          <CardTitle>Aceptar invitación</CardTitle>
          <CardDescription>
            {mode.kind === "joining"
              ? "Uniéndote a la empresa..."
              : mode.kind === "paste"
                ? "Pega el código que recibiste por correo."
                : mode.kind === "preview-error"
                  ? "No se pudo validar la invitación."
                  : "Cargando..."}
          </CardDescription>
        </CardHeader>
        <CardContent className="space-y-4">
          {mode.kind === "loading" ? <Skeleton className="h-10 w-full" /> : null}

          {mode.kind === "joining" && acceptMut.isError ? (
            <Alert variant="destructive">
              <AlertDescription>{acceptMut.error.message}</AlertDescription>
            </Alert>
          ) : null}

          {mode.kind === "joining" && acceptMut.isPending ? (
            <p className="text-sm text-muted-foreground">Aceptando...</p>
          ) : null}

          {mode.kind === "paste" ? (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                submitPasted();
              }}
              className="space-y-3"
              noValidate
            >
              <FieldGroup>
                <Field>
                  <FieldLabel htmlFor="invite-token">Código de invitación</FieldLabel>
                  <Input
                    id="invite-token"
                    value={pasted}
                    onChange={(e) => setPasted(e.target.value)}
                    autoComplete="off"
                    spellCheck={false}
                  />
                  {pasteError !== null ? <FieldError>{pasteError}</FieldError> : null}
                </Field>
              </FieldGroup>
              {acceptMut.isError ? (
                <Alert variant="destructive">
                  <AlertDescription>{acceptMut.error.message}</AlertDescription>
                </Alert>
              ) : null}
              <Button type="submit" disabled={acceptMut.isPending} className="w-full">
                {acceptMut.isPending ? "Aceptando..." : "Aceptar invitación"}
              </Button>
            </form>
          ) : null}

          {mode.kind === "preview-error" ? (
            <>
              <Alert variant="destructive">
                <AlertDescription>{mode.message}</AlertDescription>
              </Alert>
              <Link
                to="/login"
                className={buttonVariants({ variant: "outline", className: "w-full" })}
              >
                Volver a iniciar sesión
              </Link>
            </>
          ) : null}
        </CardContent>
      </Card>
    </AuthLayout>
  );
}
