// Unit tests for the DestructiveActionDialog wrapper. Cover the
// auto-focus-on-cancel default, the no-confirm-on-Escape contract,
// and the once-only confirm dispatch — the three guarantees that
// make this a safe primitive to reach for at every destructive call
// site in the empresa surface.

import { fireEvent, render, screen } from "@testing-library/react";
import { describe, expect, it, vi } from "vitest";
import { DestructiveActionDialog } from "@/components/dialog/destructive-action-dialog";

describe("DestructiveActionDialog", () => {
  it("renders the title and description in the alertdialog", () => {
    render(
      <DestructiveActionDialog
        open
        onOpenChange={() => undefined}
        title="Remover miembro"
        description="¿Remover a Ada de la empresa?"
        onConfirm={() => undefined}
      />,
    );
    const dialog = screen.getByRole("alertdialog");
    expect(dialog).toHaveTextContent("Remover miembro");
    expect(dialog).toHaveTextContent("¿Remover a Ada de la empresa?");
  });

  it("auto-focuses the cancel button on open", () => {
    render(
      <DestructiveActionDialog
        open
        onOpenChange={() => undefined}
        title="t"
        description="d"
        onConfirm={() => undefined}
      />,
    );
    // Cancel is the focused default so an accidental Enter is safe.
    const cancel = screen.getByRole("button", { name: /Cancelar/i });
    expect(cancel).toHaveFocus();
  });

  it("does not fire onConfirm when Escape closes the dialog", () => {
    const onConfirm = vi.fn();
    const onOpenChange = vi.fn();
    render(
      <DestructiveActionDialog
        open
        onOpenChange={onOpenChange}
        title="t"
        description="d"
        onConfirm={onConfirm}
      />,
    );
    fireEvent.keyDown(screen.getByRole("alertdialog"), { key: "Escape" });
    expect(onConfirm).not.toHaveBeenCalled();
    expect(onOpenChange).toHaveBeenCalledWith(false);
  });

  it("fires onConfirm exactly once when the destructive button is clicked", () => {
    const onConfirm = vi.fn();
    render(
      <DestructiveActionDialog
        open
        onOpenChange={() => undefined}
        title="t"
        description="d"
        confirmLabel="Sí, remover"
        onConfirm={onConfirm}
      />,
    );
    const confirm = screen.getByRole("button", { name: /Sí, remover/i });
    fireEvent.click(confirm);
    expect(onConfirm).toHaveBeenCalledTimes(1);
  });

  it("disables both buttons when pending is true", () => {
    render(
      <DestructiveActionDialog
        open
        onOpenChange={() => undefined}
        title="t"
        description="d"
        onConfirm={() => undefined}
        pending
      />,
    );
    expect(screen.getByRole("button", { name: /Cancelar/i })).toBeDisabled();
    expect(screen.getByRole("button", { name: /Eliminar/i })).toBeDisabled();
  });
});
