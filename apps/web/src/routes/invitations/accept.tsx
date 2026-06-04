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
import { useQueryClient } from "@tanstack/react-query";
import { Link, useNavigate } from "@tanstack/react-router";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button, buttonVariants } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { Skeleton } from "@/components/ui/skeleton";
import { AuthLayout } from "@/features/auth/components/AuthLayout";
import { meQueryKey } from "@/api/queryKeys";
import { myTenantsKey } from "@/features/tenants/api/hooks";
import {
  acceptInvitation,
  previewInvitation,
  ApiError,
  type AcceptInvitationResult,
} from "@/features/tenants/api/endpoints";
import { messageForProblem, type ProblemDetail } from "@/api/errors";
import { useLogoutMutation } from "@/features/auth/api/hooks";
import { getAccessToken, setTokens } from "@/api/tokenStore";
import { setPickerConfirmed } from "@/lib/route-guard";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

export const PENDING_INVITE_KEY = "nica-erp:pending-invite";

// In-flight accept dedup. The stash flow remounts this route several
// times in quick succession (auth shell + router transitions), and a
// component-bound `useMutation` loses its observer on every unmount,
// leaving the user stuck on "Aceptando…" even though the POST succeeded
// server-side. Holding the in-flight promise at module scope keyed by
// token means a remount picks up the SAME promise instead of starting
// a new request — the result lands wherever the route happens to be
// mounted next.
type AcceptStatus =
  | { kind: "idle" }
  | { kind: "pending" }
  | { kind: "success"; result: AcceptInvitationResult }
  | { kind: "error"; error: unknown };

interface InflightEntry {
  status: AcceptStatus;
  listeners: Set<(s: AcceptStatus) => void>;
}

const inflight = new Map<string, InflightEntry>();

function acceptErrorMessage(error: unknown): string {
  if (error instanceof ApiError) return messageForProblem(error);
  if (error instanceof Error) return error.message;
  return "No se pudo aceptar la invitación.";
}

function getProblemCode(error: unknown): string | undefined {
  if (error instanceof ApiError) {
    const detail = error.detail as ProblemDetail | undefined;
    return detail?.code;
  }
  return undefined;
}

function ensureAccept(token: string): InflightEntry {
  const existing = inflight.get(token);
  if (existing !== undefined) return existing;
  const entry: InflightEntry = {
    status: { kind: "pending" },
    listeners: new Set(),
  };
  inflight.set(token, entry);
  const fire = (next: AcceptStatus): void => {
    entry.status = next;
    for (const l of entry.listeners) l(next);
  };
  // The server reads the refresh token from the `nica_erp_rt`
  // httpOnly cookie (shipped via `credentials: include`) and rotates
  // the session if this is the user's first membership. The returned
  // `tokens` field is non-null only in that case; veteran users get
  // `tokens=null` and keep their current empresa.
  void acceptInvitation(token).then(
    (result) => fire({ kind: "success", result }),
    (error: unknown) => fire({ kind: "error", error }),
  );
  return entry;
}

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
  const qc = useQueryClient();
  const logoutMutation = useLogoutMutation();
  const [mode, setMode] = useState<Mode>({ kind: "loading" });
  const [pasted, setPasted] = useState("");
  const [pasteError, setPasteError] = useState<string | null>(null);
  const [acceptStatus, setAcceptStatus] = useState<AcceptStatus>({
    kind: "idle",
  });
  // Capture the hash token synchronously at first render so React
  // StrictMode's double-invoke of the effect does not see an empty
  // hash on its second pass (the first pass strips it).
  const [initialToken] = useState<string | null>(() => readHashToken());
  const processedRef = useRef(false);

  // Subscribe to whatever in-flight accept exists for the active
  // token, restoring the result if the route gets remounted mid-
  // request (the stash flow remounts this component several times
  // before the POST settles).
  const activeToken = mode.kind === "joining" ? mode.token : null;
  useEffect(() => {
    if (activeToken === null) return;
    const entry = inflight.get(activeToken);
    if (entry === undefined) return;
    setAcceptStatus(entry.status);
    const listener = (next: AcceptStatus): void => setAcceptStatus(next);
    entry.listeners.add(listener);
    return () => {
      entry.listeners.delete(listener);
    };
  }, [activeToken]);

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
        // Kick off (or attach to) the module-scoped in-flight accept
        // for this token. The result lands on `acceptStatus` via the
        // subscription effect above, so a mid-flight unmount does
        // not lose it.
        ensureAccept(token);
      } else {
        // Unauthenticated hash flow: validate the token via preview,
        // stash it, then route to /signup. Audit F-026: the preview
        // intentionally does NOT include the invitee email, so the
        // user types their own email — the backend's identity binding
        // catches typos before any membership row is created.
        previewInvitation(token).then(
          () => {
            try {
              window.sessionStorage.setItem(PENDING_INVITE_KEY, token);
            } catch {
              // sessionStorage write can throw in private windows; the
              // signup flow will degrade to "no pre-filled token" but
              // the user can paste it back on /invitations/accept.
            }
            void navigate({ to: "/signup", search: {} });
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
    setMode({ kind: "joining", token });
    ensureAccept(token);
  };

  // Single source of truth for the "accept succeeded → land in the
  // empresa" side effect. Hooks into the module-scoped status so the
  // navigation fires exactly once when the result arrives, regardless
  // of how many times the component has been mounted in between.
  useEffect(() => {
    if (acceptStatus.kind !== "success") return;
    // First-membership invitees receive rotated tokens with the new
    // `active_tenant` claim baked in. Store them BEFORE invalidating
    // /me so the refetch hits the API with the new bearer and reads
    // back the freshly-set empresa, not the stale "no active tenant"
    // shape.
    const tokens = acceptStatus.result.tokens;
    if (tokens != null) {
      setTokens({
        access: tokens.access_token,
        id: tokens.id_token,
      });
    }
    // Accepting (via deep link or paste) is an explicit empresa pick
    // — the operator confirmed they want THIS empresa. Set the
    // picker-confirmed flag so the route guard does not bounce them
    // to /tenants on the next render.
    setPickerConfirmed();
    void qc.invalidateQueries({ queryKey: myTenantsKey });
    void qc.invalidateQueries({ queryKey: meQueryKey });
    // Drop the in-flight entry once the result has been consumed so
    // a second invitation in the same browser session starts fresh.
    if (activeToken !== null) inflight.delete(activeToken);
    void navigate({ to: "/dashboard" });
  }, [acceptStatus, activeToken, navigate, qc]);

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

          {mode.kind === "joining" && acceptStatus.kind === "error" ? (
            <>
              <Alert variant="destructive">
                <AlertDescription>{acceptErrorMessage(acceptStatus.error)}</AlertDescription>
              </Alert>
              {getProblemCode(acceptStatus.error) === "invitation.identity_mismatch" &&
              mode.kind === "joining" ? (
                <Button
                  type="button"
                  variant="outline"
                  className="w-full"
                  disabled={logoutMutation.isPending}
                  onClick={() => {
                    const token = mode.kind === "joining" ? mode.token : null;
                    if (token !== null) {
                      try {
                        window.sessionStorage.setItem(PENDING_INVITE_KEY, token);
                      } catch {
                        // sessionStorage may be unavailable in private windows;
                        // the user can paste the token after signing in.
                      }
                    }
                    logoutMutation.mutate(undefined, {
                      onSettled: () => {
                        void navigate({ to: "/login" });
                      },
                    });
                  }}
                >
                  {logoutMutation.isPending
                    ? "Cerrando sesión..."
                    : "Cerrar sesión y volver a esta invitación"}
                </Button>
              ) : null}
            </>
          ) : null}

          {mode.kind === "joining" && acceptStatus.kind === "pending" ? (
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
              {acceptStatus.kind === "error" ? (
                <Alert variant="destructive">
                  <AlertDescription>{acceptErrorMessage(acceptStatus.error)}</AlertDescription>
                </Alert>
              ) : null}
              <Button type="submit" disabled={acceptStatus.kind === "pending"} className="w-full">
                {acceptStatus.kind === "pending" ? "Aceptando..." : "Aceptar invitación"}
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
