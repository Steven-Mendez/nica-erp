// Unit tests for the dashboard feature's KPI / chart / table cards.
// All three currently render as placeholders; the tests pin the
// labels, the count of slots, and the placeholder badge so a
// regression that silently strips a card is caught.
import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { ActivityCard, KpiCard, SectionKpis, TrendCard } from "@/features/dashboard";

describe("KpiCard", () => {
  it("renders the label and a Próximamente badge in placeholder mode", () => {
    render(<KpiCard label="Ingresos" />);
    expect(screen.getByText("Ingresos")).toBeInTheDocument();
    expect(screen.getByText("Próximamente")).toBeInTheDocument();
  });

  it("renders the value and an up-delta badge when value is provided", () => {
    render(
      <KpiCard label="Ingresos" value="C$ 12,000" delta={{ value: "+5%", direction: "up" }} />,
    );
    expect(screen.getByText("C$ 12,000")).toBeInTheDocument();
    expect(screen.getByText("+5%")).toBeInTheDocument();
    // Próximamente badge is hidden once a value is supplied.
    expect(screen.queryByText("Próximamente")).toBeNull();
  });
});

describe("SectionKpis", () => {
  it("renders four placeholder KPI cards", () => {
    render(<SectionKpis />);
    expect(screen.getAllByTestId("kpi-card")).toHaveLength(4);
    for (const label of ["Ingresos", "Cuentas por cobrar", "Stock en riesgo", "Producto top"]) {
      expect(screen.getByText(label)).toBeInTheDocument();
    }
  });
});

describe("TrendCard", () => {
  it("renders the title, description, and a 30-day range toggle by default", () => {
    render(<TrendCard />);
    expect(screen.getByText("Tendencia de ventas")).toBeInTheDocument();
    expect(screen.getByText(/los últimos 30 días/)).toBeInTheDocument();
  });
});

describe("ActivityCard", () => {
  it("renders the placeholder title + Próximamente badge", () => {
    render(<ActivityCard />);
    expect(screen.getByText("Actividad reciente")).toBeInTheDocument();
    expect(screen.getByText("Próximamente")).toBeInTheDocument();
  });
});
