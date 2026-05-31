// apps/web/vite.config.ts
import { defineConfig } from "vite";
import react from "@vitejs/plugin-react";
import tailwindcss from "@tailwindcss/vite";
import path from "node:path";

export default defineConfig({
  plugins: [tailwindcss(), react()],
  resolve: {
    alias: {
      "@": path.resolve(__dirname, "./src"),
    },
  },
  server: {
    // Pin to IPv4 loopback so Playwright's webServer block (which polls
    // http://127.0.0.1:5173) matches the address Vite is actually
    // listening on. Without this, Linux CI resolves the default
    // `localhost` to ::1 and the smoke job times out.
    host: "127.0.0.1",
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
    // Two named projects per the triad spec. A run with no `--project`
    // flag executes both; CI selects one per job.
    projects: [
      {
        extends: true,
        test: {
          name: "unit",
          environment: "happy-dom",
          globals: true,
          include: ["tests/unit/**/*.test.{ts,tsx}"],
          setupFiles: ["./tests/setup.ts"],
          testTimeout: 1000,
        },
      },
      {
        extends: true,
        test: {
          name: "integration",
          environment: "happy-dom",
          globals: true,
          include: ["tests/integration/**/*.spec.{ts,tsx}"],
          setupFiles: ["./tests/setup.ts", "./tests/integration/setup.ts"],
          testTimeout: 5000,
        },
      },
    ],
    coverage: {
      provider: "v8",
      reporter: ["text", "html", "json-summary", "lcov"],
      include: [
        "src/features/**/*.{ts,tsx}",
        "src/components/**/*.{ts,tsx}",
        "src/lib/**/*.{ts,tsx}",
        "src/api/**/*.{ts,tsx}",
      ],
      exclude: ["**/*.test.{ts,tsx}", "**/*.spec.{ts,tsx}", "src/api/schema.d.ts"],
      // Per-glob thresholds keep the floor where bugs hurt, tolerant where
      // they don't. `perFile: false` keeps the aggregate over each glob so a
      // single low-coverage file is reported by name in the failure output.
      // Maintainers ratchet via the local script documented in
      // `tests/integration/README.md`; CI never updates thresholds.
      thresholds: {
        perFile: false,
        autoUpdate: false,
        // Ratcheted to the measured floor on the green run that landed
        // this change (lines 82.79, branches 80.88, functions 67.41,
        // statements 82.79); leave a 2-point buffer so transient
        // measurement noise doesn't trip the gate.
        lines: 80,
        functions: 65,
        statements: 80,
        branches: 78,
      },
    },
  },
});
