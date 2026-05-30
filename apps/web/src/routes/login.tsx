// apps/web/src/routes/login.tsx
//
// Login route — shadcn login-02 layout (split screen, no Card). Uses
// react-hook-form + zodResolver. Re-validation fires on each keystroke after
// the first failed submit, so users see live feedback as they correct typos.

import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate } from "@tanstack/react-router";
import { Controller, useForm } from "react-hook-form";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useLoginMutation } from "@/features/auth/api/hooks";
import { AuthLayout } from "@/features/auth/components/AuthLayout";
import { loginSchema, type LoginValues } from "@/features/auth/schemas";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

export function LoginRoute() {
  useDocumentTitle("Iniciar sesión");
  const navigate = useNavigate();
  const mutation = useLoginMutation();
  const form = useForm<LoginValues>({
    resolver: zodResolver(loginSchema),
    defaultValues: { email: "", password: "" },
    mode: "onSubmit",
    reValidateMode: "onChange",
  });

  const onSubmit = (values: LoginValues): void => {
    mutation.mutate(values, {
      onSuccess: () => {
        // Route through the index — the guard there decides whether
        // to send the user to /welcome (no profile), /onboarding (no
        // memberships), /tenants (no active tenant) or /dashboard.
        void navigate({ to: "/" });
      },
    });
  };

  return (
    <AuthLayout>
      <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-6" noValidate>
        <div className="flex flex-col items-center gap-2 text-center">
          <h1 className="text-2xl font-bold">Inicia sesión en tu cuenta</h1>
          <p className="text-balance text-sm text-muted-foreground">
            Ingresa tu correo para acceder a tu cuenta
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
          <Controller
            name="password"
            control={form.control}
            render={({ field, fieldState }) => (
              <Field data-invalid={fieldState.invalid}>
                <div className="flex items-center">
                  <FieldLabel htmlFor="password">Contraseña</FieldLabel>
                  <Link
                    to="/forgot-password"
                    className="ml-auto inline-block text-sm underline-offset-4 hover:underline"
                  >
                    ¿Olvidaste tu contraseña?
                  </Link>
                </div>
                <Input
                  {...field}
                  id="password"
                  type="password"
                  autoComplete="current-password"
                  required
                  aria-invalid={fieldState.invalid}
                />
                {fieldState.invalid ? <FieldError errors={[fieldState.error]} /> : null}
              </Field>
            )}
          />
          {mutation.isError ? (
            <Alert variant="destructive">
              <AlertDescription>
                No se pudo iniciar sesión. Revisa tus credenciales.
              </AlertDescription>
            </Alert>
          ) : null}
          <Button type="submit" className="w-full" disabled={mutation.isPending}>
            {mutation.isPending ? "Iniciando sesión..." : "Iniciar sesión"}
          </Button>
        </FieldGroup>
        <div className="text-center text-sm">
          ¿No tienes cuenta?{" "}
          <Link to="/signup" className="underline underline-offset-4">
            Regístrate
          </Link>
        </div>
      </form>
    </AuthLayout>
  );
}
