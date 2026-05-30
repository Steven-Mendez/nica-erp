// Integration test for AccountMenu — verifies that selecting "Cerrar
// sesión" runs the logout mutation AND navigates to /login on settle,
// so the user does not stay stranded on a now-unauthenticated page
// (regression: clicking logout required a manual F5 to redirect).
//
// We mock the Radix DropdownMenu primitives so the items render
// inline — Radix needs real pointer events to open, which jsdom does
// not deliver. The behaviour under test is the onSelect handler, not
// the dropdown's own open/close machinery.
import { cleanup, fireEvent, render, screen, waitFor } from "@testing-library/react";
import type { ReactNode } from "react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { AccountMenu } from "@/components/account-menu";

const navigateMock = vi.fn();
const logoutMutateMock = vi.fn();

vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual<object>("@tanstack/react-router");
  return {
    ...actual,
    useNavigate: () => navigateMock,
    Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
      <a href={to}>{children}</a>
    ),
  };
});

vi.mock("@/features/auth/api/hooks", () => ({
  useMeQuery: () => ({
    data: {
      id: "u-1",
      email: "ada@nica.test",
      display_name: "Ada Lovelace",
      preferences: {},
      active_tenant: null,
      role: null,
      permissions: [],
    },
    isLoading: false,
    isError: false,
  }),
  useLogoutMutation: () => ({ mutate: logoutMutateMock, isPending: false }),
}));

vi.mock("@/components/ui/dropdown-menu", () => {
  type ChildProps = { children?: ReactNode };
  type ItemProps = ChildProps & {
    onSelect?: (event: { preventDefault: () => void }) => void;
    asChild?: boolean;
    disabled?: boolean;
    className?: string;
  };
  return {
    DropdownMenu: ({ children }: ChildProps) => <div>{children}</div>,
    DropdownMenuTrigger: ({ children }: ChildProps) => <div>{children}</div>,
    DropdownMenuContent: ({ children }: ChildProps) => <div>{children}</div>,
    DropdownMenuLabel: ({ children }: ChildProps) => <div>{children}</div>,
    DropdownMenuSeparator: () => <hr />,
    DropdownMenuItem: ({ children, onSelect, disabled }: ItemProps) => (
      <button
        type="button"
        disabled={disabled}
        onClick={() => onSelect?.({ preventDefault: () => undefined })}
      >
        {children}
      </button>
    ),
  };
});

afterEach(() => {
  cleanup();
  navigateMock.mockReset();
  logoutMutateMock.mockReset();
});

describe("AccountMenu", () => {
  it("fires the logout mutation and navigates to /login when onSettled runs", async () => {
    logoutMutateMock.mockImplementation((_input: unknown, opts?: { onSettled?: () => void }) => {
      opts?.onSettled?.();
    });

    render(<AccountMenu />);

    fireEvent.click(screen.getByRole("button", { name: /Cerrar sesión/i }));

    expect(logoutMutateMock).toHaveBeenCalledTimes(1);
    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith({ to: "/login" });
    });
  });

  it("still navigates to /login when the logout endpoint settles after an error", async () => {
    // Mirrors useLogoutMutation: clear() + cache eviction happen in
    // onSettled regardless of success/failure, so the redirect must too
    // — otherwise the tab is stuck on a 401-throwing page until F5.
    logoutMutateMock.mockImplementation((_input: unknown, opts?: { onSettled?: () => void }) => {
      opts?.onSettled?.();
    });

    render(<AccountMenu />);
    fireEvent.click(screen.getByRole("button", { name: /Cerrar sesión/i }));

    await waitFor(() => {
      expect(navigateMock).toHaveBeenCalledWith({ to: "/login" });
    });
  });
});
