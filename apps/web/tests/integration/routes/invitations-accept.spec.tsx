// Integration spec for /invitations/accept (hash-token entry point).
//
// The route has three entry modes (hash+auth, hash+no-auth, no-hash+auth)
// plus paste + error branches. The accept POST is now driven by a
// module-scoped in-flight dedup (so a mid-flight remount during the
// stash flow does not lose the response) instead of useMutation; the
// tests mock `acceptInvitation` directly and assert against the
// rendered "joining" UI + the navigation that fires when the promise
// resolves.

import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const {
  navigateSpy,
  acceptInvitationMock,
  getAccessTokenMock,
  getRefreshTokenMock,
  setTokensMock,
  previewInvitationMock,
} = vi.hoisted(() => ({
  navigateSpy: vi.fn(),
  acceptInvitationMock: vi.fn(),
  getAccessTokenMock: vi.fn(),
  getRefreshTokenMock: vi.fn(),
  setTokensMock: vi.fn(),
  previewInvitationMock: vi.fn(),
}));

vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual<object>("@tanstack/react-router");
  return {
    ...actual,
    useNavigate: () => navigateSpy,
    Link: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  };
});

vi.mock("@/api/tokenStore", () => ({
  getAccessToken: getAccessTokenMock,
  getRefreshToken: getRefreshTokenMock,
  setTokens: setTokensMock,
}));

vi.mock("@/features/tenants/api/endpoints", () => ({
  acceptInvitation: acceptInvitationMock,
  previewInvitation: previewInvitationMock,
}));

// setPickerConfirmed is a side-effect on sessionStorage; stub to avoid
// coupling these tests to its internals.
vi.mock("@/lib/route-guard", () => ({
  setPickerConfirmed: vi.fn(),
}));

import { AcceptInvitationRoute } from "@/routes/invitations/accept";

function renderAccept() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <AcceptInvitationRoute />
    </QueryClientProvider>,
  );
}

/**
 * Build a controllable Promise for `acceptInvitation` so tests can hold
 * the in-flight state, resolve it, or reject it on demand.
 */
function deferredAccept() {
  let resolve!: (value: { tenant_id: string; role: "accountant" }) => void;
  let reject!: (reason: unknown) => void;
  const promise = new Promise<{ tenant_id: string; role: "accountant" }>((res, rej) => {
    resolve = res;
    reject = rej;
  });
  acceptInvitationMock.mockReturnValueOnce(promise);
  return { promise, resolve, reject };
}

beforeEach(() => {
  navigateSpy.mockReset();
  acceptInvitationMock.mockReset();
  getAccessTokenMock.mockReset();
  getRefreshTokenMock.mockReset();
  setTokensMock.mockReset();
  previewInvitationMock.mockReset();
  // Default: authenticated paste user without a hash token.
  getAccessTokenMock.mockReturnValue("access.jwt");
  getRefreshTokenMock.mockReturnValue("refresh.jwt");
  window.location.hash = "";
});

afterEach(() => {
  cleanup();
  window.location.hash = "";
});

describe("AcceptInvitationRoute — paste branch (no hash, authenticated)", () => {
  it("renders the paste-input form when no hash token is present", () => {
    renderAccept();
    expect(
      screen.getByRole("heading", { name: /Aceptar invitación|Invitación/i }),
    ).toBeInTheDocument();
    expect(screen.getByLabelText(/Código de invitación/i)).toBeInTheDocument();
  });

  it("calls acceptInvitation with the pasted token on submit", async () => {
    deferredAccept();
    renderAccept();
    fireEvent.change(screen.getByLabelText(/Código de invitación/i), {
      target: { value: "inv-token-paste" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Aceptar invitación/i }));
    await waitFor(() => {
      expect(acceptInvitationMock).toHaveBeenCalledWith("inv-token-paste", "refresh.jwt");
    });
    // Navigation does not fire until the promise resolves.
    expect(navigateSpy).not.toHaveBeenCalled();
  });

  it("navigates to /dashboard once the accept promise resolves", async () => {
    const { resolve } = deferredAccept();
    renderAccept();
    fireEvent.change(screen.getByLabelText(/Código de invitación/i), {
      target: { value: "happy-token" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Aceptar invitación/i }));
    resolve({ tenant_id: "t-1", role: "accountant" });
    await waitFor(() => {
      expect(navigateSpy).toHaveBeenCalledWith({ to: "/dashboard" });
    });
    expect(navigateSpy).toHaveBeenCalledTimes(1);
  });

  it("shows an inline validation error when submit is fired with empty input", () => {
    renderAccept();
    fireEvent.click(screen.getByRole("button", { name: /Aceptar invitación/i }));
    expect(screen.getByText("Pega el código de invitación.")).toBeInTheDocument();
    expect(acceptInvitationMock).not.toHaveBeenCalled();
  });

  it("renders the destructive alert when the accept promise rejects", async () => {
    const { reject } = deferredAccept();
    renderAccept();
    fireEvent.change(screen.getByLabelText(/Código de invitación/i), {
      target: { value: "expired-token" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Aceptar invitación/i }));
    reject(new Error("Invitación inválida o expirada."));
    await waitFor(() => {
      expect(screen.getByText("Invitación inválida o expirada.")).toBeInTheDocument();
    });
    expect(navigateSpy).not.toHaveBeenCalled();
  });
});

describe("AcceptInvitationRoute — hash branch (unauthenticated, invalid token)", () => {
  beforeEach(() => {
    window.location.hash = "#t=opaque-token";
    getAccessTokenMock.mockReturnValue(null);
  });

  it("shows the preview-error fallback when previewInvitation rejects", async () => {
    previewInvitationMock.mockRejectedValueOnce(new Error("Invitación inválida o expirada."));
    renderAccept();
    await waitFor(() => {
      expect(screen.getByText("Invitación inválida o expirada.")).toBeInTheDocument();
    });
    // The hash must be stripped on mount so a refresh does not re-trigger.
    expect(window.location.hash).toBe("");
    // No accept attempt fires when the user is unauthenticated.
    expect(acceptInvitationMock).not.toHaveBeenCalled();
  });

  it("falls back to a generic message when preview rejects with a non-Error value", async () => {
    previewInvitationMock.mockRejectedValueOnce("plain-string-err");
    renderAccept();
    await waitFor(() => {
      expect(screen.getByText("No se pudo cargar la invitación.")).toBeInTheDocument();
    });
  });
});
