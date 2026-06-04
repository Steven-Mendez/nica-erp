import { describe, expect, it } from "vitest";

import { ROLE_LABELS, roleLabel } from "@/features/tenants/lib/role-labels";

describe("roleLabel", () => {
  it("maps every backend-issued role to its Spanish label", () => {
    expect(ROLE_LABELS.owner).toBe("Propietario");
    expect(ROLE_LABELS.admin).toBe("Administrador");
    expect(ROLE_LABELS.accountant).toBe("Contador");
    expect(ROLE_LABELS.salesperson).toBe("Vendedor");
    expect(ROLE_LABELS.viewer).toBe("Visualizador");
  });

  it("returns the Spanish label via the helper", () => {
    expect(roleLabel("owner")).toBe("Propietario");
    expect(roleLabel("viewer")).toBe("Visualizador");
  });

  it("falls back to the raw role when unknown", () => {
    expect(roleLabel("future_role")).toBe("future_role");
  });
});
