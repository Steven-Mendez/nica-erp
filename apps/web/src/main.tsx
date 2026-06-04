// apps/web/src/main.tsx
import { StrictMode } from "react";
import { createRoot } from "react-dom/client";
import { z } from "zod";
import { App } from "@/app";
import { spanishErrorMap } from "@/lib/zod-spanish-error-map";
import "@/styles/globals.css";

// Spanish-UI rule: zod's default messages ("Required", "Invalid", ...)
// must never reach the SPA. Set the global error map once at bootstrap.
z.setErrorMap(spanishErrorMap);

const rootEl = document.getElementById("root");
if (!rootEl) {
  throw new Error("Missing #root element");
}

createRoot(rootEl).render(
  <StrictMode>
    <App />
  </StrictMode>,
);
