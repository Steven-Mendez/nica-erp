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
import {
  Field,
  FieldError,
  FieldGroup,
  FieldLabel,
} from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import { useConfirmSignupMutation, useResendCodeMutation } from "@/features/auth/api/hooks";
import { AuthLayout } from "@/features/auth/components/AuthLayout";
import { confirmSchema, type ConfirmValues } from "@/features/auth/schemas";
import { useDocumentTitle } from "@/lib/useDocumentTitle";

export function ConfirmRoute() {
  useDocumentTitle("Confirm email");
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
    confirmMutation.mutate(values, {
      onSuccess: () => {
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
          <h1 className="text-2xl font-bold">Confirm your email</h1>
          <p className="text-balance text-sm text-muted-foreground">
            Enter the 6-digit code we sent to your inbox
          </p>
        </div>
        <FieldGroup>
          <Controller
            name="email"
            control={form.control}
            render={({ field, fieldState }) => (
              <Field data-invalid={fieldState.invalid}>
                <FieldLabel htmlFor="email">Email</FieldLabel>
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
                <FieldLabel htmlFor="code">Verification code</FieldLabel>
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
          {confirmMutation.isError ? (
            <Alert variant="destructive">
              <AlertDescription>
                Confirmation failed. Check the code and try again.
              </AlertDescription>
            </Alert>
          ) : null}
          {resendMutation.isSuccess ? (
            <Alert variant="success">
              <AlertDescription>A new code is on the way.</AlertDescription>
            </Alert>
          ) : null}
          <Button type="submit" className="w-full" disabled={confirmMutation.isPending}>
            {confirmMutation.isPending ? "Confirming..." : "Confirm"}
          </Button>
          <Button
            type="button"
            variant="outline"
            className="w-full"
            onClick={onResend}
            disabled={resendMutation.isPending || form.watch("email").trim() === ""}
          >
            {resendMutation.isPending ? "Resending..." : "Resend code"}
          </Button>
        </FieldGroup>
        <div className="text-center text-sm">
          <Link to="/login" className="underline underline-offset-4">
            Back to sign in
          </Link>
        </div>
      </form>
    </AuthLayout>
  );
}
