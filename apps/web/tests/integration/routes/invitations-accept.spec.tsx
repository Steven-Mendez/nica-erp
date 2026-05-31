// Integration spec for /invitations/accept (hash-token entry point).
//
// The route has three entry modes (hash+auth, hash+no-auth, no-hash+auth)
// plus paste + error branches. The original spec only drove the no-hash
// happy paste path; this file extends coverage to the failing-preview
// branch (token inválido/expirado) and the explicit accept-error branch
// the user hits when the backend rejects a valid-looking token (e.g. they
// are already authenticated against a different empresa).

import {
  cleanup,
  fireEvent,
  render,
  screen,
  waitFor,
} from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

const {
  navigateSpy,
  acceptSpy,
  useAcceptInvitationMock,
  getAccessTokenMock,
  previewInvitationMock,
} = vi.hoisted(() => ({
  navigateSpy: vi.fn(),
  acceptSpy: vi.fn(),
  useAcceptInvitationMock: vi.fn(),
  getAccessTokenMock: vi.fn(),
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
}));

vi.mock("@/features/tenants/api/hooks", () => ({
  useAcceptInvitationMutation: useAcceptInvitationMock,
}));

vi.mock("@/features/tenants/api/endpoints", () => ({
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

interface MutationOverrides {
  outcome?: "success" | "error";
  errorMessage?: string;
  isError?: boolean;
  isPending?: boolean;
}

function installAcceptMutation(overrides: MutationOverrides = {}) {
  const {
    outcome = "success",
    errorMessage = "boom",
    isError = false,
    isPending = false,
  } = overrides;
  const error = new Error(errorMessage);
  useAcceptInvitationMock.mockReturnValue({
    mutate: (
      token: string,
      opts?: { onSuccess?: () => void; onError?: (err: unknown) => void },
    ) => {
      acceptSpy(token);
      if (outcome === "success") opts?.onSuccess?.();
      else opts?.onError?.(error);
    },
    isPending,
    isError,
    error: isError ? error : null,
  });
}

beforeEach(() => {
  navigateSpy.mockReset();
  acceptSpy.mockReset();
  useAcceptInvitationMock.mockReset();
  getAccessTokenMock.mockReset();
  previewInvitationMock.mockReset();
  // Default: authenticated paste user without a hash token.
  getAccessTokenMock.mockReturnValue("access.jwt");
  window.location.hash = "";
  installAcceptMutation();
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

  it("submits the pasted token via useAcceptInvitationMutation", async () => {
    renderAccept();
    fireEvent.change(screen.getByLabelText(/Código de invitación/i), {
      target: { value: "inv-token-paste" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: /Aceptar invitación/i }),
    );
    await waitFor(() => {
      expect(acceptSpy).toHaveBeenCalledWith("inv-token-paste");
    });
    expect(navigateSpy).toHaveBeenCalledWith({ to: "/dashboard" });
  });

  it("shows an inline validation error when submit is fired with empty input", () => {
    renderAccept();
    fireEvent.click(
      screen.getByRole("button", { name: /Aceptar invitación/i }),
    );
    expect(screen.getByText("Pega el código de invitación.")).toBeInTheDocument();
    expect(acceptSpy).not.toHaveBeenCalled();
  });

  it("renders the accept-mutation error alert when the backend rejects the token", () => {
    installAcceptMutation({
      outcome: "error",
      isError: true,
      errorMessage: "Invitación inválida o expirada.",
    });
    renderAccept();
    fireEvent.change(screen.getByLabelText(/Código de invitación/i), {
      target: { value: "expired-token" },
    });
    fireEvent.click(
      screen.getByRole("button", { name: /Aceptar invitación/i }),
    );
    expect(
      screen.getByText("Invitación inválida o expirada."),
    ).toBeInTheDocument();
    // No navigation happens on error.
    expect(navigateSpy).not.toHaveBeenCalled();
  });
});

describe("AcceptInvitationRoute — hash branch (unauthenticated, invalid token)", () => {
  beforeEach(() => {
    window.location.hash = "#t=opaque-token";
    getAccessTokenMock.mockReturnValue(null);
  });

  it("shows the preview-error fallback when previewInvitation rejects", async () => {
    previewInvitationMock.mockRejectedValueOnce(
      new Error("Invitación inválida o expirada."),
    );
    renderAccept();
    await waitFor(() => {
      expect(
        screen.getByText("Invitación inválida o expirada."),
      ).toBeInTheDocument();
    });
    // The hash must be stripped on mount so a refresh does not re-trigger.
    expect(window.location.hash).toBe("");
    // No accept attempt fires when the user is unauthenticated.
    expect(acceptSpy).not.toHaveBeenCalled();
  });

  it("falls back to a generic message when preview rejects with a non-Error value", async () => {
    previewInvitationMock.mockRejectedValueOnce("plain-string-err");
    renderAccept();
    await waitFor(() => {
      expect(
        screen.getByText("No se pudo cargar la invitación."),
      ).toBeInTheDocument();
    });
  });
});
