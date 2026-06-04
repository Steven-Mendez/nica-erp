// apps/web/src/features/auth/lib/password-policy.ts
//
// Canonical password policy for every password-acceptance form (signup,
// reset, change). The Spanish help text and the zod schema live here so
// both /signup and /reset-password render the same rule (audit F-036).

import { z } from "zod";

export const PASSWORD_POLICY_TEXT = "12+ caracteres con mayúscula, minúscula, dígito y símbolo.";

export const PASSWORD_MIN_LENGTH = 12;
export const PASSWORD_MAX_LENGTH = 128;

export const passwordPolicySchema = z
  .string()
  .min(PASSWORD_MIN_LENGTH, {
    message: `La contraseña debe tener al menos ${PASSWORD_MIN_LENGTH} caracteres.`,
  })
  .max(PASSWORD_MAX_LENGTH, {
    message: `La contraseña no puede exceder ${PASSWORD_MAX_LENGTH} caracteres.`,
  })
  .regex(/[A-Z]/, { message: "La contraseña debe incluir una letra mayúscula." })
  .regex(/[a-z]/, { message: "La contraseña debe incluir una letra minúscula." })
  .regex(/\d/, { message: "La contraseña debe incluir un dígito." })
  .regex(/[\^$*.[\]{}()?\-"!@#%&/\\,><':;|_~`+=]/, {
    message: "La contraseña debe incluir un símbolo.",
  });
