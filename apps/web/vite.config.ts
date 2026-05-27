// apps/web/vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import path from "node:path";

export default defineConfig({
  plugins: [react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    port: 5173,
  },
  build: {
    // Long-term cache friendliness: keep the bulky, slow-moving libraries in
    // their own chunks so a redeploy of app code doesn't invalidate the
    // vendor bundles in user caches.
    rollupOptions: {
      output: {
        manualChunks: (id) => {
          if (!id.includes("node_modules")) return undefined;
          if (id.includes("/@tanstack/")) return "tanstack";
          if (
            id.includes("/react-hook-form/") ||
            id.includes("/@hookform/") ||
            id.includes("/zod/")
          ) {
            return "forms";
          }
          if (
            id.includes("/lucide-react/") ||
            id.includes("/@radix-ui/") ||
            id.includes("/sonner/") ||
            id.includes("/class-variance-authority/") ||
            id.includes("/tailwind-merge/")
          ) {
            return "ui";
          }
          if (id.includes("/react-dom/") || id.includes("/react/")) {
            return "react";
          }
          return undefined;
        },
      },
    },
  },
  test: {
    globals: true,
    environment: "happy-dom",
    setupFiles: ["./tests/setup.ts"],
    include: ["tests/**/*.test.{ts,tsx}"],
  },
});
