## Why

The 2026-06-03 axe scan (axe-core 4.10.0, runOnly `wcag2a`+`wcag2aa`)
reported two critical violations on the empresa area:

- **F-040** — `/empresa/users`: `aria-required-parent` × 2 nodes.
  A `[role=option]` (or `[role=listitem]`) renders without the
  required `[role=listbox]` (resp. `[role=list]`) ancestor. Likely
  the role-filter Radix Select renders portaled `<Select.Item>`s
  outside a `<Select.Viewport>` due to a `Portal` misconfiguration.
- **F-041** — `/empresa/settings`: `button-name` × 3 nodes. Three
  Radix `Select.Trigger` buttons have no accessible name. The visible
  `<label>` is positioned above (correctly with `htmlFor`) but the
  Radix combobox does not pick it up — Radix expects an explicit
  `aria-label` or `aria-labelledby` on the trigger.

Both violations are critical per WCAG 2.1 AA. Without a fix, screen
readers cannot name the affected widgets, and dictation users cannot
target them by visible label.

This change fixes both by tightening the Radix Select wrappers used on
those screens.

## What Changes

### Frontend — Radix Select wrapper hygiene

- Audit every `<Select.Trigger>` in `apps/web/src/components/ui/select*`
  AND in route files. For each, ensure either:
  - `aria-labelledby="<id-of-the-visible-label>"`, OR
  - `aria-label="Régimen"` (etc.) when no separate label exists.
- For `/empresa/settings`, set `aria-labelledby` on each of the 3
  affected triggers (Régimen, Departamento, Municipio) referencing
  the existing `<label>` IDs.
- For `/empresa/users`, ensure all `<Select.Item>` siblings live
  inside a single `<Select.Viewport>` (default in shadcn's wrapper)
  and the `<Select.Portal>` mounts `<Select.Content>` directly under
  it — no intermediate wrapper. The `aria-required-parent` violation
  is usually caused by a fragment + portal mix that drops the
  `listbox` ancestor; verify the wrapper components do not break the
  invariant.

### Tests

- Add an axe-core CI check to the existing Vitest browser-mode tests
  (or extend the e2e suite) that fails on any `aria-required-parent`
  or `button-name` violation on `/empresa/users` and
  `/empresa/settings`.
- Manual: VoiceOver / NVDA pass over each combobox to confirm the
  visible label is announced.

## Non-goals

- Replacing Radix Select with a different primitive.
- Adding accessible-name fixes to other a11y violations (e.g.
  `aria-required-parent` on the dashboard's Tendencia toolbar, if
  any) — out of scope unless a follow-up audit finds them.
- Contrast or focus-ring changes.
