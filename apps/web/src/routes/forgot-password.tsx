// apps/web/src/routes/forgot-password.tsx
//
// Forgot-password route — shadcn login-02 layout, RHF + zodResolver. POST
// /v1/auth/password/forgot (enumeration-resistant) then forward to
// /reset-password.

import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate } from "@tanstack/react-router";
import { Controller, useForm } from "react-hook-form";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useForgotPasswordMutation } from "@/features/auth/api/hooks";
import { AuthLayout } from "@/features/auth/components/AuthLayout";
import { forgotSchema, type ForgotValues } from "@/features/auth/schemas";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

export function ForgotPasswordRoute() {
  useDocumentTitle("Restablecer contraseña");
  const navigate = useNavigate();
  const mutation = useForgotPasswordMutation();
  const form = useForm<ForgotValues>({
    resolver: zodResolver(forgotSchema),
    defaultValues: { email: "" },
    mode: "onSubmit",
    reValidateMode: "onChange",
  });

  const onSubmit = (values: ForgotValues): void => {
    mutation.mutate(values, {
      onSuccess: () => {
        void navigate({ to: "/reset-password", search: { email: values.email } });
      },
    });
  };

  return (
    <AuthLayout>
      <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-6" noValidate>
        <div className="flex flex-col items-center gap-2 text-center">
          <h1 className="text-2xl font-bold">Recupera tu contraseña</h1>
          <p className="text-balance text-sm text-muted-foreground">
            Si el correo está registrado, te enviaremos un código de recuperación
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
                  placeholder="usuario@ejemplo.com"
                  required
                  aria-invalid={fieldState.invalid}
                />
                {fieldState.invalid ? <FieldError errors={[fieldState.error]} /> : null}
              </Field>
            )}
          />
          {mutation.isSuccess ? (
            <Alert variant="success">
              <AlertDescription>
                Si el correo está registrado, te enviamos un código de recuperación.
              </AlertDescription>
            </Alert>
          ) : null}
          <Button type="submit" className="w-full" disabled={mutation.isPending}>
            {mutation.isPending ? "Enviando..." : "Enviar código"}
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
