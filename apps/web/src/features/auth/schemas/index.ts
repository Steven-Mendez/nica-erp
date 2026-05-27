// apps/web/src/features/auth/schemas/index.ts
//
// Zod schemas for the auth feature forms. Wire-format types (e.g. `Me`,
// `UpdateMeInput`) live in `@/features/auth/api/endpoints` — they describe
// the server contract, not user input.
//
// Password rule mirrors the backend Identity-domain policy:
//   - minimum 12 characters
//   - at least one upper-case, one lower-case, one digit, one symbol

import { z } from "zod";

const emailSchema = z.string().trim().email({ message: "Enter a valid email address." });

const passwordSchema = z
  .string()
  .min(12, { message: "Password must be at least 12 characters." })
  .regex(/[A-Z]/, { message: "Password must include an upper-case letter." })
  .regex(/[a-z]/, { message: "Password must include a lower-case letter." })
  .regex(/\d/, { message: "Password must include a digit." })
  .regex(/[\^$*.[\]{}()?\-"!@#%&/\\,><':;|_~`+=]/, {
    message: "Password must include a symbol.",
  });

const confirmationCodeSchema = z
  .string()
  .trim()
  .min(4, { message: "Enter the confirmation code from your email." })
  .max(10, { message: "Confirmation code looks too long." });

export const signupSchema = z
  .object({
    email: emailSchema,
    password: passwordSchema,
    confirm_password: z.string().min(1, { message: "Please confirm your password." }),
  })
  .refine((data) => data.password === data.confirm_password, {
    message: "Passwords do not match.",
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
  password: z.string().min(1, { message: "Password is required." }),
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
  old_password: z.string().min(1, { message: "Current password is required." }),
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
