// apps/web/src/routes/confirm.tsx
//
// Email confirmation — shadcn login-02 layout, RHF + zodResolver. POST
// /v1/auth/confirm-signup, then forward to /login. Exposes a "Resend code"
// secondary action.

import { zodResolver } from "@hookform/resolvers/zod";
import { Link, useNavigate, useSearch } from "@tanstack/react-router";
import { Controller, useForm } from "react-hook-form";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import { Field, FieldError, FieldGroup, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { InputOTP, InputOTPGroup, InputOTPSlot } from "@/components/ui/input-otp";
import { useConfirmSignupMutation, useResendCodeMutation } from "@/features/auth/api/hooks";
import { AuthLayout } from "@/features/auth/components/AuthLayout";
import { confirmSchema, type ConfirmValues } from "@/features/auth/schemas";
import { popSignupPassword } from "@/features/auth/signup-handoff";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

export function ConfirmRoute() {
  useDocumentTitle("Confirmar correo");
  const navigate = useNavigate();
  const search = useSearch({ from: "/confirm" });
  const confirmMutation = useConfirmSignupMutation();
  const resendMutation = useResendCodeMutation();
  const form = useForm<ConfirmValues>({
    resolver: zodResolver(confirmSchema),
    defaultValues: { email: search.email ?? "", code: "" },
    mode: "onSubmit",
    reValidateMode: "onChange",
  });

  const onSubmit = (values: ConfirmValues): void => {
    // Read the password handed off by /signup. When present, post it
    // alongside email + code so the backend can authenticate atomically
    // and return tokens; the hook auto-stores them and the SPA's index
    // route lands the user on the right next step. When absent (e.g.
    // after a hard refresh of /confirm), fall back to the historical
    // "navigate to /login" path so the user can finish manually.
    const password = popSignupPassword();
    const body = password !== null ? { ...values, password } : values;
    confirmMutation.mutate(body, {
      onSuccess: (bundle) => {
        if (bundle !== null) {
          void navigate({ to: "/" });
          return;
        }
        void navigate({ to: "/login" });
      },
    });
  };

  const onResend = (): void => {
    const email = form.getValues("email").trim();
    if (email === "") return;
    resendMutation.mutate({ email });
  };

  return (
    <AuthLayout>
      <form onSubmit={form.handleSubmit(onSubmit)} className="flex flex-col gap-6" noValidate>
        <div className="flex flex-col items-center gap-2 text-center">
          <h1 className="text-2xl font-bold">Confirma tu correo</h1>
          <p className="text-balance text-sm text-muted-foreground">
            Ingresa el código de 6 dígitos que enviamos a tu correo
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
                <FieldLabel htmlFor="code">Código de verificación</FieldLabel>
                <InputOTP
                  id="code"
                  maxLength={6}
                  value={field.value}
                  onChange={field.onChange}
                  onBlur={field.onBlur}
                  autoComplete="one-time-code"
                  inputMode="numeric"
                  aria-invalid={fieldState.invalid}
                  containerClassName="justify-center"
                >
                  <InputOTPGroup>
                    <InputOTPSlot index={0} />
                    <InputOTPSlot index={1} />
                    <InputOTPSlot index={2} />
                    <InputOTPSlot index={3} />
                    <InputOTPSlot index={4} />
                    <InputOTPSlot index={5} />
                  </InputOTPGroup>
                </InputOTP>
                {fieldState.invalid ? <FieldError errors={[fieldState.error]} /> : null}
              </Field>
            )}
          />
          {confirmMutation.isError ? (
            <Alert variant="destructive">
              <AlertDescription>
                No se pudo confirmar. Verifica el código e intenta de nuevo.
              </AlertDescription>
            </Alert>
          ) : null}
          {resendMutation.isSuccess ? (
            <Alert variant="success">
              <AlertDescription>Te enviamos un nuevo código.</AlertDescription>
            </Alert>
          ) : null}
          <Button type="submit" className="w-full" disabled={confirmMutation.isPending}>
            {confirmMutation.isPending ? "Confirmando..." : "Confirmar"}
          </Button>
          <Button
            type="button"
            variant="outline"
            className="w-full"
            onClick={onResend}
            disabled={resendMutation.isPending || form.watch("email").trim() === ""}
          >
            {resendMutation.isPending ? "Reenviando..." : "Reenviar código"}
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
