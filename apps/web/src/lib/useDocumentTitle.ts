// apps/web/src/lib/useDocumentTitle.ts
//
// Sets `document.title` to `"<page> · Nica ERP"` while the calling component is
// mounted. Routes own their page label; the brand suffix is centralised here
// so it stays consistent across the SPA.

import { useEffect } from "react";

const BRAND = "Nica ERP";

export const useDocumentTitle = (page: string): void => {
  useEffect(() => {
    document.title = `${page} · ${BRAND}`;
  }, [page]);
};
