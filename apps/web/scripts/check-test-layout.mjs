#!/usr/bin/env node
// Enforces the triad layout per the frontend-testing-triad spec:
//
//   - tests/unit/routes/ MUST NOT exist (route render is integration).
//   - Files under tests/unit/ MUST NOT import createFileRoute,
//     RouterProvider, QueryClientProvider, or msw.
//   - Files under tests/integration/ MUST NOT live in tests/unit/.
//
// Exits 0 on success, prints the violations and exits 1 on failure.

import { readdirSync, statSync, readFileSync, existsSync } from "node:fs";
import { join } from "node:path";

const ROOT = new URL("../tests/unit/", import.meta.url).pathname;
const FORBIDDEN = [
  /from\s+["']@tanstack\/react-router["']/,
  /from\s+["']@tanstack\/react-query["']/,
  /from\s+["']msw["']/,
  /from\s+["']msw\/node["']/,
  /createFileRoute\b/,
  /RouterProvider\b/,
  /QueryClientProvider\b/,
];

function walk(dir) {
  const out = [];
  if (!existsSync(dir)) return out;
  for (const entry of readdirSync(dir)) {
    const p = join(dir, entry);
    const s = statSync(p);
    if (s.isDirectory()) out.push(...walk(p));
    else if (/\.(test|spec)\.tsx?$/.test(entry)) out.push(p);
  }
  return out;
}

const violations = [];

const routesDir = join(ROOT, "routes");
if (existsSync(routesDir)) {
  violations.push(
    `tests/unit/routes/ exists — route render tests belong under tests/integration/routes/`,
  );
}

for (const file of walk(ROOT)) {
  const text = readFileSync(file, "utf8");
  for (const re of FORBIDDEN) {
    if (re.test(text)) {
      violations.push(`${file} matches forbidden pattern ${re}`);
      break;
    }
  }
}

if (violations.length > 0) {
  console.error("Test layout violations:");
  for (const v of violations) console.error(`  - ${v}`);
  console.error(
    "\nPer openspec/changes/improve-frontend-testing-triad/specs/frontend-testing-triad,",
  );
  console.error("route render and MSW belong under tests/integration/.");
  process.exit(1);
}

console.log("Test layout: OK");
