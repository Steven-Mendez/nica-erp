// Unit tests for the Field family wrapper. Custom over upstream shadcn:
// FieldError can render either children OR an `errors` array shaped
// like RHF's FieldError ({ message }) entries; the Field's data-invalid
// attribute drives the group-data-[invalid=true] styling on FieldLabel
// and FieldDescription.
import { cleanup, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";
import {
  Field,
  FieldDescription,
  FieldError,
  FieldGroup,
  FieldLabel,
  FieldLegend,
  FieldSet,
} from "@/components/ui/field";

afterEach(() => {
  cleanup();
});

describe("FieldError", () => {
  it("renders nothing when errors is empty and no children are passed", () => {
    const { container } = render(<FieldError errors={[]} />);
    expect(container.querySelector('[data-slot="field-error"]')).toBeNull();
  });

  it("renders nothing when errors is undefined and no children are passed", () => {
    const { container } = render(<FieldError />);
    expect(container.querySelector('[data-slot="field-error"]')).toBeNull();
  });

  it("renders the joined messages from an errors array", () => {
    render(<FieldError errors={[{ message: "Uno" }, { message: "Dos" }]} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Uno Dos");
  });

  it("skips entries with non-string messages", () => {
    render(<FieldError errors={[{ message: "Real" }, undefined, {}, { message: "Mas" }]} />);
    expect(screen.getByRole("alert")).toHaveTextContent("Real Mas");
  });

  it("renders children when provided and ignores the errors array", () => {
    render(<FieldError errors={[{ message: "ignored" }]}>{"override"}</FieldError>);
    expect(screen.getByRole("alert")).toHaveTextContent("override");
    expect(screen.queryByText("ignored")).toBeNull();
  });

  it("renders children even when errors is empty", () => {
    render(<FieldError>fallback</FieldError>);
    expect(screen.getByRole("alert")).toHaveTextContent("fallback");
  });
});

describe("Field markup", () => {
  it("Field defaults to vertical orientation classes", () => {
    const { container } = render(<Field />);
    const field = container.querySelector('[data-slot="field"]');
    expect(field?.className).toMatch(/flex-col/);
  });

  it("Field horizontal orientation switches to flex-row classes", () => {
    const { container } = render(<Field orientation="horizontal" />);
    const field = container.querySelector('[data-slot="field"]');
    expect(field?.className).toMatch(/flex-row/);
  });

  it("Field reflects data-invalid for downstream group styling", () => {
    const { container } = render(<Field data-invalid />);
    const field = container.querySelector('[data-slot="field"]');
    expect(field?.getAttribute("data-invalid")).toBe("true");
  });

  it("FieldLabel + FieldDescription render with their data-slot markers", () => {
    const { container } = render(
      <Field>
        <FieldLabel htmlFor="x">Etiqueta</FieldLabel>
        <FieldDescription>Ayuda</FieldDescription>
      </Field>,
    );
    expect(container.querySelector('[data-slot="field-label"]')).not.toBeNull();
    expect(container.querySelector('[data-slot="field-description"]')).not.toBeNull();
  });

  it("FieldGroup wraps with the @container class", () => {
    const { container } = render(
      <FieldGroup>
        <Field />
      </FieldGroup>,
    );
    const group = container.querySelector('[data-slot="field-group"]');
    expect(group?.className).toMatch(/@container/);
  });

  it("FieldSet + FieldLegend render", () => {
    const { container } = render(
      <FieldSet>
        <FieldLegend>Sección</FieldLegend>
        <Field />
      </FieldSet>,
    );
    expect(container.querySelector('[data-slot="field-set"]')).not.toBeNull();
    expect(container.querySelector('[data-slot="field-legend"]')).not.toBeNull();
  });
});
