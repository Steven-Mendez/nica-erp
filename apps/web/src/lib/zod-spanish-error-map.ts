// apps/web/src/lib/zod-spanish-error-map.ts
//
// Global zod error map so that the default English messages
// (`Required`, `Invalid`, etc.) never reach the UI (audit F-010).
// Registered once at bootstrap via `z.setErrorMap`.

import { z } from "zod";

export const spanishErrorMap: z.ZodErrorMap = (issue, ctx) => {
  switch (issue.code) {
    case z.ZodIssueCode.invalid_type: {
      if (issue.received === "undefined" || issue.received === "null") {
        return { message: "Obligatorio" };
      }
      return { message: "Valor inválido" };
    }
    case z.ZodIssueCode.too_small: {
      if (issue.type === "string") {
        return issue.minimum === 1
          ? { message: "Obligatorio" }
          : { message: `Debe tener al menos ${issue.minimum} caracteres.` };
      }
      if (issue.type === "number") {
        return { message: `Debe ser al menos ${issue.minimum}.` };
      }
      if (issue.type === "array") {
        return { message: `Debe tener al menos ${issue.minimum} elementos.` };
      }
      return { message: "Valor demasiado pequeño." };
    }
    case z.ZodIssueCode.too_big: {
      if (issue.type === "string") {
        return { message: `Debe tener como máximo ${issue.maximum} caracteres.` };
      }
      if (issue.type === "number") {
        return { message: `Debe ser como máximo ${issue.maximum}.` };
      }
      if (issue.type === "array") {
        return { message: `Debe tener como máximo ${issue.maximum} elementos.` };
      }
      return { message: "Valor demasiado grande." };
    }
    case z.ZodIssueCode.invalid_string: {
      if (issue.validation === "email") return { message: "Correo inválido." };
      if (issue.validation === "url") return { message: "URL inválida." };
      if (issue.validation === "uuid") return { message: "UUID inválido." };
      return { message: "Valor inválido" };
    }
    case z.ZodIssueCode.invalid_enum_value: {
      return { message: "Valor inválido" };
    }
    case z.ZodIssueCode.custom: {
      return { message: ctx.defaultError || "Valor inválido" };
    }
    default:
      return { message: ctx.defaultError };
  }
};
