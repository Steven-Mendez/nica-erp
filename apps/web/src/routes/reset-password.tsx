// apps/web/src/routes/reset-password.tsx
//
// Reset-password route — shadcn login-02 layout, RHF + zodResolver. POST
// /v1/auth/password/reset then forward to /login.

import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { Controller, useForm } from "react-hook-form";
import { FormErrorAlert } from "@/components/form/form-error-alert";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useResetPasswordMutation } from "@/features/auth/api/hooks";
import { AuthLayout } from "@/features/auth/components/AuthLayout";
import { PASSWORD_POLICY_TEXT } from "@/features/auth/lib/password-policy";
import { resetSchema, type ResetValues } from "@/features/auth/schemas";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

export function ResetPasswordRoute() {
  useDocumentTitle("Establecer nueva contraseña");
  const navigate = useNavigate();
  const search = useSearch({ from: "/reset-password" });
  const mutation = useResetPasswordMutation();
  const form = useForm<ResetValues>({
    resolver: zodResolver(resetSchema),
    defaultValues: { email: search.email ?? "", code: "", new_password: "" },
    mode: "onSubmit",
    reValidateMode: "onChange",
  });

  const onSubmit = (values: ResetValues): void => {
    mutation.mutate(values, {
      onSuccess: () => {
        void navigate({ to: "/login" });
      },
    });
  };

  return (
    <AuthLayout>
      <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-6" noValidate>
        <div className="flex flex-col items-center gap-2 text-center">
          <h1 className="text-2xl font-bold">Elige una nueva contraseña</h1>
          <p className="text-balance text-sm text-muted-foreground">
            Ingresa el código que recibiste por correo y elige una contraseña segura
          </p>
        </div>
        <FieldGroup>
          <Controller
            name="email"
            control={form.control}
            render={({ field, fieldState }) => (
              <Field data-invalid={fieldState.invalid}>
                <FieldLabel htmlFor="email">Correo</FieldLabel>
                <Input
                  {...field}
                  id="email"
                  type="email"
                  autoComplete="email"
                  required
                  aria-invalid={fieldState.invalid}
                />
                {fieldState.invalid ? <FieldError errors={[fieldState.error]} /> : null}
              </Field>
            )}
          />
          <Controller
            name="code"
            control={form.control}
            render={({ field, fieldState }) => (
              <Field data-invalid={fieldState.invalid}>
                <FieldLabel htmlFor="code">Código de recuperación</FieldLabel>
                <Input
                  {...field}
                  id="code"
                  type="text"
                  inputMode="numeric"
                  autoComplete="one-time-code"
                  placeholder="123456"
                  required
                  aria-invalid={fieldState.invalid}
                />
                {fieldState.invalid ? <FieldError errors={[fieldState.error]} /> : null}
              </Field>
            )}
          />
          <Controller
            name="new_password"
            control={form.control}
            render={({ field, fieldState }) => (
              <Field data-invalid={fieldState.invalid}>
                <FieldLabel htmlFor="new_password">Nueva contraseña</FieldLabel>
                <Input
                  {...field}
                  id="new_password"
                  type="password"
                  autoComplete="new-password"
                  required
                  aria-invalid={fieldState.invalid}
                />
                {fieldState.invalid ? (
                  <FieldError errors={[fieldState.error]} />
                ) : (
                  <FieldDescription>{PASSWORD_POLICY_TEXT}</FieldDescription>
                )}
              </Field>
            )}
          />
          <FormErrorAlert error={mutation.error} />

          <Button type="submit" className="w-full" disabled={mutation.isPending}>
            {mutation.isPending ? "Restableciendo..." : "Restablecer contraseña"}
          </Button>
        </FieldGroup>
        <div className="text-center text-sm">
          <Link to="/login" className="underline underline-offset-4">
            Volver a iniciar sesión
          </Link>
        </div>
      </form>
    </AuthLayout>
  );
}
