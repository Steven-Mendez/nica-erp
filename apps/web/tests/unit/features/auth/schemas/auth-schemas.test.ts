import { describe, expect, it } from "vitest";
import {
  changePasswordSchema,
  confirmSchema,
  forgotSchema,
  loginSchema,
  resetSchema,
  signupSchema,
  updateMeSchema,
} from "@/features/auth/schemas";

const STRONG_PASSWORD = "Abcdefgh1234!";

describe("signupSchema", () => {
  it("accepts a valid signup with matching passwords", () => {
    const result = signupSchema.safeParse({
      email: "ada@nica.test",
      password: STRONG_PASSWORD,
      confirm_password: STRONG_PASSWORD,
    });
    expect(result.success).toBe(true);
  });

  it("rejects mismatched passwords with Spanish copy on confirm_password", () => {
    const result = signupSchema.safeParse({
      email: "ada@nica.test",
      password: STRONG_PASSWORD,
      confirm_password: `${STRONG_PASSWORD}x`,
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const issue = result.error.issues.find((i) => i.path[0] === "confirm_password");
      expect(issue?.message).toBe("Las contraseñas no coinciden.");
    }
  });

  it("rejects a weak password", () => {
    const result = signupSchema.safeParse({
      email: "ada@nica.test",
      password: "short",
      confirm_password: "short",
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const issue = result.error.issues.find((i) => i.path[0] === "password");
      expect(issue?.message).toContain("al menos 8 caracteres");
    }
  });

  it("rejects an invalid email with Spanish copy", () => {
    const result = signupSchema.safeParse({
      email: "not-an-email",
      password: STRONG_PASSWORD,
      confirm_password: STRONG_PASSWORD,
    });
    expect(result.success).toBe(false);
    if (!result.success) {
      const issue = result.error.issues.find((i) => i.path[0] === "email");
      expect(issue?.message).toBe("Ingresa un correo válido.");
    }
  });
});

describe("confirmSchema", () => {
  it("accepts a 4–10 char code", () => {
    expect(confirmSchema.safeParse({ email: "x@y.test", code: "1234" }).success).toBe(true);
    expect(confirmSchema.safeParse({ email: "x@y.test", code: "1234567890" }).success).toBe(true);
  });

  it("rejects codes shorter than 4 characters", () => {
    const result = confirmSchema.safeParse({ email: "x@y.test", code: "1" });
    expect(result.success).toBe(false);
  });

  it("rejects codes longer than 10 characters", () => {
    const result = confirmSchema.safeParse({ email: "x@y.test", code: "12345678901" });
    expect(result.success).toBe(false);
  });
});

describe("loginSchema", () => {
  it("requires an email and a non-empty password (no strength check at login)", () => {
    expect(loginSchema.safeParse({ email: "ada@nica.test", password: "anything" }).success).toBe(
      true,
    );
    const empty = loginSchema.safeParse({ email: "ada@nica.test", password: "" });
    expect(empty.success).toBe(false);
  });
});

describe("forgotSchema", () => {
  it("requires only an email", () => {
    expect(forgotSchema.safeParse({ email: "ada@nica.test" }).success).toBe(true);
  });
});

describe("resetSchema", () => {
  it("accepts a strong new password with a valid code", () => {
    const result = resetSchema.safeParse({
      email: "ada@nica.test",
      code: "1234",
      new_password: STRONG_PASSWORD,
    });
    expect(result.success).toBe(true);
  });

  it("rejects a weak new password", () => {
    const result = resetSchema.safeParse({
      email: "ada@nica.test",
      code: "1234",
      new_password: "weak",
    });
    expect(result.success).toBe(false);
  });
});

describe("changePasswordSchema", () => {
  it("requires the old password and a strong new password", () => {
    expect(
      changePasswordSchema.safeParse({
        old_password: "old",
        new_password: STRONG_PASSWORD,
      }).success,
    ).toBe(true);
  });

  it("rejects empty old_password", () => {
    expect(
      changePasswordSchema.safeParse({ old_password: "", new_password: STRONG_PASSWORD }).success,
    ).toBe(false);
  });
});

describe("updateMeSchema", () => {
  it("accepts a partial profile update", () => {
    expect(updateMeSchema.safeParse({ display_name: "Ada" }).success).toBe(true);
    expect(updateMeSchema.safeParse({ timezone: "America/Managua" }).success).toBe(true);
    expect(updateMeSchema.safeParse({}).success).toBe(true);
  });

  it("rejects display_name longer than 120 characters", () => {
    const longName = "x".repeat(121);
    expect(updateMeSchema.safeParse({ display_name: longName }).success).toBe(false);
  });
});
