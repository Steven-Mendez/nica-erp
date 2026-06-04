// apps/web/src/components/overlay-mutex.tsx
//
// Shared store of the currently-open header overlay. Audit F-039:
// the operator could open both the Theme popover AND the Account
// dropdown at the same time, producing two stacked menus over the
// header. A single shared id ("theme" | "account" | null) ensures
// opening one closes the other.
//
// Components opt in via `useOverlayMutex(id)` which returns the
// `open` boolean to bind to the Radix overlay's `open` prop and the
// `setOpen(next)` callback for `onOpenChange`.

import { createContext, type ReactNode, useCallback, useContext, useMemo, useState } from "react";

export type OverlayId = "theme" | "account" | null;

type Ctx = {
  current: OverlayId;
  setCurrent: (id: OverlayId) => void;
};

const OverlayMutexContext = createContext<Ctx | null>(null);

export function OverlayMutexProvider({ children }: { children: ReactNode }) {
  const [current, setCurrent] = useState<OverlayId>(null);
  const value = useMemo(() => ({ current, setCurrent }), [current]);
  return <OverlayMutexContext.Provider value={value}>{children}</OverlayMutexContext.Provider>;
}

/**
 * Bind a Radix-style overlay to the shared mutex. When the provider is
 * absent (e.g. the component is rendered outside the AppShell) the hook
 * degrades to local-only state so callers stay testable in isolation.
 */
export function useOverlayMutex(id: Exclude<OverlayId, null>): {
  open: boolean;
  setOpen: (next: boolean) => void;
} {
  const ctx = useContext(OverlayMutexContext);
  const [localOpen, setLocalOpen] = useState(false);

  const open = ctx === null ? localOpen : ctx.current === id;
  const setOpen = useCallback(
    (next: boolean) => {
      if (ctx === null) {
        setLocalOpen(next);
        return;
      }
      ctx.setCurrent(next ? id : null);
    },
    [ctx, id],
  );

  return { open, setOpen };
}
