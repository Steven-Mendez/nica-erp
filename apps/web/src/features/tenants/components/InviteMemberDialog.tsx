import { useEffect, useState } from "react";
import { Controller, useForm } from "react-hook-form";
import { zodResolver } from "@hookform/resolvers/zod";
import { UserPlus } from "lucide-react";
import { Alert, AlertDescription } from "@/components/ui/alert";
import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { Field, FieldError, FieldLabel } from "@/components/ui/field";
import { Input } from "@/components/ui/input";
import {
  Select,
  SelectContent,
  SelectItem,
  SelectTrigger,
  SelectValue,
} from "@/components/ui/select";
import { useInviteMemberMutation } from "../api/hooks";
import { inviteMemberSchema, type InviteMemberValues } from "../schemas";

const ROLE_OPTIONS: ReadonlyArray<{ value: InviteMemberValues["proposed_role"]; label: string }> = [
  { value: "admin", label: "Administrador" },
  { value: "accountant", label: "Contador" },
  { value: "salesperson", label: "Vendedor" },
  { value: "viewer", label: "Visualizador" },
];

export function InviteMemberDialog({ tenantId }: { tenantId: string }) {
  const [open, setOpen] = useState(false);
  const [submitError, setSubmitError] = useState<string | null>(null);
  const mutation = useInviteMemberMutation(tenantId);

  const { register, handleSubmit, formState, reset, control } = useForm<InviteMemberValues>({
    resolver: zodResolver(inviteMemberSchema),
    defaultValues: { email: "", proposed_role: "accountant" },
  });

  useEffect(() => {
    if (!open) {
      setSubmitError(null);
      reset({ email: "", proposed_role: "accountant" });
    }
  }, [open, reset]);

  const onSubmit = (values: InviteMemberValues) => {
    setSubmitError(null);
    mutation.mutate(values, {
      onSuccess: () => setOpen(false),
      onError: (err) => setSubmitError(err.message),
    });
  };

  const emailInvalid = Boolean(formState.errors.email);
  const roleInvalid = Boolean(formState.errors.proposed_role);

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <Button type="button">
          <UserPlus className="mr-1.5 h-4 w-4" />+ Invitar
        </Button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Invitar miembro</DialogTitle>
          <DialogDescription>
            Le enviaremos un correo con el enlace de invitación.
          </DialogDescription>
        </DialogHeader>
        <form onSubmit={handleSubmit(onSubmit)} className="space-y-4" noValidate>
          <Field data-invalid={emailInvalid}>
            <FieldLabel htmlFor="invite-email">Correo</FieldLabel>
            <Input
              id="invite-email"
              type="email"
              placeholder="persona@empresa.com"
              aria-invalid={emailInvalid}
              {...register("email")}
            />
            {formState.errors.email ? (
              <FieldError>{formState.errors.email.message}</FieldError>
            ) : null}
          </Field>
          <Field data-invalid={roleInvalid}>
            <FieldLabel htmlFor="invite-role">Rol</FieldLabel>
            <Controller
              control={control}
              name="proposed_role"
              render={({ field }) => (
                <Select value={field.value} onValueChange={field.onChange}>
                  <SelectTrigger id="invite-role" ref={field.ref} aria-invalid={roleInvalid}>
                    <SelectValue placeholder="Selecciona un rol" />
                  </SelectTrigger>
                  <SelectContent>
                    {ROLE_OPTIONS.map((opt) => (
                      <SelectItem key={opt.value} value={opt.value}>
                        {opt.label}
                      </SelectItem>
                    ))}
                  </SelectContent>
                </Select>
              )}
            />
            {formState.errors.proposed_role ? (
              <FieldError>{formState.errors.proposed_role.message}</FieldError>
            ) : null}
          </Field>
          {submitError ? (
            <Alert variant="destructive">
              <AlertDescription>{submitError}</AlertDescription>
            </Alert>
          ) : null}
          <DialogFooter>
            <Button
              type="button"
              variant="ghost"
              onClick={() => setOpen(false)}
              disabled={mutation.isPending}
            >
              Cancelar
            </Button>
            <Button type="submit" disabled={mutation.isPending}>
              {mutation.isPending ? "Enviando..." : "Enviar invitación"}
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  );
}
