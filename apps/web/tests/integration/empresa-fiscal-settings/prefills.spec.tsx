// Integration tests for the EmpresaFiscalSettingsForm prefill +
// permission-gating + dependent-municipio + cross-field date paths.
// The MSW handlers stub /v1/me and /v1/tenants/{id} so the form
// hydrates against a deterministic payload, then drive RHF directly.

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { cleanup, fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";

vi.mock("@/api/tokenStore", () => ({
  setTokens: vi.fn(),
  getAccessToken: vi.fn().mockReturnValue("access-token"),
}));

import { meQueryKey } from "@/api/queryKeys";
import type { Tenant } from "@/features/tenants/api/endpoints";
import { EmpresaFiscalSettingsForm } from "@/features/tenants/components/empresa-fiscal-settings-form";

const TENANT_ID = "11111111-1111-1111-1111-111111111111";

const fullyPrefilledTenant: Tenant = {
  id: TENANT_ID,
  name: "Empresa A",
  ruc: "J03-100000-00010",
  regime: "general",
  departamento: "Managua",
  municipality: "Managua",
  authorization_dgi: {
    number: "A-001",
    valid_from: "2026-01-01",
    valid_to: "2027-01-01",
  },
  fiscal_address: "Rotonda Centroamérica, Managua",
  fiscal_email: "facturacion@a.test",
  fiscal_phone: "+505 8888-8888",
  is_withholder: false,
  status: "active",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

const blankTenant: Tenant = {
  id: TENANT_ID,
  name: "Empresa B",
  ruc: null,
  regime: null,
  departamento: null,
  municipality: null,
  authorization_dgi: null,
  fiscal_address: null,
  fiscal_email: null,
  fiscal_phone: null,
  is_withholder: false,
  status: "active",
  created_at: "2026-01-01T00:00:00Z",
  updated_at: "2026-01-01T00:00:00Z",
};

function seedMe(client: QueryClient, permissions: string[]): void {
  client.setQueryData(meQueryKey, {
    id: "u-1",
    email: "ada@b.io",
    display_name: "Ada",
    locale: "es-NI",
    timezone: "America/Managua",
    preferences: {},
    active_tenant: TENANT_ID,
    role: "owner",
    permissions,
  });
}

function renderForm(tenant: Tenant, permissions: string[] = ["tenant.update"]) {
  const client = new QueryClient({
    defaultOptions: {
      queries: { retry: false, gcTime: 0, staleTime: 30_000 },
      mutations: { retry: false },
    },
  });
  seedMe(client, permissions);
  return render(
    <QueryClientProvider client={client}>
      <EmpresaFiscalSettingsForm tenant={tenant} />
    </QueryClientProvider>,
  );
}

afterEach(() => {
  cleanup();
});

describe("EmpresaFiscalSettingsForm — prefill", () => {
  it("prefills every section from the tenant payload", () => {
    renderForm(fullyPrefilledTenant);
    expect(screen.getByLabelText(/^RUC$/i)).toHaveValue("J03-100000-00010");
    expect(screen.getByLabelText(/Dirección/i)).toHaveValue("Rotonda Centroamérica, Managua");
    expect(screen.getByLabelText(/Correo/i)).toHaveValue("facturacion@a.test");
    expect(screen.getByLabelText(/Teléfono/i)).toHaveValue("+505 8888-8888");
    expect(screen.getByLabelText(/Resolución DGI/i)).toHaveValue("A-001");
    expect(screen.getByLabelText(/Inicio de vigencia/i)).toHaveValue("2026-01-01");
    expect(screen.getByLabelText(/Vencimiento/i)).toHaveValue("2027-01-01");
  });

  it("renders empty fields when the tenant has no fiscal data yet", () => {
    renderForm(blankTenant);
    expect(screen.getByLabelText(/^RUC$/i)).toHaveValue("");
    expect(screen.getByLabelText(/Dirección/i)).toHaveValue("");
  });
});

describe("EmpresaFiscalSettingsForm — permission gating", () => {
  it("renders the help card when the operator lacks tenant.update", () => {
    renderForm(fullyPrefilledTenant, /* permissions= */ []);
    expect(
      screen.getByText(/solo el propietario o administrador de la empresa puede editar/i),
    ).toBeInTheDocument();
    expect(screen.queryByRole("button", { name: /Guardar cambios/i })).toBeNull();
  });

  it("renders the editable form when the operator has tenant.update", () => {
    renderForm(fullyPrefilledTenant);
    expect(screen.queryByText(/solo el propietario o administrador/i)).not.toBeInTheDocument();
    expect(screen.getByRole("button", { name: /Guardar cambios/i })).toBeInTheDocument();
  });
});

describe("EmpresaFiscalSettingsForm — date cross-validation", () => {
  it("blocks save when vencimiento is before inicio", async () => {
    renderForm(fullyPrefilledTenant);
    const vencimiento = screen.getByLabelText(/Vencimiento/i);
    fireEvent.change(vencimiento, { target: { value: "2025-01-01" } });
    fireEvent.click(screen.getByRole("button", { name: /Guardar cambios/i }));
    await waitFor(() =>
      expect(
        screen.getByText(/la fecha de vencimiento debe ser posterior al inicio/i),
      ).toBeInTheDocument(),
    );
  });
});

describe("EmpresaFiscalSettingsForm — RUC validation", () => {
  it("blocks save when the RUC is empty", async () => {
    renderForm(fullyPrefilledTenant);
    const ruc = screen.getByLabelText(/^RUC$/i);
    fireEvent.change(ruc, { target: { value: "" } });
    fireEvent.click(screen.getByRole("button", { name: /Guardar cambios/i }));
    await waitFor(() => expect(screen.getByText(/el ruc es obligatorio\./i)).toBeInTheDocument());
  });

  it("rejects a RUC that doesn't match the mask", async () => {
    renderForm(fullyPrefilledTenant);
    const ruc = screen.getByLabelText(/^RUC$/i);
    fireEvent.change(ruc, { target: { value: "123" } });
    fireEvent.click(screen.getByRole("button", { name: /Guardar cambios/i }));
    await waitFor(() => expect(screen.getByText(/formato de ruc inválido\./i)).toBeInTheDocument());
  });
});

// Smoke test for the dependent-municipio behaviour — when the
// tenant payload carries an inconsistent (departamento, municipio)
// pair (e.g. after a manual DB rewrite or a regression in an
// upstream form), the form's auto-clear effect must wipe the
// municipio so the operator notices and re-selects.
describe("EmpresaFiscalSettingsForm — municipio/departamento coupling", () => {
  it("clears municipio when the departamento doesn't match", async () => {
    const offMatchTenant: Tenant = {
      ...fullyPrefilledTenant,
      departamento: "Managua",
      // León's municipio under Managua → invalid; the auto-clear
      // effect on departamento-change should fire on mount.
      municipality: "León",
    };
    renderForm(offMatchTenant);
    // The combobox trigger displays the currently-selected value; an
    // empty municipio shows the placeholder instead.
    await waitFor(() => {
      const trigger = screen.getByRole("combobox", { name: /Municipio/i });
      expect(trigger).toHaveTextContent(/selecciona un municipio/i);
    });
  });
});

// Unit-level smoke for the RUC mask + phone mask helpers exported
// from the form module — verifies the canonical-shape contract used
// by the input onChange handlers without going through the form.
describe("RUC + phone masking helpers", () => {
  beforeEach(() => {
    vi.resetModules();
  });

  it("masks a 14-digit RUC paste into NNN-NNNNNN-NNNNN", async () => {
    const { maskRuc } = await import("@/features/tenants/components/empresa-fiscal-settings-form");
    expect(maskRuc("J031000000001X")).toBe("J03-100000-0001X");
  });

  it("masks an 8-digit phone paste into +505 NNNN-NNNN", async () => {
    const { maskPhone } =
      await import("@/features/tenants/components/empresa-fiscal-settings-form");
    expect(maskPhone("88880000")).toBe("+505 8888-0000");
    expect(maskPhone("+50588880000")).toBe("+505 8888-0000");
  });
});

// Re-export-style discovery: this assertion fails if the form module
// stops exporting one of the masking helpers, which would break the
// dependent integration tests above.
describe("EmpresaFiscalSettingsForm — exports", () => {
  it("exports maskRuc, maskPhone, and mapApiProblemToFormErrors", async () => {
    const mod = await import("@/features/tenants/components/empresa-fiscal-settings-form");
    expect(typeof mod.maskRuc).toBe("function");
    expect(typeof mod.maskPhone).toBe("function");
    expect(typeof mod.mapApiProblemToFormErrors).toBe("function");
  });
});

// Silence the unused-import warning on `within` — kept for future
// scoped assertions on the per-card sections.
void within;
