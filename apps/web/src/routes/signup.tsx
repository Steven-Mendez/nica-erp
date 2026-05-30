// apps/web/src/routes/signup.tsx
//
// Sign-up route — shadcn login-02 layout. POST /v1/auth/register, then nudge
// the user to /confirm with the email in search params. Uses react-hook-form
// + zodResolver — passwords-do-not-match revalidates on every keystroke after
// the first failed submit. The password field has a show/hide toggle; the
// confirm field stays masked (the whole point of the confirm is typing it
// blind).

import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { Eye, EyeOff } from "lucide-react";
import { useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, FieldDescription, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useRegisterMutation } from "@/features/auth/api/hooks";
import { AuthLayout } from "@/features/auth/components/AuthLayout";
import { signupSchema, type SignupValues } from "@/features/auth/schemas";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

export function SignupRoute() {
  useDocumentTitle("Crear cuenta");
  const navigate = useNavigate();
  const search = useSearch({ from: "/signup" });
  const mutation = useRegisterMutation();
  const [showPassword, setShowPassword] = useState(false);
  const form = useForm<SignupValues>({
    resolver: zodResolver(signupSchema),
    defaultValues: { email: search.email ?? "", password: "", confirm_password: "" },
    mode: "onSubmit",
    reValidateMode: "onChange",
  });

  const onSubmit = (values: SignupValues): void => {
    // confirm_password is form-only — the API never sees it.
    mutation.mutate(
      { email: values.email, password: values.password },
      {
        onSuccess: () => {
          void navigate({ to: "/confirm", search: { email: values.email } });
        },
      },
    );
  };

  return (
    <AuthLayout>
      <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-6" noValidate>
        <div className="flex flex-col items-center gap-2 text-center">
          <h1 className="text-2xl font-bold">Crea tu cuenta</h1>
          <p className="text-balance text-sm text-muted-foreground">
            Te enviaremos un código de verificación a tu correo
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
                <FieldLabel htmlFor="password">Contraseña</FieldLabel>
                <div className="relative">
                  <Input
                    {...field}
                    id="password"
                    type={showPassword ? "text" : "password"}
                    autoComplete="new-password"
                    required
                    className="pr-10"
                    aria-invalid={fieldState.invalid}
                  />
                  <button
                    type="button"
                    onClick={() => setShowPassword((prev) => !prev)}
                    aria-label={showPassword ? "Ocultar contraseña" : "Mostrar contraseña"}
                    aria-pressed={showPassword}
                    className="absolute right-2 top-1/2 flex h-7 w-7 -translate-y-1/2 items-center justify-center rounded-md text-muted-foreground hover:text-foreground focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    {showPassword ? <EyeOff className="h-4 w-4" /> : <Eye className="h-4 w-4" />}
                  </button>
                </div>
                {fieldState.invalid ? (
                  <FieldError errors={[fieldState.error]} />
                ) : (
                  <FieldDescription>
                    12+ caracteres con mayúscula, minúscula, dígito y símbolo.
                  </FieldDescription>
                )}
              </Field>
            )}
          />
          <Controller
            name="confirm_password"
            control={form.control}
            render={({ field, fieldState }) => (
              <Field data-invalid={fieldState.invalid}>
                <FieldLabel htmlFor="confirm_password">Confirmar contraseña</FieldLabel>
                <Input
                  {...field}
                  id="confirm_password"
                  type="password"
                  autoComplete="new-password"
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
                No se pudo crear la cuenta. Prueba con otro correo o contraseña.
              </AlertDescription>
            </Alert>
          ) : null}
          <Button type="submit" className="w-full" disabled={mutation.isPending}>
            {mutation.isPending ? "Creando cuenta..." : "Crear cuenta"}
          </Button>
        </FieldGroup>
        <div className="text-center text-sm">
          ¿Ya tienes cuenta?{" "}
          <Link to="/login" className="underline underline-offset-4">
            Inicia sesión
          </Link>
        </div>
      </form>
    </AuthLayout>
  );
}
