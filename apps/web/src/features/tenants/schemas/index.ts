// Zod schemas for tenants forms. Per ADR-0034, only `name` is
// required at creation time. The rest of the fiscal fields stay
// strict-when-present so the future edit flow can reuse the same
// shape.

import { z } from "zod";
import { MUNICIPALITIES } from "../municipalities";

const rucPattern = z
  .string()
  .regex(/^\d{13}[A-Z]$/u, { message: "13 dígitos + 1 letra mayúscula." });

const isoDate = z
  .string()
  .regex(/^\d{4}-\d{2}-\d{2}$/u, { message: "Fecha inválida (AAAA-MM-DD)." });

const dgiSchema = z.object({
  number: z
    .string()
    .min(1, { message: "El número de autorización DGI es obligatorio." })
    .max(32, { message: "El número DGI no puede superar los 32 caracteres." }),
  valid_from: isoDate,
  valid_to: isoDate,
});

export const createTenantSchema = z.object({
  name: z
    .string()
    .min(1, { message: "El nombre es obligatorio." })
    .max(200, { message: "El nombre no puede superar los 200 caracteres." }),
  ruc: rucPattern.optional(),
  regime: z.enum(["general", "simplified"]).optional(),
  municipality: z.enum(MUNICIPALITIES).optional(),
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
    municipality: z
      .enum(MUNICIPALITIES, { message: "Selecciona un municipio del catálogo." })
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
