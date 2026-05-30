import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type ReactNode,
} from "react";

// Per-section persistence key. Sub-menu sections (e.g. "empresa")
// persist their open/closed state under
// `localStorage["nica-erp:sidebar-<key>-open"]` independent of the
// global expanded/collapsed state.
const SECTION_KEY_PREFIX = "nica-erp:sidebar-";
const SECTION_KEY_SUFFIX = "-open";

export function sidebarSectionStorageKey(key: string): string {
  return `${SECTION_KEY_PREFIX}${key}${SECTION_KEY_SUFFIX}`;
}

export function useSidebarSection(
  key: string,
  defaultOpen: boolean = false,
): { open: boolean; toggle: () => void; setOpen: (next: boolean) => void } {
  const storageKey = sidebarSectionStorageKey(key);
  const [open, setOpenInternal] = useState<boolean>(() => {
    if (typeof window === "undefined") return defaultOpen;
    try {
      const stored = window.localStorage.getItem(storageKey);
      if (stored === "1") return true;
      if (stored === "0") return false;
    } catch {
      // ignore
    }
    return defaultOpen;
  });

  useEffect(() => {
    if (typeof window === "undefined") return;
    try {
      window.localStorage.setItem(storageKey, open ? "1" : "0");
    } catch {
      // ignore
    }
  }, [storageKey, open]);

  const setOpen = useCallback((next: boolean) => setOpenInternal(next), []);
  const toggle = useCallback(() => setOpenInternal((p) => !p), []);
  return { open, toggle, setOpen };
}

export type SidebarState = "expanded" | "collapsed";

const STORAGE_KEY = "nica-erp:sidebar-state";

type SidebarContextValue = {
  state: SidebarState;
  toggle: () => void;
  setState: (next: SidebarState) => void;
  mobileOpen: boolean;
  setMobileOpen: (open: boolean) => void;
  toggleMobile: () => void;
};

const SidebarContext = createContext<SidebarContextValue | null>(null);

function readInitialState(): SidebarState {
  if (typeof window === "undefined") return "expanded";
  const stored = window.localStorage.getItem(STORAGE_KEY);
  if (stored === "expanded" || stored === "collapsed") return stored;
  return "expanded";
}

export function SidebarProvider({ children }: { children: ReactNode }) {
  const [state, setStateInternal] = useState<SidebarState>(readInitialState);
  const [mobileOpen, setMobileOpenInternal] = useState(false);

  useEffect(() => {
    if (typeof window === "undefined") return;
    window.localStorage.setItem(STORAGE_KEY, state);
  }, [state]);

  const setState = useCallback((next: SidebarState) => setStateInternal(next), []);
  const toggle = useCallback(
    () => setStateInternal((prev) => (prev === "expanded" ? "collapsed" : "expanded")),
    [],
  );

  const setMobileOpen = useCallback((open: boolean) => setMobileOpenInternal(open), []);
  const toggleMobile = useCallback(() => setMobileOpenInternal((prev) => !prev), []);

  const value = useMemo<SidebarContextValue>(
    () => ({ state, toggle, setState, mobileOpen, setMobileOpen, toggleMobile }),
    [state, toggle, setState, mobileOpen, setMobileOpen, toggleMobile],
  );

  return <SidebarContext.Provider value={value}>{children}</SidebarContext.Provider>;
}

export function useSidebar(): SidebarContextValue {
  const ctx = useContext(SidebarContext);
  if (ctx === null) {
    throw new Error("useSidebar must be used within a SidebarProvider");
  }
  return ctx;
}
