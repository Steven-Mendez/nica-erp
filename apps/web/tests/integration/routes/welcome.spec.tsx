// Smoke test for /welcome — verifies the form renders, locale is not
// exposed, and submitting calls PATCH /v1/me.
import { render, screen, fireEvent, waitFor } from "@testing-library/react";
import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { describe, expect, it, vi } from "vitest";
import { WelcomeRoute } from "@/routes/welcome";

const patchSpy = vi.fn();
vi.mock("@/features/auth/api/hooks", () => ({
  useUpdateMeMutation: () => ({
    mutate: (vars: unknown, opts?: { onSuccess?: () => void }) => {
      patchSpy(vars);
      opts?.onSuccess?.();
    },
    isPending: false,
    isError: false,
  }),
}));

vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual<object>("@tanstack/react-router");
  return {
    ...actual,
    useNavigate: () => () => undefined,
  };
});

function renderWelcome() {
  const qc = new QueryClient();
  return render(
    <QueryClientProvider client={qc}>
      <WelcomeRoute />
    </QueryClientProvider>,
  );
}

describe("WelcomeRoute", () => {
  it("renders display_name + timezone but never asks for locale", () => {
    renderWelcome();
    expect(screen.getByLabelText(/Nombre/i)).toBeInTheDocument();
    expect(screen.getByLabelText(/Zona horaria/i)).toBeInTheDocument();
    expect(screen.queryByLabelText(/locale/i)).toBeNull();
    expect(screen.queryByLabelText(/idioma/i)).toBeNull();
  });

  it("submits display_name + timezone via PATCH /v1/me", async () => {
    renderWelcome();
    fireEvent.change(screen.getByLabelText(/Nombre/i), { target: { value: "Ada Lovelace" } });
    fireEvent.submit(screen.getByRole("button", { name: /Continuar/i }).closest("form")!);
    await waitFor(() => expect(patchSpy).toHaveBeenCalled());
    const payload = patchSpy.mock.calls.at(-1)?.[0] as { display_name?: string };
    expect(payload?.display_name).toBe("Ada Lovelace");
  });
});
