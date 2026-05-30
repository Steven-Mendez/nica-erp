// Unit tests for DataTableFacetedFilter. Drives the popover via a fake
// tanstack-table Column stub; covers trigger label, badge rendering when
// values are selected, hidden popover content (it is rendered eagerly
// inside the Popover portal so we can interact without opening it via
// pointer events), and the Limpiar filtros affordance.
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Shield } from "lucide-react";
import type { Column } from "@tanstack/react-table";
import { DataTableFacetedFilter } from "@/features/tenants/components/DataTableFacetedFilter";

type Row = { role: string };

function makeColumn(initial: string[] | undefined = undefined): {
  column: Column<Row, string>;
  setFilterValue: ReturnType<typeof vi.fn>;
} {
  let filterValue: string[] | undefined = initial;
  const setFilterValue = vi.fn((next: string[] | undefined) => {
    filterValue = next;
  });
  const column = {
    getFilterValue: () => filterValue,
    setFilterValue,
    getFacetedUniqueValues: () =>
      new Map<string, number>([
        ["admin", 3],
        ["viewer", 1],
      ]),
  } as unknown as Column<Row, string>;
  return { column, setFilterValue };
}

const OPTIONS = [
  { value: "admin", label: "Administrador", icon: Shield },
  { value: "viewer", label: "Lector", icon: Shield },
];

afterEach(() => {
  cleanup();
});

describe("DataTableFacetedFilter", () => {
  it("renders the title on the trigger button", () => {
    const { column } = makeColumn();
    render(<DataTableFacetedFilter column={column} title="Rol" options={OPTIONS} />);
    expect(screen.getByRole("button", { name: /Rol/i })).toBeInTheDocument();
  });

  it("renders the selected-option badge when filters are active", () => {
    const { column } = makeColumn(["admin"]);
    render(<DataTableFacetedFilter column={column} title="Rol" options={OPTIONS} />);
    // The "Administrador" label appears inside the trigger badge.
    expect(screen.getByText("Administrador")).toBeInTheDocument();
  });

  it("opens the popover when the trigger is clicked", () => {
    const { column } = makeColumn();
    render(<DataTableFacetedFilter column={column} title="Rol" options={OPTIONS} />);
    fireEvent.click(screen.getByRole("button", { name: /Rol/i }));
    // CommandInput placeholder == title.
    expect(screen.getByPlaceholderText("Rol")).toBeInTheDocument();
  });

  it("toggling an option calls setFilterValue with the new selection", () => {
    const { column, setFilterValue } = makeColumn();
    render(<DataTableFacetedFilter column={column} title="Rol" options={OPTIONS} />);
    fireEvent.click(screen.getByRole("button", { name: /Rol/i }));

    // CommandItem is keyboard-driven by cmdk; click the role label.
    fireEvent.click(screen.getByText("Administrador"));
    expect(setFilterValue).toHaveBeenCalledWith(["admin"]);
  });

  it("Limpiar filtros calls setFilterValue with undefined", () => {
    const { column, setFilterValue } = makeColumn(["admin"]);
    render(<DataTableFacetedFilter column={column} title="Rol" options={OPTIONS} />);
    fireEvent.click(screen.getByRole("button", { name: /Rol/i }));

    fireEvent.click(screen.getByText(/Limpiar filtros/i));
    expect(setFilterValue).toHaveBeenCalledWith(undefined);
  });
});
