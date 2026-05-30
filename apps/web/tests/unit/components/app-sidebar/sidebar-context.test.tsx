import { act, cleanup, renderHook } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it } from "vitest";
import {
  SidebarProvider,
  sidebarSectionStorageKey,
  useSidebar,
  useSidebarSection,
} from "@/components/app-sidebar/sidebar-context";

const STORAGE_KEY = "nica-erp:sidebar-state";

function wrapper({ children }: { children: React.ReactNode }) {
  return <SidebarProvider>{children}</SidebarProvider>;
}

describe("SidebarProvider", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });

  afterEach(() => {
    cleanup();
  });

  it("hydrates from localStorage when a valid value is stored", () => {
    window.localStorage.setItem(STORAGE_KEY, "collapsed");
    const { result } = renderHook(() => useSidebar(), { wrapper });
    expect(result.current.state).toBe("collapsed");
  });

  it("defaults to expanded when no value is stored", () => {
    const { result } = renderHook(() => useSidebar(), { wrapper });
    expect(result.current.state).toBe("expanded");
  });

  it("toggle flips the persisted state", () => {
    const { result } = renderHook(() => useSidebar(), { wrapper });
    expect(result.current.state).toBe("expanded");
    act(() => result.current.toggle());
    expect(result.current.state).toBe("collapsed");
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe("collapsed");
    act(() => result.current.toggle());
    expect(result.current.state).toBe("expanded");
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe("expanded");
  });

  it("mobile open/close does not touch localStorage", () => {
    const { result } = renderHook(() => useSidebar(), { wrapper });
    const before = window.localStorage.getItem(STORAGE_KEY);
    act(() => result.current.setMobileOpen(true));
    expect(result.current.mobileOpen).toBe(true);
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe(before);
    act(() => result.current.toggleMobile());
    expect(result.current.mobileOpen).toBe(false);
    expect(window.localStorage.getItem(STORAGE_KEY)).toBe(before);
  });

  it("throws when useSidebar is called outside a provider", () => {
    expect(() => renderHook(() => useSidebar())).toThrow(
      /useSidebar must be used within a SidebarProvider/,
    );
  });
});

describe("useSidebarSection", () => {
  beforeEach(() => {
    window.localStorage.clear();
  });
  afterEach(() => {
    cleanup();
  });

  it("persists open under the per-section key", () => {
    const { result } = renderHook(() => useSidebarSection("empresa"));
    expect(window.localStorage.getItem(sidebarSectionStorageKey("empresa"))).toBe("0");
    act(() => result.current.toggle());
    expect(result.current.open).toBe(true);
    expect(window.localStorage.getItem(sidebarSectionStorageKey("empresa"))).toBe("1");
  });

  it("hydrates from localStorage when set", () => {
    window.localStorage.setItem(sidebarSectionStorageKey("empresa"), "1");
    const { result } = renderHook(() => useSidebarSection("empresa"));
    expect(result.current.open).toBe(true);
  });

  it("uses different storage keys per section", () => {
    expect(sidebarSectionStorageKey("empresa")).toBe("nica-erp:sidebar-empresa-open");
    expect(sidebarSectionStorageKey("settings")).toBe("nica-erp:sidebar-settings-open");
  });
});
