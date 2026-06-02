# frontend-sidebar-a11y Specification

## Purpose
TBD - created by archiving change polish-empresa-ux-and-a11y. Update Purpose after archive.
## Requirements
### Requirement: Mobile sidebar is removed from the accessibility tree when closed

The mobile sidebar MUST be removed from the accessibility tree, focus order, and DOM rendering when closed. The mobile branch in `apps/web/src/components/app-sidebar/`, when closed below 768px, SHALL simultaneously apply all three of:

- `aria-hidden="true"` on the sidebar container.
- The `inert` HTML attribute on the sidebar container.
- `display: none` on the sidebar container (via Tailwind class or
  inline style).

When the sidebar opens (or the viewport widens past 768px), all
three SHALL be removed and the existing focus-trap (provided by the
shadcn `<Sheet>` primitive or equivalent) SHALL take over.

#### Scenario: Closed mobile sidebar carries all three a11y guards

- **WHEN** the viewport is 375×812 and the sidebar is closed
- **THEN** the sidebar container carries `aria-hidden="true"`, the `inert` attribute, and is `display: none`

#### Scenario: Tab order at 375px skips the closed sidebar

- **WHEN** the operator presses Tab from the top of the page at 375×812 with the sidebar closed
- **THEN** focus visits the page's main content interactive elements in order without entering the sidebar

#### Scenario: Opening the sidebar removes all three guards

- **WHEN** the operator opens the mobile sidebar via the header trigger
- **THEN** `aria-hidden`, `inert`, and `display: none` are all removed from the sidebar container

### Requirement: Mobile sidebar trigger announces state via ARIA

The button in the AppShell header that opens the mobile sidebar SHALL:

- Carry `aria-controls="<sidebar-id>"` referencing the sidebar
  container.
- Carry `aria-expanded` reflecting the current open/closed state.
- Carry a Spanish `aria-label` consistent with the visible action
  (`"Abrir menú"` when closed, `"Cerrar menú"` when open).

#### Scenario: Closed sidebar trigger reports aria-expanded="false"

- **WHEN** the mobile sidebar is closed
- **THEN** the header trigger button has `aria-expanded="false"` and `aria-label="Abrir menú"`

#### Scenario: Open sidebar trigger reports aria-expanded="true"

- **WHEN** the mobile sidebar is open
- **THEN** the header trigger has `aria-expanded="true"` and `aria-label="Cerrar menú"`

### Requirement: Focus-trap is active while the mobile sidebar is open

While the mobile sidebar is open, focus SHALL be trapped inside the
sidebar (the shadcn `<Sheet>` primitive provides this — the
implementation MUST verify it is the primitive in use and not bypass
its focus trap). The escape key SHALL close the sidebar and return
focus to the trigger button.

#### Scenario: Tabbing inside the open sidebar wraps to the first focusable element

- **WHEN** the operator opens the mobile sidebar and tabs past the last focusable element
- **THEN** focus returns to the first focusable element within the sidebar, not to elements outside it

#### Scenario: Escape closes the sidebar and restores focus to the trigger

- **WHEN** the mobile sidebar is open and the operator presses Escape
- **THEN** the sidebar closes and focus returns to the header trigger button

