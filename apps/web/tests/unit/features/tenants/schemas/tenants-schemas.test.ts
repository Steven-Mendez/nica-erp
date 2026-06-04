import { describe, expect, it } from "vitest";
import {
  createTenantSchema,
  inviteMemberSchema,
  updateMemberRoleSchema,
  updateTenantSchema,
} from "@/features/tenants/schemas";
import { DEPARTAMENTOS } from "@/features/tenants/lib/departamentos";

const VALID_RUC = "0010101800010X";
const VALID_DGI = { number: "DGI-1", valid_from: "2026-01-01", valid_to: "2026-12-31" };

describe("createTenantSchema (post-ADR-0034 soft creation)", () => {
  it("accepts a name-only payload", () => {
    expect(createTenantSchema.safeParse({ name: "Mi Empresa" }).success).toBe(true);
  });

  it("requires a non-empty name", () => {
    const result = createTenantSchema.safeParse({ name: "" });
    expect(result.success).toBe(false);
    if (!result.success) {
      const issue = result.error.issues.find((i) => i.path[0] === "name");
      expect(issue?.message).toBe("El nombre es obligatorio.");
    }
  });

  it("accepts every fiscal field when provided in a valid shape", () => {
    const result = createTenantSchema.safeParse({
      name: "Mi Empresa",
      ruc: VALID_RUC,
      regime: "general",
      departamento: "Managua",
      municipality: "Distrito V",
      authorization_dgi: VALID_DGI,
      fiscal_address: "Calle 1",
      is_withholder: true,
    });
    expect(result.success).toBe(true);
  });

  it("rejects a malformed RUC with Spanish copy", () => {
    const result = createTenantSchema.safeParse({ name: "Mi Empresa", ruc: "abc" });
    expect(result.success).toBe(false);
    if (!result.success) {
      const issue = result.error.issues.find((i) => i.path[0] === "ruc");
      expect(issue?.message).toContain("13 dígitos");
    }
  });

  it("rejects a departamento outside the canonical catalog", () => {
    const result = createTenantSchema.safeParse({
      name: "Mi Empresa",
      departamento: "Atlántida",
    });
    expect(result.success).toBe(false);
  });

  it("accepts every canonical departamento", () => {
    for (const d of DEPARTAMENTOS) {
      const result = createTenantSchema.safeParse({ name: "Mi Empresa", departamento: d });
      expect(result.success).toBe(true);
    }
  });

  it("accepts a free-text municipality", () => {
    const result = createTenantSchema.safeParse({
      name: "Mi Empresa",
      departamento: "Managua",
      municipality: "Distrito V",
    });
    expect(result.success).toBe(true);
  });

  it("rejects an unknown regime", () => {
    expect(createTenantSchema.safeParse({ name: "Mi Empresa", regime: "fancy" }).success).toBe(
      false,
    );
  });

  it("rejects a DGI block with a non-ISO date", () => {
    const result = createTenantSchema.safeParse({
      name: "Mi Empresa",
      authorization_dgi: { ...VALID_DGI, valid_from: "2026/01/01" },
    });
    expect(result.success).toBe(false);
  });
});

describe("updateTenantSchema", () => {
  it("accepts a partial update", () => {
    expect(updateTenantSchema.safeParse({ name: "Otro" }).success).toBe(true);
    expect(updateTenantSchema.safeParse({}).success).toBe(true);
  });

  it("rejects unknown keys (strict)", () => {
    expect(updateTenantSchema.safeParse({ name: "Otro", evil: "x" }).success).toBe(false);
  });

  it("rejects empty name when provided", () => {
    const result = updateTenantSchema.safeParse({ name: "" });
    expect(result.success).toBe(false);
  });
});

describe("inviteMemberSchema", () => {
  it("accepts a valid invite", () => {
    expect(
      inviteMemberSchema.safeParse({ email: "ada@nica.test", proposed_role: "admin" }).success,
    ).toBe(true);
  });

  it("rejects owner as a proposed role (single-owner invariant)", () => {
    expect(
      inviteMemberSchema.safeParse({ email: "ada@nica.test", proposed_role: "owner" }).success,
    ).toBe(false);
  });

  it("rejects an invalid email", () => {
    expect(inviteMemberSchema.safeParse({ email: "nope", proposed_role: "admin" }).success).toBe(
      false,
    );
  });
});

describe("updateMemberRoleSchema", () => {
  it("accepts each non-owner role", () => {
    for (const role of ["admin", "accountant", "salesperson", "viewer"]) {
      expect(updateMemberRoleSchema.safeParse({ role }).success).toBe(true);
    }
  });

  it("rejects owner (single-owner invariant)", () => {
    expect(updateMemberRoleSchema.safeParse({ role: "owner" }).success).toBe(false);
  });
});
