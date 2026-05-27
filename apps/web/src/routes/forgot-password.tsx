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
  useDocumentTitle("Reset password");
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
          <h1 className="text-2xl font-bold">Reset your password</h1>
          <p className="text-balance text-sm text-muted-foreground">
            We&apos;ll email you a reset code if the address is on file
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
                  placeholder="m@example.com"
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
                If that address is on file, a reset code is on its way.
              </AlertDescription>
            </Alert>
          ) : null}
          <Button type="submit" className="w-full" disabled={mutation.isPending}>
            {mutation.isPending ? "Sending..." : "Send reset code"}
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
