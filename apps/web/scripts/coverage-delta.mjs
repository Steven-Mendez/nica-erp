#!/usr/bin/env node
// Diffs two coverage-summary.json files (base vs head) and exits non-zero
// when total `lines` or `branches` percentage drops. Used by the
// `coverage-delta` job in web-checks.yml per
// openspec/specs/frontend-testing-change-detection.

import { readFileSync } from "node:fs";

const [, , basePath, headPath] = process.argv;
if (!basePath || !headPath) {
  console.error("usage: coverage-delta <base.json> <head.json>");
  process.exit(2);
}

const base = JSON.parse(readFileSync(basePath, "utf8"));
const head = JSON.parse(readFileSync(headPath, "utf8"));

const baseTotal = base.total ?? {};
const headTotal = head.total ?? {};

const rows = ["lines", "branches", "functions", "statements"].map((k) => ({
  metric: k,
  base: baseTotal[k]?.pct ?? 0,
  head: headTotal[k]?.pct ?? 0,
}));

let failed = false;
for (const r of rows) {
  r.delta = +(r.head - r.base).toFixed(2);
  if ((r.metric === "lines" || r.metric === "branches") && r.delta < 0) failed = true;
}

console.log("metric       base     head    delta");
for (const r of rows) {
  console.log(
    `${r.metric.padEnd(12)} ${String(r.base).padStart(6)}  ${String(r.head).padStart(6)}  ${String(r.delta).padStart(6)}`,
  );
}

if (failed) {
  console.error("\ncoverage-delta: lines or branches dropped vs base — fix tests or refactor.");
  process.exit(1);
}
console.log("\ncoverage-delta: OK");
