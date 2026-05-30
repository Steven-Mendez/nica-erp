import { KpiCard } from "./kpi-card";

const KPI_LABELS = ["Ingresos", "Cuentas por cobrar", "Stock en riesgo", "Producto top"] as const;

export function SectionKpis() {
  return (
    <section
      aria-label="Métricas clave"
      className="grid grid-cols-1 gap-4 px-4 sm:grid-cols-2 lg:grid-cols-4 lg:px-6"
      data-testid="kpi-grid"
    >
      {KPI_LABELS.map((label) => (
        <KpiCard key={label} label={label} />
      ))}
    </section>
  );
}
