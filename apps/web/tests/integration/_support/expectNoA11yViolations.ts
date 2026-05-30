// Thin axe-core wrapper for integration specs.
//
// `vitest-axe` ships matchers for `expect(results).toHaveNoViolations()`,
// but the matcher is wired per-spec to keep the global vitest expect from
// having a vitest-axe shape leaking into unit specs. The helper below
// returns the typed axe report; specs assert against it directly.

import axe, { type AxeResults, type ContextObject, type RunOptions } from "axe-core";

const RUN_OPTIONS: RunOptions = {
  runOnly: { type: "tag", values: ["wcag2a", "wcag2aa"] },
};

export const runAxe = async (
  container: Document | HTMLElement | ContextObject = document,
): Promise<AxeResults> => {
  return axe.run(container, RUN_OPTIONS);
};

export const expectNoA11yViolations = async (
  container: Document | HTMLElement | ContextObject = document,
): Promise<void> => {
  const results = await runAxe(container);
  if (results.violations.length > 0) {
    const summary = results.violations
      .map((v) => `- ${v.id} (${v.impact ?? "n/a"}): ${v.help}`)
      .join("\n");
    throw new Error(`axe-core reported violations:\n${summary}`);
  }
};
