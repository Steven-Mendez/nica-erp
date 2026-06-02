// Verifies the closed-mobile a11y contract on the app sidebar: when
// the viewport is below 768px and the sidebar is closed, the panel
// MUST be removed from the a11y tree (aria-hidden), focus tree
// (inert), and layout (Tailwind `hidden`). The header trigger
// reports `aria-expanded` and swaps its Spanish label.
import { act, cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { Sidebar, SIDEBAR_ROOT_ID } from "@/components/app-sidebar/sidebar";
import { SidebarProvider, useSidebar } from "@/components/app-sidebar/sidebar-context";

vi.mock("@tanstack/react-router", async () => {
  const actual = await vi.importActual<object>("@tanstack/react-router");
  return {
    ...actual,
    useRouterState: () => ({ pathname: "/dashboard" }),
    useNavigate: () => () => undefined,
    Link: ({ children, to }: { children: React.ReactNode; to: string }) => (
      <a href={to}>{children}</a>
    ),
  };
});

type MQListener = (e: MediaQueryListEvent) => void;

function installMatchMedia(matches: boolean): { setMatches: (next: boolean) => void } {
  const listeners = new Set<MQListener>();
  let current = matches;
  Object.defineProperty(window, "matchMedia", {
    configurable: true,
    writable: true,
    value: (_query: string) => ({
      get matches() {
        return current;
      },
      media: _query,
      onchange: null,
      addEventListener: (_: string, fn: MQListener) => {
        listeners.add(fn);
      },
      removeEventListener: (_: string, fn: MQListener) => {
        listeners.delete(fn);
      },
      addListener: (fn: MQListener) => {
        listeners.add(fn);
      },
      removeListener: (fn: MQListener) => {
        listeners.delete(fn);
      },
      dispatchEvent: () => true,
    }),
  });
  return {
    setMatches: (next) => {
      current = next;
      for (const fn of listeners) {
        fn({ matches: next } as MediaQueryListEvent);
      }
    },
  };
}

function MobileTrigger() {
  const { toggleMobile, mobileOpen } = useSidebar();
  return (
    <button
      type="button"
      aria-controls={SIDEBAR_ROOT_ID}
      aria-expanded={mobileOpen}
      aria-label={mobileOpen ? "Cerrar menú" : "Abrir menú"}
      onClick={toggleMobile}
    >
      menu
    </button>
  );
}

function renderHarness() {
  return render(
    <SidebarProvider>
      <MobileTrigger />
      <Sidebar>
        <a href="/x">Inner link</a>
      </Sidebar>
    </SidebarProvider>,
  );
}

afterEach(() => {
  cleanup();
});

describe("Sidebar mobile a11y", () => {
  beforeEach(() => {
    installMatchMedia(true);
  });

  it("applies aria-hidden + inert + hidden when closed at < 768px and trigger reports collapsed state", () => {
    renderHarness();
    const sidebar = document.getElementById(SIDEBAR_ROOT_ID);
    expect(sidebar).not.toBeNull();
    expect(sidebar?.getAttribute("aria-hidden")).toBe("true");
    expect(sidebar?.hasAttribute("inert")).toBe(true);
    expect(sidebar?.classList.contains("hidden")).toBe(true);
    const trigger = screen.getByRole("button", { name: /Abrir menú/i });
    expect(trigger.getAttribute("aria-expanded")).toBe("false");
    expect(trigger.getAttribute("aria-controls")).toBe(SIDEBAR_ROOT_ID);
  });

  it("removes all three guards when the sidebar opens and the trigger flips the Spanish label", () => {
    renderHarness();
    const trigger = screen.getByRole("button", { name: /Abrir menú/i });
    act(() => {
      fireEvent.click(trigger);
    });
    const sidebar = document.getElementById(SIDEBAR_ROOT_ID);
    expect(sidebar?.getAttribute("aria-hidden")).toBeNull();
    expect(sidebar?.hasAttribute("inert")).toBe(false);
    expect(sidebar?.classList.contains("hidden")).toBe(false);
    const closeBtn = screen.getByRole("button", { name: /Cerrar menú/i });
    expect(closeBtn.getAttribute("aria-expanded")).toBe("true");
  });

  it("re-applies the guards when the viewport widens past 768px is irrelevant — at md+ the panel is always reachable", () => {
    const mm = installMatchMedia(false);
    renderHarness();
    const sidebar = document.getElementById(SIDEBAR_ROOT_ID);
    // At md+ the guards never apply, even when mobileOpen is false.
    expect(sidebar?.getAttribute("aria-hidden")).toBeNull();
    expect(sidebar?.hasAttribute("inert")).toBe(false);
    expect(sidebar?.classList.contains("hidden")).toBe(false);
    // Shrinking back to mobile re-applies them.
    act(() => {
      mm.setMatches(true);
    });
    expect(sidebar?.getAttribute("aria-hidden")).toBe("true");
    expect(sidebar?.hasAttribute("inert")).toBe(true);
    expect(sidebar?.classList.contains("hidden")).toBe(true);
  });
});
