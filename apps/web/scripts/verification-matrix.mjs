#!/usr/bin/env node
// Generates apps/web/coverage/verification-matrix.json mapping every
// inventory entry committed in the openspec proposal to the test files
// that cover it. Exits 1 when any inventory entry maps to zero tests.
//
// Strategy: read the source tree for canonical entries (routes, hooks,
// schemas, shared modules), grep tests/ for files that import the
// module path or reference the exported symbol. The match is structural
// (regex on the file text) rather than semantic — good enough for a
// pre-commit gate, cheap enough to run on every CI build.

import { readdirSync, statSync, readFileSync, existsSync, mkdirSync, writeFileSync } from "node:fs";
import { dirname, join, relative } from "node:path";

const WEB_ROOT = new URL("../", import.meta.url).pathname;
const SRC = join(WEB_ROOT, "src");
const TESTS = join(WEB_ROOT, "tests");
const OUT = join(WEB_ROOT, "coverage", "verification-matrix.json");

function walk(dir, filter = () => true) {
  const out = [];
  if (!existsSync(dir)) return out;
  for (const entry of readdirSync(dir)) {
    const p = join(dir, entry);
    const s = statSync(p);
    if (s.isDirectory()) out.push(...walk(p, filter));
    else if (filter(p)) out.push(p);
  }
  return out;
}

const isTest = (p) => /\.(test|spec)\.tsx?$/.test(p);
const testFiles = walk(TESTS, isTest);
const testTexts = new Map(testFiles.map((p) => [p, readFileSync(p, "utf8")]));

function importPathsFor(src) {
  // Compute the @/-prefixed import path and the file-stem aliases that
  // a test would conventionally use to reference this source module.
  const rel = relative(SRC, src).replace(/\\/g, "/");
  const noExt = rel.replace(/\.(tsx?|d\.ts)$/, "");
  const alias = `@/${noExt}`;
  const aliasDir = `@/${dirname(noExt)}`;
  return new Set([alias, aliasDir]);
}

function testsCovering(src, extraSymbols = []) {
  const paths = importPathsFor(src);
  const result = [];
  for (const [tfile, text] of testTexts) {
    for (const p of paths) {
      if (text.includes(p)) {
        result.push(relative(WEB_ROOT, tfile));
        break;
      }
    }
    // Fallback: scan for an exported symbol name when the import path
    // doesn't match (e.g. a barrel file re-exports).
    if (!result.includes(relative(WEB_ROOT, tfile))) {
      for (const sym of extraSymbols) {
        if (sym && text.includes(sym)) {
          result.push(relative(WEB_ROOT, tfile));
          break;
        }
      }
    }
  }
  return Array.from(new Set(result));
}

function extractExports(file) {
  if (!existsSync(file)) return [];
  const text = readFileSync(file, "utf8");
  const out = [];
  const re = /export\s+(?:const|function|class|let|var)\s+([A-Za-z0-9_]+)/g;
  let m;
  while ((m = re.exec(text)) !== null) out.push(m[1]);
  return out;
}

// ---- Inventory ----------------------------------------------------

const inventory = {};

// Routes: every src/routes/**/*.tsx
for (const f of walk(join(SRC, "routes"), (p) => p.endsWith(".tsx"))) {
  const key = `route:${relative(SRC, f).replace(/\\/g, "/")}`;
  inventory[key] = testsCovering(f);
}

// Hooks: features/{auth,tenants}/api/hooks.ts — one entry per exported hook
for (const slice of ["auth", "tenants"]) {
  const hooksFile = join(SRC, "features", slice, "api", "hooks.ts");
  if (!existsSync(hooksFile)) continue;
  const text = readFileSync(hooksFile, "utf8");
  const re = /export\s+const\s+(use[A-Z][A-Za-z0-9]*)/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    const name = m[1];
    const key = `hook:${slice}/${name}`;
    inventory[key] = testsCovering(hooksFile, [name]);
  }
}

// Schemas: features/{auth,tenants}/schemas/index.ts — one entry per exported schema
for (const slice of ["auth", "tenants"]) {
  const schemaFile = join(SRC, "features", slice, "schemas", "index.ts");
  if (!existsSync(schemaFile)) continue;
  const text = readFileSync(schemaFile, "utf8");
  const re = /export\s+const\s+([a-zA-Z0-9]+Schema)\b/g;
  let m;
  while ((m = re.exec(text)) !== null) {
    const name = m[1];
    const key = `schema:${slice}/${name}`;
    inventory[key] = testsCovering(schemaFile, [name]);
  }
}

// Shared infra: src/api/*, src/lib/*
for (const subtree of ["api", "lib"]) {
  for (const f of walk(join(SRC, subtree), (p) => /\.tsx?$/.test(p) && !p.endsWith(".d.ts"))) {
    const key = `infra:${relative(SRC, f).replace(/\\/g, "/")}`;
    inventory[key] = testsCovering(f, extractExports(f));
  }
}

// Shared components: app-shell, app-sidebar, identity-layout, standalone widgets
const sharedComponentDirs = [
  "components/app-shell",
  "components/app-sidebar",
  "components/identity-layout",
];
for (const d of sharedComponentDirs) {
  for (const f of walk(join(SRC, d), (p) => /\.tsx?$/.test(p))) {
    const key = `component:${relative(SRC, f).replace(/\\/g, "/")}`;
    inventory[key] = testsCovering(f, extractExports(f));
  }
}
for (const name of ["account-menu", "brand-header", "theme-provider", "theme-toggle", "logo"]) {
  const f = join(SRC, "components", `${name}.tsx`);
  if (!existsSync(f)) continue;
  const key = `component:components/${name}.tsx`;
  inventory[key] = testsCovering(f, extractExports(f));
}

// Feature components: features/{tenants,dashboard,auth}/components/**
for (const slice of ["auth", "tenants", "dashboard"]) {
  const dir = join(SRC, "features", slice, "components");
  for (const f of walk(dir, (p) => /\.tsx?$/.test(p))) {
    const key = `component:${relative(SRC, f).replace(/\\/g, "/")}`;
    inventory[key] = testsCovering(f, extractExports(f));
  }
}

// ---- Emit + gate --------------------------------------------------

mkdirSync(dirname(OUT), { recursive: true });
writeFileSync(OUT, JSON.stringify(inventory, null, 2) + "\n");

const empties = Object.entries(inventory).filter(([, v]) => v.length === 0);
if (empties.length > 0) {
  console.error(`verification-matrix: ${empties.length} inventory entries have NO test`);
  for (const [k] of empties) console.error(`  - ${k}`);
  console.error(`\nMatrix written to ${relative(WEB_ROOT, OUT)}`);
  process.exit(1);
}

console.log(`verification-matrix: ${Object.keys(inventory).length} entries verified (${OUT})`);
