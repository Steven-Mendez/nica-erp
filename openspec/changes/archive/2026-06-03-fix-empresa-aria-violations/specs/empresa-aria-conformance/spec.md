## ADDED Requirements

### Requirement: Every Radix Select on empresa routes exposes an accessible name and a conformant listbox structure

The empresa routes SHALL expose an accessible name on every Radix `<Select.Trigger>` (via either `aria-label` or `aria-labelledby` referencing the visible label) and SHALL keep every `<Select.Item>` nested under a single `<Select.Viewport>` inside `<Select.Content>`. Affected routes include `/empresa`, `/empresa/users`, `/empresa/settings`, and the `/tenants/new` wizard.
This structure ensures axe-core's `aria-required-parent` rule is satisfied (`[role=option]` always nested under `[role=listbox]`).

#### Scenario: axe-core sees zero button-name violations on /empresa/settings

- **GIVEN** the SPA mounts `/empresa/settings`
- **WHEN** axe-core runs with `runOnly:['wcag2a','wcag2aa']`
- **THEN** the violations list SHALL contain no `button-name`
  violation
- **AND** SHALL contain no `aria-required-parent` violation

#### Scenario: axe-core sees zero aria-required-parent violations on /empresa/users

- **GIVEN** the SPA mounts `/empresa/users`
- **WHEN** axe-core runs
- **THEN** the violations list SHALL contain no `aria-required-parent`
  violation

#### Scenario: Screen-reader announces the Régimen combobox label

- **GIVEN** a screen-reader user on `/empresa/settings`
- **WHEN** the user tabs into the Régimen combobox trigger
- **THEN** the screen reader SHALL announce `Régimen fiscal`
  (the visible label) followed by the current value or
  `Selecciona un régimen` placeholder
