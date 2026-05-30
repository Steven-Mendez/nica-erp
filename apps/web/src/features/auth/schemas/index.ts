// apps/web/src/features/auth/schemas/index.ts
//
// Zod schemas for the auth feature forms. Wire-format types (e.g. `Me`,
// `UpdateMeInput`) live in `@/features/auth/api/endpoints` — they describe
// the server contract, not user input.
//
// Password rule mirrors the backend Identity-domain policy:
//   - minimum 8 characters
//   - at least one upper-case, one lower-case, one digit, one symbol

import { z } from "zod";

const emailSchema = z.string().trim().email({ message: "Ingresa un correo válido." });

const passwordSchema = z
  .string()
  .min(8, { message: "La contraseña debe tener al menos 8 caracteres." })
  .regex(/[A-Z]/, { message: "La contraseña debe incluir una letra mayúscula." })
  .regex(/[a-z]/, { message: "La contraseña debe incluir una letra minúscula." })
  .regex(/\d/, { message: "La contraseña debe incluir un dígito." })
  .regex(/[\^$*.[\]{}()?\-"!@#%&/\\,><':;|_~`+=]/, {
    message: "La contraseña debe incluir un símbolo.",
  });

const confirmationCodeSchema = z
  .string()
  .trim()
  .min(4, { message: "Ingresa el código de confirmación que recibiste por correo." })
  .max(10, { message: "El código de confirmación es demasiado largo." });

export const signupSchema = z
  .object({
    email: emailSchema,
    password: passwordSchema,
    confirm_password: z.string().min(1, { message: "Confirma tu contraseña." }),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: "Las contraseñas no coinciden.",
    path: ["confirm_password"],
  });
export type SignupValues = z.infer<typeof signupSchema>;

export const confirmSchema = z.object({
  email: emailSchema,
  code: confirmationCodeSchema,
});
export type ConfirmValues = z.infer<typeof confirmSchema>;

export const loginSchema = z.object({
  email: emailSchema,
  password: z.string().min(1, { message: "La contraseña es obligatoria." }),
});
export type LoginValues = z.infer<typeof loginSchema>;

export const forgotSchema = z.object({
  email: emailSchema,
});
export type ForgotValues = z.infer<typeof forgotSchema>;

export const resetSchema = z.object({
  email: emailSchema,
  code: confirmationCodeSchema,
  new_password: passwordSchema,
});
export type ResetValues = z.infer<typeof resetSchema>;

export const changePasswordSchema = z.object({
  old_password: z.string().min(1, { message: "La contraseña actual es obligatoria." }),
  new_password: passwordSchema,
});
export type ChangePasswordValues = z.infer<typeof changePasswordSchema>;

export const updateMeSchema = z
  .object({
    display_name: z.string().min(1).max(120),
    locale: z.string().min(2).max(20),
    timezone: z.string().min(1).max(64),
    preferences: z.record(z.unknown()),
  })
  .partial();
export type UpdateMeValues = z.infer<typeof updateMeSchema>;
