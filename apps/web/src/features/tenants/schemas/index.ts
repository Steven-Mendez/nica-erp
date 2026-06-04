// Zod schemas for tenants forms. Per ADR-0034, only `name` is
// required at creation time. The rest of the fiscal fields stay
// strict-when-present so the future edit flow can reuse the same
// shape.

import { z } from "zod";
import { DEPARTAMENTOS } from "../lib/departamentos";

const rucPattern = z
  .string()
  .regex(/^\d{13}[A-Z]$/u, { message: "13 dígitos + 1 letra mayúscula." });

const isoDate = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/u, { message: "Fecha inválida (AAAA-MM-DD)." });

// Each DGI field is optional individually, but the refinement enforces
// the all-or-nothing rule per audit F-009: if the user fills any field,
// they must fill all three.
const dgiSchema = z
  .object({
    number: z
      .string()
      .max(32, { message: "El número DGI no puede superar los 32 caracteres." })
      .optional(),
    // Accept empty string OR ISO date. The wizard's controllers can
    // emit empty strings when the user clears a date picker.
    valid_from: z.union([z.literal(""), isoDate]).optional(),
    valid_to: z.union([z.literal(""), isoDate]).optional(),
  })
  .superRefine((value, ctx) => {
    const number = (value.number ?? "").trim();
    const validFrom = (value.valid_from ?? "").trim();
    const validTo = (value.valid_to ?? "").trim();
    const filled = [number, validFrom, validTo].filter((v) => v.length > 0);
    if (filled.length === 0 || filled.length === 3) {
      return;
    }
    if (number === "") {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["number"],
        message: "Obligatorio si llenas las fechas",
      });
    }
    if (validFrom === "") {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["valid_from"],
        message: "Obligatorio si llenas el número",
      });
    }
    if (validTo === "") {
      ctx.addIssue({
        code: z.ZodIssueCode.custom,
        path: ["valid_to"],
        message: "Obligatorio si llenas el número",
      });
    }
  });

export const createTenantSchema = z.object({
  name: z
    .string()
    .min(1, { message: "El nombre es obligatorio." })
    .max(200, { message: "El nombre no puede superar los 200 caracteres." }),
  ruc: rucPattern.optional(),
  regime: z.enum(["general", "cuota_fija", "pequeno_contribuyente"]).optional(),
  // Audit F-006: the wizard used to collect `municipality` from the
  // 17-value department list (mislabelled). The canonical model splits
  // this into `departamento` (enum) + `municipality` (free text).
  departamento: z.enum(DEPARTAMENTOS).optional(),
  municipality: z
    .string()
    .max(120, { message: "El municipio no puede superar 120 caracteres." })
    .optional(),
  authorization_dgi: dgiSchema.optional(),
  fiscal_address: z
    .string()
    .min(1, { message: "La dirección fiscal es obligatoria." })
    .max(500, { message: "La dirección fiscal no puede superar los 500 caracteres." })
    .optional(),
  is_withholder: z.boolean().optional(),
});

export type CreateTenantValues = z.infer<typeof createTenantSchema>;

export const updateTenantSchema = z
  .object({
    name: z
      .string()
      .min(1, { message: "El nombre es obligatorio." })
      .max(200, { message: "El nombre no puede superar los 200 caracteres." })
      .optional(),
    regime: z
      .enum(["general", "simplified"], { message: "Selecciona un régimen válido." })
      .optional(),
    departamento: z
      .enum(DEPARTAMENTOS, { message: "Selecciona un departamento válido." })
      .optional(),
    municipality: z
      .string()
      .max(120, { message: "El municipio no puede superar 120 caracteres." })
      .optional(),
    fiscal_address: z
      .string()
      .min(1, { message: "La dirección fiscal es obligatoria." })
      .max(500, { message: "La dirección fiscal no puede superar los 500 caracteres." })
      .optional(),
    is_withholder: z.boolean().optional(),
  })
  .strict();

export type UpdateTenantValues = z.infer<typeof updateTenantSchema>;

export const inviteMemberSchema = z.object({
  email: z.string().email({ message: "Ingresa un correo válido." }),
  proposed_role: z.enum(["admin", "accountant", "salesperson", "viewer"], {
    message: "Selecciona un rol válido.",
  }),
});

export type InviteMemberValues = z.infer<typeof inviteMemberSchema>;

export const updateMemberRoleSchema = z.object({
  role: z.enum(["admin", "accountant", "salesperson", "viewer"], {
    message: "Selecciona un rol válido.",
  }),
});

export type UpdateMemberRoleValues = z.infer<typeof updateMemberRoleSchema>;
