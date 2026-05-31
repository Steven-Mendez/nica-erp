// apps/web/src/lib/useDebouncedValue.ts
//
// Returns `value` after it stops changing for `delayMs`. Keeps the input
// element responsive while throttling expensive consumers — filters,
// network queries, URL search params.

import { useEffect, useState } from "react";

export function useDebouncedValue<T>(value: T, delayMs: number): T {
  const [debounced, setDebounced] = useState(value);

  useEffect(() => {
    if (delayMs <= 0) {
      setDebounced(value);
      return;
    }
    const handle = window.setTimeout(() => setDebounced(value), delayMs);
    return () => window.clearTimeout(handle);
  }, [value, delayMs]);

  return debounced;
}
