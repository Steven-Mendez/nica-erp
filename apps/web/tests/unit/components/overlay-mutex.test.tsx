// Unit test for the shared overlay mutex. Audit F-039: opening one
// header overlay must close the other.

import { render, screen, fireEvent, cleanup } from "@testing-library/react";
import { afterEach, describe, expect, it } from "vitest";

import { OverlayMutexProvider, useOverlayMutex } from "@/components/overlay-mutex";

function Probe({ id, label }: { id: "theme" | "account"; label: string }) {
  const { open, setOpen } = useOverlayMutex(id);
  return (
    <div>
      <button type="button" onClick={() => setOpen(!open)}>
        toggle-{label}
      </button>
      {open ? <span data-testid={`${label}-open`}>open</span> : null}
    </div>
  );
}

afterEach(() => {
  cleanup();
});

describe("useOverlayMutex", () => {
  it("opening the second overlay closes the first", () => {
    render(
      <OverlayMutexProvider>
        <Probe id="theme" label="theme" />
        <Probe id="account" label="account" />
      </OverlayMutexProvider>,
    );

    fireEvent.click(screen.getByText("toggle-theme"));
    expect(screen.getByTestId("theme-open")).toBeInTheDocument();
    expect(screen.queryByTestId("account-open")).toBeNull();

    fireEvent.click(screen.getByText("toggle-account"));
    expect(screen.getByTestId("account-open")).toBeInTheDocument();
    expect(screen.queryByTestId("theme-open")).toBeNull();
  });

  it("toggling the same overlay closes it", () => {
    render(
      <OverlayMutexProvider>
        <Probe id="theme" label="theme" />
      </OverlayMutexProvider>,
    );

    fireEvent.click(screen.getByText("toggle-theme"));
    expect(screen.getByTestId("theme-open")).toBeInTheDocument();
    fireEvent.click(screen.getByText("toggle-theme"));
    expect(screen.queryByTestId("theme-open")).toBeNull();
  });

  it("degrades to local state when no provider is mounted", () => {
    render(<Probe id="theme" label="theme" />);
    fireEvent.click(screen.getByText("toggle-theme"));
    expect(screen.getByTestId("theme-open")).toBeInTheDocument();
  });
});
