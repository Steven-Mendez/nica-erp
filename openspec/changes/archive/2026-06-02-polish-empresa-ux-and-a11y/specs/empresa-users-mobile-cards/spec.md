## ADDED Requirements

### Requirement: Members table reflows to a card list below 768px

The `<MembersTable>` component (rendered on `/empresa/usuarios`) SHALL
render two layouts conditionally on viewport width:

- **≥ 768px** (Tailwind `md` breakpoint): the existing `<table>`
  structure with columns for nombre, correo, rol, estado, acciones.
- **< 768px**: a stacked card list. Each row renders as a
  `<Card>` with the following ordered content:
  1. Nombre (heading, `text-base font-semibold`)
  2. Correo (line below, muted)
  3. Rol (badge, inline)
  4. Estado (badge, inline)
  5. Acciones (button row, `w-full`, primary action first)

The same component renders both views — implementation MUST be a
single component branching via Tailwind class selectors (e.g.
`hidden md:block` / `block md:hidden`). The component MUST NOT
issue duplicate data fetches or maintain duplicate state for the
two views.

#### Scenario: 375px viewport renders cards, not a horizontally scrolling table

- **WHEN** `/empresa/usuarios` is rendered at 375×812
- **THEN** members render as `<Card>` blocks and no `<table>` element is visible

#### Scenario: 1024px viewport renders the table

- **WHEN** `/empresa/usuarios` is rendered at 1024×768
- **THEN** members render in the `<table>` structure with all five columns visible

### Requirement: Pagination controls render in both layouts and apply equally

The pagination control row SHALL render outside both branches so it
appears once in either layout. The pagination MUST drive the same
underlying `useMembersQuery` params for both layouts — there is no
separate mobile pagination state.

#### Scenario: Pagination next-page works identically in card and table layouts

- **WHEN** the operator clicks "Siguiente" at 375×812 viewport, then resizes the window to 1024×768
- **THEN** the table layout shows the same page of members that the card layout showed

### Requirement: Card layout preserves keyboard navigation order

In the card layout, the tab order within each card SHALL be: nombre
heading is non-interactive; tab progresses through correo (if it is
a link) → rol → estado → acciones (primary action first). The tab
order across cards proceeds top-to-bottom.

#### Scenario: Tab order in the card layout follows the documented sequence

- **WHEN** the operator tabs through the card layout from the top of the list
- **THEN** focus visits the first card's interactive elements in the documented order before moving to the second card's elements
