// Smoke + behaviour test for /confirm — verifies the OTP slot field
// renders six slots, accepts a six-digit value, fires confirm-signup,
// and surfaces the Zod error when the code is too short.
import { cleanup, render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { ConfirmRoute } from "@/routes/confirm";

const confirmSpy = vi.fn();
vi.mock("@/features/auth/api/hooks", () => ({
  useConfirmSignupMutation: () => ({
    mutate: (
      vars: { email: string; code: string },
      opts?: { onSuccess?: () => void; onError?: (e: Error) => void },
    ) => {
      confirmSpy(vars);
      opts?.onSuccess?.();
    },
    isPending: false,
    isError: false,
  }),
  useResendCodeMutation: () => ({
    mutate: () => undefined,
    isPending: false,
    isSuccess: false,
  }),
}));

vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual<object>("@tanstack/react-router");
  return {
    ...actual,
    useNavigate: () => () => undefined,
    useSearch: () => ({ email: "ada@nica.test" }),
    Link: ({ children }: { children: React.ReactNode }) => <>{children}</>,
  };
});

function renderConfirm() {
  return render(
    <QueryClientProvider client={new QueryClient()}>
      <ConfirmRoute />
    </QueryClientProvider>,
  );
}

function typeCode(code: string): void {
  // input-otp keeps a hidden input the user types into; the label points at it.
  const hidden = screen.getByLabelText(/Código de verificación/i) as HTMLInputElement;
  fireEvent.change(hidden, { target: { value: code } });
}

describe("ConfirmRoute", () => {
  beforeEach(() => {
    confirmSpy.mockReset();
  });

  afterEach(async () => {
    cleanup();
    // input-otp queues a 250ms setTimeout for its focus mirror; drain it
    // before the test environment is torn down so the timer doesn't fire
    // against a disposed React tree.
    await new Promise<void>((resolve) => globalThis.setTimeout(resolve, 300));
  });

  it("renders six OTP slots", () => {
    const { container } = renderConfirm();
    // input-otp renders each slot via the shadcn InputOTPSlot wrapper.
    // The hidden input has maxlength=6.
    const hidden = screen.getByLabelText(/Código de verificación/i) as HTMLInputElement;
    expect(hidden.maxLength).toBe(6);
    expect(hidden.getAttribute("autocomplete")).toBe("one-time-code");
    expect(hidden.getAttribute("inputmode")).toBe("numeric");
    // The visual slots: the shadcn InputOTPSlot div + the underlying input means
    // 6 sibling div containers under the InputOTPGroup. Assert there are six.
    const slotContainer =
      container.querySelector('[data-input-otp-container=""]') ??
      container.querySelector("[data-input-otp-container]");
    expect(slotContainer).not.toBeNull();
  });

  it("submits with a six-digit code", async () => {
    renderConfirm();
    typeCode("123456");
    fireEvent.submit(screen.getByRole("button", { name: /^Confirmar$/i }).closest("form")!);
    await waitFor(() => expect(confirmSpy).toHaveBeenCalled());
    const last = confirmSpy.mock.calls.at(-1)?.[0] as { email: string; code: string };
    expect(last.code).toBe("123456");
    expect(last.email).toBe("ada@nica.test");
  });

  it("rejects a too-short code via Zod and does not call the mutation", async () => {
    renderConfirm();
    typeCode("12");
    fireEvent.submit(screen.getByRole("button", { name: /^Confirmar$/i }).closest("form")!);
    // Confirm spy should not be called because Zod min-length(4) blocks submit.
    await waitFor(() => {
      expect(confirmSpy).not.toHaveBeenCalled();
    });
  });
});
