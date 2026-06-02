// Zod schema for the empresa fiscal-settings editor. The four
// sections — Identificación, Dirección, Vigencia DGI, Contacto —
// match the spec's field list. Spanish error messages render
// inline on the form via RHF + zodResolver; the same messages flow
// through the FormErrorAlert when the backend rejects with a
// problem-detail body.

import { z } from "zod";
import { isValidMunicipio } from "../data/nicaragua-geography";

// RUC mask: `NNN-NNNNNN-NNNNN`. We accept either the masked form or
// the bare 14-character form (the input mask emits the masked form
// but a paste may carry digits only). Normalisation to the masked
// form happens at submit time, not in the schema.
const RUC_PATTERN = /^(\d{3}-\d{6}-\d{4}[A-Z0-9]|\d{13}[A-Z0-9])$/;

// `+505 NNNN-NNNN` canonical shape. Backend's FiscalPhone VO insists
// on this exact format; the SPA's input mask emits it.
const PHONE_PATTERN = /^\+505 \d{4}-\d{4}$/;

const REGIMEN_VALUES = ["general", "cuota_fija", "pequeno_contribuyente"] as const;

export const empresaFiscalSettingsSchema = z
  .object({
    // --- Identificación fiscal --------------------------------------
    ruc: z
      .string()
      .min(1, { message: "El RUC es obligatorio." })
      .regex(RUC_PATTERN, { message: "Formato de RUC inválido." }),
    regimen: z.enum(REGIMEN_VALUES, {
      errorMap: () => ({ message: "Selecciona un régimen." }),
    }),
    retenedor: z.boolean(),

    // --- Dirección fiscal -------------------------------------------
    departamento: z
      .string()
      .min(1, { message: "Selecciona un departamento." }),
    municipio: z.string().min(1, { message: "Selecciona un municipio." }),
    direccion: z
      .string()
      .min(10, { message: "Ingresa al menos 10 caracteres." })
      .max(500, { message: "Máximo 500 caracteres." }),

    // --- Vigencia DGI -----------------------------------------------
    resolucion_dgi: z
      .string()
      .min(1, { message: "Ingresa el número de resolución DGI." })
      .max(32, { message: "Máximo 32 caracteres." }),
    vigencia_inicio: z
      .string()
      .min(1, { message: "Selecciona la fecha de inicio de vigencia." }),
    vigencia_vencimiento: z
      .string()
      .min(1, { message: "Selecciona la fecha de vencimiento." }),

    // --- Contacto fiscal --------------------------------------------
    correo_fiscal: z
      .string()
      .min(1, { message: "El correo es obligatorio." })
      .email({ message: "Correo inválido." }),
    telefono_fiscal: z
      .string()
      .min(1, { message: "El teléfono es obligatorio." })
      .regex(PHONE_PATTERN, { message: "Formato de teléfono inválido." }),
  })
  .superRefine((data, ctx) => {
    // Cross-field: vencimiento must be >= inicio.
    if (data.vigencia_inicio && data.vigencia_vencimiento) {
      if (data.vigencia_vencimiento < data.vigencia_inicio) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["vigencia_vencimiento"],
          message: "La fecha de vencimiento debe ser posterior al inicio.",
        });
      }
    }
    // Cross-field: municipio must belong to departamento.
    if (data.departamento && data.municipio) {
      if (!isValidMunicipio(data.departamento, data.municipio)) {
        ctx.addIssue({
          code: z.ZodIssueCode.custom,
          path: ["municipio"],
          message: "El municipio no pertenece al departamento seleccionado.",
        });
      }
    }
  });

export type EmpresaFiscalSettingsValues = z.infer<
  typeof empresaFiscalSettingsSchema
>;

export const EMPRESA_FISCAL_REGIMEN_LABELS: Record<
  (typeof REGIMEN_VALUES)[number],
  string
> = {
  general: "Régimen general",
  cuota_fija: "Cuota fija",
  pequeno_contribuyente: "Pequeño contribuyente",
};
