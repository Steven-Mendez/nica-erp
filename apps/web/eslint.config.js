// apps/web/eslint.config.js
import js from "@eslint/js";
import globals from "globals";
import reactHooks from "eslint-plugin-react-hooks";
import tseslint from "typescript-eslint";

export default tseslint.config(
  {
    ignores: [
      "dist",
      "node_modules",
      "src/api/schema.d.ts",
      "coverage",
      "playwright-report",
      "test-results",
    ],
  },
  {
    extends: [js.configs.recommended, ...tseslint.configs.recommended],
    files: ["**/*.{ts,tsx}"],
    languageOptions: {
      ecmaVersion: 2022,
      globals: globals.browser,
    },
    plugins: {
      "react-hooks": reactHooks,
    },
    rules: {
      ...reactHooks.configs.recommended.rules,
      "@typescript-eslint/no-explicit-any": "error",
    },
  },
  // No cross-feature imports: a file inside `src/features/<X>/` may not import
  // from any sibling `src/features/<Y>/`. Per docs/09-frontend.md, routes,
  // `src/api`, `src/lib`, and `src/components` may freely import features —
  // they're the composition layer.
  //
  // Convention this rule enforces by construction:
  //   - within a slice  →  use relative imports (`./endpoints`, `../schemas`)
  //   - cross-slice     →  use the `@/features/<other>/...` alias  (BLOCKED)
  //   - shared infra    →  use `@/api`, `@/lib`, `@/components`     (OK)
  //
  // The pattern matches any import string containing a `features/<slice>/...`
  // segment — which only happens via the alias form. Relative paths stay
  // clean because they never carry the `features/` segment.
  {
    files: ["src/features/**/*.{ts,tsx}"],
    rules: {
      "no-restricted-imports": [
        "error",
        {
          patterns: [
            {
              group: ["**/features/*/**"],
              message:
                "Cross-feature imports are forbidden. Use a relative path for same-slice imports, or share via src/api, src/lib, src/components.",
            },
          ],
        },
      ],
    },
  },
);
