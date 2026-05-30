// Smoke test for /onboarding — verifies the two CTAs render and the
// paste-token flow calls acceptInvitation.
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { OnboardingRoute } from "@/routes/onboarding";

const acceptSpy = vi.fn();
vi.mock("@/features/tenants/api/hooks", () => ({
  useAcceptInvitationMutation: () => ({
    mutate: (token: string, opts?: { onSuccess?: () => void; onError?: (e: Error) => void }) => {
      acceptSpy(token);
      opts?.onSuccess?.();
    },
    isPending: false,
  }),
}));

vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual<object>("@tanstack/react-router");
  return {
    ...actual,
    useNavigate: () => () => undefined,
  };
});

function renderOnboarding() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <OnboardingRoute />
    </QueryClientProvider>,
  );
}

describe("OnboardingRoute", () => {
  it("renders both CTAs", () => {
    renderOnboarding();
    expect(screen.getByRole("button", { name: /Crear empresa/i })).toBeInTheDocument();
    expect(screen.getByLabelText(/Código de invitación/i)).toBeInTheDocument();
  });

  it("calls acceptInvitation when a token is pasted and submitted", async () => {
    renderOnboarding();
    fireEvent.change(screen.getByLabelText(/Código de invitación/i), {
      target: { value: "abc.def.ghi" },
    });
    fireEvent.click(screen.getByRole("button", { name: /Unirme/i }));
    await waitFor(() => expect(acceptSpy).toHaveBeenCalledWith("abc.def.ghi"));
  });
});
